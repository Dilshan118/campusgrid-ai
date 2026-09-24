import React, { useEffect, useId, useRef, useState } from 'react';
import {
  AlertTriangle, Ban, CheckCircle2, ChevronDown, Clock, Hourglass, Info, Loader2, X, XCircle, CircleSlash,
} from 'lucide-react';
import { cn } from '../lib/utils';

// ---------------------------------------------------------------------------
// Buttons
// ---------------------------------------------------------------------------

const BUTTON_VARIANTS = {
  primary: 'bg-accent text-white hover:bg-accent-hover disabled:bg-accent/50',
  secondary: 'bg-surface border border-line-strong text-ink hover:bg-surface-2 disabled:text-ink-3',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink disabled:text-ink-3',
  danger: 'bg-critical text-white hover:bg-critical/90 disabled:bg-critical/50',
};

export function Button({ variant = 'primary', size = 'md', loading = false, icon: Icon, children, className, disabled, type = 'button', ...rest }) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed',
        size === 'sm' ? 'h-8 px-3 text-sm' : 'h-10 px-4 text-sm',
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function IconButton({ label, icon: Icon, className, ...rest }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn('inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink-2 hover:bg-surface-2 hover:text-ink', className)}
      {...rest}
    >
      <Icon className="h-5 w-5" aria-hidden />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------

export function Card({ title, description, actions, children, className, bodyClassName, as: Tag = 'section', ...rest }) {
  const headingId = useId();
  return (
    <Tag className={cn('rounded-xl border border-line bg-surface', className)} aria-labelledby={title ? headingId : undefined} {...rest}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            {title && <h2 id={headingId} className="text-base font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-sm text-ink-2">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn('p-5', bodyClassName)}>{children}</div>
    </Tag>
  );
}

export function PageHeader({ title, description, actions, breadcrumb }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {breadcrumb && (
          <nav aria-label="Breadcrumb" className="mb-1 text-sm text-ink-2">
            {breadcrumb.map((crumb, i) => (
              <span key={crumb.label}>
                {i > 0 && <span className="mx-1.5 text-ink-3">›</span>}
                {crumb.to ? <a href={`#${crumb.to}`} className="hover:text-ink hover:underline">{crumb.label}</a> : <span aria-current="page">{crumb.label}</span>}
              </span>
            ))}
          </nav>
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status & badges — status always carries an icon and a word, never colour alone
// ---------------------------------------------------------------------------

const STATUS_META = {
  pending: { label: 'Pending approval', icon: Clock, className: 'bg-accent-soft text-accent-text' },
  approved: { label: 'Approved', icon: CheckCircle2, className: 'bg-good-soft text-good-text' },
  rejected: { label: 'Rejected', icon: XCircle, className: 'bg-surface-3 text-ink-2' },
  expired: { label: 'Expired', icon: Hourglass, className: 'bg-surface-3 text-ink-2 line-through decoration-ink-3' },
  not_required: { label: 'No approval needed', icon: CircleSlash, className: 'bg-surface-2 text-ink-2' },
};

export function StatusPill({ status, className }) {
  const meta = STATUS_META[status] || { label: status || 'Unknown', icon: Info, className: 'bg-surface-2 text-ink-2' };
  const Icon = meta.icon;
  return (
    <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium', meta.className, className)}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}

const BADGE_TONES = {
  neutral: 'bg-surface-2 text-ink-2 border-line',
  info: 'bg-accent-soft text-accent-text border-transparent',
  good: 'bg-good-soft text-good-text border-transparent',
  warning: 'bg-warn-soft text-warn-text border-transparent',
  critical: 'bg-critical-soft text-critical-text border-transparent',
};

export function Badge({ tone = 'neutral', icon: Icon, children, className, title }) {
  return (
    <span title={title} className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium', BADGE_TONES[tone], className)}>
      {Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
      {children}
    </span>
  );
}

const BANNER_TONES = {
  info: { icon: Info, className: 'border-accent/30 bg-accent-soft', iconClass: 'text-accent-text' },
  success: { icon: CheckCircle2, className: 'border-good/30 bg-good-soft', iconClass: 'text-good-text' },
  warning: { icon: AlertTriangle, className: 'border-warn/40 bg-warn-soft', iconClass: 'text-warn-text' },
  critical: { icon: XCircle, className: 'border-critical/40 bg-critical-soft', iconClass: 'text-critical-text' },
  neutral: { icon: Info, className: 'border-line bg-surface-2', iconClass: 'text-ink-2' },
};

export function Banner({ tone = 'info', title, children, icon, action, onDismiss, className, role }) {
  const meta = BANNER_TONES[tone];
  const Icon = icon || meta.icon;
  return (
    <div role={role || (tone === 'critical' ? 'alert' : 'status')} className={cn('flex gap-3 rounded-xl border p-4 text-sm', meta.className, className)}>
      <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', meta.iconClass)} aria-hidden />
      <div className="min-w-0 flex-1 text-ink">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn('text-ink-2', title && 'mt-1')}>{children}</div>}
        {action && <div className="mt-3">{action}</div>}
      </div>
      {onDismiss && <IconButton label="Dismiss" icon={X} onClick={onDismiss} className="-m-2 h-8 w-8" />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Numbers
// ---------------------------------------------------------------------------

export function StatTile({ label, value, sub, className, hero = false }) {
  return (
    <div className={cn('rounded-xl border border-line bg-surface p-4', className)}>
      <p className="text-sm text-ink-2">{label}</p>
      <p className={cn('mt-1 font-semibold text-ink', hero ? 'text-4xl sm:text-5xl' : 'text-2xl')}>{value}</p>
      {sub && <p className="mt-1 text-sm text-ink-2">{sub}</p>}
    </div>
  );
}

export function KeyValue({ items, className }) {
  return (
    <dl className={cn('grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2', className)}>
      {items.filter(Boolean).map(({ label, value }) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs uppercase tracking-wide text-ink-3">{label}</dt>
          <dd className="mt-0.5 break-words text-sm text-ink">{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------------------
// Feedback states
// ---------------------------------------------------------------------------

export function Spinner({ label = 'Loading' }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-2" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}
    </span>
  );
}

export function LoadingBlock({ label = 'Loading…' }) {
  return <div className="flex min-h-[160px] items-center justify-center"><Spinner label={label} /></div>;
}

export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-3 rounded-full bg-surface-2 p-3"><Icon className="h-6 w-6 text-ink-2" aria-hidden /></div>
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-ink-2">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

const STEP_NAMES = { 1: 'forecast', 2: 'comfort check', 3: 'regulations', 4: 'plan & explanation' };

/** Plain-language message for an ApiError (spec §8). */
export function describeError(error) {
  if (!error) return { title: 'Something went wrong on our side.' };
  const code = error.code;
  if (code === 'NETWORK_ERROR') return { title: "Can't reach CampusGrid.", body: 'Check your connection and try again.' };
  if (code === 'PERMISSION_DENIED') return { title: "You don't have permission to do this." };
  if (code === 'ACCOUNT_TEMPORARILY_LOCKED') return { title: 'Too many attempts.', body: 'The account is locked for a few minutes.' };
  if (error.status === 413) return { title: 'That text is too long.', body: 'The limit is 1 MB per request.' };
  if (code === 'VALIDATION_ERROR') {
    const fields = (error.details?.errors || []).map((e) => `${e.field || 'input'}: ${e.message}`);
    return { title: error.message || 'Some input is not valid.', body: fields.join(' · ') || undefined };
  }
  if (code === 'AGENT_EXECUTION_FAILED' || code === 'AGENT_PIPELINE_FAILED') {
    const match = `${error.details?.agent || ''} ${error.message || ''}`.match(/Agent (\d)/);
    const step = match ? STEP_NAMES[match[1]] : null;
    return { title: step ? `The ${step} step could not finish.` : 'The planning pipeline could not finish.', body: 'Your question is kept — try again in a moment.' };
  }
  if (code === 'WORKFLOW_CONFLICT' || code === 'ENTITY_NOT_FOUND') return { title: error.message };
  if (code === 'MALICIOUS_INPUT_DETECTED') return { title: 'The request contained characters that are not allowed.', body: error.details?.reason };
  return { title: 'Something went wrong on our side.' };
}

export function ErrorPanel({ error, onRetry, className }) {
  const { title, body } = describeError(error);
  return (
    <Banner
      tone="critical"
      title={title}
      className={className}
      action={onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>Try again</Button>}
    >
      {body && <p>{body}</p>}
      {error?.requestId && <p className="mt-1 text-xs">Reference: <span className="font-mono">{error.requestId}</span></p>}
    </Banner>
  );
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

function useFocusTrap(open, onClose) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const node = ref.current;
    const focusables = () => node?.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])') || [];
    (focusables()[0] || node)?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
      if (e.key === 'Tab') {
        const items = Array.from(focusables()).filter((el) => !el.disabled);
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus?.(); };
  }, [open, onClose]);
  return ref;
}

export function Dialog({ open, title, onClose, children, footer, size = 'md' }) {
  const ref = useFocusTrap(open, onClose);
  const titleId = useId();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className={cn('w-full rounded-xl border border-line bg-surface shadow-xl', size === 'lg' ? 'max-w-3xl' : 'max-w-lg')}>
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id={titleId} className="text-base font-semibold text-ink">{title}</h2>
          <IconButton label="Close" icon={X} onClick={onClose} className="-m-2" />
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4 text-sm text-ink-2">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, children, confirmLabel, confirmVariant = 'primary', busy, onConfirm, onCancel }) {
  return (
    <Dialog
      open={open}
      title={title}
      onClose={busy ? undefined : onCancel}
      footer={(
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button variant={confirmVariant} onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
        </>
      )}
    >
      {children}
    </Dialog>
  );
}

export function Drawer({ open, title, onClose, children }) {
  const ref = useFocusTrap(open, onClose);
  const titleId = useId();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className="flex h-full w-full max-w-2xl flex-col border-l border-line bg-surface shadow-xl">
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id={titleId} className="text-base font-semibold text-ink">{title}</h2>
          <IconButton label="Close" icon={X} onClick={onClose} />
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Forms
// ---------------------------------------------------------------------------

export function Field({ label, hint, error, children, htmlFor, className }) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label && <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">{label}</label>}
      {children}
      {hint && !error && <p className="text-xs text-ink-2">{hint}</p>}
      {error && <p className="text-xs font-medium text-critical-text" role="alert">{error}</p>}
    </div>
  );
}

const INPUT_CLASS = 'w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent-text focus:outline-none focus:ring-2 focus:ring-accent/30 disabled:bg-surface-2';

export const TextInput = React.forwardRef(function TextInput({ className, ...rest }, ref) {
  return <input ref={ref} className={cn(INPUT_CLASS, 'h-10', className)} {...rest} />;
});

export const Textarea = React.forwardRef(function Textarea({ className, maxLength, value, showCount = true, ...rest }, ref) {
  return (
    <div className="relative">
      <textarea ref={ref} className={cn(INPUT_CLASS, 'min-h-[96px] resize-y pb-6', className)} maxLength={maxLength} value={value} {...rest} />
      {maxLength && showCount && (
        <span className="pointer-events-none absolute bottom-2 right-3 text-xs text-ink-3 tabular" aria-hidden>
          {(value || '').length}/{maxLength}
        </span>
      )}
    </div>
  );
});

export function Select({ className, children, ...rest }) {
  return <select className={cn(INPUT_CLASS, 'h-10 pr-8', className)} {...rest}>{children}</select>;
}

export function Slider({ id, label, value, min, max, step, onChange, format = (v) => v, hint, marks }) {
  return (
    <Field label={<span className="flex justify-between gap-2"><span>{label}</span><span className="tabular text-ink-2">{format(value)}</span></span>} htmlFor={id} hint={hint}>
      <input id={id} type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[rgb(var(--accent))]" aria-valuetext={String(format(value))} />
      {marks && <div className="flex justify-between text-xs text-ink-3">{marks.map((m) => <span key={m}>{m}</span>)}</div>}
    </Field>
  );
}

export function Checkbox({ id, checked, onChange, children }) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-2 text-sm text-ink">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-line-strong accent-[rgb(var(--accent))]" />
      <span>{children}</span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Misc
// ---------------------------------------------------------------------------

export function Chip({ children, onClick, icon: Icon, className }) {
  return (
    <button type="button" onClick={onClick}
      className={cn('inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-surface px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink', className)}>
      {Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
      {children}
    </button>
  );
}

export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface-2 p-1">
      {tabs.map((tab) => (
        <button key={tab.value} role="tab" type="button" aria-selected={value === tab.value}
          onClick={() => onChange(tab.value)}
          className={cn('rounded-md px-3 py-1.5 text-sm font-medium', value === tab.value ? 'bg-surface text-ink shadow-sm' : 'text-ink-2 hover:text-ink')}>
          {tab.label}{tab.count !== undefined && <span className="ml-1.5 text-ink-3 tabular">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Disclosure({ summary, children, defaultOpen = false, onOpen, className }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={cn('rounded-lg border border-line', className)}>
      <button type="button" aria-expanded={open} aria-controls={id}
        onClick={() => { setOpen((o) => !o); if (!open) onOpen?.(); }}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium text-ink hover:bg-surface-2">
        <span className="min-w-0">{summary}</span>
        <ChevronDown className={cn('h-4 w-4 shrink-0 text-ink-2 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && <div id={id} className="border-t border-line px-4 py-3">{children}</div>}
    </div>
  );
}

export function NotAllowed() {
  return (
    <EmptyState icon={Ban} title="You don't have permission to view this page.">
      Your role does not include this area. If you need it, ask a facility manager.
    </EmptyState>
  );
}
