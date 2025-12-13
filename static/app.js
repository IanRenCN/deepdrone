// DeepDrone Web Application
// Handles UI interactions, WebSocket communication, and API calls

class DeepDroneApp {
    constructor() {
        this.ws = null;
        this.isAIConfigured = false;
        this.isDroneConnected = false;
        this.telemetryInterval = null;

        this.initializeElements();
        this.attachEventListeners();
        this.loadSavedConfig();
        this.checkHealth();
    }

    initializeElements() {
        // Configuration elements
        this.providerSelect = document.getElementById('provider');
        this.apiKeyGroup = document.getElementById('apiKeyGroup');
        this.apiKeyInput = document.getElementById('apiKey');
        this.modelGroup = document.getElementById('modelGroup');
        this.modelSelect = document.getElementById('model');
        this.modelLoading = document.getElementById('modelLoading');
        this.configureBtn = document.getElementById('configureBtn');
        this.configStatus = document.getElementById('configStatus');

        // Drone connection elements
        this.connectionString = document.getElementById('connectionString');
        this.connectDroneBtn = document.getElementById('connectDroneBtn');
        this.disconnectDroneBtn = document.getElementById('disconnectDroneBtn');
        this.droneStatus = document.getElementById('droneStatus');

        // Chat elements
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');

        // Status indicators
        this.aiIndicator = document.getElementById('aiIndicator');
        this.aiStatus = document.getElementById('aiStatus');
        this.droneIndicator = document.getElementById('droneIndicator');
        this.droneStatusText = document.getElementById('droneStatusText');

        // Telemetry
        this.telemetrySection = document.getElementById('telemetry');
        this.telemetryMode = document.getElementById('telemetryMode');
        this.telemetryArmed = document.getElementById('telemetryArmed');
        this.telemetryAlt = document.getElementById('telemetryAlt');
        this.telemetryBattery = document.getElementById('telemetryBattery');
    }

    attachEventListeners() {
        // Provider selection
        this.providerSelect.addEventListener('change', () => this.onProviderChange());

        // Configure AI button
        this.configureBtn.addEventListener('click', () => this.configureAI());

        // Drone connection
        this.connectDroneBtn.addEventListener('click', () => this.connectDrone());
        this.disconnectDroneBtn.addEventListener('click', () => this.disconnectDrone());

        // Chat
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.clearChatBtn.addEventListener('click', () => this.clearChat());
    }

    // Provider Models Configuration
    getProviderModels(provider) {
        const models = {
            openai: [
                'gpt-4o',
                'gpt-4o-mini',
                'gpt-4-turbo',
                'gpt-3.5-turbo'
            ],
            anthropic: [
                'claude-3-5-sonnet-20241022',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307'
            ],
            google: [
                'gemini-1.5-pro',
                'gemini-1.5-flash',
                'gemini-pro'
            ],
            ollama: [] // Will be loaded dynamically
        };
        return models[provider] || [];
    }

    async onProviderChange() {
        const provider = this.providerSelect.value;

        if (!provider) {
            this.apiKeyGroup.style.display = 'none';
            this.modelGroup.style.display = 'none';
            this.configureBtn.disabled = true;
            return;
        }

        // Show/hide API key field based on provider
        if (provider === 'ollama') {
            this.apiKeyGroup.style.display = 'none';
        } else {
            this.apiKeyGroup.style.display = 'block';
        }

        this.modelGroup.style.display = 'block';
        this.modelSelect.innerHTML = '<option value="">Select Model...</option>';

        // Load models
        if (provider === 'ollama') {
            await this.loadOllamaModels();
        } else {
            const models = this.getProviderModels(provider);
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                this.modelSelect.appendChild(option);
            });
        }

        this.updateConfigureButton();
    }

    async loadOllamaModels() {
        this.modelLoading.style.display = 'block';
        this.modelSelect.disabled = true;

        try {
            const response = await fetch('/api/ollama/models');
            const data = await response.json();

            if (data.models && data.models.length > 0) {
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    this.modelSelect.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = data.error || 'No Ollama models found';
                this.modelSelect.appendChild(option);
            }
        } catch (error) {
            console.error('Error loading Ollama models:', error);
            this.showStatus(this.configStatus, 'Error loading Ollama models', 'error');
        } finally {
            this.modelLoading.style.display = 'none';
            this.modelSelect.disabled = false;
        }
    }

    updateConfigureButton() {
        const provider = this.providerSelect.value;
        const model = this.modelSelect.value;
        const apiKey = this.apiKeyInput.value;

        if (provider === 'ollama') {
            this.configureBtn.disabled = !provider || !model;
        } else {
            this.configureBtn.disabled = !provider || !model || !apiKey;
        }
    }

    async configureAI() {
        const provider = this.providerSelect.value;
        const model = this.modelSelect.value;
        const apiKey = provider === 'ollama' ? null : this.apiKeyInput.value;

        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ provider, model, api_key: apiKey })
            });

            const data = await response.json();

            if (response.ok) {
                this.isAIConfigured = true;
                this.updateAIStatus(true);
                this.showStatus(this.configStatus, `✓ ${data.message}`, 'success');
                this.sendBtn.disabled = false;
                this.saveConfig({ provider, model });
                this.connectWebSocket();
            } else {
                throw new Error(data.detail || 'Configuration failed');
            }
        } catch (error) {
            console.error('Error configuring AI:', error);
            this.showStatus(this.configStatus, `✗ ${error.message}`, 'error');
        }
    }

    async connectDrone() {
        const connectionStr = this.connectionString.value;

        if (!connectionStr) {
            this.showStatus(this.droneStatus, 'Please enter a connection string', 'error');
            return;
        }

        try {
            this.connectDroneBtn.disabled = true;
            this.showStatus(this.droneStatus, 'Connecting...', 'success');

            const response = await fetch('/api/drone/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ connection_string: connectionStr })
            });

            const data = await response.json();

            if (response.ok) {
                this.isDroneConnected = true;
                this.updateDroneStatus(true);
                this.showStatus(this.droneStatus, `✓ ${data.message}`, 'success');
                this.connectDroneBtn.style.display = 'none';
                this.disconnectDroneBtn.style.display = 'block';
                this.startTelemetryUpdates();
            } else {
                throw new Error(data.detail || 'Connection failed');
            }
        } catch (error) {
            console.error('Error connecting to drone:', error);
            this.showStatus(this.droneStatus, `✗ ${error.message}`, 'error');
        } finally {
            this.connectDroneBtn.disabled = false;
        }
    }

    async disconnectDrone() {
        try {
            const response = await fetch('/api/drone/disconnect', {
                method: 'POST'
            });

            if (response.ok) {
                this.isDroneConnected = false;
                this.updateDroneStatus(false);
                this.showStatus(this.droneStatus, 'Disconnected', 'success');
                this.connectDroneBtn.style.display = 'block';
                this.disconnectDroneBtn.style.display = 'none';
                this.stopTelemetryUpdates();
            }
        } catch (error) {
            console.error('Error disconnecting from drone:', error);
        }
    }

    startTelemetryUpdates() {
        this.telemetrySection.style.display = 'block';
        this.updateTelemetry();
        this.telemetryInterval = setInterval(() => this.updateTelemetry(), 1000);
    }

    stopTelemetryUpdates() {
        if (this.telemetryInterval) {
            clearInterval(this.telemetryInterval);
            this.telemetryInterval = null;
        }
        this.telemetrySection.style.display = 'none';
    }

    async updateTelemetry() {
        try {
            const response = await fetch('/api/drone/status');
            const data = await response.json();

            if (data.connected) {
                this.telemetryMode.textContent = data.mode || '-';
                this.telemetryArmed.textContent = data.armed ? 'Yes' : 'No';
                this.telemetryAlt.textContent = data.altitude ? `${data.altitude.toFixed(1)}m` : '-';
                this.telemetryBattery.textContent = data.battery ? `${data.battery}%` : '-';
            }
        } catch (error) {
            console.error('Error updating telemetry:', error);
        }
    }

    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                if (this.isAIConfigured) {
                    this.connectWebSocket();
                }
            }, 3000);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'user_message':
                // Already displayed, no action needed
                break;
            case 'ai_message':
                this.addMessage(data.content, 'ai');
                break;
            case 'error':
                this.addMessage(data.content, 'error');
                break;
        }
    }

    sendMessage() {
        const message = this.chatInput.value.trim();

        if (!message) return;

        if (!this.isAIConfigured) {
            alert('Please configure an AI provider first');
            return;
        }

        // Add user message to chat
        this.addMessage(message, 'user');

        // Send via WebSocket
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ message }));
        }

        // Clear input
        this.chatInput.value = '';
        this.chatInput.style.height = 'auto';
    }

    addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = type === 'user' ? '👤' : type === 'error' ? '⚠️' : '🤖';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);

        // Remove welcome message if present
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        this.chatMessages.appendChild(messageDiv);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    clearChat() {
        this.chatMessages.innerHTML = `
            <div class="welcome-message">
                <h3>👋 Chat cleared!</h3>
                <p>Start a new conversation with DeepDrone AI.</p>
            </div>
        `;
    }

    updateAIStatus(configured) {
        this.aiIndicator.classList.toggle('active', configured);
        this.aiStatus.textContent = configured ? 'Configured' : 'Not Configured';
    }

    updateDroneStatus(connected) {
        this.droneIndicator.classList.toggle('active', connected);
        this.droneStatusText.textContent = connected ? 'Connected' : 'Disconnected';
    }

    showStatus(element, message, type) {
        element.textContent = message;
        element.className = `status-message ${type}`;
        element.style.display = 'block';

        setTimeout(() => {
            element.style.display = 'none';
        }, 5000);
    }

    saveConfig(config) {
        localStorage.setItem('deepdrone_config', JSON.stringify(config));
    }

    loadSavedConfig() {
        const saved = localStorage.getItem('deepdrone_config');
        if (saved) {
            try {
                const config = JSON.parse(saved);
                this.providerSelect.value = config.provider;
                this.onProviderChange().then(() => {
                    this.modelSelect.value = config.model;
                    this.updateConfigureButton();
                });
            } catch (error) {
                console.error('Error loading saved config:', error);
            }
        }
    }

    async checkHealth() {
        try {
            const response = await fetch('/api/health');
            const data = await response.json();

            if (data.llm_configured) {
                this.isAIConfigured = true;
                this.updateAIStatus(true);
                this.sendBtn.disabled = false;
                this.connectWebSocket();
            }

            if (data.drone_connected) {
                this.isDroneConnected = true;
                this.updateDroneStatus(true);
            }
        } catch (error) {
            console.error('Health check failed:', error);
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new DeepDroneApp();
});
