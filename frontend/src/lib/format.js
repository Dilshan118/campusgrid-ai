// Display conventions from the UI/UX spec §9.4: Asia/Colombo time, LKR, kW / kWh / kVA, °C.

const TZ = 'Asia/Colombo';

export function formatLKR(value, { decimals = 0 } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `LKR ${Number(value).toLocaleString('en-LK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('en-LK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export const formatKw = (v, d = 0) => (v === null || v === undefined ? '—' : `${formatNumber(v, d)} kW`);
export const formatKwh = (v, d = 0) => (v === null || v === undefined ? '—' : `${formatNumber(v, d)} kWh`);
export const formatTemp = (v) => (v === null || v === undefined ? '—' : `${Number(v).toFixed(1)} °C`);
export const formatPct = (v, d = 1) => (v === null || v === undefined ? '—' : `${Number(v).toFixed(d)}%`);

function toDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(iso) {
  const d = toDate(iso);
  if (!d) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(d);
}

export function formatDate(isoDate) {
  if (!isoDate) return '—';
  const d = toDate(isoDate.length === 10 ? `${isoDate}T12:00:00+05:30` : isoDate);
  if (!d) return isoDate;
  return new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }).format(d);
}

export function utcTitle(iso) {
  const d = toDate(iso);
  return d ? `${d.toISOString().replace('T', ' ').slice(0, 19)} UTC` : '';
}

export function relativeTime(iso, now = Date.now()) {
  const d = toDate(iso);
  if (!d) return '—';
  const minutes = Math.round((now - d.getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

/** Time left before a plan created at `iso` passes its 24-hour validity. */
export function expiresIn(iso, validityHours = 24, now = Date.now()) {
  const d = toDate(iso);
  if (!d) return { expired: false, label: '—', ms: Infinity };
  const ms = d.getTime() + validityHours * 3600_000 - now;
  if (ms <= 0) return { expired: true, label: 'Expired', ms };
  const h = Math.floor(ms / 3600_000);
  const m = Math.floor((ms % 3600_000) / 60000);
  return { expired: false, label: h > 0 ? `${h} h ${m} min` : `${m} min`, ms };
}

export function tomorrowIso() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' })
    .format(new Date(Date.now() + 86400_000));
  return parts; // en-CA formats as YYYY-MM-DD
}

export const RECORD_TYPE_LABELS = {
  dispatch_recommendation: 'Dispatch plan',
  approval_decision: 'Decision',
  what_if_simulation: 'What-if simulation',
  policy_lookup: 'Regulation lookup',
  forecast_review: 'Forecast',
  out_of_scope_query: 'Out of scope',
  knowledge_ingestion: 'Document upload',
};

export const INTENT_LABELS = {
  optimize_dispatch: 'Dispatch plan',
  what_if_simulation: 'What-if simulation',
  policy_lookup: 'Regulation lookup',
  telemetry_status: 'Forecast',
  out_of_scope: 'Out of scope',
  knowledge_search: 'Regulation search',
  unclassified: 'Unclassified',
};

export const ROLE_LABELS = {
  FACILITY_MANAGER: 'Facility Manager',
  OPERATOR: 'Operator',
  ENERGY_AUDITOR: 'Energy Auditor',
};
