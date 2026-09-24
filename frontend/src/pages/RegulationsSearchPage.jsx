import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, Search } from 'lucide-react';
import { api } from '../api/client';
import { analytics } from '../lib/analytics';
import { sessionStore } from '../lib/storage';
import { buildPath, navigate } from '../lib/router';
import { useSystem } from '../components/Layout';
import { ClauseCard } from '../components/plan';
import { Badge, Button, Chip, EmptyState, ErrorPanel, PageHeader, Select, TextInput } from '../components/ui';

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

export default function RegulationsSearchPage({ query }) {
  const { health } = useSystem();
  const [text, setText] = useState(query.q || '');
  const [topK, setTopK] = useState(3);
  const [state, setState] = useState({ loading: false, error: null, results: null, searched: '' });
  const [expanded, setExpanded] = useState(null);
  const sessionId = useMemo(searchSessionId, []);

  async function search(q = text) {
    const trimmed = q.trim();
    if (trimmed.length < 2) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    setExpanded(null);
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

  const open = (citation, rank) => {
    if (expanded !== rank) analytics.searchResultClicked(rank, state.searched, sessionId);
    setExpanded(expanded === rank ? null : rank);
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
              <div className={expanded === i + 1 ? '' : '[&_article>p:last-of-type]:line-clamp-3'}>
                <ClauseCard citation={c} rank={i + 1} highlight={highlight} />
              </div>
              <button type="button" onClick={() => open(c, i + 1)} aria-expanded={expanded === i + 1}
                className="mt-1 text-sm font-medium text-accent-text hover:underline">
                {expanded === i + 1 ? 'Show less' : 'Read the full clause'}
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
