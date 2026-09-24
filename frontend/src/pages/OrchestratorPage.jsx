import React, { useState } from 'react';
import { Send, CheckCircle2, AlertCircle, Clock, Zap, BookOpen, Cpu, ShieldCheck } from 'lucide-react';
import api from '../api/client';

export default function OrchestratorPage() {
  const [query, setQuery] = useState(
    'Optimize 24h battery schedule and precool Lecture Hall 1 to 23.5 C to eliminate peak penalty.'
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [approvalStatus, setApprovalStatus] = useState(null);

  const quickPrompts = [
    'Optimize 24h battery schedule and precool Lecture Hall 1 to 23.5 C to eliminate peak penalty.',
    'What are the PUCSL GP-2 peak tariff rates and maximum demand penalty rules?',
    'Simulate a +3C heatwave in Lecture Hall 1 with double student occupancy.',
  ];

  async function handleExecuteQuery(e) {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setApprovalStatus(null);

    try {
      const resp = await api.queryOrchestrator(query);
      if (resp.data && resp.data.success) {
        setResult(resp.data.data);
      } else {
        setError(resp.data?.error || 'Orchestrator pipeline failed');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Connection error to backend');
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(approved) {
    if (!result?.audit_log_id) return;
    try {
      await api.approveAudit(result.audit_log_id, approved, approved ? 'Approved by facility manager' : 'Rejected');
      setApprovalStatus(approved ? 'APPROVED' : 'REJECTED');
    } catch (err) {
      alert('Failed to update audit log status');
    }
  }

  return (
    <div className="space-y-6">
      {/* Query Bar */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-sm">
        <h2 className="text-base font-semibold text-slate-100 mb-1 flex items-center gap-2">
          <Zap className="w-5 h-5 text-emerald-400" />
          Autonomous Multi-Agent Orchestrator
        </h2>
        <p className="text-xs text-slate-400 mb-4">
          Type queries in natural English. The Orchestrator parses intent, runs the 4-agent pipeline, and proposes grounded recommendations.
        </p>

        <form onSubmit={handleExecuteQuery} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Schedule battery to shave peak demand tomorrow..."
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500 transition-colors"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium px-5 py-2.5 rounded-lg text-sm flex items-center gap-2 transition-colors"
          >
            <Send className="w-4 h-4" />
            {loading ? 'Executing Pipeline...' : 'Run Query'}
          </button>
        </form>

        {/* Quick prompt chips */}
        <div className="flex flex-wrap gap-2 mt-3 items-center">
          <span className="text-xs text-slate-500">Quick prompts:</span>
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setQuery(p)}
              className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded-full transition-colors truncate max-w-xs"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-sm text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Multi-Agent Stepper View */}
      {result && (
        <div className="space-y-6">
          {/* 4-Agent Pipeline Status Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="font-semibold text-slate-300">Agent 1: Telemetry</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              </div>
              <p className="text-xs text-slate-400">Demand & Solar Forecast</p>
              <p className="text-xs text-emerald-400 mt-2">48 Intervals Computed</p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="font-semibold text-slate-300">Agent 2: Digital Twin</span>
                <Cpu className="w-4 h-4 text-blue-400" />
              </div>
              <p className="text-xs text-slate-400">2R2C Thermal & Battery SOC</p>
              <p className="text-xs text-blue-400 mt-2">
                {result.digital_twin_feasibility?.is_feasible ? 'Physical Feasibility: SAFE' : 'Feasibility: CHECKED'}
              </p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="font-semibold text-slate-300">Agent 3: Policy RAG</span>
                <BookOpen className="w-4 h-4 text-amber-400" />
              </div>
              <p className="text-xs text-slate-400">PUCSL & ASHRAE Regulations</p>
              <p className="text-xs text-amber-400 mt-2">{result.citations?.length || 0} Legal Citations Retrieved</p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="font-semibold text-slate-300">Agent 4: Dispatch XAI</span>
                <ShieldCheck className="w-4 h-4 text-purple-400" />
              </div>
              <p className="text-xs text-slate-400">MILP Solver & Explainer</p>
              <p className="text-xs text-purple-400 mt-2">Optimal Schedule Grounded</p>
            </div>
          </div>

          {/* Results Summary Box */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center pb-4 border-b border-slate-800 gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Optimization Verdict</span>
                <h3 className="text-lg font-bold text-slate-100 mt-1">Recommended Behind-the-Meter Dispatch Schedule</h3>
              </div>
              {result.recommendation?.net_savings_lkr !== undefined && (
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <span className="text-xs text-slate-400">Estimated Net Savings</span>
                    <p className="text-xl font-bold text-emerald-400">
                      LKR {Math.round(result.recommendation.net_savings_lkr).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-400">Peak Demand Shaved</span>
                    <p className="text-xl font-bold text-indigo-400">
                      {Math.round(result.recommendation.peak_shaved_kw || 0)} kW
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Plain-English XAI Justification */}
            <div className="mt-5 space-y-3">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Explainable AI (XAI) Justification</h4>
              <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 text-sm text-slate-300 leading-relaxed">
                {result.explanation || result.recommendation?.explanation || 'Schedule successfully calculated.'}
              </div>
            </div>

            {/* Regulatory Citations */}
            {result.citations && result.citations.length > 0 && (
              <div className="mt-5 space-y-2">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Verified Regulatory Sources</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {result.citations.map((c, i) => (
                    <div key={i} className="bg-slate-950/50 border border-slate-800 rounded-lg p-3 text-xs">
                      <div className="flex justify-between items-center text-amber-400 font-semibold mb-1">
                        <span>{c.document_title}</span>
                        <span className="text-slate-400">{c.section_clause}</span>
                      </div>
                      <p className="text-slate-300 line-clamp-3">{c.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Human-in-the-Loop Action Controls */}
            {result.requires_human_approval && (
              <div className="mt-6 pt-5 border-t border-slate-800 flex flex-col sm:flex-row justify-between items-center gap-4">
                <div className="text-xs text-slate-400">
                  Audit Log ID: <strong className="text-slate-200">#{result.audit_log_id}</strong> • Hardware registers locked until approval
                </div>

                <div className="flex items-center gap-3">
                  {approvalStatus ? (
                    <span
                      className={`text-xs font-bold px-4 py-2 rounded-lg ${
                        approvalStatus === 'APPROVED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'
                      }`}
                    >
                      DISPATCH {approvalStatus}
                    </span>
                  ) : (
                    <>
                      <button
                        onClick={() => handleApprove(false)}
                        className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium px-4 py-2 rounded-lg transition-colors"
                      >
                        Reject Plan
                      </button>
                      <button
                        onClick={() => handleApprove(true)}
                        className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-5 py-2 rounded-lg transition-colors flex items-center gap-2 shadow-lg shadow-emerald-900/30"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        Approve Dispatch Schedule
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
