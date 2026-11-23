import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { Package, DollarSign, AlertTriangle, Clock, RefreshCw, Zap, Bell, CheckCircle2 } from 'lucide-react'

function formatEventMessage(event, data) {
  if (!data) return 'Event processed.'
  if (typeof data === 'string') return data
  if (data.message) return data.message

  switch (event) {
    case 'LOW_STOCK_ALERT':
      return `Critical low stock for SKU ${data.sku || '#' + (data.product_id || '')} (${data.stock_quantity ?? 0} units remaining)`

    case 'STOCK_UPDATED':
      if (data.name) {
        return `Product "${data.name}" (${data.sku}) updated to ${data.stock_quantity} units @ $${Number(data.unit_price).toFixed(2)}`
      }
      if (data.sku) {
        return `Stock updated for SKU ${data.sku} (${data.stock_quantity ?? ''} units)`
      }
      return 'Inventory stock state updated.'

    case 'APPROVAL_CREATED':
      return `Adjustment request #${data.id} submitted for ${data.product_name || data.product_sku || 'Product'} (${data.quantity_delta > 0 ? '+' : ''}${data.quantity_delta} units): "${data.reason}"`

    case 'APPROVAL_RESOLVED':
      return `Adjustment request #${data.id} was ${data.status} for ${data.product_name || data.product_sku || 'Product'}`

    default:
      return typeof data === 'object' ? Object.values(data).filter(v => typeof v !== 'object').join(' • ') : String(data)
  }
}

export default function DashboardKpis({ lastWsEvent }) {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notifications, setNotifications] = useState([])

  const fetchMetrics = async () => {
    try {
      setLoading(true)
      const res = await api.get('/dashboard/metrics')
      setMetrics(res.data)
    } catch (err) {
      console.error('Failed to fetch dashboard metrics:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
  }, [])

  // React to incoming WebSocket events
  useEffect(() => {
    if (!lastWsEvent) return
    if (['CONNECTION_STATUS', 'CONNECTED'].includes(lastWsEvent.event)) return

    // Add to live notification feed with deduplication
    const newNotif = {
      id: Date.now() + Math.random(),
      timestamp: new Date().toLocaleTimeString(),
      event: lastWsEvent.event,
      data: lastWsEvent.data,
    }

    setNotifications((prev) => {
      // Avoid duplicate display of identical consecutive events
      if (
        prev.length > 0 &&
        prev[0].event === lastWsEvent.event &&
        JSON.stringify(prev[0].data) === JSON.stringify(lastWsEvent.data)
      ) {
        return prev
      }
      return [newNotif, ...prev.slice(0, 19)]
    })

    // Re-fetch metrics whenever inventory or approvals change
    if (['STOCK_UPDATED', 'APPROVAL_CREATED', 'APPROVAL_RESOLVED', 'LOW_STOCK_ALERT'].includes(lastWsEvent.event)) {
      fetchMetrics()
    }
  }, [lastWsEvent])

  return (
    <div className="space-y-6">
      {/* Top Header & Cache Status */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Operations Dashboard</h1>
          <p className="text-sm text-slate-500">Live operational KPIs & real-time inventory signals</p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Cache Status Badge */}
          {metrics && (
            <span
              className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                metrics.from_cache
                  ? 'bg-amber-100 text-amber-900 border border-amber-200'
                  : 'bg-emerald-100 text-emerald-900 border border-emerald-200'
              }`}
              title="Redis Cache-Aside indicator"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>{metrics.from_cache ? 'Redis Cache Hit' : 'PostgreSQL Miss (Fresh)'}</span>
            </span>
          )}

          <button
            onClick={fetchMetrics}
            disabled={loading}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg shadow-sm transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total SKUs */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Total SKUs</span>
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Package className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-slate-900">{metrics?.total_skus ?? 0}</span>
            <span className="text-xs text-slate-500 ml-2">items in catalog</span>
          </div>
        </div>

        {/* Total Inventory Value */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Inventory Value</span>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-slate-900">
              ${(metrics?.total_inventory_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
            <span className="text-xs text-slate-500 ml-2">USD total</span>
          </div>
        </div>

        {/* Low Stock Items */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Low Stock Alerts</span>
            <div className="p-2 bg-rose-50 text-rose-600 rounded-lg">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-rose-600">{metrics?.low_stock_count ?? 0}</span>
            <span className="text-xs text-slate-500 ml-2">SKUs below threshold</span>
          </div>
        </div>

        {/* Pending Approvals */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase">Pending Approvals</span>
            <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-amber-600">{metrics?.pending_approvals ?? 0}</span>
            <span className="text-xs text-slate-500 ml-2">awaiting review</span>
          </div>
        </div>
      </div>

      {/* Real-Time WebSocket Event Feed */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Bell className="w-5 h-5 text-indigo-600" />
            <h3 className="font-bold text-slate-900">Real-Time Event Stream</h3>
            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono">
              room:merchant_{metrics ? 'active' : ''}
            </span>
          </div>
          <span className="text-xs text-slate-400">WebSocket broadcast (no echo-back)</span>
        </div>

        {notifications.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-sm">
            Listening for real-time inventory events...
          </div>
        ) : (
          <div className="divide-y divide-slate-100 max-h-64 overflow-y-auto pr-2">
            {notifications.map((n) => (
              <div key={n.id} className="py-2.5 flex items-start justify-between text-xs">
                <div className="flex items-start space-x-3">
                  <span
                    className={`px-2 py-0.5 rounded font-mono font-bold tracking-tight shrink-0 ${
                      n.event === 'LOW_STOCK_ALERT'
                        ? 'bg-rose-100 text-rose-800'
                        : n.event === 'APPROVAL_CREATED'
                        ? 'bg-amber-100 text-amber-800'
                        : n.event === 'APPROVAL_RESOLVED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-indigo-100 text-indigo-800'
                    }`}
                  >
                    {n.event}
                  </span>
                  <span className="text-slate-700 font-medium">
                    {formatEventMessage(n.event, n.data)}
                  </span>
                </div>
                <span className="text-slate-400 shrink-0 ml-4 font-mono">{n.timestamp}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}