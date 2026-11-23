import React from 'react'
import { Building2, User, LogOut, Radio } from 'lucide-react'

export default function Navbar({ user, merchant, isWsConnected, onLogout, activeTab, setActiveTab }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo & Navigation */}
          <div className="flex items-center space-x-8">
            <div className="flex items-center space-x-2">
              <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xl shadow-sm">
                C
              </div>
              <div>
                <span className="font-bold text-lg text-slate-900 tracking-tight">CleanDesk</span>
                <span className="text-xs bg-indigo-50 text-indigo-700 font-semibold px-2 py-0.5 rounded-full ml-2">
                  Operations
                </span>
              </div>
            </div>

            <nav className="hidden md:flex space-x-2">
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'dashboard'
                    ? 'bg-slate-100 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setActiveTab('catalog')}
                className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'catalog'
                    ? 'bg-slate-100 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                Product Catalog
              </button>
              <button
                onClick={() => setActiveTab('approvals')}
                className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'approvals'
                    ? 'bg-slate-100 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                Stock Approvals
              </button>
            </nav>
          </div>

          {/* Tenant Info & User State */}
          <div className="flex items-center space-x-4">
            {/* Live WebSocket Status Indicator */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                isWsConnected ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
              }`}
              title={isWsConnected ? 'Real-time WebSocket connected' : 'Connecting to real-time feed...'}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isWsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                }`}
              />
              <span className="hidden sm:inline">{isWsConnected ? 'Live' : 'Syncing'}</span>
            </div>

            {/* Merchant Workspace Info */}
            <div className="hidden lg:flex items-center space-x-1.5 text-xs text-slate-500 bg-slate-50 px-2.5 py-1 rounded border border-slate-200">
              <Building2 className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-semibold text-slate-700">{merchant?.name}</span>
              <span className="text-slate-400">({merchant?.slug})</span>
            </div>

            {/* User Role Badge */}
            <div className="flex items-center space-x-2">
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                  user?.role === 'OWNER'
                    ? 'bg-indigo-100 text-indigo-800'
                    : 'bg-emerald-100 text-emerald-800'
                }`}
              >
                {user?.role}
              </span>
              <span className="text-sm font-medium text-slate-700 hidden sm:inline">{user?.name}</span>
            </div>

            {/* Logout Button */}
            <button
              onClick={onLogout}
              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}