import React, { useMemo, useRef, useState } from 'react';
import { CalendarDays, CheckCircle2, Download, Plus, Trash2, Upload } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useAsync } from '../lib/hooks';
import {
  Banner, Button, Card, ConfirmDialog, EmptyState, ErrorPanel, Field, IconButton, LoadingBlock, PageHeader, Select, Tabs, TextInput,
} from '../components/ui';
import { useToast } from '../components/feedback';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const HEADER = 'room_id,course_code,day,start_time,end_time,expected_students';
const TEMPLATE = [
  HEADER,
  'LH-1,IT3041,Mon,08:30,11:30,220',
  'LH-1,IT3020,Mon,13:00,16:00,240',
  'AUD-1,EN1010,Tue,09:00,12:00,550',
].join('\r\n');

function downloadTemplate() {
  const blob = new Blob([TEMPLATE], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'campusgrid-timetable-template.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function TimetablePage() {
  const { can } = useAuth();
  const timetable = useAsync(() => api.timetable(), []);
  const [day, setDay] = useState('all');
  const entries = timetable.data?.entries || [];
  const shown = day === 'all' ? entries : entries.filter((e) => e.day_of_week === Number(day));
  const canManage = can('timetable:manage');

  return (
    <div>
      <PageHeader title="Teaching timetable"
        description="Weekly sessions and expected students per room. The planner uses them for room occupancy; there is no live timetable feed, so keep this current each semester." />
      <div className="space-y-6">
        {timetable.data?.source === 'seed' && (
          <Banner tone="warning" title="These are the built-in demo sessions">
            {canManage ? 'Upload this semester’s timetable below so plans use real occupancy.' : 'Ask the timetable coordinator to upload this semester’s timetable.'}
          </Banner>
        )}
        {canManage && (
          <div className="grid items-start gap-6 xl:grid-cols-2">
            <UploadCard onApplied={timetable.reload} />
            <AddSessionCard onAdded={timetable.reload} />
          </div>
        )}
        <Card title="Sessions" description={timetable.data ? `${entries.length} weekly sessions` : undefined}
          actions={<Tabs label="Day" value={day} onChange={setDay} tabs={[
            { value: 'all', label: 'All', count: entries.length },
            ...DAYS.map((d, i) => ({ value: String(i + 1), label: d, count: entries.filter((e) => e.day_of_week === i + 1).length })),
          ]} />}>
          {timetable.error ? <ErrorPanel error={timetable.error} onRetry={timetable.reload} />
            : timetable.loading && !timetable.data ? <LoadingBlock />
              : !shown.length ? <EmptyState icon={CalendarDays} title="No sessions on this day." />
                : <SessionTable rows={shown} canManage={canManage} onChanged={timetable.reload} />}
        </Card>
      </div>
    </div>
  );
}

function SessionTable({ rows, canManage, onChanged }) {
  const { notify } = useToast();
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteTimetableSession(removing.schedule_id);
      notify(`${removing.course_code} removed from ${removing.room_id}`, { tone: 'info' });
      onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      setRemoving(null);
    }
  }

  return (
    <div className="space-y-3">
      {error && <ErrorPanel error={error} />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-ink-2">
            <tr>
              <th scope="col" className="pb-2 font-medium">Day</th>
              <th scope="col" className="pb-2 font-medium">Time</th>
              <th scope="col" className="pb-2 font-medium">Room</th>
              <th scope="col" className="pb-2 font-medium">Course</th>
              <th scope="col" className="pb-2 text-right font-medium">Students</th>
              {canManage && <th scope="col" className="pb-2"><span className="sr-only">Actions</span></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((e) => (
              <tr key={e.schedule_id}>
                <td className="py-2 text-ink">{DAYS[e.day_of_week - 1]}</td>
                <td className="py-2 text-ink tabular">{e.start_time}–{e.end_time}</td>
                <td className="py-2 text-ink">{e.room_id}</td>
                <td className="py-2 text-ink">{e.course_code}</td>
                <td className="py-2 text-right text-ink tabular">{e.expected_students}</td>
                {canManage && (
                  <td className="py-1 text-right">
                    <IconButton label={`Remove ${e.course_code} on ${DAYS[e.day_of_week - 1]}`} icon={Trash2} onClick={() => setRemoving(e)} />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ConfirmDialog open={Boolean(removing)} busy={busy} title="Remove this session?" confirmLabel="Remove" confirmVariant="danger"
        onCancel={() => setRemoving(null)} onConfirm={remove}>
        {removing && <p>{removing.course_code} in {removing.room_id}, {DAYS[removing.day_of_week - 1]} {removing.start_time}–{removing.end_time}. The change is recorded in the audit trail.</p>}
      </ConfirmDialog>
    </div>
  );
}

function UploadCard({ onApplied }) {
  const { notify } = useToast();
  const fileRef = useRef(null);
  const [file, setFile] = useState(null); // { name, lines }
  const [mode, setMode] = useState('replace');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);

  async function readFile(ev) {
    const picked = ev.target.files?.[0];
    setPreview(null);
    setError(null);
    if (!picked) { setFile(null); return; }
    if (picked.size > 900_000) { setError({ code: 'VALIDATION_ERROR', message: 'The file is larger than 900 KB. Split it by faculty and upload with “Add to the timetable”.' }); return; }
    const text = await picked.text();
    // Sent line by line: one long string would be cut at 10,000 characters by the server's input filter.
    const lines = text.split(/\r?\n/);
    setFile({ name: picked.name, lines });
    check({ name: picked.name, lines }, mode);
  }

  async function check(current = file, currentMode = mode) {
    if (!current) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await api.uploadTimetable({ csv_lines: current.lines, mode: currentMode, dry_run: true, filename: current.name }));
    } catch (err) {
      setPreview(null);
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.uploadTimetable({ csv_lines: file.lines, mode, dry_run: false, filename: file.name });
      notify(`${res.valid_rows} sessions ${mode === 'replace' ? 'now make up the timetable' : 'added'}`, { tone: 'success', detail: `Recorded as audit #${res.audit_log_id}.` });
      setFile(null);
      setPreview(null);
      if (fileRef.current) fileRef.current.value = '';
      onApplied();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  const errors = preview?.errors || [];
  return (
    <Card title="Upload a timetable (CSV)"
      description="One row per weekly session. Export from Excel with “Save as → CSV UTF-8”. Every row is checked before anything changes."
      actions={<Button size="sm" variant="secondary" icon={Download} onClick={downloadTemplate}>Template</Button>}>
      <div className="space-y-4">
        <p className="rounded-lg bg-surface-2 px-3 py-2 font-mono text-xs text-ink-2">{HEADER}</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="CSV file" htmlFor="tt-file">
            <input id="tt-file" ref={fileRef} type="file" accept=".csv,text/csv" onChange={readFile}
              className="block w-full text-sm text-ink-2 file:mr-3 file:rounded-md file:border-0 file:bg-surface-3 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink" />
          </Field>
          <Field label="What to do with it" htmlFor="tt-mode"
            hint={mode === 'replace' ? 'Start of semester: the file becomes the whole timetable.' : 'Add the file’s sessions to the current timetable.'}>
            <Select id="tt-mode" value={mode} onChange={(e) => { setMode(e.target.value); check(file, e.target.value); }}>
              <option value="replace">Replace the whole timetable</option>
              <option value="append">Add to the current timetable</option>
            </Select>
          </Field>
        </div>
        {error && <ErrorPanel error={error} />}
        {busy && !preview && <LoadingBlock label="Checking the file…" />}
        {preview && (
          errors.length ? (
            <Banner tone="critical" title={`${errors.length} problem${errors.length === 1 ? '' : 's'} — nothing will change until they are fixed`}>
              <ul className="mt-1 max-h-56 space-y-0.5 overflow-y-auto">
                {errors.map((e, i) => <li key={i}><span className="font-medium">Line {e.line}</span> · {e.field}: {e.message}</li>)}
              </ul>
            </Banner>
          ) : (
            <Banner tone="success" icon={CheckCircle2} title={`${preview.valid_rows} sessions are ready`}>
              {DAYS.map((d) => `${d} ${preview.sessions_by_day?.[d] || 0}`).join(' · ')} · {preview.rooms?.length || 0} rooms
            </Banner>
          )
        )}
        <Button icon={Upload} disabled={!preview || errors.length > 0 || busy} onClick={() => setConfirming(true)}>
          {mode === 'replace' ? 'Replace the timetable' : 'Add these sessions'}
        </Button>
      </div>
      <ConfirmDialog open={confirming} busy={busy} title={mode === 'replace' ? 'Replace the whole timetable?' : 'Add these sessions?'}
        confirmLabel={mode === 'replace' ? 'Replace' : 'Add'} onCancel={() => setConfirming(false)} onConfirm={apply}>
        <p>{preview?.valid_rows} sessions from {file?.name}. {mode === 'replace' && 'Every current session is removed. '}The change and the file’s fingerprint are recorded in the audit trail.</p>
      </ConfirmDialog>
    </Card>
  );
}

const EMPTY_SESSION = { room_id: '', course_code: '', day: 'Mon', start_time: '08:00', end_time: '10:00', expected_students: '' };

function AddSessionCard({ onAdded }) {
  const { notify } = useToast();
  const rooms = useAsync(() => api.rooms(), []);
  const [form, setForm] = useState(EMPTY_SESSION);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const room = useMemo(() => (rooms.data || []).find((r) => r.room_id === form.room_id), [rooms.data, form.room_id]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.addTimetableSession({ ...form, expected_students: Number(form.expected_students) });
      notify(`${res.entry.course_code} added to ${res.entry.room_id}`, { tone: 'success' });
      setForm((f) => ({ ...EMPTY_SESSION, room_id: f.room_id, day: f.day }));
      onAdded();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Add one session" description="For a make-up lecture, an exam or a room change. Clashes with another session in the same room are refused.">
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorPanel error={error} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Room" htmlFor="s-room" hint={room ? `${room.room_type}, seats ${room.max_capacity}` : undefined}>
            <Select id="s-room" value={form.room_id} onChange={set('room_id')} required>
              <option value="" disabled>Choose a room</option>
              {(rooms.data || []).map((r) => <option key={r.room_id} value={r.room_id}>{r.room_id} — {r.building_name}</option>)}
            </Select>
          </Field>
          <Field label="Course code" htmlFor="s-course">
            <TextInput id="s-course" value={form.course_code} maxLength={50} onChange={set('course_code')} placeholder="IT3041" required />
          </Field>
          <Field label="Day" htmlFor="s-day">
            <Select id="s-day" value={form.day} onChange={set('day')}>{DAYS.map((d) => <option key={d} value={d}>{d}</option>)}</Select>
          </Field>
          <Field label="Expected students" htmlFor="s-students">
            <TextInput id="s-students" type="number" inputMode="numeric" min={0} max={room?.max_capacity || 5000}
              value={form.expected_students} onChange={set('expected_students')} required />
          </Field>
          <Field label="Starts" htmlFor="s-start"><TextInput id="s-start" type="time" value={form.start_time} onChange={set('start_time')} required /></Field>
          <Field label="Ends" htmlFor="s-end"><TextInput id="s-end" type="time" value={form.end_time} onChange={set('end_time')} required /></Field>
        </div>
        <Button type="submit" icon={Plus} loading={busy}>Add session</Button>
      </form>
    </Card>
  );
}

