import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import {
  BarChart3, BatteryCharging, BookOpen, ClipboardCheck, Library, LayoutDashboard, LineChart, LogOut, Menu,
  MessageSquare, Monitor, Moon, MoreHorizontal, Plus, ServerCog, ShieldCheck, Sun, Thermometer, X,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import { PLANS_CHANGED } from '../lib/hooks';
import { useTheme } from '../lib/theme';
import { ROLE_LABELS } from '../lib/format';
import { cn } from '../lib/utils';
import { Banner, Button, IconButton } from './ui';

// Navigation per spec §5. `match` decides which item is highlighted for a path.
export const NAV_ITEMS = [
  { to: '/', label: 'Overview', short: 'Home', group: 'Operate', icon: LayoutDashboard, permission: null, match: (p) => p === '/' },
  { to: '/ask', label: 'Ask CampusGrid', short: 'Ask', group: 'Operate', icon: MessageSquare, permission: 'orchestrator:query', match: (p) => p === '/ask' },
  { to: '/what-if', label: 'What-if simulator', short: 'What-if', group: 'Operate', icon: Thermometer, permission: 'simulation:run', match: (p) => p === '/what-if' },
  { to: '/forecast', label: 'Forecast', short: 'Forecast', group: 'Operate', icon: LineChart, permission: 'telemetry:read', match: (p) => p === '/forecast' },
  { to: '/plans', label: 'Approvals', short: 'Approvals', group: 'Plans', icon: ClipboardCheck, permission: 'audit:read', badge: 'pending', match: (p) => p === '/plans' || /^\/plans\/\d+/.test(p) },
  { to: '/plans/new', label: 'New dispatch plan', short: 'New plan', group: 'Plans', icon: Plus, permission: 'optimizer:run', match: (p) => p === '/plans/new' },
  { to: '/regulations', label: 'Regulation search', short: 'Rules', group: 'Regulations', icon: BookOpen, permission: 'rag:search', match: (p) => p === '/regulations' },
  { to: '/regulations/library', label: 'Regulation library', short: 'Library', group: 'Regulations', icon: Library, permission: 'rag:search', match: (p) => p === '/regulations/library' },
  { to: '/audit', label: 'Audit & Compliance', short: 'Audit', group: 'Oversight', icon: ShieldCheck, permission: 'audit:read', match: (p) => p === '/audit' },
  { to: '/analytics', label: 'Analytics', short: 'Analytics', group: 'Oversight', icon: BarChart3, permission: 'analytics:read', match: (p) => p === '/analytics' },
  { to: '/system', label: 'System status', short: 'System', group: 'Oversight', icon: ServerCog, permission: 'system:read', match: (p) => p === '/system' },
];
const NAV_GROUPS = ['Operate', 'Plans', 'Regulations', 'Oversight'];

// The four most-used destinations per role, for the mobile tab bar.
const MOBILE_PRIMARY = {
  FACILITY_MANAGER: ['/', '/plans', '/ask', '/audit'],
  OPERATOR: ['/ask', '/plans', '/what-if', '/'],
  ENERGY_AUDITOR: ['/audit', '/plans', '/regulations', '/analytics'],
};

// ---------------------------------------------------------------------------
// System health (public endpoint) — drives degraded-mode banners
// ---------------------------------------------------------------------------

const SystemContext = createContext({ health: null });
export const useSystem = () => useContext(SystemContext);

function usePendingCount(enabled) {
  const [count, setCount] = useState(null);
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    const load = () => api.pending(100).then((rows) => alive && setCount(rows.length)).catch(() => {});
    load();
    const timer = setInterval(load, 60_000);
    window.addEventListener(PLANS_CHANGED, load);
    return () => { alive = false; clearInterval(timer); window.removeEventListener(PLANS_CHANGED, load); };
  }, [enabled]);
  return count;
}

// ---------------------------------------------------------------------------

export function AppLayout({ path, children }) {
  const { user, can, expiringSoon, dismissExpiryWarning } = useAuth();
  const [health, setHealth] = useState(null);
  const [moreOpen, setMoreOpen] = useState(false);
  const pendingCount = usePendingCount(can('audit:read'));
  const isManager = can('audit:approve');

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  useEffect(() => { setMoreOpen(false); }, [path]);

  const items = NAV_ITEMS.filter((item) => can(item.permission));
  const primaryPaths = MOBILE_PRIMARY[user.role] || ['/'];
  const mobilePrimary = primaryPaths.map((to) => items.find((i) => i.to === to)).filter(Boolean);
  const mobileMore = items.filter((i) => !mobilePrimary.includes(i));

  const badgeFor = (item) => (item.badge === 'pending' && pendingCount ? pendingCount : null);

  return (
    <SystemContext.Provider value={{ health }}>
      <a href="#main" className="sr-only-focusable fixed left-2 top-2 z-50 rounded-md bg-accent px-3 py-2 text-white">Skip to content</a>
      <div className="flex min-h-full">
        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-surface lg:flex">
          <Brand />
          <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
            {NAV_GROUPS.map((group) => {
              const groupItems = items.filter((i) => i.group === group);
              if (!groupItems.length) return null;
              return (
                <div key={group}>
                  <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider text-ink-3">{group}</p>
                  <div className="space-y-0.5">
                    {groupItems.map((item) => (
                      <NavLink key={item.to} item={item} active={item.match(path)} badge={badgeFor(item)} badgeTone={isManager ? 'action' : 'neutral'} />
                    ))}
                  </div>
                </div>
              );
            })}
          </nav>
          <SidebarFooter health={health} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur lg:px-8">
            <div className="lg:hidden"><Brand compact /></div>
            <div className="hidden items-center gap-2 text-sm text-ink-2 lg:flex">
              <span className="rounded-md bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink-2">Advisory only</span>
              Recommendations are approved by a facility manager; nothing is switched automatically.
            </div>
            <UserMenu />
          </header>

          <main id="main" tabIndex={-1} className="flex-1 px-4 pb-24 pt-6 lg:px-8 lg:pb-10">
            <div className="mx-auto max-w-7xl space-y-4">
              {expiringSoon && (
                <Banner tone="warning" title="Your session ends in 5 minutes" onDismiss={dismissExpiryWarning}>
                  Save your work. You will need to sign in again; unsent text on this page is kept.
                </Banner>
              )}
              {health && health.dense_search_enabled === false && path.startsWith('/regulations') && (
                <Banner tone="neutral" title="Keyword matching only">Semantic search is off, so results match on exact words.</Banner>
              )}
              <div>{children}</div>
            </div>
          </main>
        </div>
      </div>

      {/* Mobile bottom tab bar */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-line bg-surface lg:hidden">
        {mobilePrimary.map((item) => (
          <a key={item.to} href={`#${item.to}`} aria-current={item.match(path) ? 'page' : undefined}
            className={cn('relative flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px]', item.match(path) ? 'text-accent-text' : 'text-ink-2')}>
            <item.icon className="h-5 w-5" aria-hidden />
            <span className="max-w-full truncate px-1">{item.short}</span>
            {badgeFor(item) && <CountBadge count={badgeFor(item)} className="absolute right-3 top-1.5" tone={isManager ? 'action' : 'neutral'} />}
          </a>
        ))}
        <button type="button" onClick={() => setMoreOpen(true)} className="flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px] text-ink-2" aria-haspopup="dialog">
          <MoreHorizontal className="h-5 w-5" aria-hidden /> More
        </button>
      </nav>

      {moreOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 lg:hidden" onClick={() => setMoreOpen(false)}>
          <div role="dialog" aria-modal="true" aria-label="More pages" className="absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-line bg-surface p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between">
              <p className="font-semibold text-ink">More</p>
              <IconButton label="Close" icon={X} onClick={() => setMoreOpen(false)} />
            </div>
            <nav aria-label="More pages" className="grid gap-1">
              {mobileMore.map((item) => <NavLink key={item.to} item={item} active={item.match(path)} badge={badgeFor(item)} />)}
            </nav>
          </div>
        </div>
      )}
    </SystemContext.Provider>
  );
}

function Brand({ compact = false }) {
  return (
    <a href="#/" className={cn('flex items-center gap-2.5', !compact && 'px-5 py-5')}>
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-white">
        <BatteryCharging className="h-5 w-5" aria-hidden />
      </span>
      <span className="leading-tight">
        <span className="block font-semibold text-ink">CampusGrid AI</span>
        {!compact && <span className="block text-xs text-ink-2">Energy planning assistant</span>}
      </span>
    </a>
  );
}

function CountBadge({ count, className, tone = 'action' }) {
  return (
    <span className={cn('inline-flex min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold tabular',
      tone === 'action' ? 'bg-accent text-white' : 'bg-surface-3 text-ink', className)}>
      <span className="sr-only">(</span>{count}<span className="sr-only"> pending)</span>
    </span>
  );
}

function NavLink({ item, active, badge, badgeTone = 'action' }) {
  const Icon = item.icon;
  return (
    <a href={`#${item.to}`} aria-current={active ? 'page' : undefined}
      className={cn('flex min-h-[40px] items-center gap-3 rounded-lg px-3 text-sm font-medium',
        active ? 'bg-accent-soft text-accent-text' : 'text-ink-2 hover:bg-surface-2 hover:text-ink')}>
      <Icon className="h-4 w-4 shrink-0" aria-hidden />
      <span className="flex-1 truncate">{item.label}</span>
      {badge ? <CountBadge count={badge} tone={badgeTone} /> : null}
    </a>
  );
}

function SidebarFooter({ health }) {
  const slices = health?.agent_slices || {};
  const baselines = Object.values(slices).filter((s) => String(s).startsWith('reference_baseline')).length;
  return (
    <div className="border-t border-line px-5 py-4 text-xs text-ink-2">
      {health ? (
        <p className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-good" aria-hidden />
          <span>Online · v{health.version}{baselines ? ` · ${baselines} agent on reference model` : ''}</span>
        </p>
      ) : (
        <p>Status unavailable</p>
      )}
    </div>
  );
}

const THEME_OPTIONS = [
  { value: 'system', label: 'System', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
];

const PERMISSION_LABELS = {
  'orchestrator:query': 'Ask questions', 'simulation:run': 'Run simulations', 'optimizer:run': 'Create dispatch plans',
  'telemetry:read': 'View forecasts', 'rag:search': 'Search regulations', 'rag:ingest': 'Add regulations',
  'audit:read': 'Read the audit trail', 'audit:approve': 'Approve or reject plans', 'analytics:read': 'View analytics',
  'system:read': 'View system status',
};

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useTheme();
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const initials = (user.full_name || user.user_id).split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-3 text-xs font-semibold text-ink">{initials}</span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-medium text-ink">{user.full_name}</span>
          <span className="block text-xs text-ink-2">{ROLE_LABELS[user.role] || user.role}</span>
        </span>
        <Menu className="h-4 w-4 text-ink-2 sm:hidden" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-50 mt-2 w-72 rounded-xl border border-line bg-surface p-2 shadow-xl">
          <div className="px-3 py-2">
            <p className="font-medium text-ink">{user.full_name}</p>
            <p className="text-sm text-ink-2">{user.user_id} · {ROLE_LABELS[user.role]}</p>
          </div>
          <div className="border-t border-line px-3 py-2">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-3">You can</p>
            <ul className="space-y-0.5 text-sm text-ink-2">
              {(user.permissions || []).map((p) => <li key={p}>{PERMISSION_LABELS[p] || p}</li>)}
            </ul>
          </div>
          <div className="border-t border-line px-3 py-2">
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-3">Theme</p>
            <div className="grid grid-cols-3 gap-1" role="radiogroup" aria-label="Theme">
              {THEME_OPTIONS.map((opt) => (
                <button key={opt.value} type="button" role="radio" aria-checked={theme === opt.value} onClick={() => setTheme(opt.value)}
                  className={cn('flex flex-col items-center gap-1 rounded-lg py-2 text-xs', theme === opt.value ? 'bg-accent-soft text-accent-text' : 'text-ink-2 hover:bg-surface-2')}>
                  <opt.icon className="h-4 w-4" aria-hidden />{opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="border-t border-line pt-2">
            <Button variant="ghost" icon={LogOut} className="w-full justify-start" onClick={logout} role="menuitem">Sign out</Button>
          </div>
        </div>
      )}
    </div>
  );
}
