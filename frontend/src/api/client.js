import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Attach JWT token if available in localStorage
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('campusgrid_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  // Auth
  login: (username, password) => apiClient.post('/api/auth/login', { username, password }),
  getProfile: () => apiClient.get('/api/auth/me'),

  // Health
  getHealth: () => apiClient.get('/api/health'),

  // Orchestrator
  queryOrchestrator: (query, userId = 'facility_director', perturb = {}) =>
    apiClient.post('/api/orchestrator/query', {
      query,
      user_id: userId,
      perturb_temp_delta_c: perturb.temp_delta || 0.0,
      perturb_occ_multiplier: perturb.occ_multiplier || 1.0,
    }),

  // Telemetry
  getTelemetryForecast: (date = '2026-09-06', room = 'LH-1', building = 'Main Academic Complex') =>
    apiClient.get('/api/telemetry/forecast', { params: { date, room, building } }),

  // Simulation
  runSimulation: (initialTemp = 24.0, deltaTemp = 0.0, occMultiplier = 1.0) =>
    apiClient.post('/api/simulation/what-if', {
      initial_temp_c: initialTemp,
      ambient_temp_delta_c: deltaTemp,
      occupancy_multiplier: occMultiplier,
    }),

  // Optimization
  runOptimization: (params = {}) =>
    apiClient.post('/api/optimizer/dispatch', {
      battery_capacity_kwh: params.capacity || 500.0,
      max_charge_rate_kw: params.maxCharge || 100.0,
      max_discharge_rate_kw: params.maxDischarge || 100.0,
      initial_soc_ratio: params.initialSoc || 0.5,
    }),

  // RAG Knowledge Base
  searchRAG: (query, topK = 2) =>
    apiClient.post('/api/rag/search', { query, top_k: topK }),
  ingestDocument: (text, sourceDocument = 'Custom Regulation', effectiveDate = '2024-01-01') =>
    apiClient.post('/api/rag/ingest', {
      text,
      source_document: sourceDocument,
      effective_date: effectiveDate,
    }),

  // Audit
  getAuditLogs: (limit = 20) => apiClient.get('/api/audit/logs', { params: { limit } }),
  approveAudit: (logId, approved = true, notes = '') =>
    apiClient.post('/api/audit/approve', {
      log_id: logId,
      approved,
      operator_notes: notes,
    }),

  // Analytics
  getAnalytics: () => apiClient.get('/api/analytics/summary'),
};

export default api;
