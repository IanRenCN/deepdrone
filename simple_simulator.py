#!/usr/bin/env python3
"""
Simple Drone Simulator for DeepDrone
Provides proper MAVLink simulation using pymavlink for DroneKit compatibility.
Uses TCP for reliable DroneKit connection.
"""

import socket
import time
import sys
import select
from threading import Thread
from pymavlink import mavutil

class MAVLinkSimulator:
    """MAVLink simulator that works with DroneKit over TCP."""

    def __init__(self, host='127.0.0.1', port=5760):
        self.host = host
        self.port = port
        self.running = False
        self.server_sock = None
        self.clients = []
        self.mav = None

        # Vehicle state
        self.system_id = 1
        self.component_id = 1

    def heartbeat_thread(self):
        """Send heartbeat messages periodically to all clients."""
        while self.running:
            if not self.clients:
                time.sleep(0.5)
                continue

            # Create heartbeat message
            msg = self.mav.heartbeat_encode(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                mavutil.mavlink.MAV_MODE_GUIDED_ARMED,
                0,
                mavutil.mavlink.MAV_STATE_ACTIVE
            )

            # Send to all connected clients
            msg_bytes = msg.pack(self.mav)
            for client_sock in self.clients[:]:
                try:
                    client_sock.send(msg_bytes)
                except Exception as e:
                    print(f"❌ Error sending to client: {e}")
                    try:
                        client_sock.close()
                    except:
                        pass
                    if client_sock in self.clients:
                        self.clients.remove(client_sock)

            time.sleep(1)

    def handle_client(self, client_sock, addr):
        """Handle messages from a connected client."""
        print(f"📡 DroneKit connected from {addr[0]}:{addr[1]}")

        client_sock.setblocking(False)
        buffer = bytearray()

        while self.running:
            try:
                ready = select.select([client_sock], [], [], 0.5)
                if not ready[0]:
                    continue

                data = client_sock.recv(4096)
                if not data:
                    break

                buffer.extend(data)

                # Parse MAVLink messages
                while len(buffer) > 0:
                    # Try to parse a message
                    msg = None
                    try:
                        # Find MAVLink message in buffer
                        if len(buffer) < 8:
                            break

                        # Simple parsing - just look for valid MAVLink header
                        if buffer[0] == 0xFE or buffer[0] == 0xFD:  # MAVLink v1 or v2
                            # For simplicity, just clear buffer and send responses
                            buffer.clear()

                            # Send system status
                            sys_status = self.mav.sys_status_encode(
                                0, 0, 0, 500, 11000, -1, -1, 0, 0, 0, 0, 0, 0
                            )
                            client_sock.send(sys_status.pack(self.mav))

                            # Send GPS raw
                            gps = self.mav.gps_raw_int_encode(
                                0, 3, 377491040, -1224194000, 0, 0, 0, 0, 10, 255
                            )
                            client_sock.send(gps.pack(self.mav))

                            break
                        else:
                            buffer.pop(0)

                    except Exception as e:
                        break

            except BlockingIOError:
                continue
            except Exception as e:
                break

        print(f"🔌 Client {addr[0]}:{addr[1]} disconnected")
        try:
            client_sock.close()
        except:
            pass
        if client_sock in self.clients:
            self.clients.remove(client_sock)

    def accept_thread(self):
        """Accept new client connections."""
        while self.running:
            try:
                self.server_sock.settimeout(1.0)
                client_sock, addr = self.server_sock.accept()
                self.clients.append(client_sock)

                # Start handler thread for this client
                handler = Thread(target=self.handle_client, args=(client_sock, addr), daemon=True)
                handler.start()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Accept error: {e}")

    def start(self):
        """Start the simulator."""
        print(f"🚁 Starting MAVLink Simulator...")

        try:
            # Create TCP server socket
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(5)

            # Create MAVLink instance
            self.mav = mavutil.mavlink.MAVLink(
                None,
                srcSystem=self.system_id,
                srcComponent=self.component_id
            )

            self.running = True

            print(f"✅ Simulator listening on {self.host}:{self.port}")
            print("="*60)
            print(f"📡 Connection String: tcp:127.0.0.1:5760")
            print("="*60)
            print("⚠️  Press Ctrl+C to stop")
            print()

            # Start threads
            heartbeat_t = Thread(target=self.heartbeat_thread, daemon=True)
            accept_t = Thread(target=self.accept_thread, daemon=True)

            heartbeat_t.start()
            accept_t.start()

            # Keep main thread alive
            while self.running:
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n🛑 Stopping simulator...")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        """Stop the simulator."""
        self.running = False

        # Close all client connections
        for client in self.clients[:]:
            try:
                client.close()
            except:
                pass
        self.clients.clear()

        # Close server socket
        if self.server_sock:
            try:
                self.server_sock.close()
            except:
                pass

        print("✅ Simulator stopped")

def main():
    """Main entry point."""
    simulator = MAVLinkSimulator()
    simulator.start()

if __name__ == "__main__":
    main()
