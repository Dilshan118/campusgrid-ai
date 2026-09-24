import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, RotateCcw, X, XCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './ui';

// ---------------------------------------------------------------------------
// Toasts: short confirmations of completed actions ("Plan #4 approved")
// ---------------------------------------------------------------------------

const ToastContext = createContext({ notify: () => {} });
export const useToast = () => useContext(ToastContext);

const TOAST_TONES = {
  success: { icon: CheckCircle2, iconClass: 'text-good-text' },
  info: { icon: Info, iconClass: 'text-accent-text' },
  warning: { icon: AlertTriangle, iconClass: 'text-warn-text' },
  error: { icon: XCircle, iconClass: 'text-critical-text' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), []);
  const notify = useCallback((message, { tone = 'success', detail, duration = 5000 } = {}) => {
    const id = nextId.current++;
    setToasts((list) => [...list.slice(-3), { id, message, detail, tone }]);
    if (duration) setTimeout(() => dismiss(id), duration);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div aria-live="polite" aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 lg:bottom-6 lg:items-end lg:px-6 print:hidden">
        {toasts.map((t) => {
          const tone = TOAST_TONES[t.tone] || TOAST_TONES.info;
          const Icon = tone.icon;
          return (
            <div key={t.id} role="status"
              className="cg-toast pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-line bg-surface p-3 shadow-xl">
              <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', tone.iconClass)} aria-hidden />
              <div className="min-w-0 flex-1 text-sm">
                <p className="font-medium text-ink">{t.message}</p>
                {t.detail && <p className="mt-0.5 text-ink-2">{t.detail}</p>}
              </div>
              <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="rounded p-1 text-ink-3 hover:bg-surface-2 hover:text-ink">
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Error boundary: a crash in one page shows a recoverable panel; navigation keeps working
// ---------------------------------------------------------------------------

export class PageErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Page crashed', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="mx-auto max-w-lg rounded-xl border border-line bg-surface p-6 text-center">
        <XCircle className="mx-auto mb-3 h-8 w-8 text-critical-text" aria-hidden />
        <p className="font-semibold text-ink">This page ran into a problem.</p>
        <p className="mt-1 text-sm text-ink-2">The rest of CampusGrid still works. Try loading the page again; if it keeps happening, note the time and tell the Team Lead.</p>
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="secondary" icon={RotateCcw} onClick={() => this.setState({ error: null })}>Try again</Button>
          <Button variant="ghost" onClick={() => window.location.reload()}>Reload the app</Button>
        </div>
      </div>
    );
  }
}

// ---------------------------------------------------------------------------
// Skeleton: first-load placeholder only (reloads keep the previous content dimmed instead)
// ---------------------------------------------------------------------------

export function Skeleton({ className }) {
  return <div className={cn('cg-skeleton rounded-md bg-surface-3', className)} aria-hidden />;
}

export function CardSkeleton({ lines = 3, className }) {
  return (
    <div className={cn('space-y-3 rounded-xl border border-line bg-surface p-5', className)} role="status" aria-label="Loading">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      {Array.from({ length: lines - 2 }, (_, i) => <Skeleton key={i} className="h-3 w-3/4" />)}
    </div>
  );
}

/** Seconds since `running` became true — for "working… 4 s" indicators. */
export function useElapsed(running) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) { setSeconds(0); return undefined; }
    const started = Date.now();
    const t = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(t);
  }, [running]);
  return seconds;
}
