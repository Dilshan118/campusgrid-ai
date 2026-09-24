import React from 'react';
import { BarChart3, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { useAsync } from '../lib/hooks';
import { formatNumber, formatPct, INTENT_LABELS } from '../lib/format';
import { HorizontalBars, DataTable } from '../components/charts';
import { Banner, Button, Card, EmptyState, ErrorPanel, LoadingBlock, PageHeader, StatTile } from '../components/ui';

const STAGE_LABELS = {
  '1_recommendation_shown': 'Recommendation shown',
  '2_explanation_opened': 'Explanation opened',
  '3_citation_clicked': 'Citation clicked',
  '4_decision_made': 'Decision made',
};
const VARIANT_LABELS = { A_concise_summary: 'A · Concise summary first', B_cited_explanation: 'B · Cited explanation first' };
const pct = (v) => (v === null || v === undefined ? '—' : formatPct(v * 100, 0));

export default function AnalyticsPage() {
  const { data, error, loading, reload } = useAsync(() => api.analyticsSummary(), []);

  return (
    <div>
      <PageHeader title="Analytics" description="How people use CampusGrid: whether plans are acted on, which explanation style earns trust, what people ask about, and whether the sources are useful."
        actions={<Button variant="secondary" icon={RefreshCw} onClick={reload} loading={loading && Boolean(data)}>Refresh</Button>} />
      {error && <ErrorPanel error={error} onRetry={reload} />}
      {loading && !data ? <LoadingBlock /> : data && (
        <div className={loading ? 'space-y-6 opacity-60' : 'space-y-6'}>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label="Questions logged" value={formatNumber(data.total_queries_logged)} sub={data.top_intent_cluster ? `Most common: ${INTENT_LABELS[data.top_intent_cluster] || data.top_intent_cluster}` : undefined} />
            <StatTile label="Plans decided after being shown" value={pct(data.funnel_decision_rate)} />
            <StatTile label="Approval rate of decided plans" value={pct(data.approval_rate_of_decided)} />
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <FunnelPanel funnel={data.acceptance_funnel} />
            <AbPanel ab={data.ab_test} />
            <ClustersPanel clusters={data.query_clusters} />
            <CitationPanel ctr={data.citation_click_through} />
          </div>
        </div>
      )}
    </div>
  );
}

function FunnelPanel({ funnel }) {
  const shown = funnel.stages[0]?.count || 0;
  return (
    <Card title="Acceptance funnel" description="Do people act on plans, and do they read why?">
      {shown === 0 ? <EmptyState icon={BarChart3} title="No plans have been shown yet." /> : (
        <div className="space-y-4">
          <HorizontalBars
            title="Plans reaching each step"
            summary={`${funnel.approved} approved and ${funnel.rejected} rejected out of ${shown} shown.`}
            data={funnel.stages.map((s) => ({ label: STAGE_LABELS[s.stage] || s.stage, value: s.count }))}
            valueLabel="Plans"
          />
          {funnel.decided_without_opening_explanation > 0 && (
            <Banner tone="neutral">{funnel.decided_without_opening_explanation} plan{funnel.decided_without_opening_explanation > 1 ? 's were' : ' was'} decided without anyone opening the explanation.</Banner>
          )}
        </div>
      )}
    </Card>
  );
}

function AbPanel({ ab }) {
  const rows = Object.entries(ab.variants).map(([variant, v]) => ({ variant: VARIANT_LABELS[variant] || variant, ...v }));
  const [a, b] = Object.values(ab.variants);
  const decidedA = a.approved + a.rejected;
  const decidedB = b.approved + b.rejected;
  let verdict;
  if (!ab.sufficient_sample) {
    verdict = <Banner tone="neutral" title="Not enough data yet">A result needs {ab.min_decisions_per_variant} decisions per variant (now {decidedA} and {decidedB}). Until then, neither style is better.</Banner>;
  } else if (ab.significant_at_0_05) {
    const higher = (a.approval_rate ?? 0) > (b.approval_rate ?? 0) ? rows[0].variant : rows[1].variant;
    verdict = <Banner tone="success" title="Statistically significant difference">{higher} has the higher approval rate (p = {ab.p_value}).</Banner>;
  } else {
    verdict = <Banner tone="neutral" title="No significant difference">p = {ab.p_value} — the approval rates are not reliably different.</Banner>;
  }
  return (
    <Card title="Explanation A/B test" description={ab.hypothesis}>
      <div className="space-y-4">
        <DataTable caption="A/B test results" columns={[
          { key: 'variant', label: 'Variant' },
          { key: 'recommendations_shown', label: 'Shown', numeric: true },
          { key: 'approved', label: 'Approved', numeric: true },
          { key: 'rejected', label: 'Rejected', numeric: true },
          { key: 'approval_rate', label: 'Approval rate', numeric: true, format: pct },
        ]} rows={rows} />
        <p className="text-xs text-ink-2">Two-proportion z-test: z = {ab.z_statistic ?? '—'}, p = {ab.p_value ?? '—'}. Each user always sees the same variant.</p>
        {verdict}
      </div>
    </Card>
  );
}

function ClustersPanel({ clusters }) {
  if (!clusters.clusters.length) return <Card title="What people ask about"><EmptyState icon={BarChart3} title="No questions yet." /></Card>;
  return (
    <Card title="What people ask about" description="Questions grouped by what the system understood them to be.">
      <div className="space-y-5">
        <HorizontalBars
          title="Questions per intent"
          summary={`${clusters.total_queries} questions in ${clusters.clusters.length} groups.`}
          data={clusters.clusters.map((c) => ({ label: INTENT_LABELS[c.intent] || c.intent, value: c.query_count }))}
          valueLabel="Questions"
        />
        <ul className="space-y-3 text-sm">
          {clusters.clusters.map((c) => (
            <li key={c.intent}>
              <p className="font-medium text-ink">{INTENT_LABELS[c.intent] || c.intent} <span className="font-normal text-ink-2">· {pct(c.share)}</span></p>
              {c.top_keywords.length > 0 && <p className="text-ink-2">Keywords: {c.top_keywords.join(', ')}</p>}
              {c.example_queries[0] && <p className="truncate text-ink-3" title={c.example_queries[0]}>e.g. “{c.example_queries[c.example_queries.length - 1]}”</p>}
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function CitationPanel({ ctr }) {
  const ranks = Object.entries(ctr.clicks_by_rank || {}).map(([rank, count]) => ({ label: `Rank ${rank}`, value: count }));
  return (
    <Card title="Citation usefulness" description="When people open a source, is it the first one listed?">
      {ctr.result_sets_with_clicks === 0 ? <EmptyState icon={BarChart3} title="No citations opened yet." /> : (
        <div className="space-y-4">
          <StatTile label="Mean reciprocal rank of the first click" value={formatNumber(ctr.mean_reciprocal_rank, 2)}
            sub={`1.00 means people always open the top source first · ${ctr.result_sets_with_clicks} result lists`} />
          <HorizontalBars title="Clicks by position" data={ranks} valueLabel="Clicks" />
        </div>
      )}
    </Card>
  );
}
