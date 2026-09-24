import React, { useEffect, useId, useState } from 'react';
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { BarChart3, Table2 } from 'lucide-react';
import { formatNumber } from '../lib/format';
import { cn } from '../lib/utils';

// One palette for the whole app (validated: reference slots 1-3, light + dark).
// Demand / grid import / indoor temperature = slot 1, solar = slot 2, battery = slot 3,
// "before" and context series = neutral gray.
export const SERIES = {
  primary: 'rgb(var(--series-1))',
  solar: 'rgb(var(--series-2))',
  battery: 'rgb(var(--series-3))',
  context: 'rgb(var(--series-base))',
};
const GRID = 'rgb(var(--chart-grid))';
const AXIS_TEXT = 'rgb(var(--ink-3))';
const BAND = 'rgb(var(--chart-band))';
const SURFACE = 'rgb(var(--surface))';
const CRITICAL = 'rgb(var(--critical))';

const THREE_HOUR_TICKS = ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00'];
const SIX_HOUR_TICKS = ['00:00', '06:00', '12:00', '18:00'];

/** Fewer time ticks on phones so the labels never collide. */
function useNarrow() {
  const query = '(max-width: 640px)';
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return narrow;
}
const PEAK_WINDOW = { start: '18:00', end: '22:00' }; // last peak interval starts 22:00 (ends 22:30)

const slotEnd = (slot) => {
  const [h, m] = slot.split(':').map(Number);
  const total = h * 60 + m + 30;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};

// ---------------------------------------------------------------------------
// Frame: title, one-sentence summary, legend, chart/table toggle
// ---------------------------------------------------------------------------

export function ChartFrame({ title, summary, legend, table, children, actions }) {
  const [showTable, setShowTable] = useState(false);
  const summaryId = useId();
  return (
    <figure className="min-w-0">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          {title && <figcaption className="text-sm font-semibold text-ink">{title}</figcaption>}
          {summary && <p id={summaryId} className="text-sm text-ink-2">{summary}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {table && (
            <button type="button" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">
              {showTable ? <BarChart3 className="h-3.5 w-3.5" aria-hidden /> : <Table2 className="h-3.5 w-3.5" aria-hidden />}
              {showTable ? 'View as chart' : 'View as table'}
            </button>
          )}
        </div>
      </div>
      {legend && legend.length > 1 && !showTable && <Legend items={legend} />}
      {showTable && table ? (
        <DataTable caption={title} {...table} />
      ) : (
        <div role="img" aria-describedby={summary ? summaryId : undefined} aria-label={summary ? undefined : title}>
          {children}
        </div>
      )}
    </figure>
  );
}

function Legend({ items }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <LegendKey kind={item.kind} color={item.color} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function LegendKey({ kind = 'line', color }) {
  if (kind === 'rect') return <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} aria-hidden />;
  if (kind === 'wash') return <span className="inline-block h-2.5 w-3.5 rounded-sm" style={{ background: color, opacity: 0.25 }} aria-hidden />;
  if (kind === 'dot') return <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />;
  return <span className="inline-block h-0.5 w-3.5 rounded-full" style={{ background: color }} aria-hidden />;
}

export function DataTable({ caption, columns, rows, maxHeight = 320 }) {
  return (
    <div className="overflow-auto rounded-lg border border-line" style={{ maxHeight }}>
      <table className="w-full text-left text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="sticky top-0 bg-surface-2 text-xs uppercase tracking-wide text-ink-2">
          <tr>{columns.map((c) => <th key={c.key} scope="col" className={cn('px-3 py-2 font-medium', c.numeric && 'text-right')}>{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={cn('px-3 py-1.5 text-ink', c.numeric && 'text-right tabular')}>
                  {c.format ? c.format(row[c.key], row) : row[c.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tooltip: value leads, series name follows, keyed with a short line in the series colour
// ---------------------------------------------------------------------------

function ChartTooltip({ active, payload, label, series, labelFormat = (l) => `${l}–${slotEnd(l)}` }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-ink-2">{labelFormat(label)}</p>
      <ul className="space-y-0.5">
        {series.filter((s) => row[s.key] !== undefined && row[s.key] !== null).map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <LegendKey kind={s.kind === 'rect' ? 'rect' : 'line'} color={s.color} />
            <span className="font-semibold text-ink tabular">{s.format ? s.format(row[s.key], row) : row[s.key]}</span>
            <span className="text-ink-2">{s.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const axisProps = {
  x: { dataKey: 'slot', ticks: THREE_HOUR_TICKS, interval: 0, tick: { fill: AXIS_TEXT, fontSize: 11 }, tickLine: false, axisLine: { stroke: GRID } },
  xNarrow: { dataKey: 'slot', ticks: SIX_HOUR_TICKS, interval: 0, tick: { fill: AXIS_TEXT, fontSize: 11 }, tickLine: false, axisLine: { stroke: GRID } },
  y: { tick: { fill: AXIS_TEXT, fontSize: 11 }, tickLine: false, axisLine: false, width: 52, tickFormatter: (v) => formatNumber(v) },
};

// Recharts only recognises reference elements that are direct children of the chart, so the
// peak-window band is spread as props (<ReferenceArea {...peakArea(narrow)} />) rather than wrapped in a component.
const peakArea = (narrow) => ({
  x1: PEAK_WINDOW.start,
  x2: PEAK_WINDOW.end,
  fill: BAND,
  fillOpacity: 0.07,
  label: { value: narrow ? 'Peak' : 'Peak tariff 18:00–22:30', position: 'insideTop', fill: AXIS_TEXT, fontSize: 11 },
});

const kw = (v) => `${formatNumber(v, 1)} kW`;

function peakOf(values, slots) {
  if (!values?.length) return { value: null, slot: null };
  let idx = 0;
  values.forEach((v, i) => { if (v > values[idx]) idx = i; });
  return { value: values[idx], slot: slots[idx] };
}

// ---------------------------------------------------------------------------
// Demand & solar forecast
// ---------------------------------------------------------------------------

export function ForecastChart({ slots = [], demand = [], solar = [], lower = [], upper = [], historical, height = 280 }) {
  const narrow = useNarrow();
  const data = slots.map((slot, i) => ({
    slot,
    demand: demand[i],
    solar: solar[i],
    band: lower[i] !== undefined && upper[i] !== undefined ? [lower[i], upper[i]] : undefined,
    low: lower[i],
    high: upper[i],
    historical: historical?.[i],
  }));
  const peak = peakOf(demand, slots);
  const solarPeak = peakOf(solar, slots);
  const series = [
    { key: 'demand', label: 'Demand forecast', color: SERIES.primary, format: kw },
    { key: 'solar', label: 'Solar generation', color: SERIES.solar, format: kw },
    ...(historical ? [{ key: 'historical', label: 'Historical (privacy-protected)', color: SERIES.context, format: kw }] : []),
  ];
  return (
    <ChartFrame
      title="Demand and solar, next 24 hours"
      summary={peak.value !== null ? `Forecast peak ${kw(peak.value)} at ${peak.slot}; solar peaks at ${kw(solarPeak.value)} at ${solarPeak.slot}.` : undefined}
      legend={[
        { label: 'Demand forecast', color: SERIES.primary },
        { label: 'Likely range', color: SERIES.primary, kind: 'wash' },
        { label: 'Solar generation', color: SERIES.solar },
        ...(historical ? [{ label: 'Historical (privacy-protected)', color: SERIES.context }] : []),
      ]}
      table={{
        columns: [
          { key: 'slot', label: 'Time' },
          { key: 'demand', label: 'Demand kW', numeric: true, format: (v) => formatNumber(v, 1) },
          { key: 'low', label: 'Low kW', numeric: true, format: (v) => formatNumber(v, 1) },
          { key: 'high', label: 'High kW', numeric: true, format: (v) => formatNumber(v, 1) },
          { key: 'solar', label: 'Solar kW', numeric: true, format: (v) => formatNumber(v, 1) },
          ...(historical ? [{ key: 'historical', label: 'Historical kW', numeric: true, format: (v) => formatNumber(v, 1) }] : []),
        ],
        rows: data,
      }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <ReferenceArea {...peakArea(narrow)} />
          <XAxis {...(narrow ? axisProps.xNarrow : axisProps.x)} />
          <YAxis {...axisProps.y} />
          <Tooltip cursor={{ stroke: AXIS_TEXT, strokeWidth: 1 }} content={<ChartTooltip series={series} />} />
          <Area dataKey="band" stroke="none" fill={SERIES.primary} fillOpacity={0.1} isAnimationActive={false} activeDot={false} />
          {historical && <Line dataKey="historical" stroke={SERIES.context} strokeWidth={2} dot={false} isAnimationActive={false} />}
          <Line dataKey="solar" stroke={SERIES.solar} strokeWidth={2} dot={false} strokeLinecap="round" isAnimationActive={false} />
          <Line dataKey="demand" stroke={SERIES.primary} strokeWidth={2} dot={false} strokeLinecap="round" isAnimationActive={false}
            activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------------------
// Grid import before vs after the plan (emphasis: plan in slot 1, "before" in gray)
// ---------------------------------------------------------------------------

export function GridImportChart({ slots = [], baseline = [], optimized = [], height = 260 }) {
  const narrow = useNarrow();
  const data = slots.map((slot, i) => ({ slot, baseline: baseline[i], optimized: optimized[i] }));
  const before = peakOf(baseline, slots);
  const after = peakOf(optimized, slots);
  const series = [
    { key: 'optimized', label: 'With plan', color: SERIES.primary, format: kw },
    { key: 'baseline', label: 'Without plan', color: SERIES.context, format: kw },
  ];
  return (
    <ChartFrame
      title="Grid import"
      summary={before.value !== null && after.value !== null ? `Peak grid import falls from ${kw(before.value)} (${before.slot}) to ${kw(after.value)} (${after.slot}).` : undefined}
      legend={[{ label: 'With plan', color: SERIES.primary }, { label: 'Without plan', color: SERIES.context }]}
      table={{
        columns: [
          { key: 'slot', label: 'Time' },
          { key: 'baseline', label: 'Without plan kW', numeric: true, format: (v) => formatNumber(v, 1) },
          { key: 'optimized', label: 'With plan kW', numeric: true, format: (v) => formatNumber(v, 1) },
        ],
        rows: data,
      }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <ReferenceArea {...peakArea(narrow)} />
          <XAxis {...(narrow ? axisProps.xNarrow : axisProps.x)} />
          <YAxis {...axisProps.y} />
          <Tooltip cursor={{ stroke: AXIS_TEXT, strokeWidth: 1 }} content={<ChartTooltip series={series} />} />
          <Line dataKey="baseline" stroke={SERIES.context} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="optimized" stroke={SERIES.primary} strokeWidth={2} dot={false} isAnimationActive={false}
            activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------------------
// Battery power: one series, charging above the baseline, discharging below
// ---------------------------------------------------------------------------

/** Bar with a 4px rounded data-end and a square end on the zero baseline, for either sign. */
function DataEndBar({ x, y, width, height, fill, value }) {
  if (!height || !width) return null;
  const top = Math.min(y, y + height);
  const h = Math.abs(height);
  const r = Math.min(4, h, width / 2);
  const negative = (Array.isArray(value) ? value[1] : value) < 0;
  const path = negative
    ? `M${x},${top} h${width} v${h - r} a${r},${r} 0 0 1 -${r},${r} h-${width - 2 * r} a${r},${r} 0 0 1 -${r},-${r} z`
    : `M${x},${top + h} v-${h - r} a${r},${r} 0 0 1 ${r},-${r} h${width - 2 * r} a${r},${r} 0 0 1 ${r},${r} v${h - r} z`;
  return <path d={path} fill={fill} />;
}

export function BatteryPowerChart({ slots = [], charge = [], discharge = [], height = 220 }) {
  const narrow = useNarrow();
  const data = slots.map((slot, i) => ({ slot, net: (charge[i] || 0) - (discharge[i] || 0), charge: charge[i], discharge: discharge[i] }));
  const charged = charge.reduce((a, b) => a + (b || 0), 0) * 0.5;
  const discharged = discharge.reduce((a, b) => a + (b || 0), 0) * 0.5;
  const series = [{
    key: 'net', label: 'battery power', color: SERIES.battery, kind: 'rect',
    format: (v) => (v > 0 ? `Charging ${kw(v)}` : v < 0 ? `Discharging ${kw(-v)}` : 'Idle'),
  }];
  return (
    <ChartFrame
      title="Battery charging (above the line) and discharging (below)"
      summary={`Charges ${formatNumber(charged)} kWh and discharges ${formatNumber(discharged)} kWh over the day.`}
      table={{
        columns: [
          { key: 'slot', label: 'Time' },
          { key: 'charge', label: 'Charge kW', numeric: true, format: (v) => formatNumber(v, 1) },
          { key: 'discharge', label: 'Discharge kW', numeric: true, format: (v) => formatNumber(v, 1) },
        ],
        rows: data,
      }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 16, right: 12, bottom: 0, left: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <ReferenceArea {...peakArea(narrow)} />
          <XAxis {...(narrow ? axisProps.xNarrow : axisProps.x)} />
          <YAxis {...axisProps.y} />
          <ReferenceLine y={0} stroke="rgb(var(--line-strong))" />
          <Tooltip cursor={{ fill: BAND, fillOpacity: 0.05 }} content={<ChartTooltip series={series} />} />
          <Bar dataKey="net" fill={SERIES.battery} maxBarSize={24} shape={<DataEndBar />} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------------------
// Battery charge level with its 20 % / 90 % safety limits
// ---------------------------------------------------------------------------

export function BatteryLevelChart({ slots = [], soc = [], limits = {}, height = 220 }) {
  const narrow = useNarrow();
  const data = slots.map((slot, i) => ({ slot, soc: soc[i] }));
  const { capacity_kwh: capacity, min_soc_kwh: minKwh, max_soc_kwh: maxKwh } = limits;
  const lowest = soc.length ? Math.min(...soc) : null;
  const pct = (v) => (capacity ? ` (${Math.round((v / capacity) * 100)}%)` : '');
  const series = [{ key: 'soc', label: 'stored energy', color: SERIES.battery, format: (v) => `${formatNumber(v, 0)} kWh${pct(v)}` }];
  const limitLabel = (text) => ({ value: text, position: 'insideTopRight', fill: AXIS_TEXT, fontSize: 11 });
  return (
    <ChartFrame
      title="Battery charge level"
      summary={lowest !== null ? `Lowest level ${formatNumber(lowest)} kWh${pct(lowest)}${minKwh !== undefined ? `; the safe minimum is ${formatNumber(minKwh)} kWh.` : '.'}` : undefined}
      table={{
        columns: [
          { key: 'slot', label: 'Time' },
          { key: 'soc', label: 'Stored kWh', numeric: true, format: (v) => `${formatNumber(v, 1)}${pct(v)}` },
        ],
        rows: data,
      }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis {...(narrow ? axisProps.xNarrow : axisProps.x)} />
          <YAxis {...axisProps.y} domain={[0, capacity || 'auto']}
            ticks={capacity ? [0, 0.2, 0.4, 0.6, 0.8, 1].map((f) => Math.round(capacity * f)) : undefined} />
          {minKwh !== undefined && <ReferenceLine y={minKwh} stroke={AXIS_TEXT} label={limitLabel('Minimum 20%')} />}
          {maxKwh !== undefined && <ReferenceLine y={maxKwh} stroke={AXIS_TEXT} label={limitLabel('Maximum 90%')} />}
          <Tooltip cursor={{ stroke: AXIS_TEXT, strokeWidth: 1 }} content={<ChartTooltip series={series} />} />
          <Line dataKey="soc" stroke={SERIES.battery} strokeWidth={2} dot={false} isAnimationActive={false}
            activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------------------
// Indoor temperature vs the comfort band
// ---------------------------------------------------------------------------

function ViolationDot({ cx, cy, payload, band }) {
  if (cx === undefined || cy === undefined) return null;
  const outside = payload.indoor < band[0] || payload.indoor > band[1];
  if (!outside) return null;
  return <circle cx={cx} cy={cy} r={4} fill={CRITICAL} stroke={SURFACE} strokeWidth={2} />;
}

export function TemperatureChart({ slots = [], indoor = [], outdoor = [], band = [21, 25.5], height = 280 }) {
  const narrow = useNarrow();
  const data = slots.map((slot, i) => ({ slot, indoor: indoor[i], outdoor: outdoor[i] }));
  const violations = indoor.filter((t) => t < band[0] || t > band[1]).length;
  // A dot per violation helps when there are a few; past that the band itself shows it and dots become noise.
  const markViolations = violations > 0 && violations <= 12;
  const values = [...indoor, ...outdoor].filter((v) => typeof v === 'number');
  const domain = values.length ? [Math.floor(Math.min(...values, band[0]) - 1), Math.ceil(Math.max(...values, band[1]) + 1)] : [18, 32];
  const temp = (v) => `${Number(v).toFixed(1)} °C`;
  const series = [
    { key: 'indoor', label: 'Indoor', color: SERIES.primary, format: temp },
    { key: 'outdoor', label: 'Outdoor', color: SERIES.context, format: temp },
  ];
  return (
    <ChartFrame
      title="Indoor temperature against the comfort band"
      summary={violations ? `${violations} of ${indoor.length} half-hours fall outside ${band[0]}–${band[1]} °C.` : `Indoor temperature stays within ${band[0]}–${band[1]} °C all day.`}
      legend={[
        { label: 'Indoor', color: SERIES.primary },
        { label: 'Outdoor', color: SERIES.context },
        { label: `Comfort band ${band[0]}–${band[1]} °C`, color: 'rgb(var(--ink-3))', kind: 'wash' },
        ...(markViolations ? [{ label: 'Outside the band', color: CRITICAL, kind: 'dot' }] : []),
      ]}
      table={{
        columns: [
          { key: 'slot', label: 'Time' },
          { key: 'indoor', label: 'Indoor °C', numeric: true, format: (v, row) => `${Number(v).toFixed(1)}${row.indoor < band[0] || row.indoor > band[1] ? ' ⚠ outside band' : ''}` },
          { key: 'outdoor', label: 'Outdoor °C', numeric: true, format: (v) => (v === undefined ? '—' : Number(v).toFixed(1)) },
        ],
        rows: data,
      }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <ReferenceArea y1={band[0]} y2={band[1]} fill={BAND} fillOpacity={0.07} />
          <XAxis {...(narrow ? axisProps.xNarrow : axisProps.x)} />
          <YAxis {...axisProps.y} domain={domain} tickFormatter={(v) => `${v}°`} width={40} />
          <Tooltip cursor={{ stroke: AXIS_TEXT, strokeWidth: 1 }} content={<ChartTooltip series={series} />} />
          <Line dataKey="outdoor" stroke={SERIES.context} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="indoor" stroke={SERIES.primary} strokeWidth={2} isAnimationActive={false}
            dot={markViolations ? <ViolationDot band={band} /> : false} activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

// ---------------------------------------------------------------------------
// Horizontal bars (funnel stages, intent clusters, clicks by rank) — single series, value at the tip
// ---------------------------------------------------------------------------

export function HorizontalBars({ title, summary, data, valueLabel = 'Value', format = (v) => formatNumber(v) }) {
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  return (
    <ChartFrame
      title={title}
      summary={summary}
      table={{ columns: [{ key: 'label', label: 'Item' }, { key: 'value', label: valueLabel, numeric: true, format }], rows: data }}
    >
      <ul className="space-y-2.5">
        {data.map((d) => (
          <li key={d.label} className="grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 text-sm sm:grid-cols-[minmax(0,12rem)_1fr]" title={`${d.label}: ${format(d.value)}`}>
            <span className="truncate text-ink-2">{d.label}</span>
            <span className="flex items-center gap-2">
              <span className="h-4 rounded-r" style={{ width: `${Math.max(0.5, ((d.value || 0) / max) * 85)}%`, background: SERIES.primary }} aria-hidden />
              <span className="shrink-0 font-medium text-ink tabular">{format(d.value)}</span>
            </span>
          </li>
        ))}
      </ul>
    </ChartFrame>
  );
}
