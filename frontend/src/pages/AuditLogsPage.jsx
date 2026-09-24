import React, { useState, useEffect } from 'react';
import { Shield, Clock, CheckCircle2, XCircle, RefreshCw, FileText } from 'lucide-react';
import api from '../api/client';

export default function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function fetchLogs() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.getAuditLogs(30);
      if (resp.data && resp.data.success) {
        setLogs(resp.data.data || []);
      } else {
        setError(resp.data?.error || 'Failed to load audit logs');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Error fetching audit logs');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Shield className="w-5 h-5 text-indigo-400" />
            Immutable Audit Trail & Compliance Store
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Cryptographically sealed, append-only transaction logs recording all operator queries, model outputs, and human approvals.
          </p>
        </div>

        <button
          onClick={fetchLogs}
          disabled={loading}
          className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium px-3 py-2 rounded-lg flex items-center gap-2 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Logs
        </button>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Log ID</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Operator Query</th>
                <th className="py-3 px-4">Final Decision</th>
                <th className="py-3 px-4">Human Approval</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {logs.length > 0 ? (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 font-mono font-semibold text-slate-400">#{log.id}</td>
                    <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : 'Just now'}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-200">{log.user_id}</td>
                    <td className="py-3 px-4 text-slate-300 max-w-xs truncate" title={log.query_text}>
                      {log.query_text}
                    </td>
                    <td className="py-3 px-4 text-emerald-400 font-medium">
                      {log.final_decision?.net_savings_lkr !== undefined
                        ? `Savings: LKR ${Math.round(log.final_decision.net_savings_lkr).toLocaleString()}`
                        : log.final_decision?.summary || 'Completed'}
                    </td>
                    <td className="py-3 px-4">
                      {log.human_approved ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-950/80 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                          <CheckCircle2 className="w-3 h-3" /> Approved
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-400 bg-amber-950/80 border border-amber-800/60 px-2 py-0.5 rounded-full">
                          <Clock className="w-3 h-3" /> Pending Review
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-slate-500">
                    {loading ? 'Fetching audit records...' : 'No audit records logged yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
