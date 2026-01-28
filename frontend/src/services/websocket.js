/**
 * WebSocket Service
 * 
 * EXPLANATION FOR VIVA:
 * =====================
 * This module manages WebSocket connections for real-time features.
 * 
 * WebSocket vs HTTP:
 * - HTTP: Request-response, connection closes after each request
 * - WebSocket: Persistent connection, bidirectional communication
 * 
 * Used for:
 * - Real-time document updates
 * - Cursor position sharing
 * - User presence (who's online)
 * - Instant notifications
 */

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.isConnecting = false;
    this.shouldBeConnected = false; // Track desired state
    this.currentToken = null; // Store token for reconnection
  }

  /**
   * Connect to WebSocket server
   * @param {string} token - JWT authentication token
   */
  connect(token) {
    this.shouldBeConnected = true;
    this.currentToken = token;
    
    if (this.socket?.readyState === WebSocket.OPEN || this.isConnecting) {
      return;
    }

    this.isConnecting = true;
    this.reconnectAttempts = 0;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // Use environment variable for WebSocket URL, fallback to auto-detect
    let wsUrl;
    if (process.env.REACT_APP_WS_URL) {
      wsUrl = `${process.env.REACT_APP_WS_URL}/ws?token=${token}`;
    } else {
      // In development, React runs on port 3000 but backend is on 8000
      let wsHost = window.location.host;
      if (window.location.port === '3000') {
        wsHost = window.location.hostname + ':8000';
      }
      wsUrl = `${protocol}//${wsHost}/ws?token=${token}`;
    }

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.emit('connected', { connected: true });
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.socket.onclose = (event) => {
        this.isConnecting = false;
        this.socket = null;
        this.emit('disconnected', { code: event.code, reason: event.reason });
        
        if (this.shouldBeConnected && event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect(this.currentToken);
        }
      };

      this.socket.onerror = () => {
        this.isConnecting = false;
        this.emit('error', {});
      };
    } catch (error) {
      this.isConnecting = false;
    }
  }

  /**
   * Schedule a reconnection attempt
   * @param {string} token - JWT token for reconnection
   */
  scheduleReconnect(token) {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * this.reconnectAttempts;
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      if (token) {
        this.connect(token);
      }
    }, delay);
  }

  /**
   * Disconnect from WebSocket server
   * @param {boolean} permanent - If true, prevents auto-reconnection
   */
  disconnect(permanent = false) {
    if (permanent) {
      this.shouldBeConnected = false;
      this.currentToken = null;
      this.reconnectAttempts = this.maxReconnectAttempts;
    }
    
    if (this.socket) {
      if (this.socket.readyState === WebSocket.OPEN || 
          this.socket.readyState === WebSocket.CONNECTING) {
        this.socket.close(1000, 'Client disconnecting');
      }
      this.socket = null;
    }
    
    if (permanent) {
      this.listeners.clear();
    }
    
    this.isConnecting = false;
  }

  /**
   * Send a message through WebSocket
   * @param {string} type - Message type
   * @param {Object} data - Message payload
   */
  send(type, data = {}) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, ...data }));
    }
  }

  /**
   * Handle incoming WebSocket message
   * @param {Object} data - Parsed message data
   */
  handleMessage(data) {
    const { type, ...payload } = data;
    this.emit(type, payload);
  }

  /**
   * Subscribe to a message type
   * @param {string} event - Event type to listen for
   * @param {Function} callback - Handler function
   * @returns {Function} Unsubscribe function
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(callback);
    };
  }

  /**
   * Emit an event to all listeners
   * @param {string} event - Event type
   * @param {Object} data - Event data
   */
  emit(event, data) {
    this.listeners.get(event)?.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error(`Error in WebSocket listener for ${event}:`, error);
      }
    });
  }

  // ==================== DOCUMENT COLLABORATION ====================

  /**
   * Join a document room
   * @param {string} documentId - Document to join
   */
  joinDocument(documentId) {
    this.send('join_document', { document_id: documentId });
  }

  /**
   * Leave a document room
   * @param {string} documentId - Document to leave
   */
  leaveDocument(documentId) {
    this.send('leave_document', { document_id: documentId });
  }

  /**
   * Send cursor position update
   * @param {string} documentId - Current document
   * @param {number} position - Cursor position
   * @param {number} selectionStart - Selection start position
   * @param {number} selectionEnd - Selection end position
   */
  updateCursor(documentId, position, selectionStart = null, selectionEnd = null) {
    this.send('cursor_update', { 
      document_id: documentId, 
      position,
      selection_start: selectionStart,
      selection_end: selectionEnd
    });
  }

  /**
   * Send text change to other users
   * @param {string} documentId - Current document
   * @param {Object} change - { type, position, content, length }
   */
  sendTextChange(documentId, change) {
    this.send('text_change', { document_id: documentId, change });
  }

  /**
   * Send ping to keep connection alive
   */
  ping() {
    this.send('ping');
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

// Export singleton instance
export const wsService = new WebSocketService();
export default wsService;
