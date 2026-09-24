import React, { useState, useEffect } from 'react';
import { Activity, Sun, Battery, DollarSign, ShieldCheck, Zap, AlertTriangle } from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import api from '../api/client';

export default function OverviewPage() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    async function loadData() {
      try {
        const [healthRes, forecastRes] = await Promise.all([
          api.getHealth().catch(() => ({ data: { data: { status: 'offline' } } })),
          api.getTelemetryForecast().catch(() => null),
        ]);

        if (healthRes?.data?.data) {
          setHealth(healthRes.data.data);
        }

        if (forecastRes?.data?.data) {
          const d = forecastRes.data.data;
          const slots = d.time_slots || [];
          const demand = d.forecast_demand_kw || [];
          const solar = d.forecast_solar_kw || [];

          const formatted = slots.map((slot, i) => ({
            time: slot,
            demand: Math.round(demand[i] || 0),
            solar: Math.round(solar[i] || 0),
            netGrid: Math.max(0, Math.round((demand[i] || 0) - (solar[i] || 0))),
          }));
          setChartData(formatted);
        }
      } catch (err) {
        console.error('Error loading overview data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Campus Total Load</span>
            <Activity className="w-5 h-5 text-indigo-400" />
          </div>
          <p className="text-3xl font-bold text-slate-100">420.5 <span className="text-sm font-normal text-slate-400">kW</span></p>
          <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
            <span>↓ 8.2%</span> vs yesterday baseline
          </p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Solar PV Output</span>
            <Sun className="w-5 h-5 text-amber-400" />
          </div>
          <p className="text-3xl font-bold text-amber-400">285.0 <span className="text-sm font-normal text-slate-400">kW</span></p>
          <p className="text-xs text-slate-400 mt-2">Peak generation: 12:30 PM</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">BESS State of Charge</span>
            <Battery className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-3xl font-bold text-emerald-400">68.5 <span className="text-sm font-normal text-slate-400">%</span></p>
          <p className="text-xs text-slate-400 mt-2">Safe Envelope: 20% – 90%</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Estimated Day Savings</span>
            <DollarSign className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-3xl font-bold text-emerald-300">LKR 43,500</p>
          <p className="text-xs text-emerald-400 mt-2">Peak penalty avoided</p>
        </div>
      </div>

      {/* Main 24-Hour Telemetry & Solar Chart */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <Zap className="w-5 h-5 text-amber-400" />
              48-Interval Campus Power Profile (Demand vs Solar PV)
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Telemetry load forecast calibrated with Open-Meteo solar irradiance and timetable occupancy.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1 text-indigo-400">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span> Total Demand
            </span>
            <span className="flex items-center gap-1 text-amber-400 ml-3">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Solar Generation
            </span>
            <span className="flex items-center gap-1 text-emerald-400 ml-3">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Net Grid Draw
            </span>
          </div>
        </div>

        <div className="h-72 w-full">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorDemand" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorSolar" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit=" kW" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Area type="monotone" dataKey="demand" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorDemand)" name="Demand (kW)" />
                <Area type="monotone" dataKey="solar" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorSolar)" name="Solar PV (kW)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
              Loading telemetry forecast...
            </div>
          )}
        </div>
      </div>

      {/* Grid Tariff Windows & System Health */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Active PUCSL GP-2 Tariff Windows
          </h3>
          <ul className="space-y-2 text-xs">
            <li className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">Peak Window (18:00 – 22:30)</span>
              <strong className="text-rose-400 font-semibold">LKR 58.00 / kWh</strong>
            </li>
            <li className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">Day Window (05:30 – 18:00)</span>
              <strong className="text-amber-300 font-semibold">LKR 30.00 / kWh</strong>
            </li>
            <li className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">Off-Peak (22:30 – 05:30)</span>
              <strong className="text-emerald-400 font-semibold">LKR 15.00 / kWh</strong>
            </li>
            <li className="flex justify-between items-center py-1">
              <span className="text-slate-400">Max Demand Surcharge</span>
              <strong className="text-purple-400 font-semibold">LKR 1,100 / kVA</strong>
            </li>
          </ul>
        </div>

        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Microgrid Safety Guardrails
          </h3>
          <ul className="space-y-2 text-xs">
            <li className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">ASHRAE-55 Thermal Comfort</span>
              <strong className="text-slate-200">21.0°C – 25.5°C</strong>
            </li>
            <li className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">BESS SOC Operating Limits</span>
              <strong className="text-slate-200">20.0% – 90.0%</strong>
            </li>
            <li className="flex justify-between items-center py-1 border-b border-slate-800">
              <span className="text-slate-400">BESS Max Inverter Power</span>
              <strong className="text-slate-200">±100 kW</strong>
            </li>
            <li className="flex justify-between items-center py-1">
              <span className="text-slate-400">Precooling Max Drift Rate</span>
              <strong className="text-slate-200">1.1°C / hour</strong>
            </li>
          </ul>
        </div>

        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Infrastructure Status
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">FastAPI Gateway</span>
              <span className="text-emerald-400 font-medium">Online (v4.2)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">LLM Provider</span>
              <span className="text-slate-200 capitalize">{health?.providers?.llm || 'LiteLLM'}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Vector Store</span>
              <span className="text-slate-200 capitalize">{health?.providers?.vector_store || 'Memory'}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-400">Database Engine</span>
              <span className="text-slate-200 capitalize">{health?.providers?.database || 'PostgreSQL'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
