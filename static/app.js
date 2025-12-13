// DeepDrone - Minimal ChatGPT-style Interface

class DeepDrone {
    constructor() {
        this.ws = null;
        this.isAIConfigured = false;
        this.isDroneConnected = false;
        this.telemetryInterval = null;

        this.init();
    }

    init() {
        this.cacheElements();
        this.attachEventListeners();
        this.loadSavedConfig();
        this.checkHealth();
    }

    cacheElements() {
        // Sidebar
        this.sidebar = document.getElementById('sidebar');
        this.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
        this.openSidebarBtn = document.getElementById('openSidebarBtn');
        this.newChatBtn = document.getElementById('newChatBtn');

        // Modals
        this.settingsModal = document.getElementById('settingsModal');
        this.droneModal = document.getElementById('droneModal');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.droneConnectBtn = document.getElementById('droneConnectBtn');
        this.closeSettingsBtn = document.getElementById('closeSettingsBtn');
        this.closeDroneBtn = document.getElementById('closeDroneBtn');

        // Settings form
        this.provider = document.getElementById('provider');
        this.apiKeyGroup = document.getElementById('apiKeyGroup');
        this.apiKey = document.getElementById('apiKey');
        this.modelGroup = document.getElementById('modelGroup');
        this.model = document.getElementById('model');
        this.saveAIBtn = document.getElementById('saveAIBtn');
        this.aiStatus = document.getElementById('aiStatus');

        // Drone form
        this.connectionString = document.getElementById('connectionString');
        this.connectBtn = document.getElementById('connectBtn');
        this.disconnectBtn = document.getElementById('disconnectBtn');
        this.droneStatus = document.getElementById('droneStatus');

        // Chat
        this.messages = document.getElementById('messages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');

        // Top bar
        this.currentModel = document.getElementById('currentModel');
        this.statusDot = document.getElementById('statusDot');

        // Telemetry
        this.telemetryPanel = document.getElementById('telemetryPanel');
        this.telemetryToggleBtn = document.getElementById('telemetryToggleBtn');
        this.closeTelemetryBtn = document.getElementById('closeTelemetryBtn');
        this.telemMode = document.getElementById('telemMode');
        this.telemArmed = document.getElementById('telemArmed');
        this.telemAlt = document.getElementById('telemAlt');
        this.telemBattery = document.getElementById('telemBattery');
    }

    attachEventListeners() {
        // Sidebar toggle
        this.toggleSidebarBtn.addEventListener('click', () => this.toggleSidebar());
        this.openSidebarBtn.addEventListener('click', () => this.toggleSidebar());
        this.newChatBtn.addEventListener('click', () => this.newChat());

        // Modal controls
        this.settingsBtn.addEventListener('click', () => this.openModal(this.settingsModal));
        this.droneConnectBtn.addEventListener('click', () => this.openModal(this.droneModal));
        this.closeSettingsBtn.addEventListener('click', () => this.closeModal(this.settingsModal));
        this.closeDroneBtn.addEventListener('click', () => this.closeModal(this.droneModal));

        // Click outside modal to close
        this.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.settingsModal) this.closeModal(this.settingsModal);
        });
        this.droneModal.addEventListener('click', (e) => {
            if (e.target === this.droneModal) this.closeModal(this.droneModal);
        });

        // Settings
        this.provider.addEventListener('change', () => this.onProviderChange());
        this.model.addEventListener('change', () => this.updateSaveButton());
        this.apiKey.addEventListener('input', () => this.updateSaveButton());
        this.saveAIBtn.addEventListener('click', () => this.saveAISettings());

        // Drone
        this.connectBtn.addEventListener('click', () => this.connectDrone());
        this.disconnectBtn.addEventListener('click', () => this.disconnectDrone());

        // Chat
        this.messageInput.addEventListener('input', () => this.handleInputChange());
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.sendBtn.addEventListener('click', () => this.sendMessage());

        // Suggestion cards
        document.querySelectorAll('.suggestion-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.dataset.prompt;
                this.messageInput.value = prompt;
                this.handleInputChange();
                this.sendMessage();
            });
        });

        // Telemetry
        this.telemetryToggleBtn.addEventListener('click', () => this.toggleTelemetry());
        this.closeTelemetryBtn.addEventListener('click', () => this.toggleTelemetry());
    }

    // Sidebar
    toggleSidebar() {
        this.sidebar.classList.toggle('collapsed');
        if (this.sidebar.classList.contains('collapsed')) {
            this.openSidebarBtn.style.display = 'flex';
        } else {
            this.openSidebarBtn.style.display = 'none';
        }
    }

    newChat() {
        this.messages.innerHTML = `
            <div class="welcome-screen">
                <div class="welcome-icon">🚁</div>
                <h1>DeepDrone</h1>
                <p>Control your drone with natural language</p>
                <div class="suggestion-grid">
                    <button class="suggestion-card" data-prompt="Take off to 20 meters">
                        <div class="suggestion-title">Take Off</div>
                        <div class="suggestion-text">Take off to 20 meters</div>
                    </button>
                    <button class="suggestion-card" data-prompt="What's my current altitude and battery status?">
                        <div class="suggestion-title">Check Status</div>
                        <div class="suggestion-text">Get altitude and battery</div>
                    </button>
                    <button class="suggestion-card" data-prompt="Fly in a square pattern with 30m sides">
                        <div class="suggestion-title">Square Pattern</div>
                        <div class="suggestion-text">Fly in a square pattern</div>
                    </button>
                    <button class="suggestion-card" data-prompt="Return home and land safely">
                        <div class="suggestion-title">Return Home</div>
                        <div class="suggestion-text">Return and land safely</div>
                    </button>
                </div>
            </div>
        `;
        // Reattach suggestion card listeners
        this.attachEventListeners();
    }

    // Modal controls
    openModal(modal) {
        modal.classList.add('open');
    }

    closeModal(modal) {
        modal.classList.remove('open');
    }

    // AI Configuration
    getProviderModels(provider) {
        const models = {
            openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
            anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
            google: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro'],
            ollama: []
        };
        return models[provider] || [];
    }

    async onProviderChange() {
        const provider = this.provider.value;

        if (!provider) {
            this.apiKeyGroup.style.display = 'none';
            this.modelGroup.style.display = 'none';
            this.saveAIBtn.disabled = true;
            return;
        }

        this.apiKeyGroup.style.display = provider === 'ollama' ? 'none' : 'block';
        this.modelGroup.style.display = 'block';
        this.model.innerHTML = '<option value="">Loading...</option>';

        if (provider === 'ollama') {
            await this.loadOllamaModels();
        } else {
            const models = this.getProviderModels(provider);
            this.model.innerHTML = '<option value="">Select model...</option>';
            models.forEach(m => {
                const option = document.createElement('option');
                option.value = m;
                option.textContent = m;
                this.model.appendChild(option);
            });
        }

        this.updateSaveButton();
    }

    async loadOllamaModels() {
        try {
            const response = await fetch('/api/ollama/models');
            const data = await response.json();

            this.model.innerHTML = '<option value="">Select model...</option>';

            if (data.models && data.models.length > 0) {
                data.models.forEach(m => {
                    const option = document.createElement('option');
                    option.value = m;
                    option.textContent = m;
                    this.model.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = data.error || 'No models found';
                this.model.appendChild(option);
            }
        } catch (error) {
            console.error('Error loading Ollama models:', error);
            this.showStatus(this.aiStatus, 'Error loading Ollama models', 'error');
        }
    }

    updateSaveButton() {
        const provider = this.provider.value;
        const model = this.model.value;
        const apiKey = this.apiKey.value;

        if (provider === 'ollama') {
            this.saveAIBtn.disabled = !provider || !model;
        } else {
            this.saveAIBtn.disabled = !provider || !model || !apiKey;
        }
    }

    async saveAISettings() {
        const provider = this.provider.value;
        const model = this.model.value;
        const apiKey = provider === 'ollama' ? null : this.apiKey.value;

        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, model, api_key: apiKey })
            });

            const data = await response.json();

            if (response.ok) {
                this.isAIConfigured = true;
                this.updateStatus(true, false);
                this.showStatus(this.aiStatus, '✓ ' + data.message, 'success');
                this.currentModel.textContent = `${provider} - ${model.split('/').pop()}`;
                this.sendBtn.disabled = false;
                this.saveConfig({ provider, model });
                this.connectWebSocket();

                setTimeout(() => {
                    this.closeModal(this.settingsModal);
                }, 1500);
            } else {
                throw new Error(data.detail || 'Configuration failed');
            }
        } catch (error) {
            this.showStatus(this.aiStatus, '✗ ' + error.message, 'error');
        }
    }

    // Drone Connection
    async connectDrone() {
        const connStr = this.connectionString.value;

        if (!connStr) {
            this.showStatus(this.droneStatus, 'Please enter a connection string', 'error');
            return;
        }

        try {
            this.connectBtn.disabled = true;
            this.showStatus(this.droneStatus, 'Connecting...', 'success');

            const response = await fetch('/api/drone/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ connection_string: connStr })
            });

            const data = await response.json();

            if (response.ok) {
                this.isDroneConnected = true;
                this.updateStatus(this.isAIConfigured, true);
                this.showStatus(this.droneStatus, '✓ ' + data.message, 'success');
                this.connectBtn.style.display = 'none';
                this.disconnectBtn.style.display = 'block';
                this.startTelemetry();

                setTimeout(() => {
                    this.closeModal(this.droneModal);
                }, 1500);
            } else {
                throw new Error(data.detail || 'Connection failed');
            }
        } catch (error) {
            this.showStatus(this.droneStatus, '✗ ' + error.message, 'error');
        } finally {
            this.connectBtn.disabled = false;
        }
    }

    async disconnectDrone() {
        try {
            await fetch('/api/drone/disconnect', { method: 'POST' });

            this.isDroneConnected = false;
            this.updateStatus(this.isAIConfigured, false);
            this.showStatus(this.droneStatus, 'Disconnected', 'success');
            this.connectBtn.style.display = 'block';
            this.disconnectBtn.style.display = 'none';
            this.stopTelemetry();
        } catch (error) {
            console.error('Error disconnecting:', error);
        }
    }

    // Telemetry
    toggleTelemetry() {
        this.telemetryPanel.classList.toggle('open');
    }

    startTelemetry() {
        this.updateTelemetry();
        this.telemetryInterval = setInterval(() => this.updateTelemetry(), 1000);
    }

    stopTelemetry() {
        if (this.telemetryInterval) {
            clearInterval(this.telemetryInterval);
            this.telemetryInterval = null;
        }
    }

    async updateTelemetry() {
        try {
            const response = await fetch('/api/drone/status');
            const data = await response.json();

            if (data.connected) {
                this.telemMode.textContent = data.mode || '-';
                this.telemArmed.textContent = data.armed ? 'Yes' : 'No';
                this.telemAlt.textContent = data.altitude ? `${data.altitude.toFixed(1)}m` : '-';
                this.telemBattery.textContent = data.battery ? `${data.battery}%` : '-';
            }
        } catch (error) {
            console.error('Telemetry error:', error);
        }
    }

    // Chat
    handleInputChange() {
        const value = this.messageInput.value.trim();
        this.sendBtn.disabled = !value || !this.isAIConfigured;

        // Auto-resize textarea
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    sendMessage() {
        const message = this.messageInput.value.trim();

        if (!message || !this.isAIConfigured) return;

        // Remove welcome screen
        const welcome = this.messages.querySelector('.welcome-screen');
        if (welcome) welcome.remove();

        // Add user message
        this.addMessage(message, 'user');

        // Send to server
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ message }));
        }

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.handleInputChange();
    }

    addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;

        messageDiv.appendChild(contentDiv);
        this.messages.appendChild(messageDiv);

        // Scroll to bottom
        this.messages.parentElement.scrollTop = this.messages.parentElement.scrollHeight;
    }

    // WebSocket
    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => console.log('WebSocket connected');

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'ai_message') {
                this.addMessage(data.content, 'assistant');
            } else if (data.type === 'error') {
                this.addMessage(data.content, 'error');
            }
        };

        this.ws.onerror = (error) => console.error('WebSocket error:', error);

        this.ws.onclose = () => {
            console.log('WebSocket closed');
            setTimeout(() => {
                if (this.isAIConfigured) this.connectWebSocket();
            }, 3000);
        };
    }

    // Status
    updateStatus(aiConfigured, droneConnected) {
        if (aiConfigured || droneConnected) {
            this.statusDot.classList.add('connected');
        } else {
            this.statusDot.classList.remove('connected');
        }
    }

    showStatus(element, message, type) {
        element.textContent = message;
        element.className = `status-msg ${type}`;

        setTimeout(() => {
            element.className = 'status-msg';
        }, 5000);
    }

    // Storage
    saveConfig(config) {
        localStorage.setItem('deepdrone_config', JSON.stringify(config));
    }

    loadSavedConfig() {
        const saved = localStorage.getItem('deepdrone_config');
        if (saved) {
            try {
                const config = JSON.parse(saved);
                this.provider.value = config.provider;
                this.onProviderChange().then(() => {
                    this.model.value = config.model;
                    this.updateSaveButton();
                });
            } catch (error) {
                console.error('Error loading config:', error);
            }
        }
    }

    async checkHealth() {
        try {
            const response = await fetch('/api/health');
            const data = await response.json();

            if (data.llm_configured) {
                this.isAIConfigured = true;
                this.sendBtn.disabled = false;
                this.connectWebSocket();
            }

            if (data.drone_connected) {
                this.isDroneConnected = true;
                this.startTelemetry();
            }

            this.updateStatus(data.llm_configured, data.drone_connected);
        } catch (error) {
            console.error('Health check failed:', error);
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new DeepDrone();
});
