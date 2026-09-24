import React, { useState } from 'react';
import { BookOpen, Search, PlusCircle, CheckCircle2, FileText, Scale } from 'lucide-react';
import api from '../api/client';

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState('PUCSL peak tariff hours and maximum demand penalty');
  const [topK, setTopK] = useState(3);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  // Ingestion form state
  const [showIngest, setShowIngest] = useState(false);
  const [ingestDoc, setIngestDoc] = useState('PUCSL Industrial Schedule I-2');
  const [ingestText, setIngestText] = useState(
    '### Clause 5.1: Off-Peak Water Pumping Incentive\nIndustrial institutions pumping water to overhead reservoirs between 23:00 and 05:00 hours qualify for a 5% rebate on off-peak energy consumption.'
  );
  const [ingestStatus, setIngestStatus] = useState(null);

  async function handleSearch(e) {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const resp = await api.searchRAG(query, topK);
      if (resp.data && resp.data.success) {
        setResults(resp.data.data);
      } else {
        setError(resp.data?.error || 'Search failed');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Error searching knowledge base');
    } finally {
      setLoading(false);
    }
  }

  async function handleIngest(e) {
    e.preventDefault();
    if (!ingestText.trim()) return;

    setIngestStatus('ingesting');
    try {
      const resp = await api.ingestDocument(ingestText, ingestDoc);
      if (resp.data && resp.data.success) {
        setIngestStatus('success');
        setIngestText('');
      } else {
        setIngestStatus('error');
      }
    } catch (err) {
      setIngestStatus('error');
    }
  }

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <Scale className="w-5 h-5 text-amber-400" />
              Hybrid Regulatory Knowledge Base (Agent 3 RAG)
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Dense vector embeddings fused with Okapi BM25 keyword search (Reciprocal Rank Fusion k=60) across CEB/PUCSL electricity tariffs and ASHRAE standards.
            </p>
          </div>

          <button
            onClick={() => setShowIngest(!showIngest)}
            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <PlusCircle className="w-3.5 h-3.5 text-emerald-400" />
            {showIngest ? 'Hide Ingestion Form' : 'Ingest Document'}
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search regulations (e.g. peak energy charges, precooling comfort envelope)..."
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition-colors"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium px-5 py-2.5 rounded-lg text-sm flex items-center gap-2 transition-colors"
          >
            <Search className="w-4 h-4" />
            {loading ? 'Searching...' : 'Hybrid Search'}
          </button>
        </form>
      </div>

      {/* Ingestion Panel */}
      {showIngest && (
        <div className="bg-slate-900/80 border border-emerald-900/50 rounded-xl p-6 space-y-4">
          <h3 className="text-sm font-semibold text-emerald-400 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Ingest Regulatory Clause or Standard
          </h3>
          <form onSubmit={handleIngest} className="space-y-3">
            <div>
              <label className="text-xs text-slate-400">Source Document Title</label>
              <input
                type="text"
                value={ingestDoc}
                onChange={(e) => setIngestDoc(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 mt-1"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400">Markdown Content (Clauses)</label>
              <textarea
                rows={4}
                value={ingestText}
                onChange={(e) => setIngestText(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 mt-1 font-mono"
              />
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400">Automatically chunks, embeds, and updates BM25 indices</span>
              <button
                type="submit"
                disabled={ingestStatus === 'ingesting'}
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors"
              >
                {ingestStatus === 'ingesting' ? 'Ingesting...' : 'Add to Vector Store'}
              </button>
            </div>
            {ingestStatus === 'success' && (
              <p className="text-xs text-emerald-400 flex items-center gap-1 mt-2">
                <CheckCircle2 className="w-4 h-4" /> Document ingested and indexed successfully.
              </p>
            )}
          </form>
        </div>
      )}

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 rounded-xl p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {/* Search Results List */}
      {results && (
        <div className="space-y-3">
          <div className="flex justify-between items-center px-1 text-xs text-slate-400">
            <span>
              Retrieved <strong>{results.citations?.length || 0}</strong> verified legal clauses
            </span>
            <span>Retrieval Algorithm: Hybrid Dense + Okapi BM25 (RRF k=60)</span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {results.citations?.map((item, idx) => (
              <div key={idx} className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="text-xs font-bold text-amber-400">{item.document_title}</span>
                    <h4 className="text-sm font-semibold text-slate-200 mt-0.5">{item.section_clause}</h4>
                  </div>
                  <span className="text-[11px] bg-slate-800 border border-slate-700 text-slate-300 px-2.5 py-1 rounded-full font-mono">
                    RRF Score: {item.confidence_score?.toFixed(4)}
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/50 rounded-lg p-3 border border-slate-800/80">
                  {item.content}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
