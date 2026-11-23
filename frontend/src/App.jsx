import React, { useEffect, useState } from 'react'
import { wsService } from './services/websocket'
import Navbar from './components/Navbar'
import AuthModal from './components/AuthModal'
import DashboardKpis from './components/DashboardKpis'
import ProductCatalog from './components/ProductCatalog'
import ApprovalQueue from './components/ApprovalQueue'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('cleandesk_token'))
  const [user, setUser] = useState(() => {
    const u = localStorage.getItem('cleandesk_user')
    return u ? JSON.parse(u) : null
  })
  const [merchant, setMerchant] = useState(() => {
    const m = localStorage.getItem('cleandesk_merchant')
    return m ? JSON.parse(m) : null
  })

  const [activeTab, setActiveTab] = useState('dashboard')
  const [isWsConnected, setIsWsConnected] = useState(false)
  const [lastWsEvent, setLastWsEvent] = useState(null)

  // Handle WebSocket connection lifecycle
  useEffect(() => {
    if (!token) return

    wsService.connect(token)

    const unsubscribe = wsService.subscribe((msg) => {
      if (msg.event === 'CONNECTION_STATUS') {
        setIsWsConnected(msg.connected)
      } else {
        setLastWsEvent(msg)
      }
    })

    return () => {
      unsubscribe()
      wsService.disconnect()
    }
  }, [token])

  const handleAuthSuccess = ({ token, user, merchant }) => {
    setToken(token)
    setUser(user)
    setMerchant(merchant)
  }

  const handleLogout = () => {
    localStorage.removeItem('cleandesk_token')
    localStorage.removeItem('cleandesk_user')
    localStorage.removeItem('cleandesk_merchant')
    setToken(null)
    setUser(null)
    setMerchant(null)
    wsService.disconnect()
  }

  if (!token) {
    return <AuthModal onAuthSuccess={handleAuthSuccess} />
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar
        user={user}
        merchant={merchant}
        isWsConnected={isWsConnected}
        onLogout={handleLogout}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'dashboard' && <DashboardKpis lastWsEvent={lastWsEvent} />}
        {activeTab === 'catalog' && <ProductCatalog user={user} lastWsEvent={lastWsEvent} />}
        {activeTab === 'approvals' && <ApprovalQueue user={user} lastWsEvent={lastWsEvent} />}
      </main>
    </div>
  )
}