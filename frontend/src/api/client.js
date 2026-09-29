// Thin fetch wrapper around the CampusGrid API. Every failure becomes an ApiError carrying the
// server's error_code, message, details and X-Request-ID, so screens can react per spec §8.

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

let accessToken = null;
let onUnauthorized = () => {};

export function setAccessToken(token) { accessToken = token; }
export function setUnauthorizedHandler(handler) { onUnauthorized = handler; }

export class ApiError extends Error {
  constructor({ status, code, message, details = {}, requestId = null }) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

async function request(method, path, { body, query, auth = true, signal, raw = false } = {}) {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  Object.entries(query || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
  });

  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let response;
  try {
    response = await fetch(url.toString(), {
      method, headers, signal, body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError({ status: 0, code: 'NETWORK_ERROR', message: "Can't reach CampusGrid. Check your connection." });
  }

  const requestId = response.headers.get('X-Request-ID');
  let payload = null;
  try { payload = await response.json(); } catch { payload = null; }

  // `raw` callers get the whole body for a 200 with success:false (e.g. an upload where every clause was rejected).
  if (!response.ok || (!raw && payload && payload.success === false)) {
    const error = new ApiError({
      status: response.status,
      code: payload?.error_code || `HTTP_${response.status}`,
      message: payload?.message || payload?.error || 'Something went wrong on our side.',
      details: payload?.details || {},
      requestId,
    });
    if (response.status === 401 && auth) onUnauthorized(error);
    throw error;
  }
  if (raw) return payload;
  return path === '/api/health' ? payload : payload?.data;
}

export const api = {
  // Authentication
  login: (username, password) => request('POST', '/api/auth/login', { body: { username, password }, auth: false }),
  logout: () => request('POST', '/api/auth/logout'),
  me: () => request('GET', '/api/auth/me'),
  health: () => request('GET', '/api/health', { auth: false }),

  // Planning
  ask: (payload, signal) => request('POST', '/api/orchestrator/query', { body: payload, signal }),
  dispatch: (payload) => request('POST', '/api/optimizer/dispatch', { body: payload }),
  whatIf: (payload) => request('POST', '/api/simulation/what-if', { body: payload }),
  forecast: (date, room) => request('GET', '/api/telemetry/forecast', { query: { date, room } }),
  historical: (date) => request('GET', '/api/telemetry/historical', { query: { date } }),
  rooms: () => request('GET', '/api/campus/rooms'),

  // Regulations
  searchRegulations: (query, topK, sessionId) =>
    request('POST', '/api/rag/search', { body: { query, top_k: topK, session_id: sessionId } }),
  regulationLibrary: () => request('GET', '/api/rag/documents'),
  ingestRegulation: (payload) => request('POST', '/api/rag/ingest', { body: payload, raw: true }),

  // Audit & approvals
  auditLogs: (params) => request('GET', '/api/audit/logs', { query: params }),
  // includeDetails=false skips every agent's full output (the plan review page needs only the decision).
  auditRecord: (id, { includeDetails = true } = {}) =>
    request('GET', `/api/audit/logs/${encodeURIComponent(id)}`, { query: { include_details: includeDetails } }),
  pending: (limit = 100) => request('GET', '/api/audit/pending', { query: { limit } }),
  decide: (payload) => request('POST', '/api/audit/approve', { body: payload }),
  verifyAudit: () => request('GET', '/api/audit/verify'),

  // Analytics
  trackEvent: (event) => request('POST', '/api/analytics/event', { body: event }),
  abAssignment: () => request('GET', '/api/analytics/ab/assignment'),
  analyticsSummary: () => request('GET', '/api/analytics/summary'),
};
