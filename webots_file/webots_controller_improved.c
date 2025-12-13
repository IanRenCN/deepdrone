/*
 * Copyright 1996-2024 Cyberbotics Ltd.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Description:
 * - Drone stabilization + UDP external control
 * - Compatible with DeepDrone Python UDP controller
 */

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <time.h>

#include <webots/robot.h>
#include <webots/camera.h>
#include <webots/compass.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
#include <webots/led.h>
#include <webots/motor.h>

#define CLAMP(value, low, high) ((value) < (low) ? (low) : ((value) > (high) ? (high) : (value)))

int main(int argc, char **argv) {
  wb_robot_init();
  int timestep = (int)wb_robot_get_basic_time_step();

  /* ---------------- UDP SOCKET (API) ---------------- */
  int sock = socket(AF_INET, SOCK_DGRAM, 0);
  if (sock < 0) {
    printf("❌ Failed to create socket\n");
    return EXIT_FAILURE;
  }

  struct sockaddr_in addr;
  addr.sin_family = AF_INET;
  addr.sin_port = htons(9000);      // API PORT (matches Python controller)
  addr.sin_addr.s_addr = INADDR_ANY;

  if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
    printf("❌ Failed to bind to port 9000\n");
    return EXIT_FAILURE;
  }
  
  fcntl(sock, F_SETFL, O_NONBLOCK);

  // API control values (received from Python)
  double api_roll = 0.0;      // Range: [-2.0, 2.0]
  double api_pitch = 0.0;     // Range: [-2.0, 2.0]
  double api_yaw = 0.0;       // Range: [-2.0, 2.0]
  double api_throttle = 0.0;  // Range: [-1.0, 1.0] - treated as vertical velocity

  /* ---------------- DEVICES ---------------- */
  WbDeviceTag camera = wb_robot_get_device("camera");
  wb_camera_enable(camera, timestep);

  WbDeviceTag front_left_led = wb_robot_get_device("front left led");
  WbDeviceTag front_right_led = wb_robot_get_device("front right led");

  WbDeviceTag imu = wb_robot_get_device("inertial unit");
  wb_inertial_unit_enable(imu, timestep);

  WbDeviceTag gps = wb_robot_get_device("gps");
  wb_gps_enable(gps, timestep);

  WbDeviceTag gyro = wb_robot_get_device("gyro");
  wb_gyro_enable(gyro, timestep);

  WbDeviceTag camera_roll_motor = wb_robot_get_device("camera roll");
  WbDeviceTag camera_pitch_motor = wb_robot_get_device("camera pitch");

  WbDeviceTag front_left_motor = wb_robot_get_device("front left propeller");
  WbDeviceTag front_right_motor = wb_robot_get_device("front right propeller");
  WbDeviceTag rear_left_motor = wb_robot_get_device("rear left propeller");
  WbDeviceTag rear_right_motor = wb_robot_get_device("rear right propeller");

  WbDeviceTag motors[4] = {
    front_left_motor, front_right_motor,
    rear_left_motor, rear_right_motor
  };

  for (int i = 0; i < 4; ++i) {
    wb_motor_set_position(motors[i], INFINITY);
    wb_motor_set_velocity(motors[i], 1.0);
  }

  /* ---------------- CONSTANTS ---------------- */
  const double k_vertical_thrust = 68.5;
  const double k_vertical_offset = 0.6;
  const double k_vertical_p = 3.0;
  const double k_roll_p = 50.0;
  const double k_pitch_p = 30.0;

  double target_altitude = 1.0;  // Initial altitude

  // Packet statistics
  int packets_received = 0;
  time_t last_packet_time = time(NULL);
  time_t last_status_print = time(NULL);

  printf("========================================\n");
  printf("🚁 DeepDrone Webots Controller\n");
  printf("========================================\n");
  printf("✅ UDP socket listening on port 9000\n");
  printf("✅ Waiting for commands from Python...\n");
  printf("========================================\n\n");

  /* ---------------- MAIN LOOP ---------------- */
  while (wb_robot_step(timestep) != -1) {

    /* Read UDP command (30 Hz from Python) */
    char buffer[128];
    int len = recv(sock, buffer, sizeof(buffer) - 1, 0);
    if (len > 0) {
      buffer[len] = '\0';
      
      // Parse: "roll pitch yaw throttle"
      if (sscanf(buffer, "%lf %lf %lf %lf",
                 &api_roll, &api_pitch, &api_yaw, &api_throttle) == 4) {
        packets_received++;
        last_packet_time = time(NULL);
        
        // Log every 100 packets (roughly every 3 seconds at 30 Hz)
        if (packets_received % 100 == 0) {
          printf("📡 Packets received: %d | Latest: r=%.2f p=%.2f y=%.2f t=%.2f\n",
                 packets_received, api_roll, api_pitch, api_yaw, api_throttle);
        }
      }
    }

    // IMPROVED: Treat throttle as vertical velocity (m/s)
    // throttle = 0.6 means climb at 0.6 m/s
    // throttle = 0.0 means maintain altitude
    // throttle = -0.2 means descend at 0.2 m/s
    double dt = timestep / 1000.0;  // Convert ms to seconds
    target_altitude += api_throttle * dt;
    
    // Keep altitude reasonable
    target_altitude = CLAMP(target_altitude, 0.0, 100.0);

    // Get current sensor values
    const double roll = wb_inertial_unit_get_roll_pitch_yaw(imu)[0];
    const double pitch = wb_inertial_unit_get_roll_pitch_yaw(imu)[1];
    const double altitude = wb_gps_get_values(gps)[2];
    const double roll_velocity = wb_gyro_get_values(gyro)[0];
    const double pitch_velocity = wb_gyro_get_values(gyro)[1];

    // Stabilize camera
    wb_motor_set_position(camera_roll_motor, -0.115 * roll_velocity);
    wb_motor_set_position(camera_pitch_motor, -0.1 * pitch_velocity);

    // Roll control (with API input)
    const double roll_input =
      k_roll_p * CLAMP(roll, -1.0, 1.0) + roll_velocity + api_roll;

    // Pitch control (with API input)
    const double pitch_input =
      k_pitch_p * CLAMP(pitch, -1.0, 1.0) + pitch_velocity + api_pitch;

    // Yaw control (direct from API)
    const double yaw_input = api_yaw;

    // Altitude control
    const double diff_alt =
      CLAMP(target_altitude - altitude + k_vertical_offset, -1.0, 1.0);

    const double vertical_input = k_vertical_p * pow(diff_alt, 3.0);

    // Calculate motor velocities
    const double fl =
      k_vertical_thrust + vertical_input - roll_input + pitch_input - yaw_input;
    const double fr =
      k_vertical_thrust + vertical_input + roll_input + pitch_input + yaw_input;
    const double rl =
      k_vertical_thrust + vertical_input - roll_input - pitch_input + yaw_input;
    const double rr =
      k_vertical_thrust + vertical_input + roll_input - pitch_input - yaw_input;

    wb_motor_set_velocity(front_left_motor, fl);
    wb_motor_set_velocity(front_right_motor, -fr);
    wb_motor_set_velocity(rear_left_motor, -rl);
    wb_motor_set_velocity(rear_right_motor, rr);

    // Print status every 5 seconds
    time_t now = time(NULL);
    if (now - last_status_print >= 5) {
      printf("\n📊 Status:\n");
      printf("   Altitude: %.2f m (target: %.2f m)\n", altitude, target_altitude);
      printf("   Roll: %.2f | Pitch: %.2f\n", roll * 180.0 / M_PI, pitch * 180.0 / M_PI);
      printf("   API inputs: r=%.2f p=%.2f y=%.2f t=%.2f\n", 
             api_roll, api_pitch, api_yaw, api_throttle);
      printf("   Packets: %d total | Last: %ld sec ago\n", 
             packets_received, now - last_packet_time);
      last_status_print = now;
    }

    // Warning if no packets received recently
    if (packets_received > 0 && (now - last_packet_time) > 3) {
      printf("⚠️  WARNING: No packets received in %ld seconds!\n", 
             now - last_packet_time);
    }
  }

  printf("\n🛑 Shutting down...\n");
  wb_robot_cleanup();
  close(sock);
  return EXIT_SUCCESS;
}
