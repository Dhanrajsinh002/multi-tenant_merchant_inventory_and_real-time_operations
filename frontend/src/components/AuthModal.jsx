import React, { useState } from 'react'
import api from '../services/api'
import { Building2, KeyRound, Mail, User, AlertCircle, ArrowRight } from 'lucide-react'

export default function AuthModal({ onAuthSuccess }) {
  const [isRegister, setIsRegister] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Form states
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [merchantName, setMerchantName] = useState('')
  const [merchantSlug, setMerchantSlug] = useState('')
  const [ownerName, setOwnerName] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      let res
      if (isRegister) {
        res = await api.post('/auth/register', {
          merchant_name: merchantName,
          merchant_slug: merchantSlug,
          owner_name: ownerName,
          email,
          password,
        })
      } else {
        res = await api.post('/auth/login', {
          email,
          password,
        })
      }

      const { access_token, user, merchant } = res.data
      localStorage.setItem('cleandesk_token', access_token)
      localStorage.setItem('cleandesk_user', JSON.stringify(user))
      localStorage.setItem('cleandesk_merchant', JSON.stringify(merchant))

      onAuthSuccess({ token: access_token, user, merchant })
    } catch (err) {
      console.error('Auth error:', err)
      setError(err.message || 'Authentication failed. Please check credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-100">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 to-indigo-700 px-6 py-8 text-white text-center">
          <h2 className="text-2xl font-bold tracking-tight">CleanDesk Operations</h2>
          <p className="text-indigo-100 text-sm mt-1">Multi-Tenant Merchant Inventory Platform</p>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => { setIsRegister(false); setError(null); }}
            className={`flex-1 py-3 text-sm font-semibold text-center transition-colors ${
              !isRegister ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => { setIsRegister(true); setError(null); }}
            className={`flex-1 py-3 text-sm font-semibold text-center transition-colors ${
              isRegister ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Register Workspace
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-left">
          {error && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {isRegister && (
            <>
              <div>
                <label className="block text-left text-xs font-semibold text-slate-700 uppercase mb-1">Merchant Store Name</label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={merchantName}
                    onChange={(e) => {
                      setMerchantName(e.target.value)
                      setMerchantSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-'))
                    }}
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                    placeholder="e.g. CleanDesk Superstore"
                  />
                </div>
              </div>

              <div>
                <label className="block text-left text-xs font-semibold text-slate-700 uppercase mb-1">Workspace Slug (Unique)</label>
                <input
                  type="text"
                  required
                  value={merchantSlug}
                  onChange={(e) => setMerchantSlug(e.target.value)}
                  placeholder="e.g. acme-superstore"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none bg-slate-50"
                />
              </div>

              <div>
                <label className="block text-left text-xs font-semibold text-slate-700 uppercase mb-1">Owner Full Name</label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={ownerName}
                    onChange={(e) => setOwnerName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                    placeholder="e.g. John Doe"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-left text-xs font-semibold text-slate-700 uppercase mb-1">Email Address</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                placeholder="name@company.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-left text-xs font-semibold text-slate-700 uppercase mb-1">Password</label>
            <div className="relative">
              <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 px-4 rounded-lg shadow-md transition-all flex items-center justify-center space-x-2 text-sm disabled:opacity-50"
          >
            <span>{loading ? 'Processing...' : isRegister ? 'Create Merchant Workspace' : 'Sign In'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  )
}