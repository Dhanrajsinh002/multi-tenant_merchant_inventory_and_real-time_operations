import React, { useEffect, useState } from 'react'
import api from '../services/api'
import { Search, Plus, Upload, Download, AlertTriangle, Check, X, FileText } from 'lucide-react'

export default function ProductCatalog({ user }) {
  const [products, setProducts] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [category, setCategory] = useState('')
  const [lowStockOnly, setLowStockOnly] = useState(false)
  const [loading, setLoading] = useState(false)

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showBulkModal, setShowBulkModal] = useState(false)
  const [editingProductId, setEditingProductId] = useState(null)
  const [editStockValue, setEditStockValue] = useState(0)

  // Form inputs for Create
  const [newSku, setNewSku] = useState('')
  const [newName, setNewName] = useState('')
  const [newCategory, setNewCategory] = useState('')
  const [newPrice, setNewPrice] = useState(0)
  const [newStock, setNewStock] = useState(0)
  const [newThreshold, setNewThreshold] = useState(10)
  const [createError, setCreateError] = useState(null)

  // Bulk upload state
  const [bulkJson, setBulkJson] = useState(`[
{"sku": "SKU-DEMO-1", "stock_quantity": 40, "unit_price": 29.99},
{"sku": "SKU-DEMO-2", "stock_quantity": 15, "unit_price": 99.50}]`)
  const [bulkFile, setBulkFile] = useState(null) 
  const [bulkStatus, setBulkStatus] = useState(null)

  const fetchProducts = async () => {
    try {
      setLoading(true)
      const params = { page, size: 20 }
      if (category) params.category = category
      if (lowStockOnly) params.low_stock = true
  
      const res = await api.get('/products', { params })
      setProducts(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      console.error('Failed to fetch products:', err)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchProducts()
  }, [page, category, lowStockOnly])
  
  const handleCreate = async (e) => {
    e.preventDefault()
    setCreateError(null)
    try {
      await api.post('/products', {
        sku: newSku,
        name: newName,
        category: newCategory,
        unit_price: parseFloat(newPrice),
        stock_quantity: parseInt(newStock),
        low_stock_threshold: parseInt(newThreshold),
      })
      setShowCreateModal(false)
      setNewSku('')
      setNewName('')
      fetchProducts()
    } catch (err) {
      setCreateError(err.message || 'Failed to create product.')
    }
  }
  
  const handleInlineStockSave = async (product) => {
    try {
      await api.put(`/products/${product.id}`, {
        stock_quantity: parseInt(editStockValue),
      })
      setEditingProductId(null)
      fetchProducts()
    } catch (err) {
      alert(err.message || 'Failed to update stock.')
    }
  }
  
  const handleExportCsv = async () => {
    try {
      const response = await api.get('/reports/inventory-export', {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `inventory_export_${new Date().toISOString().slice(0, 10)}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Failed to export inventory CSV.')
    }
  }
  
  const handleBulkSubmit = async () => {
    setBulkStatus({ type: 'loading', message: 'Processing bulk update atomically...' })
    try {
      if (bulkFile) {
        const formData = new FormData()
        formData.append('file', bulkFile)
        const res = await api.post('/products/bulk-update', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        setBulkStatus({ type: 'success', message: res.data.message })
      } else {
        const parsed = JSON.parse(bulkJson)
        const res = await api.post('/products/bulk-update', parsed)
        setBulkStatus({ type: 'success', message: res.data.message })
      }
      fetchProducts()
    } catch (err) {
      setBulkStatus({
        type: 'error',
        error_code: err.error_code,
        message: err.message || 'Bulk transaction failed and was rolled back.',
      })
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
          {/* Category Filter */}
          <input
            type="text"
            placeholder="Filter by category..."
            value={category}
            onChange={(e) => { setCategory(e.target.value); setPage(1); }}
            className="px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 w-44"
          />
  
          {/* Low Stock Filter */}
          <button
            onClick={() => { setLowStockOnly(!lowStockOnly); setPage(1); }}
            className={`px-3 py-2 text-sm font-semibold rounded-lg border transition-colors flex items-center space-x-1.5 ${
              lowStockOnly
                ? 'bg-rose-50 text-rose-700 border-rose-300'
                : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
            }`}
          >
            <AlertTriangle className="w-4 h-4 text-rose-500" />
            <span>Low Stock Only</span>
          </button>
        </div>
  
        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          <button
            onClick={handleExportCsv}
            className="inline-flex items-center space-x-1.5 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg shadow-sm transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Export CSV</span>
          </button>
  
          <button
            onClick={() => { setShowBulkModal(true); setBulkStatus(null); }}
            className="inline-flex items-center space-x-1.5 px-3 py-2 text-sm font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 rounded-lg transition-colors"
          >
            <Upload className="w-4 h-4" />
            <span>Bulk Update (CSV/JSON)</span>
          </button>
  
          {user?.role === 'OWNER' && (
            <button
              onClick={() => { setShowCreateModal(true); setCreateError(null); }}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>New Product</span>
            </button>
          )}
        </div>
      </div>
  
      {/* Product Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-slate-600 font-semibold text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5 text-left">SKU</th>
                <th className="px-6 py-3.5 text-left">Product Name</th>
                <th className="px-6 py-3.5 text-left">Category</th>
                <th className="px-6 py-3.5 text-right">Unit Price</th>
                <th className="px-6 py-3.5 text-center">Stock Quantity</th>
                <th className="px-6 py-3.5 text-center">Status</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {products.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-6 py-12 text-center text-slate-400">
                    No products found. Add a product or run a bulk import.
                  </td>
                </tr>
              ) : (
                products.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/75 transition-colors">
                    <td className="px-6 py-4 font-mono font-semibold text-slate-900">{p.sku}</td>
                    <td className="px-6 py-4 font-medium text-slate-800">{p.name}</td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                        {p.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-semibold text-slate-900">
                      ${p.unit_price.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-center">
                      {editingProductId === p.id ? (
                        <div className="inline-flex items-center space-x-1">
                          <input
                            type="number"
                            min="0"
                            value={editStockValue}
                            onChange={(e) => setEditStockValue(e.target.value)}
                            className="w-16 px-1.5 py-0.5 border border-indigo-500 rounded text-center text-sm"
                          />
                          <button
                            onClick={() => handleInlineStockSave(p)}
                            className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setEditingProductId(null)}
                            className="p-1 text-slate-400 hover:bg-slate-100 rounded"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <span className="font-bold text-slate-800">{p.stock_quantity}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-center">
                      {p.is_low_stock ? (
                        <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
                          <AlertTriangle className="w-3 h-3 text-rose-600" />
                          <span>Low Stock (&le; {p.low_stock_threshold})</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                          Healthy
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {editingProductId !== p.id && (
                        <button
                          onClick={() => {
                            setEditingProductId(p.id)
                            setEditStockValue(p.stock_quantity)
                          }}
                          className="text-xs font-semibold text-indigo-600 hover:text-indigo-900"
                        >
                          Edit Stock
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
  
      {/* Modal: Create Product */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-lg text-slate-900">Add New Product</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
  
            {createError && (
              <div className="p-3 mb-4 rounded-lg bg-rose-50 text-rose-700 text-xs">{createError}</div>
            )}
  
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase">SKU (Unique)</label>
                <input
                  type="text"
                  required
                  value={newSku}
                  onChange={(e) => setNewSku(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm mt-1"
                  placeholder="e.g. MOUSE-PRO-01"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase">Product Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm mt-1"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase">Category</label>
                  <input
                    type="text"
                    required
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm mt-1"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase">Stock Quantity</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={newStock}
                    onChange={(e) => setNewStock(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase">Low Threshold</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={newThreshold}
                    onChange={(e) => setNewThreshold(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg text-sm mt-1"
                  />
                </div>
              </div>
  
              <div className="flex justify-end space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700"
                >
                  Create Product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
  
      {/* Modal: Bulk Update (CSV / JSON) */}
      {showBulkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 border border-slate-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-lg text-slate-900">Bulk Product Update (Atomic)</h3>
              <button onClick={() => setShowBulkModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
  
            {bulkStatus && (
              <div
                className={`p-3 rounded-lg text-xs mb-4 flex items-start space-x-2 ${
                  bulkStatus.type === 'error'
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : bulkStatus.type === 'success'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-indigo-50 text-indigo-700'
                }`}
              >
                <span>
                  {bulkStatus.error_code && <strong className="mr-1.5">[{bulkStatus.error_code}]</strong>}
                  {bulkStatus.message}
                </span>
              </div>
            )}
  
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Option 1: Upload CSV File
                </label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setBulkFile(e.target.files[0])}
                  className="w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
                <p className="text-[11px] text-slate-400 mt-1">Expected columns: sku, unit_price, stock_quantity</p>
              </div>
  
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Option 2: JSON Payload
                </label>
                <textarea
                  rows="6"
                  value={bulkJson}
                  onChange={(e) => { setBulkJson(e.target.value); setBulkFile(null); }}
                  className="w-full p-2.5 font-mono text-xs border rounded-lg border-slate-300 outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50"
                />
              </div>
  
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  onClick={() => setShowBulkModal(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-slate-600 hover:bg-slate-50"
                >
                  Close
                </button>
                <button
                  onClick={handleBulkSubmit}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700"
                >
                  Execute Atomic Update
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
