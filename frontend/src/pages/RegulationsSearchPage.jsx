import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, Check, Copy, ExternalLink, FileText, Search, ShieldAlert, ShieldCheck, Sparkles } from 'lucide-react';
import { api } from '../api/client';
import { analytics } from '../lib/analytics';
import { sessionStore } from '../lib/storage';
import { buildPath, navigate } from '../lib/router';
import { formatDate } from '../lib/format';
import { useSystem } from '../components/Layout';
import { ClauseCard } from '../components/plan';
import { Badge, Button, Chip, Drawer, EmptyState, ErrorPanel, PageHeader, Select, TextInput } from '../components/ui';

const EXAMPLES = ['GP-2 peak rate', 'Maximum demand charge per kVA', 'Clause 6.3', 'How low can precooling go?', 'Net metering and solar'];

function searchSessionId() {
  let id = sessionStore.get('cg-search-session');
  if (!id) {
    id = (window.crypto?.randomUUID?.() || `s-${Date.now()}`).slice(0, 36);
    sessionStore.set('cg-search-session', id);
  }
  return id;
}

/** Wraps query words in <mark> using React elements (never innerHTML). */
function highlighter(query) {
  const words = Array.from(new Set(query.toLowerCase().match(/[a-z0-9.\-]{3,}/g) || []));
  if (!words.length) return null;
  const pattern = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
  return (text) => text.split(pattern).map((part, i) => (
    i % 2 === 1 ? <mark key={i} className="rounded bg-warn-soft px-0.5 text-ink">{part}</mark> : <React.Fragment key={i}>{part}</React.Fragment>
  ));
}

function extractParameters(content = '') {
  const params = [];
  const peakMatch = content.match(/peak\s*(?:window|hours?|rate)?.*?LKR\s*([0-9.,]+)/i);
  if (peakMatch) params.push({ label: 'Peak Energy Rate', value: `LKR ${peakMatch[1]} / kWh`, tone: 'critical' });

  const dayMatch = content.match(/day(?:-time)?\s*(?:energy|rate)?.*?LKR\s*([0-9.,]+)/i);
  if (dayMatch) params.push({ label: 'Day Energy Rate', value: `LKR ${dayMatch[1]} / kWh`, tone: 'info' });

  const offPeakMatch = content.match(/off-peak\s*(?:energy|rate)?.*?LKR\s*([0-9.,]+)/i);
  if (offPeakMatch) params.push({ label: 'Off-Peak Rate', value: `LKR ${offPeakMatch[1]} / kWh`, tone: 'success' });

  const demandMatch = content.match(/(?:maximum\s*demand|demand\s*charge).*?LKR\s*([0-9.,]+)(?:\s*per\s*kVA)?/i);
  if (demandMatch) params.push({ label: 'Demand Surcharge', value: `LKR ${demandMatch[1]} / kVA`, tone: 'warn' });

  const tempMatch = content.match(/([0-9.]+\s*°C\s*(?:and|to|-)\s*[0-9.]+\s*°C)/i);
  if (tempMatch) params.push({ label: 'Operative Envelope', value: tempMatch[1], tone: 'info' });

  const precoolMatch = content.match(/precooling.*?([0-9.]+\s*°C)/i);
  if (precoolMatch) params.push({ label: 'Precooling Min Bound', value: precoolMatch[1], tone: 'warn' });

  return params;
}

function CopyableHash({ label, hash }) {
  const [copied, setCopied] = useState(false);
  if (!hash) return null;
  const copy = () => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs">
      <div className="min-w-0 flex-1">
        <span className="font-semibold text-ink-2">{label}: </span>
        <code className="font-mono text-ink text-[11px] break-all">{hash}</code>
      </div>
      <button
        type="button"
        onClick={copy}
        title={`Copy ${label}`}
        className="inline-flex items-center gap-1 rounded border border-line bg-surface px-2.5 py-1 text-[11px] font-medium text-ink hover:bg-surface-3 transition-colors"
      >
        {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3 text-ink-2" />}
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  );
}

function ClauseDetailDrawer({ citation, open, onClose, highlight }) {
  if (!citation) return null;
  const isVerified = citation.provenance_status === 'verified_official';
  const params = extractParameters(citation.content);

  const handleAskAI = () => {
    const q = `How does ${citation.section_clause || citation.document_title} impact microgrid dispatch?`;
    navigate(buildPath('/ask', { q }));
    onClose();
  };

  return (
    <Drawer open={open} title={citation.section_clause || 'Clause Details'} onClose={onClose}>
      <div className="space-y-5 text-sm">
        {/* Provenance Status Card */}
        <div className={`rounded-xl border p-4 ${isVerified ? 'border-emerald-200 bg-emerald-50/70 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200' : 'border-amber-200 bg-amber-50/70 text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200'}`}>
          <div className="flex items-start gap-3">
            {isVerified ? (
              <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
            ) : (
              <ShieldAlert className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
            )}
            <div>
              <h4 className="font-semibold text-base">
                {isVerified ? 'Verified Official Legal Document' : 'Unverified Simulation Reference'}
              </h4>
              <p className="mt-1 text-xs leading-relaxed opacity-90">
                {isVerified
                  ? 'Cryptographically authenticated against official PUCSL regulatory schedules. The MILP solver uses verified rates to calculate day-ahead costs.'
                  : 'Document is in quarantine or classified as an unverified educational reference fixture. It will not override statutory billing rates without administrative review.'}
              </p>
            </div>
          </div>
        </div>

        {/* Extracted Parameters */}
        {params.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-2 mb-2">Detected Parameters</h4>
            <div className="grid grid-cols-2 gap-2">
              {params.map((p) => (
                <div key={p.label} className="rounded-lg border border-line bg-surface p-2.5">
                  <span className="block text-[11px] text-ink-3">{p.label}</span>
                  <span className="font-semibold text-ink text-sm tabular">{p.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Clause Content */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-2 mb-2">Full Statutory Text</h4>
          <div className="rounded-xl border border-line bg-surface p-4 leading-relaxed text-ink font-serif text-sm">
            {highlight ? highlight(citation.content) : citation.content}
          </div>
        </div>

        {/* Cryptographic Provenance */}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-2 mb-2">Cryptographic Provenance</h4>
          <div className="space-y-2">
            <CopyableHash label="Content SHA-256" hash={citation.content_sha256} />
            <CopyableHash label="Source SHA-256" hash={citation.source_sha256} />
            {citation.effective_date && (
              <div className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-ink-2">
                <span className="font-semibold">Effective Date: </span>
                <span className="text-ink">{formatDate(citation.effective_date)}</span>
              </div>
            )}
            {citation.source_uri && (
              <a
                href={citation.source_uri}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-text hover:underline pt-1"
              >
                <ExternalLink className="h-3.5 w-3.5" /> View original publication source
              </a>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="border-t border-line pt-4 flex flex-wrap gap-2">
          <Button variant="primary" icon={Sparkles} onClick={handleAskAI}>
            Ask AI about this clause
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Drawer>
  );
}

export default function RegulationsSearchPage({ query }) {
  const { health } = useSystem();
  const [text, setText] = useState(query.q || '');
  const [topK, setTopK] = useState(3);
  const [state, setState] = useState({ loading: false, error: null, results: null, searched: '' });
  const [drawerClause, setDrawerClause] = useState(null);
  const sessionId = useMemo(searchSessionId, []);

  async function search(q = text) {
    const trimmed = q.trim();
    if (trimmed.length < 2) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await api.searchRegulations(trimmed, topK, sessionId);
      setState({ loading: false, error: null, results: data.citations || [], searched: trimmed });
      if (trimmed !== query.q) navigate(buildPath('/regulations', { q: trimmed }), { replace: true });
    } catch (error) {
      setState((s) => ({ ...s, loading: false, error }));
    }
  }

  useEffect(() => { if (query.q) { setText(query.q); search(query.q); } }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const highlight = useMemo(() => highlighter(state.searched), [state.searched]);

  const handleOpenDrawer = (citation, rank) => {
    analytics.searchResultClicked(rank, state.searched, sessionId);
    setDrawerClause(citation);
  };

  return (
    <div>
      <PageHeader title="Regulation search" description="Search the PUCSL tariff schedules and ASHRAE-55 comfort standard. Results combine meaning-based and keyword search." />
      <form onSubmit={(e) => { e.preventDefault(); search(); }} className="mb-3 flex flex-wrap gap-2">
        <label htmlFor="reg-q" className="sr-only">Search regulations</label>
        <TextInput id="reg-q" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} placeholder="For example: What is the peak tariff rate?" className="min-w-[16rem] flex-1" />
        <label htmlFor="reg-k" className="sr-only">Number of results</label>
        <Select id="reg-k" value={topK} onChange={(e) => setTopK(Number(e.target.value))} className="w-auto">
          {[1, 2, 3, 4, 5].map((k) => <option key={k} value={k}>{k} result{k > 1 ? 's' : ''}</option>)}
        </Select>
        <Button type="submit" icon={Search} loading={state.loading}>Search</Button>
      </form>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        {health?.dense_search_enabled === false && <Badge tone="neutral">Keyword matching only</Badge>}
        {EXAMPLES.map((ex) => <Chip key={ex} onClick={() => { setText(ex); search(ex); }}>{ex}</Chip>)}
      </div>

      {state.error && <ErrorPanel error={state.error} onRetry={() => search()} />}
      {state.results && state.results.length === 0 && (
        <EmptyState icon={BookOpen} title="No matching clause.">Try the clause number (for example “Clause 6.3”) or simpler words.</EmptyState>
      )}
      {state.results && state.results.length > 0 && (
        <ol className={state.loading ? 'space-y-3 opacity-60' : 'space-y-3'} aria-label="Search results">
          {state.results.map((c, i) => (
            <li key={`${c.document_title}-${c.section_clause}`}>
              <div>
                <ClauseCard citation={c} rank={i + 1} highlight={highlight} onOpen={() => handleOpenDrawer(c, i + 1)} />
              </div>
              <div className="mt-1 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleOpenDrawer(c, i + 1)}
                  className="inline-flex items-center gap-1 text-sm font-medium text-accent-text hover:underline"
                >
                  <FileText className="h-3.5 w-3.5" /> Inspect full clause & cryptographic provenance
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}

      {/* Slide-Out Provenance & Detail Drawer */}
      <ClauseDetailDrawer
        citation={drawerClause}
        open={Boolean(drawerClause)}
        onClose={() => setDrawerClause(null)}
        highlight={highlight}
      />
    </div>
  );
}
