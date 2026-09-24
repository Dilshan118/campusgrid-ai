import { api } from '../api/client';
import { sessionStore } from './storage';

// UI events for the web-analytics module (spec §10). Fire and forget: never block or break the UI.
// The server stamps user, role and A/B variant itself.

const SENT_KEY = 'cg-analytics-sent';
const DEMO_ACCOUNTS = ['admin', 'operator', 'auditor'];
let currentUserId = null;

export function setAnalyticsUser(userId) { currentUserId = userId; }

function excluded() {
  return import.meta.env.VITE_EXCLUDE_DEMO_ANALYTICS === 'true' && DEMO_ACCOUNTS.includes(currentUserId);
}

function send(event) {
  if (excluded()) return;
  api.trackEvent(event).catch(() => { /* analytics must never surface errors */ });
}

/** Sends an event at most once per browser session for the given dedupe key. */
function sendOnce(key, event) {
  const sent = new Set(sessionStore.get(SENT_KEY, []));
  if (sent.has(key)) return;
  sent.add(key);
  sessionStore.set(SENT_KEY, Array.from(sent).slice(-500));
  send(event);
}

export const analytics = {
  recommendationShown: (auditLogId) =>
    auditLogId && sendOnce(`shown:${auditLogId}`, { event_type: 'recommendation_shown', audit_log_id: auditLogId }),
  explanationOpened: (auditLogId) =>
    auditLogId && sendOnce(`opened:${auditLogId}`, { event_type: 'explanation_opened', audit_log_id: auditLogId }),
  citationClicked: (auditLogId, rank, clauseReference) =>
    auditLogId && send({ event_type: 'citation_clicked', audit_log_id: auditLogId, rank, clause_reference: clauseReference?.slice(0, 200) }),
  searchResultClicked: (rank, queryText, sessionId) =>
    send({ event_type: 'search_result_clicked', rank, query_text: queryText?.slice(0, 500), session_id: sessionId }),
};
