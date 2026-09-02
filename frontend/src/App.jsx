import React, { useState } from 'react';
import { Activity, BatteryCharging, Cpu, BookOpen, BarChart3, ShieldAlert } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');

  const navItems = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'twin', label: 'Digital Twin (What-If)', icon: Cpu },
    { id: 'optimizer', label: 'Dispatch Optimizer', icon: BatteryCharging },
    { id: 'knowledge', label: 'Tariff Knowledge Base', icon: BookOpen },
    { id: 'analytics', label: 'Web Analytics', icon: BarChart3 },
    { id: 'security', label: 'Security Audit (Red Team)', icon: ShieldAlert },
  ];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-slate-800 p-4 flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-2 mb-8 px-2">
            <BatteryCharging className="w-8 h-8 text-emerald-400" />
            <span className="font-bold text-lg tracking-tight">CampusGrid AI</span>
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-emerald-600 text-white'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
        <div className="px-3 py-2 text-xs text-slate-500 border-t border-slate-800">
          CampusGrid AI v4.2 • SLIIT IT3041
        </div>
      </aside>

      {/* Main View Container */}
      <main className="flex-1 flex flex-col overflow-auto">
        <header className="h-16 border-b border-slate-800 px-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold capitalize">{activeTab} Console</h1>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <span>Status: <strong className="text-emerald-400">Microgrid Online</strong></span>
            <span>PUCSL Schedule: <strong>GP-2 (Active)</strong></span>
          </div>
        </header>

        <section className="p-6 flex-1">
          {/* Skeleton Placeholder for Components */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
              <span className="text-xs text-slate-400">Campus Total Load</span>
              <p className="text-2xl font-bold text-slate-100 mt-1">420.5 kW</p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
              <span className="text-xs text-slate-400">Solar PV Output</span>
              <p className="text-2xl font-bold text-emerald-400 mt-1">285.0 kW</p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
              <span className="text-xs text-slate-400">BESS State-of-Charge</span>
              <p className="text-2xl font-bold text-blue-400 mt-1">68.5%</p>
            </div>
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
              <span className="text-xs text-slate-400">Estimated Today Savings</span>
              <p className="text-2xl font-bold text-amber-400 mt-1">LKR 43,500</p>
            </div>
          </div>

          <div className="bg-slate-900/30 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
            <p className="text-base">Active View: <strong className="text-slate-200">{activeTab}</strong></p>
            <p className="text-xs text-slate-500 mt-2">
              Ready for Member 1 to plug in Recharts power curves and XAI chat assistant.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
