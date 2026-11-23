class TenantWebSocketService {
  constructor() {
    this.socket = null
    this.listeners = new Set()
    this.reconnectTimer = null
    this.pingInterval = null
  }

  connect(token) {
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/merchant?token=${token}`

    try {
      this.socket = new WebSocket(wsUrl)

      this.socket.onopen = () => {
        console.log('[WebSocket] Connected to merchant room.')
        this.notifyListeners({ event: 'CONNECTION_STATUS', connected: true })

        // Send heartbeat ping every 25 seconds
        this.pingInterval = setInterval(() => {
          if (this.socket?.readyState === WebSocket.OPEN) {
            this.socket.send('ping')
          }
        }, 25000)
      }

      this.socket.onmessage = (event) => {
        if (event.data === 'pong') return
        try {
          const data = JSON.parse(event.data)
          this.notifyListeners(data)
        } catch (e) {
          console.warn('[WebSocket] Non-JSON message received:', event.data)
        }
      }

      this.socket.onclose = () => {
        console.log('[WebSocket] Disconnected from merchant room.')
        this.cleanup()
        this.notifyListeners({ event: 'CONNECTION_STATUS', connected: false })
        // Auto-reconnect after 3 seconds if token still exists
        this.reconnectTimer = setTimeout(() => {
          const currentToken = localStorage.getItem('cleandesk_token')
          if (currentToken) this.connect(currentToken)
        }, 3000)
      }

      this.socket.onerror = (err) => {
        console.error('[WebSocket] Error:', err)
        this.socket?.close()
      }
    } catch (err) {
      console.error('[WebSocket] Failed to initialize connection:', err)
    }
  }

  subscribe(callback) {
    this.listeners.add(callback)
    return () => this.listeners.delete(callback)
  }

  notifyListeners(payload) {
    this.listeners.forEach((listener) => {
      try {
        listener(payload)
      } catch (e) {
        console.error('[WebSocket] Listener error:', e)
      }
    })
  }

  cleanup() {
    if (this.pingInterval) clearInterval(this.pingInterval)
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
  }

  disconnect() {
    this.cleanup()
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
  }
}

export const wsService = new TenantWebSocketService()