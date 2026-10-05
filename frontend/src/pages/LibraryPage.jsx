import React, { useEffect, useState } from 'react';
import { CheckCircle2, FilePlus2, Library, RefreshCw, ShieldAlert, ShieldCheck, ThumbsDown, ThumbsUp } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useAsync, useDraft } from '../lib/hooks';
import { formatDate, formatDateTime, formatNumber } from '../lib/format';
import {
  Badge, Banner, Button, Card, ConfirmDialog, Dialog, EmptyState, ErrorPanel, Field, LoadingBlock, PageHeader, Select,
  StatusPill, Tabs, TextInput, Textarea,
} from '../components/ui';
import { useToast } from '../components/feedback';

export default function LibraryPage() {
  const { can } = useAuth();
  const library = useAsync(() => api.regulationLibrary(), []);
  const [queueVersion, setQueueVersion] = useState(0);
  const docs = library.data?.documents || [];
  const refresh = () => { library.reload(); setQueueVersion((v) => v + 1); };

  return (
    <div>
      <PageHeader title="Regulation library"
        description="The documents CampusGrid searches. Every tariff figure in a plan comes from a clause in this library, or is marked as a reference value. New documents are quarantined until a second person approves them." />
      <div className="space-y-6">
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <Card title="Indexed documents" description={library.data ? `${formatNumber(library.data.total_clauses)} clauses in ${docs.length} documents` : undefined}
            actions={can('rag:ingest') && <ReindexButton onDone={refresh} />}>
            {library.error && <ErrorPanel error={library.error} onRetry={library.reload} />}
            {library.loading && !library.data ? <LoadingBlock /> : docs.length === 0 ? (
              <EmptyState icon={Library} title="The library is empty." />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-ink-2">
                  <tr><th scope="col" className="pb-2 font-medium">Document</th><th scope="col" className="pb-2 text-right font-medium">Clauses</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {docs.map((d) => (
                    <tr key={d.source_document}><td className="py-2 text-ink">{d.source_document}</td><td className="py-2 text-right text-ink tabular">{d.clauses}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          {can('rag:ingest') ? <SubmitPanel documents={docs} onSubmitted={refresh} /> : (
            <Card title="Adding documents">
              <p className="text-sm text-ink-2">Facility managers submit new regulations; a second facility manager or the energy auditor approves them before they are used, because a document can change the tariff the solver uses.</p>
            </Card>
          )}
        </div>
        <ReviewQueue key={queueVersion} onReviewed={refresh} />
      </div>
    </div>
  );
}

function ReindexButton({ onDone }) {
  const { notify } = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function reindex() {
    setBusy(true);
    try {
      const res = await api.ingestRegulation({});
      notify(`${res.data?.total_clauses_ingested ?? 0} new clauses from the corpus folder`, { tone: 'info' });
      onDone();
    } catch (err) {
      notify('Re-index failed', { tone: 'warning', detail: err.message });
    } finally {
      setBusy(false);
      setOpen(false);
    }
  }
  return (
    <>
      <Button variant="secondary" size="sm" icon={RefreshCw} onClick={() => setOpen(true)}>Re-index</Button>
      <ConfirmDialog open={open} busy={busy} title="Re-index the corpus folder?" confirmLabel="Re-index" onCancel={() => setOpen(false)} onConfirm={reindex}>
        Re-reads the files kept on the server in the corpus folder (version-controlled with the code). Clauses already present are skipped.
      </ConfirmDialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Submit (maker)
// ---------------------------------------------------------------------------

const EMPTY = { title: '', publisher: 'PUCSL', reference: '', sourceUrl: '', effective: '', supersedes: '' };

function SubmitPanel({ documents, onSubmitted }) {
  const { notify } = useToast();
  const sources = useAsync(() => api.regulationSources(), []);
  const [form, setForm] = useState(EMPTY);
  const [text, setText, clearText] = useDraft('library-submission');
  const [filename, setFilename] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const source = (sources.data || []).find((s) => s.code === form.publisher);

  async function readFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 200_000) { setError({ code: 'VALIDATION_ERROR', message: 'The file is larger than 200 KB.' }); return; }
    setText(await file.text());
    setFilename(file.name);
    if (!form.title) setForm((f) => ({ ...f, title: file.name.replace(/\.(md|txt)$/i, '') }));
  }

  async function submit(e) {
    e.preventDefault();
    setError(null);
    if (!form.title.trim() || !form.reference.trim() || !form.effective || !text.trim()) {
      setError({ code: 'VALIDATION_ERROR', message: 'Add the title, reference, effective date and the document text.' });
      return;
    }
    setBusy(true);
    try {
      const sub = await api.submitRegulation({
        // Line by line: the server's input filter cuts any single string at 10,000 characters.
        text_lines: text.split(/\r?\n/),
        title: form.title.trim(), publisher: form.publisher, reference: form.reference.trim(), effective_date: form.effective,
        source_url: form.sourceUrl.trim() || undefined, supersedes: form.supersedes || undefined, filename: filename || undefined,
      });
      notify(`Submitted for review as #${sub.submission_id}`, {
        tone: 'success', detail: `${sub.screening.clauses_accepted} clause(s) passed screening. Nothing is searchable until a second person approves it.`,
      });
      setForm(EMPTY);
      setFilename(null);
      clearText();
      onSubmitted();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const [screening, setScreening] = useState({ clauses: 0, flags: [], sha256: '' });

  useEffect(() => {
    const rawText = typeof text === 'string' ? text : '';
    if (!rawText.trim()) {
      setScreening({ clauses: 0, flags: [], sha256: '' });
      return;
    }
    const lines = rawText.split(/\r?\n/);
    const clauseCount = lines.filter((l) => /^###\s+clause/i.test(l.trim())).length;

    const flags = [];
    const lower = rawText.toLowerCase();
    if (/ignore\s+(all\s+)?(previous|prior)\s+instructions?/i.test(lower)) flags.push('Instruction Override / Jailbreak');
    if (/system\s*:\s*/i.test(lower)) flags.push('Role Impersonation (System Tag)');
    if (/<script|javascript:/i.test(lower)) flags.push('XSS / Executable Markup');
    if (/drop\s+table|delete\s+from/i.test(lower)) flags.push('SQL Injection Pattern');
    if (/you\s+are\s+(now\s+)?(dan|evil|unrestricted)/i.test(lower)) flags.push('Persona Hijacking');

    if (window.crypto?.subtle) {
      const encoder = new TextEncoder();
      window.crypto.subtle.digest('SHA-256', encoder.encode(rawText)).then((buf) => {
        const hashHex = Array.from(new Uint8Array(buf))
          .map((b) => b.toString(16).padStart(2, '0'))
          .join('');
        setScreening({ clauses: clauseCount, flags, sha256: hashHex });
      }).catch(() => {
        setScreening({ clauses: clauseCount, flags, sha256: '' });
      });
    } else {
      setScreening({ clauses: clauseCount, flags, sha256: '' });
    }
  }, [text]);

  return (
    <Card title="Submit a regulation for review"
      description="Upload a .md or .txt file, or paste the text. Each “### Clause x.y: Title” heading becomes one clause. PDFs: copy the text out, or add the file to the corpus folder.">
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorPanel error={error} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Publisher" htmlFor="reg-pub" hint={source ? `${source.name}${source.domains?.length ? ` · links must be on ${source.domains.join(', ')}` : ''}` : undefined}>
            <Select id="reg-pub" value={form.publisher} onChange={set('publisher')}>
              {(sources.data || [{ code: 'PUCSL', name: 'PUCSL' }]).map((s) => <option key={s.code} value={s.code}>{s.code} — {s.name}</option>)}
            </Select>
          </Field>
          <Field label="Reference" htmlFor="reg-ref" hint="Gazette, decision or circular number.">
            <TextInput id="reg-ref" maxLength={200} value={form.reference} onChange={set('reference')} placeholder="PUCSL Tariff Decision 2026/03" />
          </Field>
          <Field label="Document title" htmlFor="reg-title" hint="A new version needs its own title, e.g. with its year.">
            <TextInput id="reg-title" maxLength={255} value={form.title} onChange={set('title')} placeholder="PUCSL Electricity Tariff Schedule GP-2 (2026)" />
          </Field>
          <Field label="Effective from" htmlFor="reg-date"><TextInput id="reg-date" type="date" value={form.effective} onChange={set('effective')} /></Field>
          <Field label="Source link (optional)" htmlFor="reg-url"><TextInput id="reg-url" type="url" maxLength={500} value={form.sourceUrl} onChange={set('sourceUrl')} placeholder="https://www.pucsl.gov.lk/…" /></Field>
          <Field label="Replaces" htmlFor="reg-sup" hint="The replaced document stops being used from the effective date.">
            <Select id="reg-sup" value={form.supersedes} onChange={set('supersedes')}>
              <option value="">Nothing — a new document</option>
              {documents.map((d) => <option key={d.source_document} value={d.source_document}>{d.source_document}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="File" htmlFor="reg-file">
          <input id="reg-file" type="file" accept=".md,.txt,text/markdown,text/plain" onChange={readFile}
            className="block w-full text-sm text-ink-2 file:mr-3 file:rounded-md file:border-0 file:bg-surface-3 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink" />
        </Field>
        <Field label="Text" htmlFor="reg-text">
          <Textarea id="reg-text" className="min-h-[180px] font-mono text-xs" value={text} maxLength={200000} onChange={(e) => { setText(e.target.value); setFilename(null); }}
            placeholder={'### Clause 4.1: Peak Energy Charges\nConsumption during the peak window (18:30 to 22:30 hours) shall be billed at LKR 58.00 per kWh.'} />
        </Field>

        {/* Real-time Pre-Ingestion Screening Sandbox */}
        {text.trim() && (
          <div className="rounded-xl border border-line bg-surface-2 p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-2">Pre-Ingestion Screening Sandbox</span>
              <span className="text-[11px] text-ink-3">Live Validation</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div className="rounded-lg border border-line bg-surface p-2.5">
                <span className="block text-[11px] text-ink-3">Clauses Detected</span>
                <span className={`text-sm font-semibold tabular ${screening.clauses > 0 ? 'text-ink' : 'text-amber-700 dark:text-amber-400'}`}>
                  {screening.clauses} clause{screening.clauses !== 1 ? 's' : ''}
                </span>
                {screening.clauses === 0 && (
                  <span className="block text-[10px] text-ink-3 mt-0.5">Prefix sections with ### Clause</span>
                )}
              </div>
              <div className="rounded-lg border border-line bg-surface p-2.5">
                <span className="block text-[11px] text-ink-3">Injection Screening</span>
                <span className={`text-sm font-semibold flex items-center gap-1 ${screening.flags.length === 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-critical-text'}`}>
                  {screening.flags.length === 0 ? (
                    <>
                      <ShieldCheck className="h-3.5 w-3.5" /> Clean (0 flags)
                    </>
                  ) : (
                    <>
                      <ShieldAlert className="h-3.5 w-3.5" /> {screening.flags.length} Flag{screening.flags.length !== 1 ? 's' : ''}
                    </>
                  )}
                </span>
                {screening.flags.length > 0 && (
                  <span className="block text-[10px] text-critical-text mt-0.5">{screening.flags.join(', ')}</span>
                )}
              </div>
              <div className="rounded-lg border border-line bg-surface p-2.5">
                <span className="block text-[11px] text-ink-3">Live Content Hash</span>
                <span className="font-mono text-[11px] text-ink truncate block">
                  {screening.sha256 ? `${screening.sha256.slice(0, 14)}...` : 'Computing...'}
                </span>
                <span className="block text-[10px] text-ink-3 mt-0.5">SHA-256 Digest</span>
              </div>
            </div>
          </div>
        )}

        <Button type="submit" icon={FilePlus2} loading={busy}>Submit for review</Button>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Review queue (checker)
// ---------------------------------------------------------------------------

function ReviewQueue({ onReviewed }) {
  const { can } = useAuth();
  const [status, setStatus] = useState('pending');
  const list = useAsync(() => api.regulationSubmissions(status === 'all' ? undefined : status), [status]);
  const [open, setOpen] = useState(null);
  const rows = list.data || [];

  return (
    <Card title="Submissions" description="Quarantined documents are screened but not searchable until approved."
      actions={<Tabs label="Status" value={status} onChange={setStatus} tabs={[
        { value: 'pending', label: 'Waiting' }, { value: 'approved', label: 'Approved' }, { value: 'rejected', label: 'Rejected' }, { value: 'all', label: 'All' },
      ]} />} bodyClassName="p-0">
      {list.error ? <div className="p-4"><ErrorPanel error={list.error} onRetry={list.reload} /></div>
        : list.loading && !list.data ? <LoadingBlock />
          : !rows.length ? <EmptyState icon={ShieldCheck} title={status === 'pending' ? 'Nothing waiting for review.' : 'No submissions.'} />
            : (
              <ul className="divide-y divide-line">
                {rows.map((s) => (
                  <li key={s.submission_id}>
                    <button type="button" onClick={() => setOpen(s.submission_id)} className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left hover:bg-surface-2">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-ink">#{s.submission_id} {s.title}</span>
                        <span className="block text-xs text-ink-2">
                          {s.publisher} · {s.reference} · effective {formatDate(s.effective_date)} · {s.screening?.clauses_accepted} clause(s)
                          {s.supersedes ? ` · replaces “${s.supersedes}”` : ''}
                        </span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2 text-xs text-ink-2">
                        {s.submitted_by} · {formatDateTime(s.submitted_at)} <StatusPill status={s.status} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
      <SubmissionDialog id={open} canReview={can('rag:review')} onClose={() => setOpen(null)} onReviewed={() => { setOpen(null); list.reload(); onReviewed(); }} />
    </Card>
  );
}

function SubmissionDialog({ id, canReview, onClose, onReviewed }) {
  const { user } = useAuth();
  const { notify } = useToast();
  const detail = useAsync(() => (id ? api.regulationSubmission(id) : Promise.resolve(null)), [id]);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const s = detail.data;
  const own = s && s.submitted_by === user.user_id;

  async function decide(approved) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.reviewRegulation(id, { approved, notes: notes.trim() || undefined });
      notify(approved ? `#${id} approved and indexed` : `#${id} rejected`, {
        tone: approved ? 'success' : 'info',
        detail: approved ? `${res.ingestion?.clauses_added ?? 0} clause(s) are now searchable from ${formatDate(res.effective_date)}.` : undefined,
      });
      setNotes('');
      onReviewed();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={Boolean(id)} title={s ? `Submission #${s.submission_id}` : 'Submission'} onClose={onClose} size="lg">
      {detail.error ? <ErrorPanel error={detail.error} /> : !s ? <LoadingBlock /> : (
        <div className="space-y-4 text-sm">
          <div className="space-y-1 text-ink-2">
            <p className="text-base font-semibold text-ink">{s.title}</p>
            <p>{s.publisher_name} · {s.reference} · effective {formatDate(s.effective_date)}</p>
            {s.source_url && <p>Source: <a className="text-accent-text underline" href={s.source_url} target="_blank" rel="noreferrer noopener">{s.source_url}</a></p>}
            {s.supersedes && <p>Replaces “{s.supersedes}” from the effective date.</p>}
            <p>Submitted by {s.submitted_by} · {formatDateTime(s.submitted_at)} · SHA-256 <span className="font-mono text-xs">{s.sha256?.slice(0, 16)}…</span></p>
          </div>
          <Banner tone="success" icon={CheckCircle2} title={`${s.screening.clauses_accepted} of ${s.screening.clauses_parsed} clause(s) passed screening`}>
            {s.screening.already_indexed > 0 && <p>{s.screening.already_indexed} already in the library and will be skipped.</p>}
          </Banner>
          {s.screening.rejected_clauses?.length > 0 && (
            <Banner tone="warning" icon={ShieldAlert} title={`${s.screening.rejected_clauses.length} clause(s) quarantined and will not be indexed`}>
              <ul className="list-disc pl-5">{s.screening.rejected_clauses.map((r) => <li key={r.clause_reference}>{r.clause_reference} — {r.reason}</li>)}</ul>
            </Banner>
          )}
          <div className="max-h-64 space-y-2 overflow-y-auto rounded-lg border border-line p-3">
            {s.screening.clauses.map((c) => (
              <div key={c.clause_reference}>
                <p className="font-medium text-ink">{c.clause_reference}{c.section_title ? ` — ${c.section_title}` : ''}</p>
                <p className="whitespace-pre-wrap text-ink-2">{c.content}</p>
              </div>
            ))}
          </div>
          {s.review ? (
            <Banner tone={s.status === 'approved' ? 'success' : 'neutral'} title={`${s.status === 'approved' ? 'Approved' : 'Rejected'} by ${s.review.reviewed_by} · ${formatDateTime(s.review.reviewed_at)}`}>
              {s.review.notes && <p>“{s.review.notes}”</p>}
            </Banner>
          ) : !canReview ? (
            <p className="text-ink-2">Waiting for a facility manager or the energy auditor to review it.</p>
          ) : own ? (
            <Badge tone="neutral">You submitted this, so someone else must review it.</Badge>
          ) : (
            <div className="space-y-3">
              {error && <ErrorPanel error={error} />}
              <p className="text-ink-2">Check the figures against the publisher’s own copy before approving: once approved, they can change the tariff every new plan uses.</p>
              <Field label="Notes" htmlFor="rev-notes" hint="Required when rejecting.">
                <Textarea id="rev-notes" value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} />
              </Field>
              <div className="flex flex-wrap gap-2">
                <Button icon={ThumbsUp} loading={busy} onClick={() => decide(true)}>Approve and index</Button>
                <Button variant="secondary" icon={ThumbsDown} disabled={!notes.trim() || busy} onClick={() => decide(false)}>Reject</Button>
              </div>
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
}
