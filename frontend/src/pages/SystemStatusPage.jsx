import React from 'react';
import { CheckCircle2, TriangleAlert } from 'lucide-react';
import { api } from '../api/client';
import { useAsync } from '../lib/hooks';
import { Badge, Card, ErrorPanel, KeyValue, LoadingBlock, PageHeader } from '../components/ui';

const SLICE_LABELS = {
  agent1_telemetry: 'Forecast (Agent 1)',
  agent2_digital_twin: 'Comfort check (Agent 2)',
  agent3_policy_rag: 'Regulations (Agent 3)',
  agent4_dispatch: 'Plan & explanation (Agent 4)',
};
const PROVIDER_LABELS = {
  llm_provider: 'Language model', embedding_provider: 'Embeddings', vector_store: 'Vector store',
  cache_provider: 'Cache', database_provider: 'Database', reranker: 'Result fusion',
};

export default function SystemStatusPage() {
  const { data, error, loading, reload } = useAsync(() => api.health(), []);
  return (
    <div>
      <PageHeader title="System status" description="Which components are live. Useful before a demo or when results look unusual." />
      {error && <ErrorPanel error={error} onRetry={reload} />}
      {loading && !data ? <LoadingBlock /> : data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Agents">
            <ul className="divide-y divide-line">
              {Object.entries(data.agent_slices || {}).map(([key, value]) => (
                <li key={key} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="text-ink">{SLICE_LABELS[key] || key}</span>
                  {value === 'reference_baseline_auto'
                    ? <Badge tone="warning" icon={TriangleAlert} title="The team's code for this agent is not finished yet, so the reference model is used automatically.">Reference model (team code not finished)</Badge>
                    : value === 'reference_baseline'
                      ? <Badge tone="warning" icon={TriangleAlert} title="Chosen in the configuration (REFERENCE_BASELINE_AGENTS).">Reference model (by configuration)</Badge>
                      : <Badge tone="good" icon={CheckCircle2}>Team implementation</Badge>}
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Providers" description={`${data.system} v${data.version} · ${data.status}`}>
            <KeyValue items={[
              ...Object.entries(data.active_providers || {}).map(([k, v]) => ({ label: PROVIDER_LABELS[k] || k, value: v })),
              { label: 'Semantic search', value: data.dense_search_enabled ? 'On' : 'Off — keyword matching only' },
            ]} />
          </Card>
        </div>
      )}
    </div>
  );
}
