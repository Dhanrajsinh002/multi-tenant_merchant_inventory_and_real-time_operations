import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { Check, X, Plus, Clock, ShieldAlert, ArrowUpRight, ArrowDownRight } from 'lucide-react'

export default function ApprovalQueue({ user, lastWsEvent }) {
  const [approvals, setApprovals] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState('ALL')

  // Request modal state
  const [showModal, setShowModal] = useState(false)
  const [productId, setProductId] = useState('')
  const [quantityDelta, setQuantityDelta] = useState(10)
  const [reason, setReason] = useState('')
  const [requestError, setRequestError] = useState(null)
  const [decisionError, setDecisionError] = useState(null)

  const fetchApprovals = async () => {
    try {
      setLoading(true)
      const params = statusFilter !== 'ALL' ? { status: statusFilter } : {}
      const res = await api.get('/approvals', { params })
      setApprovals(res.data)
    } catch (err) {
      console.error('Failed to fetch approvals:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchProductsForSelect = async () => {
    try {
      const res = await api.get('/products?size=100')
      setProducts(res.data.items)
      if (res.data.items.length > 0 && !productId) {
        setProductId(res.data.items[0].id)
      }
    } catch (err) {
      console.error('Failed to fetch products for modal:', err)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [statusFilter])

  useEffect(() => {
    fetchProductsForSelect()
  }, [])

  // Real-time updates when approvals change
  useEffect(() => {
    if (['APPROVAL_CREATED', 'APPROVAL_RESOLVED'].includes(lastWsEvent?.event)) {
      fetchApprovals()
    }
  }, [lastWsEvent])

  const handleCreateRequest = async (e) => {
    e.preventDefault()
    setRequestError(null)
    try {
      await api.post('/approvals', {
        product_id: parseInt(productId),
        quantity_delta: parseInt(quantityDelta),
        reason,
      })
      setShowModal(false)
      setReason('')
      fetchApprovals()
    } catch (err) {
      setRequestError(err.message || 'Failed to submit request.')
    }
  }

  const handleDecision = async (approvalId, status) => {
    setDecisionError(null)
    try {
      await api.post(`/approvals/${approvalId}/decision`, { status })
      fetchApprovals()
    } catch (err) {
      setDecisionError(err.message || `Failed to ${status.toLowerCase()} request.`)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Stock Adjustment Queue</h2>
          <p className="text-xs text-slate-500">
            Staff can submit requests &bull; Only <span className="font-semibold text-indigo-600">OWNER</span> users can approve/reject
          </p>
        </div>

        <div className="flex items-center space-x-3 w-full sm:w-auto">
          {/* Filter Tabs */}
          <div className="flex bg-slate-100 p-1 rounded-lg text-xs font-semibold">
            {['ALL', 'PENDING', 'APPROVED', 'REJECTED'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded-md transition-colors ${
                  statusFilter === s ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <button
            onClick={() => { setShowModal(true); setRequestError(null); fetchProductsForSelect(); }}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Request Adjustment</span>
          </button>
        </div>
      </div>

      {decisionError && (
        <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-rose-500 shrink-0" />
          <span>{decisionError}</span>
        </div>
      )}

      {/* Requests Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-slate-600 font-semibold text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5 text-left">Request ID</th>
                <th className="px-6 py-3.5 text-left">Product</th>
                <th className="px-6 py-3.5 text-center">Adjustment</th>
                <th className="px-6 py-3.5 text-left">Reason</th>
                <th className="px-6 py-3.5 text-left">Requested By</th>
                <th className="px-6 py-3.5 text-center">Status</th>
                <th className="px-6 py-3.5 text-right">Decision Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {approvals.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-6 py-12 text-center text-slate-400">
                    No stock approval requests found in this view.
                  </td>
                </tr>
              ) : (
                approvals.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="px-6 py-4 font-mono font-bold text-slate-900">#{req.id}</td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-800">{req.product_name}</div>
                      <div className="font-mono text-xs text-slate-400">{req.product_sku}</div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                          req.quantity_delta > 0
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {req.quantity_delta > 0 ? (
                          <ArrowUpRight className="w-3.5 h-3.5 mr-0.5 text-emerald-600" />
                        ) : (
                          <ArrowDownRight className="w-3.5 h-3.5 mr-0.5 text-rose-600" />
                        )}
                        {req.quantity_delta > 0 ? `+${req.quantity_delta}` : req.quantity_delta}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-700 text-xs max-w-xs truncate">{req.reason}</td>
                    <td className="px-6 py-4 text-xs">
                      <span className="font-semibold text-slate-800">{req.requester_name || `User #${req.requested_by}`}</span>
                      <div className="text-[11px] text-slate-400">
                        {new Date(req.created_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span
                        className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                          req.status === 'APPROVED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : req.status === 'REJECTED'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {req.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {req.status === 'PENDING' ? (
                        user?.role === 'OWNER' ? (
                          <div className="inline-flex space-x-1.5">
                            <button
                              onClick={() => handleDecision(req.id, 'APPROVED')}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold transition-colors flex items-center space-x-1"
                            >
                              <Check className="w-3.5 h-3.5" />
                              <span>Approve</span>
                            </button>
                            <button
                              onClick={() => handleDecision(req.id, 'REJECTED')}
                              className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold transition-colors flex items-center space-x-1"
                            >
                              <X className="w-3.5 h-3.5" />
                              <span>Reject</span>
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Owner decision required</span>
                        )
                      ) : (
                        <span className="text-xs text-slate-400">
                          Resolved by {req.approver_name || 'Owner'}
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Request Stock Adjustment */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-lg text-slate-900">Request Stock Adjustment</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {requestError && (
              <div className="p-3 mb-4 rounded-lg bg-rose-50 text-rose-700 text-xs">{requestError}</div>
            )}

            <form onSubmit={handleCreateRequest} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">Select Product</label>
                <select
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  required
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku}) — Current Stock: {p.stock_quantity}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">
                  Stock Quantity Delta (+ for addition, - for deduction)
                </label>
                <input
                  type="number"
                  required
                  value={quantityDelta}
                  onChange={(e) => setQuantityDelta(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                  placeholder="e.g. 25 or -10"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">Reason for Adjustment</label>
                <textarea
                  rows="3"
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Shipment received from supplier batch #849"
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700"
                >
                  Submit for Approval
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}