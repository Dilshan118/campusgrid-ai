import React, { useState } from 'react';
import { FilePlus2, Library, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useAsync, useDraft } from '../lib/hooks';
import { formatNumber } from '../lib/format';
import {
  Banner, Button, Card, ConfirmDialog, EmptyState, ErrorPanel, Field, LoadingBlock, PageHeader, TextInput, Textarea,
} from '../components/ui';
import { useToast } from '../components/feedback';

export default function LibraryPage() {
  const { can } = useAuth();
  const library = useAsync(() => api.regulationLibrary(), []);
  const docs = library.data?.documents || [];

  return (
    <div>
      <PageHeader title="Regulation library" description="The documents CampusGrid searches. Every tariff figure in a plan comes from a clause in this library, or is marked as a reference value." />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <Card title="Indexed documents" description={library.data ? `${formatNumber(library.data.total_clauses)} clauses in ${docs.length} documents` : undefined}>
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
        {can('rag:ingest') ? <UploadPanel onChanged={library.reload} /> : (
          <Card title="Adding documents"><p className="text-sm text-ink-2">Only facility managers can add or re-index regulations, because a document can change the tariff the solver uses.</p></Card>
        )}
      </div>
    </div>
  );
}

function IngestResult({ result }) {
  if (!result) return null;
  const data = result.data || {};
  const added = data.clauses_added ?? data.total_clauses_ingested ?? 0;
  const skipped = data.duplicates_skipped || 0;
  const rejected = data.rejected_clauses || [];
  return (
    <div className="space-y-3" aria-live="polite">
      <Banner tone={added ? 'success' : 'neutral'} title={`${added} clause${added === 1 ? '' : 's'} added.`}>
        {skipped > 0 && <p>{skipped} clause{skipped === 1 ? ' was' : 's were'} already in the library and {skipped === 1 ? 'was' : 'were'} skipped.</p>}
        {!added && !skipped && !rejected.length && <p>{result.error || 'No clauses could be read. Use “### Clause 4.1: Title” headings.'}</p>}
      </Banner>
      {rejected.length > 0 && (
        <Banner tone="warning" icon={ShieldAlert} title={`${rejected.length} clause${rejected.length === 1 ? ' was' : 's were'} quarantined and not added`}>
          <ul className="list-disc space-y-1 pl-5">
            {rejected.map((r) => <li key={`${r.source_document}-${r.clause_reference}`}><span className="font-medium text-ink">{r.clause_reference}</span> — {r.reason}</li>)}
          </ul>
          <p className="mt-2">Quarantine protects the planner from poisoned or mistyped documents. Fix the source text and add it again.</p>
        </Banner>
      )}
    </div>
  );
}

function UploadPanel({ onChanged }) {
  const { notify } = useToast();
  const [title, setTitle] = useState('');
  const [effective, setEffective] = useState('');
  const [text, setText, clearText] = useDraft('library-upload');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [confirmReindex, setConfirmReindex] = useState(false);

  async function send(payload) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.ingestRegulation(payload);
      setResult(response);
      const added = response.data?.clauses_added ?? response.data?.total_clauses_ingested ?? 0;
      const rejected = response.data?.rejected_clauses?.length || 0;
      notify(added ? `${added} clause${added === 1 ? '' : 's'} added to the library` : 'Nothing new was added',
        { tone: rejected ? 'warning' : added ? 'success' : 'info', detail: rejected ? `${rejected} quarantined — see the details below.` : undefined });
      if (payload.text && response.data?.clauses_added) { clearText(); setTitle(''); }
      onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      setConfirmReindex(false);
    }
  }

  function submit(e) {
    e.preventDefault();
    if (!title.trim() || !text.trim()) { setError({ code: 'VALIDATION_ERROR', message: 'Add a document title and the regulation text.' }); return; }
    if (effective && !/^\d{4}-\d{2}-\d{2}$/.test(effective)) { setError({ code: 'VALIDATION_ERROR', message: 'Effective date must be YYYY-MM-DD.' }); return; }
    send({ text, source_document: title.trim(), effective_date: effective || undefined });
  }

  return (
    <Card title="Add a regulation" description="Paste text or Markdown. Each “### Clause x.y: Title” heading becomes one searchable clause."
      actions={<Button variant="secondary" size="sm" icon={RefreshCw} onClick={() => setConfirmReindex(true)}>Re-index library</Button>}>
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorPanel error={error} />}
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_11rem]">
          <Field label="Document title" htmlFor="doc-title"><TextInput id="doc-title" maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="PUCSL Tariff Revision 2026" /></Field>
          <Field label="Effective date" htmlFor="doc-date"><TextInput id="doc-date" type="date" value={effective} onChange={(e) => setEffective(e.target.value)} /></Field>
        </div>
        <Field label="Text" htmlFor="doc-text" hint="PDF / TXT file upload is planned; for now, files go in the corpus folder and are picked up by “Re-index library”.">
          <Textarea id="doc-text" className="min-h-[200px] font-mono text-xs" value={text} maxLength={200000} onChange={(e) => setText(e.target.value)}
            placeholder={'### Clause 4.1: Peak Energy Charges\nConsumption during the peak window (18:00 to 22:30 hours) shall be billed at LKR 58.00 per kWh.'} />
        </Field>
        <Button type="submit" icon={FilePlus2} loading={busy}>Add to library</Button>
        <IngestResult result={result} />
      </form>
      <ConfirmDialog open={confirmReindex} busy={busy} title="Re-index the library?" confirmLabel="Re-index"
        onCancel={() => setConfirmReindex(false)} onConfirm={() => send({})}>
        Re-indexing re-reads every file in the corpus folder. Clauses already present are skipped.
      </ConfirmDialog>
    </Card>
  );
}
