import React, { useState } from 'react';
import { Send } from 'lucide-react';
import { api } from '../api/client';
import { announcePlansChanged, useAsync } from '../lib/hooks';
import { navigate } from '../lib/router';
import { tomorrowIso } from '../lib/format';
import { Button, Card, ErrorPanel, Field, PageHeader, Select, Slider, TextInput } from '../components/ui';
import { useToast } from '../components/feedback';

const DEFAULTS = {
  capacity: 500, maxCharge: 100, maxDischarge: 100, startSoc: 50,
  hvacFlex: 10, shiftKw: 0, shiftHours: 0, shiftStart: '08:00', mtdPeak: '', powerFactor: '',
};
const HALF_HOURS = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);

export default function NewPlanPage() {
  const { notify } = useToast();
  const rooms = useAsync(() => api.rooms(), []);
  const [form, setForm] = useState({ date: tomorrowIso(), room: 'LH-1', ...DEFAULTS });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  function validate() {
    const e = {};
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date)) e.date = 'Choose a date.';
    if (!(form.capacity > 0 && form.capacity <= 10000)) e.capacity = 'Enter a capacity between 1 and 10,000 kWh.';
    if (!(form.maxCharge > 0 && form.maxCharge <= 5000)) e.maxCharge = 'Enter a rate between 1 and 5,000 kW.';
    if (!(form.maxDischarge > 0 && form.maxDischarge <= 5000)) e.maxDischarge = 'Enter a rate between 1 and 5,000 kW.';
    if (!(Number(form.shiftKw) >= 0 && Number(form.shiftKw) <= 2000)) e.shiftKw = 'Enter 0 to 2,000 kW.';
    if (!(Number(form.shiftHours) >= 0 && Number(form.shiftHours) <= 24 && Number(form.shiftHours) * 2 % 1 === 0)) e.shiftHours = 'Enter 0 to 24 hours in half-hour steps.';
    if (form.mtdPeak !== '' && !(Number(form.mtdPeak) >= 0)) e.mtdPeak = 'Enter the kVA from the bill, or leave it empty.';
    if (form.powerFactor !== '' && !(Number(form.powerFactor) > 0.5 && Number(form.powerFactor) <= 1)) e.powerFactor = 'Enter a power factor between 0.51 and 1.';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit(ev) {
    ev.preventDefault();
    if (!validate()) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.dispatch({
        date: form.date,
        room: form.room,
        battery_capacity_kwh: Number(form.capacity),
        max_charge_rate_kw: Number(form.maxCharge),
        max_discharge_rate_kw: Number(form.maxDischarge),
        initial_soc_ratio: form.startSoc / 100,
        hvac_flex_percent: form.hvacFlex,
        shiftable_load_kw: Number(form.shiftKw) || 0,
        shiftable_hours: Number(form.shiftHours) || 0,
        shiftable_usual_start: form.shiftStart,
        month_to_date_peak_kva: form.mtdPeak === '' ? undefined : Number(form.mtdPeak),
        power_factor: form.powerFactor === '' ? undefined : Number(form.powerFactor),
      });
      announcePlansChanged();
      notify(`Plan #${data.audit_log_id} created`, { detail: 'It is waiting for a facility manager to approve it.' });
      navigate(`/plans/${data.audit_log_id}`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        breadcrumb={[{ label: 'Approvals', to: '/plans' }, { label: 'New dispatch plan' }]}
        title="New dispatch plan"
        description="The same planning run as the console, as a form. Plans are recommendations; a facility manager must approve them."
      />
      <form onSubmit={submit} className="max-w-3xl space-y-6" noValidate>
        {error && <ErrorPanel error={error} onRetry={() => submit({ preventDefault() {} })} />}
        <Card title="When and where">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date" htmlFor="plan-date" error={errors.date} hint="Day-ahead planning defaults to tomorrow.">
              <TextInput id="plan-date" type="date" value={form.date} onChange={(e) => set('date')(e.target.value)} />
            </Field>
            <Field label="Room" htmlFor="plan-room" error={rooms.error ? 'Room list unavailable — using LH-1.' : undefined}>
              <Select id="plan-room" value={form.room} onChange={(e) => set('room')(e.target.value)}>
                {(rooms.data || [{ room_id: 'LH-1', room_type: 'Lecture Hall', building_name: 'Main Academic Complex' }]).map((r) => (
                  <option key={r.room_id} value={r.room_id}>{r.room_id} — {r.room_type}, {r.building_name}</option>
                ))}
              </Select>
            </Field>
          </div>
        </Card>
        <Card title="Battery" description="Physical limits of the campus battery.">
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Capacity (kWh)" htmlFor="cap" error={errors.capacity}>
                <TextInput id="cap" type="number" inputMode="decimal" min={1} max={10000} value={form.capacity} onChange={(e) => set('capacity')(e.target.value)} />
              </Field>
              <Field label="Max charge (kW)" htmlFor="chg" error={errors.maxCharge}>
                <TextInput id="chg" type="number" inputMode="decimal" min={1} max={5000} value={form.maxCharge} onChange={(e) => set('maxCharge')(e.target.value)} />
              </Field>
              <Field label="Max discharge (kW)" htmlFor="dis" error={errors.maxDischarge}>
                <TextInput id="dis" type="number" inputMode="decimal" min={1} max={5000} value={form.maxDischarge} onChange={(e) => set('maxDischarge')(e.target.value)} />
              </Field>
            </div>
            <Slider id="soc" label="Starting battery level" min={20} max={90} step={5} value={form.startSoc} onChange={set('startSoc')}
              format={(v) => `${v}%`} marks={['20% safe minimum', '90% safe maximum']} />
            <p className="text-xs text-ink-2">The optimizer uses exactly these limits; the plan review shows them next to the schedule.</p>
          </div>
        </Card>
        <Card title="Flexible loads" description="What else the plan may move besides the battery. Critical loads (labs, server rooms) are never curtailed.">
          <div className="space-y-4">
            <Slider id="hvac-flex" label="Air-conditioning flexibility" min={0} max={30} step={5} value={form.hvacFlex} onChange={set('hvacFlex')}
              format={(v) => (v ? `±${v}% per half-hour` : 'Off')} marks={['Off', '±30%']}
              hint="Pre-cool before the peak and ease off during it, using the same energy over the day. The digital twin re-checks comfort; if it fails, the plan is re-solved with this off." />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Shiftable equipment (kW)" htmlFor="shift-kw" error={errors.shiftKw} hint="Pumps, EV chargers — 0 if none.">
                <TextInput id="shift-kw" type="number" inputMode="decimal" min={0} max={2000} value={form.shiftKw} onChange={(e) => set('shiftKw')(e.target.value)} />
              </Field>
              <Field label="Hours it must run" htmlFor="shift-h" error={errors.shiftHours}>
                <TextInput id="shift-h" type="number" inputMode="decimal" min={0} max={24} step={0.5} value={form.shiftHours} onChange={(e) => set('shiftHours')(e.target.value)} />
              </Field>
              <Field label="Normally starts" htmlFor="shift-start">
                <Select id="shift-start" value={form.shiftStart} onChange={(e) => set('shiftStart')(e.target.value)}>
                  {HALF_HOURS.map((t) => <option key={t} value={t}>{t}</option>)}
                </Select>
              </Field>
            </div>
          </div>
        </Card>
        <Card title="Billing this month" description="Optional, from the latest CEB bill or meter reading. Makes the demand-charge saving exact instead of a 1/30 estimate.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Highest demand so far this month (kVA)" htmlFor="mtd" error={errors.mtdPeak}>
              <TextInput id="mtd" type="number" inputMode="decimal" min={0} value={form.mtdPeak} onChange={(e) => set('mtdPeak')(e.target.value)} placeholder="e.g. 780" />
            </Field>
            <Field label="Power factor" htmlFor="pf" error={errors.powerFactor} hint="Leave empty to use the site setting.">
              <TextInput id="pf" type="number" inputMode="decimal" min={0.5} max={1} step={0.01} value={form.powerFactor} onChange={(e) => set('powerFactor')(e.target.value)} placeholder="e.g. 0.95" />
            </Field>
          </div>
        </Card>
        <div className="flex justify-end">
          <Button type="submit" icon={Send} loading={busy}>Create plan</Button>
        </div>
      </form>
    </div>
  );
}
