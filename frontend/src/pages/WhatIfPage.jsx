import React, { useState } from 'react';
import { ArrowRight, CloudOff, Play } from 'lucide-react';
import { api } from '../api/client';
import { buildPath, navigate } from '../lib/router';
import { formatDate, tomorrowIso } from '../lib/format';
import { TemperatureChart } from '../components/charts';
import { Banner, Button, Card, Chip, ErrorPanel, Field, PageHeader, Select, Slider, TextInput } from '../components/ui';
import { useAsync } from '../lib/hooks';
import { scenarioToPlanQuestion } from '../components/plan';

const PRESETS = [
  { label: 'Normal', occ: 1 },
  { label: 'Exam hall 1.5×', occ: 1.5 },
  { label: 'Crowd surge 2.5×', occ: 2.5 },
];

const slots48 = (n) => Array.from({ length: n }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);

export default function WhatIfPage() {
  const rooms = useAsync(() => api.rooms(), []);
  const [room, setRoom] = useState('LH-1');
  const [date, setDate] = useState(tomorrowIso());
  const [initial, setInitial] = useState(24);
  const [delta, setDelta] = useState(0);
  const [occ, setOcc] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function run(e) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.whatIf({ date, room, initial_temp_c: initial, ambient_temp_delta_c: delta, occupancy_multiplier: occ }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const indoor = result?.simulated_indoor_temps_c || [];
  const band = [result?.comfort_limits?.min_c ?? 21, result?.comfort_limits?.max_c ?? 25.5];
  const violations = result?.comfort_violations_count || 0;

  return (
    <div>
      <PageHeader title="What-if simulator" description="Test a scenario on building comfort before planning around it. Simulations change nothing and need no approval." />
      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card title="Scenario">
          <form onSubmit={run} className="space-y-5">
            <Field label="Room" htmlFor="wi-room" hint="Its capacity caps how many people are simulated.">
              <Select id="wi-room" value={room} onChange={(e) => setRoom(e.target.value)}>
                {(rooms.data || [{ room_id: 'LH-1', room_type: 'Lecture Hall', max_capacity: 250 }]).map((r) => (
                  <option key={r.room_id} value={r.room_id}>{r.room_id} — {r.room_type}{r.max_capacity ? ` (${r.max_capacity} seats)` : ''}</option>
                ))}
              </Select>
            </Field>
            <Field label="Date" htmlFor="wi-date" hint="Uses that day's weather forecast.">
              <TextInput id="wi-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
            <Slider id="wi-initial" label="Starting indoor temperature" min={18} max={35} step={0.5} value={initial} onChange={setInitial} format={(v) => `${v.toFixed(1)} °C`} />
            <Slider id="wi-delta" label="Outdoor temperature change" min={-10} max={15} step={0.5} value={delta} onChange={setDelta}
              format={(v) => `${v > 0 ? '+' : ''}${v} °C`} marks={['−10', '0', '+15']} />
            <div className="space-y-2">
              <Slider id="wi-occ" label="Occupancy" min={0} max={5} step={0.1} value={occ} onChange={setOcc} format={(v) => `${v.toFixed(1)}×`} />
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <Chip key={p.label} onClick={() => setOcc(p.occ)} className={occ === p.occ ? 'border-accent-text text-accent-text' : ''}>{p.label}</Chip>
                ))}
              </div>
            </div>
            <Button type="submit" icon={Play} loading={busy} className="w-full">Run simulation</Button>
          </form>
        </Card>

        <div className="min-w-0 space-y-4">
          {error && <ErrorPanel error={error} onRetry={run} />}
          {!result && !error && (
            <Card><p className="text-sm text-ink-2">Set a scenario and run it to see the indoor temperature for {formatDate(date)} against the 21.0–25.5 °C comfort band.</p></Card>
          )}
          {result && (
            <div className={busy ? 'space-y-4 opacity-60' : 'space-y-4'}>
              <Banner tone={violations ? 'warning' : 'success'}
                title={violations ? `${violations} of ${indoor.length} half-hours too ${indoor.some((t) => t > band[1]) ? 'hot' : 'cold'}` : 'Comfort maintained all day'}>
                {result.room || room} · outdoor {delta > 0 ? '+' : ''}{delta} °C · occupancy {occ.toFixed(1)}× · starting at {initial.toFixed(1)} °C · {formatDate(result.target_date)}
              </Banner>
              {result.occupancy_capped_intervals > 0 && (
                <Banner tone="neutral">Occupancy was capped at {result.room}'s {result.room_capacity} seats for {result.occupancy_capped_intervals} half-hours (the campus meter counts are building-wide).</Banner>
              )}
              {String(result.weather_source || '').includes('fallback') && (
                <Banner tone="neutral" icon={CloudOff}>Live weather unavailable — using a typical-day weather curve.</Banner>
              )}
              <Card>
                <TemperatureChart slots={slots48(indoor.length)} indoor={indoor} outdoor={result.ambient_temperatures_c} band={band} />
              </Card>
              <Button variant="secondary" icon={ArrowRight} onClick={() => navigate(buildPath('/ask', { q: scenarioToPlanQuestion(room, delta, occ) }))}>
                Plan for this scenario
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
