import React, { useState } from 'react';
import { api } from '../api/client';
import { useAsync } from '../lib/hooks';
import { formatDate, formatKw, formatNumber, tomorrowIso } from '../lib/format';
import { ForecastChart } from '../components/charts';
import { Card, Checkbox, ErrorPanel, Field, LoadingBlock, PageHeader, Select, StatTile, TextInput } from '../components/ui';

function peak(values = [], slots = []) {
  if (!values.length) return { value: null, slot: null };
  let i = 0;
  values.forEach((v, idx) => { if (v > values[i]) i = idx; });
  return { value: values[i], slot: slots[i] };
}

export default function ForecastPage() {
  const [date, setDate] = useState(tomorrowIso());
  const [room, setRoom] = useState('LH-1');
  const [showHistory, setShowHistory] = useState(false);
  const rooms = useAsync(() => api.rooms(), []);
  const forecast = useAsync(() => api.forecast(date, room), [date, room]);
  const history = useAsync(() => (showHistory ? api.historical(date) : Promise.resolve(null)), [showHistory, date]);

  const f = forecast.data;
  const demandPeak = peak(f?.forecast_demand_kw, f?.time_slots);
  const solarPeak = peak(f?.forecast_solar_kw, f?.time_slots);

  return (
    <div>
      <PageHeader title="Forecast" description="Day-ahead demand and solar forecast from Agent 1, half-hour by half-hour." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Date" htmlFor="fc-date"><TextInput id="fc-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto" /></Field>
        <Field label="Room (sets the timetable used)" htmlFor="fc-room">
          <Select id="fc-room" value={room} onChange={(e) => setRoom(e.target.value)} className="w-auto">
            {(rooms.data || [{ room_id: 'LH-1', room_type: 'Lecture Hall' }]).map((r) => <option key={r.room_id} value={r.room_id}>{r.room_id} — {r.room_type}</option>)}
          </Select>
        </Field>
        <div className="pb-2"><Checkbox id="fc-history" checked={showHistory} onChange={setShowHistory}>Overlay historical profile</Checkbox></div>
      </div>

      {forecast.error && <ErrorPanel error={forecast.error} onRetry={forecast.reload} />}
      {forecast.loading && !f ? <LoadingBlock label="Forecasting…" /> : f && (
        <div className={forecast.loading ? 'space-y-4 opacity-60' : 'space-y-4'}>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label="Forecast peak" value={formatKw(demandPeak.value)} sub={`at ${demandPeak.slot} on ${formatDate(f.target_date)}`} />
            <StatTile label="Solar peak" value={formatKw(solarPeak.value)} sub={solarPeak.slot ? `at ${solarPeak.slot}` : undefined} />
            <StatTile label="Flagged intervals" value={formatNumber(f.anomaly_count)} sub="Unusually high demand" />
          </div>
          {f.forecast_summary && <Card title="Summary"><p className="text-sm text-ink">{f.forecast_summary}</p></Card>}
          <Card>
            <ForecastChart
              slots={f.time_slots} demand={f.forecast_demand_kw} solar={f.forecast_solar_kw}
              lower={f.lower_bound_kw} upper={f.upper_bound_kw}
              historical={showHistory && history.data ? history.data.map((r) => r.base_load_kw) : undefined}
            />
            {showHistory && <p className="mt-2 text-xs text-ink-2">Historical readings carry differential-privacy noise, so they are approximate by design.</p>}
          </Card>
        </div>
      )}
    </div>
  );
}
