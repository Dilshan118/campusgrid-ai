import React, { useEffect, useState } from 'react';
import { ArrowRight, CloudOff, PencilLine, Play } from 'lucide-react';
import { api } from '../api/client';
import { buildPath, navigate } from '../lib/router';
import { formatDate, formatKw, formatKwh, formatLKR, isWeekendIso, todayIso, tomorrowIso } from '../lib/format';
import { TemperatureChart } from '../components/charts';
import { Banner, Button, Card, Chip, ErrorPanel, Field, PageHeader, Select, Slider, StatTile, TextInput } from '../components/ui';
import { useAsync } from '../lib/hooks';
import { scenarioToPlanQuestion } from '../components/plan';
import { cn } from '../lib/utils';

const PRESETS = [
  { label: 'Normal', occ: 1 },
  { label: 'Exam hall 1.5×', occ: 1.5 },
  { label: 'Crowd surge 2.5×', occ: 2.5 },
];

// Used only until GET /api/simulation/venues answers (or if it fails).
const FALLBACK_VENUE_TYPES = [
  {
    key: 'lecture_hall', label: 'Lecture Hall', capacity_options: [50, 100, 150, 200, 250], default_capacity: 100,
    seats_per_ac_unit: 35, ac_unit_cooling_kw: 7, equipment_kw_per_seat: 0.012,
    rooms: [{ room_id: 'LH-1', building_name: 'Main Academic Complex', capacity: 250, suggested_ac_count: 8 }],
  },
];
const FALLBACK_HOURS = { weekday: { start: '08:30', end: '17:30' }, weekend: { start: '08:00', end: '20:00' } };
const NO_ROOMS = [];
const PRECOOL_OPTIONS = [0, 30, 60, 90, 120];

const minusMinutes = (hhmm, minutes) => {
  const [h, m] = hhmm.split(':').map(Number);
  const t = Math.max(0, h * 60 + m - minutes);
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
};

const slots48 = (n) => Array.from({ length: n }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);

// Rounds up exactly like room_presets.suggest_ac_count, so the number shown is the number simulated.
const suggestAcs = (type, capacity) => Math.max(1, Math.ceil(capacity / (type?.seats_per_ac_unit || 35) - 1e-9));

export default function WhatIfPage() {
  const venues = useAsync(() => api.venues(), []);
  const venueTypes = venues.data?.venue_types || FALLBACK_VENUE_TYPES;
  const hoursByDay = venues.data?.operating_hours || FALLBACK_HOURS;
  const today = venues.data?.today || todayIso();

  // 1. Venue type  →  2. a listed room of that type, or  →  3. "Custom" with the room's own details.
  const [typeKey, setTypeKey] = useState('lecture_hall');
  const activeType = venueTypes.find((t) => t.key === typeKey) || venueTypes[0];
  const roomsOfType = activeType?.rooms || NO_ROOMS;

  const [roomId, setRoomId] = useState('LH-1');
  const [custom, setCustom] = useState(false);
  const [capacity, setCapacity] = useState(activeType?.default_capacity ?? 100);
  const [numAcs, setNumAcs] = useState(suggestAcs(activeType, activeType?.default_capacity ?? 100));
  const [acsTouched, setAcsTouched] = useState(false);

  // When the real inventory arrives, keep the selection pointing at a room that exists.
  useEffect(() => {
    if (!venueTypes.some((t) => t.key === typeKey)) selectType(venueTypes[0]?.key);
    else if (!custom && roomsOfType.length && !roomsOfType.some((r) => r.room_id === roomId)) setRoomId(roomsOfType[0].room_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [venueTypes]);

  function selectType(key) {
    const t = venueTypes.find((x) => x.key === key) || venueTypes[0];
    if (!t) return;
    setTypeKey(t.key);
    setRoomId(t.rooms?.[0]?.room_id || '');
    setCustom(!t.rooms?.length); // nothing listed for this type: go straight to entering details
    setCapacity(t.default_capacity);
    setAcsTouched(false);
    setNumAcs(suggestAcs(t, t.default_capacity));
  }

  function changeCapacity(value) {
    const c = Math.min(2000, Math.max(1, Math.round(Number(value)) || 1));
    setCapacity(c);
    if (!acsTouched) setNumAcs(suggestAcs(activeType, c));
  }

  const selectedRoom = roomsOfType.find((r) => r.room_id === roomId);

  const [date, setDate] = useState(tomorrowIso());
  const [initial, setInitial] = useState(24);
  const [delta, setDelta] = useState(0);
  const [occ, setOcc] = useState(1);
  const [precool, setPrecool] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const dateError = !date ? 'Pick a date.' : date < today ? 'Pick today or a later date — simulations look ahead, not back.' : null;
  const dayHours = isWeekendIso(date) ? { ...hoursByDay.weekend, label: 'Weekend' } : { ...hoursByDay.weekday, label: 'Weekday' };
  const canRun = !dateError && (custom || !!selectedRoom);

  async function run(e) {
    e?.preventDefault();
    if (!canRun) return;
    setBusy(true);
    setError(null);
    try {
      const payload = { date, initial_temp_c: initial, ambient_temp_delta_c: delta, occupancy_multiplier: occ, precool_minutes: precool };
      if (custom) {
        payload.room_type = activeType.key;
        payload.seating_capacity = capacity;
        payload.num_acs = numAcs;
      } else {
        payload.room = roomId;
      }
      setResult(await api.whatIf(payload));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const indoor = result?.simulated_indoor_temps_c || [];
  const band = [result?.comfort_limits?.min_c ?? 21, result?.comfort_limits?.max_c ?? 25.5];
  const violations = result?.comfort_violations_count || 0;
  const hot = result?.comfort_violations_hot || 0;
  const cold = result?.comfort_violations_cold || 0;
  const assessed = result?.assessed_intervals_count ?? indoor.length;
  const resultRoomConfig = result?.room_config;
  const resultHours = result?.operating_hours;
  const violationWord = hot && cold ? 'outside the comfort band' : hot ? 'too hot' : 'too cold';

  const roomLabel = (r) => `${r.room_id} — ${r.building_name} (${r.capacity} seats)`;

  return (
    <div>
      <PageHeader title="What-if simulator" description="Test a scenario on building comfort before planning around it. Simulations change nothing and need no approval." />
      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <Card title="Scenario">
          <form onSubmit={run} className="space-y-5">
            <Field label="Venue type" htmlFor="wi-type">
              <Select id="wi-type" value={typeKey} onChange={(e) => selectType(e.target.value)}>
                {venueTypes.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
              </Select>
            </Field>

            <Field
              label="Room"
              htmlFor="wi-room"
              hint={custom
                ? (roomsOfType.length ? `Enter the room's details below. Press Custom again to pick a listed ${activeType.label.toLowerCase()}.` : `No ${activeType.label.toLowerCase()} is listed yet — enter the room's details below.`)
                : selectedRoom && `${selectedRoom.capacity} seats · ${selectedRoom.suggested_ac_count} AC unit${selectedRoom.suggested_ac_count === 1 ? '' : 's'} assumed (${selectedRoom.suggested_ac_count * (activeType.ac_unit_cooling_kw || 7)} kW cooling)`}
            >
              <div className="flex gap-2">
                {custom ? (
                  <div className="flex h-10 min-w-0 flex-1 items-center rounded-lg border border-dashed border-line-strong bg-surface-2 px-3 text-sm text-ink">
                    <span className="truncate">Custom {activeType.label.toLowerCase()}</span>
                  </div>
                ) : (
                  <Select id="wi-room" className="min-w-0 flex-1" value={roomId} onChange={(e) => setRoomId(e.target.value)}>
                    {roomsOfType.map((r) => <option key={r.room_id} value={r.room_id}>{roomLabel(r)}</option>)}
                  </Select>
                )}
                <Button
                  variant={custom ? 'primary' : 'secondary'}
                  icon={PencilLine}
                  aria-pressed={custom}
                  disabled={custom && !roomsOfType.length}
                  onClick={() => setCustom((c) => !c)}
                  title={custom ? 'Pick a listed room instead' : "Room not listed? Enter its details"}
                >
                  Custom
                </Button>
              </div>
            </Field>

            {custom && (
              <div className="space-y-4 rounded-lg border border-line bg-surface-2 p-3">
                <Field label="Seating capacity" htmlFor="wi-capacity">
                  <div className="flex flex-wrap gap-2">
                    {(activeType?.capacity_options || []).map((c) => (
                      <Chip key={c} onClick={() => changeCapacity(c)} className={capacity === c ? 'border-accent-text text-accent-text' : ''}>{c}</Chip>
                    ))}
                  </div>
                  <TextInput id="wi-capacity" type="number" min={1} max={2000} value={capacity}
                    onChange={(e) => changeCapacity(e.target.value)} className="mt-2" />
                </Field>
                <Field label="Number of air conditioners" htmlFor="wi-num-acs"
                  hint={`Suggested for a ${activeType.label.toLowerCase()} of this size — change it if you know the real count.`}>
                  <TextInput id="wi-num-acs" type="number" min={1} max={50} value={numAcs}
                    onChange={(e) => { setAcsTouched(true); setNumAcs(Math.min(50, Math.max(1, Math.round(Number(e.target.value)) || 1))); }} />
                </Field>
                <p className="text-xs text-ink-2">
                  Total cooling: <span className="tabular font-medium text-ink">{(numAcs * (activeType.ac_unit_cooling_kw || 7)).toFixed(1)} kW</span>
                  {' '}({activeType.ac_unit_cooling_kw || 7} kW per unit)
                  {activeType.equipment_kw_per_seat > 0 && <> · lighting &amp; equipment {(activeType.equipment_kw_per_seat * capacity).toFixed(1)} kW while in use</>}
                </p>
              </div>
            )}

            <Field label="Date" htmlFor="wi-date" error={dateError}
              hint={`${dayHours.label} — room in use ${dayHours.start}–${dayHours.end}. Uses that day's weather forecast.`}>
              <TextInput id="wi-date" type="date" min={today} value={date} onChange={(e) => setDate(e.target.value)}
                aria-invalid={!!dateError} className={cn(dateError && 'border-critical')} />
            </Field>
            <Field label="Pre-cool before opening" htmlFor="wi-precool"
              hint={precool
                ? `ACs start at ${minusMinutes(dayHours.start, precool)} to cool the room before it opens at ${dayHours.start}.`
                : `ACs start when the room opens at ${dayHours.start}.`}>
              <Select id="wi-precool" value={precool} onChange={(e) => setPrecool(Number(e.target.value))}>
                {PRECOOL_OPTIONS.map((m) => <option key={m} value={m}>{m ? `${m} minutes` : 'Off'}</option>)}
              </Select>
            </Field>
            <Slider id="wi-initial" label="Starting indoor temperature" min={18} max={35} step={0.5} value={initial} onChange={setInitial} format={(v) => `${v.toFixed(1)} °C`} />
            <Slider id="wi-delta" label="Outdoor temperature change" min={-10} max={15} step={0.5} value={delta} onChange={setDelta}
              format={(v) => `${v > 0 ? '+' : ''}${v} °C`} marks={['−10', '0', '+15']} />
            <div className="space-y-2">
              <Slider id="wi-occ" label="Occupancy (of seats)" min={0} max={5} step={0.1} value={occ} onChange={setOcc} format={(v) => `${v.toFixed(1)}×`} />
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <Chip key={p.label} onClick={() => setOcc(p.occ)} className={occ === p.occ ? 'border-accent-text text-accent-text' : ''}>{p.label}</Chip>
                ))}
              </div>
            </div>
            <Button type="submit" icon={Play} loading={busy} disabled={!canRun} className="w-full">Run simulation</Button>
          </form>
        </Card>

        <div className="min-w-0 space-y-4">
          {error && <ErrorPanel error={error} onRetry={run} />}
          {!result && !error && (
            <Card><p className="text-sm text-ink-2">Pick a venue and run the scenario to see the indoor temperature for {formatDate(date)} against the 21.0–25.5 °C comfort band while the room is in use.</p></Card>
          )}
          {result && (
            <div className={busy ? 'space-y-4 opacity-60' : 'space-y-4'}>
              <Banner tone={violations ? 'warning' : 'success'}
                title={violations ? `${violations} of ${assessed} occupied half-hours ${violationWord}` : 'Comfort maintained while the room is in use'}>
                {result.room}{result.building_name ? `, ${result.building_name}` : ''} · {formatDate(result.target_date)}
                {resultHours && ` (in use ${resultHours.start}–${resultHours.end})`} · outdoor {delta > 0 ? '+' : ''}{delta} °C · occupancy {occ.toFixed(1)}× · starting at {initial.toFixed(1)} °C
              </Banner>
              {resultRoomConfig && (
                <Banner tone="neutral">
                  {resultRoomConfig.label} · {resultRoomConfig.capacity} seats · {resultRoomConfig.num_acs} AC unit{resultRoomConfig.num_acs === 1 ? '' : 's'} ({resultRoomConfig.total_hvac_capacity_kw} kW cooling, thermostat at {result.target_setpoint_c ?? 24} °C while in use
                  {result.precool_intervals ? `, from ${result.precool_intervals * 30} min before opening` : ''})
                  {resultRoomConfig.equipment_heat_kw > 0 && ` · ${resultRoomConfig.equipment_heat_kw} kW lighting & equipment`}
                </Banner>
              )}
              {result.hvac_energy && (
                <div className="grid gap-3 sm:grid-cols-3">
                  <StatTile label="AC electricity" value={formatKwh(result.hvac_energy.electricity_kwh, 1)}
                    sub={`Cooling ÷ efficiency (COP ${result.hvac_energy.cop})`} />
                  <StatTile label="Cost for the day" value={formatLKR(result.hvac_energy.cost_lkr)}
                    sub="PUCSL GP-2 time-of-use rates" />
                  <StatTile label="Peak electrical draw" value={formatKw(result.hvac_energy.peak_electric_kw, 1)}
                    sub={result.hvac_energy.peak_time
                      ? `at ${result.hvac_energy.peak_time}${result.hvac_energy.peak_in_tariff_peak_window ? ' — in the 18:00–22:30 peak window' : ''}`
                      : 'ACs never ran'} />
                </div>
              )}
              {String(result.weather_source || '').includes('fallback') && (
                <Banner tone="neutral" icon={CloudOff}>Live weather unavailable — using a typical-day weather curve.</Banner>
              )}
              <Card>
                <TemperatureChart slots={slots48(indoor.length)} indoor={indoor} outdoor={result.ambient_temperatures_c} band={band}
                  occupied={result.occupied_mask || undefined} occupiedWindow={resultHours || undefined} />
              </Card>
              {!result.is_custom_room && (
                <Button variant="secondary" icon={ArrowRight} onClick={() => navigate(buildPath('/ask', { q: scenarioToPlanQuestion(result.room, delta, occ) }))}>
                  Plan for this scenario
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
