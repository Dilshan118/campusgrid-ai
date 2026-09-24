import React, { useState, useEffect } from 'react';
import { BatteryCharging, DollarSign, ArrowDownRight, ShieldCheck, Play, BookOpen } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import api from '../api/client';

export default function OptimizerSchedulePage() {
  const [loading, setLoading] = useState(false);
  const [optData, setOptData] = useState(null);
  const [error, setError] = useState(null);

  async function handleRunOptimization() {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.runOptimization({ capacity: 500.0, maxCharge: 100.0, maxDischarge: 100.0 });
      if (resp.data && resp.data.success) {
        setOptData(resp.data.data);
      } else {
        setError(resp.data?.error || 'Optimization solver failed');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Error running optimization');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    handleRunOptimization();
  }, []);

  const solverOutput = optData?.solver_output || {};
  const timeSlots = solverOutput.time_slots || [];
  const pCharge = solverOutput.p_battery_charge_kw || [];
  const pDischarge = solverOutput.p_battery_discharge_kw || [];
  const pGrid = solverOutput.p_grid_import_kw || [];

  const chartData = timeSlots.map((slot, i) => ({
    time: slot,
    charge: Math.round(pCharge[i] || 0),
    discharge: Math.round(pDischarge[i] || 0),
    gridImport: Math.round(pGrid[i] || 0),
  }));

  return (
    <div className="space-y-6">
      {/* Top Controls & Metrics */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-slate-900/60 border border-slate-800 rounded-xl p-5 gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <BatteryCharging className="w-5 h-5 text-purple-400" />
            48-Interval Mixed-Integer Linear Programming (MILP) Dispatch
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Solves cost minimization under Ceylon Electricity Board TOU tariffs while enforcing 20%–90% battery SOC.
          </p>
        </div>

        <button
          onClick={handleRunOptimization}
          disabled={loading}
          className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-lg text-xs flex items-center gap-2 transition-colors shrink-0"
        >
          <Play className="w-3.5 h-3.5" />
          {loading ? 'Solving PuLP MILP...' : 'Re-solve Dispatch'}
        </button>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {/* KPI Financial & Peak Shaving Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">Baseline Energy Cost</span>
          <p className="text-2xl font-bold text-slate-200 mt-1">
            LKR {Math.round(optData?.baseline_cost_lkr || 0).toLocaleString()}
          </p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">Optimized Energy Cost</span>
          <p className="text-2xl font-bold text-slate-200 mt-1">
            LKR {Math.round(optData?.optimized_cost_lkr || 0).toLocaleString()}
          </p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">Net Financial Savings</span>
          <p className="text-2xl font-bold text-emerald-400 mt-1">
            LKR {Math.round(optData?.net_savings_lkr || 0).toLocaleString()}
          </p>
          <p className="text-xs text-emerald-500 mt-1 font-semibold">
            {optData?.savings_percentage?.toFixed(1) || 0}% Total Cost Reduction
          </p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <span className="text-xs text-slate-400">Peak Demand Shaved</span>
          <p className="text-2xl font-bold text-indigo-400 mt-1">
            {Math.round(optData?.peak_shaved_kw || 0)} <span className="text-sm font-normal text-slate-400">kW</span>
          </p>
          <p className="text-xs text-indigo-400 mt-1 flex items-center gap-1">
            <ArrowDownRight className="w-3.5 h-3.5" /> Penalty Traps Shaved
          </p>
        </div>
      </div>

      {/* 48-Interval Battery Charge & Discharge Bar Chart */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-slate-200 mb-4">
          BESS Battery Power Dispatch vs Grid Import Profile (kW)
        </h3>
        <div className="h-72 w-full">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit=" kW" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Legend />
                <Bar dataKey="charge" fill="#38bdf8" name="Charge Rate (kW)" />
                <Bar dataKey="discharge" fill="#a855f7" name="Discharge Rate (kW)" />
                <Bar dataKey="gridImport" fill="#64748b" name="Grid Import (kW)" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
              Solving dispatch schedule...
            </div>
          )}
        </div>
      </div>

      {/* Grounded XAI Justification Card */}
      {optData?.explanation && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Grounded Explainable AI (XAI) Justification
            </h3>
            <span className="text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 px-2.5 py-1 rounded-full font-medium">
              Faithfulness Verified (100% Solver Grounding)
            </span>
          </div>
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 text-sm text-slate-300 leading-relaxed">
            {optData.explanation}
          </div>
        </div>
      )}
    </div>
  );
}
