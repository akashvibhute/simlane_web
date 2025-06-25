// simlane/static/js/ws.js

// Usage: import wsClient from './ws';
// wsClient.on('sync_status', (data) => { ... });

class WSClient {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.handlers = {};
    this.reconnectDelay = 2000;
    this.shouldReconnect = true;
    this.connect();
  }

  connect() {
    this.socket = new WebSocket(this.url);
    this.socket.onopen = () => {
      // console.log('WebSocket connected');
    };
    this.socket.onclose = () => {
      if (this.shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectDelay);
      }
    };
    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type && this.handlers[data.type]) {
          this.handlers[data.type].forEach((cb) => cb(data));
        }
      } catch (e) {
        // Ignore non-JSON messages
      }
    };
  }

  on(type, callback) {
    if (!this.handlers[type]) {
      this.handlers[type] = [];
    }
    this.handlers[type].push(callback);
  }

  send(data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    }
  }

  close() {
    this.shouldReconnect = false;
    if (this.socket) {
      this.socket.close();
    }
  }
}

// Only connect if user is authenticated (window.isAuthenticated or data attribute)
let wsClient = null;
if (window.isAuthenticated) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = protocol + '//' + window.location.host + '/ws/app/';
  wsClient = new WSClient(wsUrl);
}

export default wsClient; 