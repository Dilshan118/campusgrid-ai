import React, { useState } from 'react';
import { BatteryCharging, Send } from 'lucide-react';
import { api } from '../api/client';
import { announcePlansChanged, useAsync } from '../lib/hooks';
import { navigate } from '../lib/router';
import { tomorrowIso } from '../lib/format';
import { Banner, Button, Card, ErrorPanel, Field, PageHeader, Select, Slider, TextInput } from '../components/ui';
import { useToast } from '../components/feedback';

const DEFAULTS = { capacity: 500, maxCharge: 100, maxDischarge: 100, startSoc: 50 };

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
            <Banner tone="neutral" icon={BatteryCharging}>
              These values are sent with the plan. The current optimiser version still applies the campus default battery
              (500 kWh, 100 kW) until Agent 4 reads them — the plan review shows the limits actually used.
            </Banner>
          </div>
        </Card>
        <div className="flex justify-end">
          <Button type="submit" icon={Send} loading={busy}>Create plan</Button>
        </div>
      </form>
    </div>
  );
}
