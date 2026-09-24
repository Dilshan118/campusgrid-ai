import React, { useState, useEffect } from 'react';
import {
  Activity,
  Zap,
  Cpu,
  BatteryCharging,
  BookOpen,
  Shield,
  BarChart3,
  User,
  LogOut,
} from 'lucide-react';
import OverviewPage from './pages/OverviewPage';
import OrchestratorPage from './pages/OrchestratorPage';
import WhatIfSimulatorPage from './pages/WhatIfSimulatorPage';
import OptimizerSchedulePage from './pages/OptimizerSchedulePage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import AuditLogsPage from './pages/AuditLogsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import api from './api/client';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [currentUser, setCurrentUser] = useState({
    user_id: 'admin',
    role: 'FACILITY_MANAGER',
    full_name: 'Chief Campus Energy Director',
  });

  const navItems = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'orchestrator', label: 'Multi-Agent Console', icon: Zap },
    { id: 'twin', label: 'Digital Twin (What-If)', icon: Cpu },
    { id: 'optimizer', label: 'Dispatch Optimizer', icon: BatteryCharging },
    { id: 'knowledge', label: 'Tariff Knowledge Base', icon: BookOpen },
    { id: 'audit', label: 'Audit & Compliance', icon: Shield },
    { id: 'analytics', label: 'Web Analytics', icon: BarChart3 },
  ];

  useEffect(() => {
    // Attempt login as default admin to store initial token
    async function initAuth() {
      try {
        const resp = await api.login('admin', 'campusgrid2026');
        if (resp.data && resp.data.success) {
          localStorage.setItem('campusgrid_token', resp.data.data.access_token);
          setCurrentUser({
            user_id: resp.data.data.user_id,
            role: resp.data.data.role,
            full_name: resp.data.data.full_name,
          });
        }
      } catch (err) {
        console.warn('Using local fallback authentication');
      }
    }
    initAuth();
  }, []);

  function handleRoleSwitch(roleName, user, pass, fullName) {
    api.login(user, pass)
      .then((resp) => {
        if (resp.data && resp.data.success) {
          localStorage.setItem('campusgrid_token', resp.data.data.access_token);
          setCurrentUser({
            user_id: user,
            role: roleName,
            full_name: fullName,
          });
        }
      })
      .catch(() => {
        setCurrentUser({
          user_id: user,
          role: roleName,
          full_name: fullName,
        });
      });
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-slate-800 p-4 flex flex-col justify-between shrink-0 bg-slate-950">
        <div>
          <div className="flex items-center gap-3 mb-8 px-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-950">
              <BatteryCharging className="w-6 h-6 text-white" />
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-slate-100 block">CampusGrid AI</span>
              <span className="text-[11px] text-emerald-400 font-medium">Smart Microgrid EMS</span>
            </div>
          </div>

          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-950'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* User Account & Role Switcher */}
        <div className="pt-4 border-t border-slate-800 space-y-3">
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl p-3 text-xs">
            <div className="flex items-center gap-2 mb-1 text-slate-300">
              <User className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-medium truncate">{currentUser.full_name}</span>
            </div>
            <div className="text-[11px] text-emerald-400 font-mono font-semibold">
              ROLE: {currentUser.role}
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-500 px-1">
            <span>Switch Role:</span>
            <div className="flex gap-1.5">
              <button
                onClick={() => handleRoleSwitch('FACILITY_MANAGER', 'admin', 'campusgrid2026', 'Chief Energy Director')}
                title="Facility Manager"
                className={`px-1.5 py-0.5 rounded text-[10px] ${currentUser.role === 'FACILITY_MANAGER' ? 'bg-emerald-800 text-white' : 'bg-slate-800 text-slate-400'}`}
              >
                Lead
              </button>
              <button
                onClick={() => handleRoleSwitch('OPERATOR', 'operator', 'operator123', 'Shift Operator')}
                title="Operator"
                className={`px-1.5 py-0.5 rounded text-[10px] ${currentUser.role === 'OPERATOR' ? 'bg-emerald-800 text-white' : 'bg-slate-800 text-slate-400'}`}
              >
                Op
              </button>
              <button
                onClick={() => handleRoleSwitch('ENERGY_AUDITOR', 'auditor', 'audit123', 'PUCSL Compliance Auditor')}
                title="Compliance Auditor"
                className={`px-1.5 py-0.5 rounded text-[10px] ${currentUser.role === 'ENERGY_AUDITOR' ? 'bg-emerald-800 text-white' : 'bg-slate-800 text-slate-400'}`}
              >
                Aud
              </button>
            </div>
          </div>

          <div className="text-[10px] text-slate-500 px-1">
            SLIIT IRWA • Production v4.2
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-auto bg-slate-950">
        <header className="h-16 border-b border-slate-800/80 px-8 flex items-center justify-between shrink-0 bg-slate-950/80 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-slate-100 uppercase tracking-wider">
              {activeTab === 'overview' && 'System Overview & Live Microgrid Telemetry'}
              {activeTab === 'orchestrator' && 'Central Multi-Agent Coordination Pipeline'}
              {activeTab === 'twin' && '2R2C Cyber-Physical Digital Twin & What-If Simulation'}
              {activeTab === 'optimizer' && '48-Interval PuLP MILP Cost & Peak Shaving Solver'}
              {activeTab === 'knowledge' && 'Hybrid Regulatory Information Retrieval (Dense + BM25 RAG)'}
              {activeTab === 'audit' && 'Cryptographically Signed Immutable Audit Log'}
              {activeTab === 'analytics' && 'Operational Web Analytics & Query Performance'}
            </h1>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Grid Gateway: <strong className="text-emerald-400 font-semibold">Online</strong>
            </span>
            <span className="hidden sm:inline border-l border-slate-800 pl-4">
              Tariff: <strong className="text-slate-200">CEB GP-2 / I-2</strong>
            </span>
          </div>
        </header>

        <section className="p-8 flex-1 overflow-auto">
          {activeTab === 'overview' && <OverviewPage />}
          {activeTab === 'orchestrator' && <OrchestratorPage />}
          {activeTab === 'twin' && <WhatIfSimulatorPage />}
          {activeTab === 'optimizer' && <OptimizerSchedulePage />}
          {activeTab === 'knowledge' && <KnowledgeBasePage />}
          {activeTab === 'audit' && <AuditLogsPage />}
          {activeTab === 'analytics' && <AnalyticsPage />}
        </section>
      </main>
    </div>
  );
}
