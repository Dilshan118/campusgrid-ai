import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Users, Target, Activity } from 'lucide-react';
import api from '../api/client';

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState({
    total_queries: 142,
    approval_rate_pct: 94.2,
    avg_latency_ms: 124.5,
    top_intents: [
      { intent: 'optimize_dispatch', count: 88, pct: '62%' },
      { intent: 'what_if_simulation', count: 34, pct: '24%' },
      { intent: 'policy_lookup', count: 20, pct: '14%' },
    ],
    query_funnel: [
      { step: 'Queries Received', count: 142, pct: '100%' },
      { step: 'Pipeline Executed', count: 140, pct: '98.6%' },
      { step: 'Safety Verified', count: 138, pct: '97.2%' },
      { step: 'Facility Manager Approved', count: 130, pct: '91.5%' },
    ],
  });

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
        <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-indigo-400" />
          Operator Usage Analytics & Query Performance
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Telemetry on facility manager interactions, multi-agent dispatch latency, and operator approval rates.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
          <span className="text-xs text-slate-400">Total Pipeline Queries</span>
          <p className="text-3xl font-bold text-slate-100 mt-1">{analytics.total_queries}</p>
          <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" /> +18% weekly growth
          </p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
          <span className="text-xs text-slate-400">Recommendation Approval Rate</span>
          <p className="text-3xl font-bold text-emerald-400 mt-1">{analytics.approval_rate_pct}%</p>
          <p className="text-xs text-slate-400 mt-2">Human facility manager sign-off</p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
          <span className="text-xs text-slate-400">Average End-to-End Latency</span>
          <p className="text-3xl font-bold text-indigo-400 mt-1">{analytics.avg_latency_ms} <span className="text-sm font-normal text-slate-400">ms</span></p>
          <p className="text-xs text-slate-400 mt-2">Across 4 sequential agents</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Intent Distribution */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">NLP Intent Classification Distribution</h3>
          <div className="space-y-3">
            {analytics.top_intents.map((item, i) => (
              <div key={i} className="space-y-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="font-mono">{item.intent}</span>
                  <span>{item.count} queries ({item.pct})</span>
                </div>
                <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                  <div className="bg-indigo-500 h-full rounded-full" style={{ width: item.pct }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Operational Funnel */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Execution & Approval Funnel</h3>
          <div className="space-y-3">
            {analytics.query_funnel.map((step, i) => (
              <div key={i} className="space-y-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span>{step.step}</span>
                  <span>{step.count} ({step.pct})</span>
                </div>
                <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                  <div className="bg-emerald-500 h-full rounded-full" style={{ width: step.pct }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
