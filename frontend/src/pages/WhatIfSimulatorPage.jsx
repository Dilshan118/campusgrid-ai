import React, { useState } from 'react';
import { Cpu, Thermometer, Users, Sun, AlertTriangle, CheckCircle2 } from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import api from '../api/client';

export default function WhatIfSimulatorPage() {
  const [initialTemp, setInitialTemp] = useState(24.0);
  const [deltaTemp, setDeltaTemp] = useState(3.0);
  const [occMultiplier, setOccMultiplier] = useState(1.5);
  const [loading, setLoading] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleRunSimulation(e) {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const resp = await api.runSimulation(initialTemp, deltaTemp, occMultiplier);
      if (resp.data && resp.data.success) {
        setSimResult(resp.data.data);
      } else {
        setError(resp.data?.error || 'Simulation failed');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Error communicating with simulation backend');
    } finally {
      setLoading(false);
    }
  }

  // Format chart data from 48 intervals
  const chartData = simResult?.simulated_indoor_temps_c?.map((temp, i) => {
    const hour = Math.floor(i / 2);
    const minute = i % 2 === 0 ? '00' : '30';
    return {
      time: `${hour.toString().padStart(2, '0')}:${minute}`,
      indoorTemp: parseFloat(temp.toFixed(2)),
      upperBound: 25.5,
      lowerBound: 21.0,
    };
  }) || [];

  return (
    <div className="space-y-6">
      {/* Simulation Controls Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-sm">
        <h2 className="text-base font-semibold text-slate-100 mb-1 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-blue-400" />
          Digital Twin Cyber-Physical "What-If" Simulator
        </h2>
        <p className="text-xs text-slate-400 mb-6">
          Perturb ambient climate conditions and student occupancy to evaluate building thermal inertia under ASHRAE Standard 55-2023.
        </p>

        <form onSubmit={handleRunSimulation} className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label className="text-xs text-slate-300 font-medium flex items-center justify-between mb-2">
              <span className="flex items-center gap-1"><Thermometer className="w-4 h-4 text-emerald-400" /> Initial Room Temp</span>
              <span className="text-emerald-400 font-bold">{initialTemp.toFixed(1)} °C</span>
            </label>
            <input
              type="range"
              min="20.0"
              max="28.0"
              step="0.5"
              value={initialTemp}
              onChange={(e) => setInitialTemp(parseFloat(e.target.value))}
              className="w-full accent-emerald-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-1">
              <span>20.0 °C</span>
              <span>24.0 °C (Std)</span>
              <span>28.0 °C</span>
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-300 font-medium flex items-center justify-between mb-2">
              <span className="flex items-center gap-1"><Sun className="w-4 h-4 text-amber-400" /> Heatwave Ambient Delta</span>
              <span className="text-amber-400 font-bold">+{deltaTemp.toFixed(1)} °C</span>
            </label>
            <input
              type="range"
              min="-3.0"
              max="8.0"
              step="0.5"
              value={deltaTemp}
              onChange={(e) => setDeltaTemp(parseFloat(e.target.value))}
              className="w-full accent-amber-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-1">
              <span>-3.0 °C</span>
              <span>0.0 °C</span>
              <span>+8.0 °C</span>
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-300 font-medium flex items-center justify-between mb-2">
              <span className="flex items-center gap-1"><Users className="w-4 h-4 text-indigo-400" /> Occupancy Surge Multiplier</span>
              <span className="text-indigo-400 font-bold">{occMultiplier.toFixed(1)}x</span>
            </label>
            <input
              type="range"
              min="0.5"
              max="3.0"
              step="0.1"
              value={occMultiplier}
              onChange={(e) => setOccMultiplier(parseFloat(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-1">
              <span>0.5x</span>
              <span>1.0x (Normal)</span>
              <span>3.0x (Surge)</span>
            </div>
          </div>

          <div className="md:col-span-3 flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-6 py-2.5 rounded-lg text-sm transition-colors flex items-center gap-2"
            >
              <Cpu className="w-4 h-4" />
              {loading ? 'Simulating 2R2C Physics...' : 'Run Physics Simulation'}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-sm text-rose-300 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Simulation Results and Temperature Graph */}
      {simResult && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-6">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">Continuous 2R2C Model Output</span>
              <h3 className="text-lg font-bold text-slate-100 mt-1">Indoor Operative Temperature Trajectory</h3>
            </div>

            <div className="flex items-center gap-3">
              <span
                className={`text-xs font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 ${
                  simResult.is_feasible
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : 'bg-rose-950 text-rose-400 border border-rose-800'
                }`}
              >
                {simResult.is_feasible ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                {simResult.is_feasible ? 'FEASIBLE: WITHIN ENVELOPE' : 'COMFORT LIMITS VIOLATED'}
              </span>

              <div className="text-xs text-slate-400">
                Max Temp: <strong className="text-slate-200">{simResult.max_temp_c?.toFixed(1)}°C</strong> • Violations: <strong className="text-amber-400">{simResult.comfort_violations_count || 0}</strong>
              </div>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis domain={[19, 29]} stroke="#64748b" tick={{ fontSize: 11 }} unit="°C" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <ReferenceLine y={25.5} stroke="#f43f5e" strokeDasharray="4 4" label={{ value: 'ASHRAE Max (25.5°C)', fill: '#f43f5e', fontSize: 11 }} />
                <ReferenceLine y={21.0} stroke="#38bdf8" strokeDasharray="4 4" label={{ value: 'Precooling Min (21.0°C)', fill: '#38bdf8', fontSize: 11 }} />
                <Line type="monotone" dataKey="indoorTemp" stroke="#3b82f6" strokeWidth={2.5} dot={false} name="Indoor Temp (°C)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
