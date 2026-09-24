import React, { useEffect, useRef, useState } from 'react';
import { BatteryCharging, ChevronDown, Eye, EyeOff, Lock } from 'lucide-react';
import { useAuth, HOME_BY_ROLE } from '../auth/AuthContext';
import { navigate } from '../lib/router';
import { Banner, Button, Field, TextInput } from '../components/ui';

const SHOW_DEMO_ACCOUNTS = import.meta.env.DEV || import.meta.env.VITE_SHOW_DEMO_ACCOUNTS === 'true';
const DEMO_ACCOUNTS = [
  { username: 'admin', password: 'campusgrid2026', role: 'Facility Manager' },
  { username: 'operator', password: 'operator123', role: 'Operator' },
  { username: 'auditor', password: 'audit123', role: 'Energy Auditor' },
];

export default function LoginPage({ next }) {
  const { login, notice } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [lockedUntil, setLockedUntil] = useState(null);
  const [now, setNow] = useState(Date.now());
  const usernameRef = useRef(null);

  useEffect(() => { usernameRef.current?.focus(); }, []);
  useEffect(() => {
    if (!lockedUntil) return undefined;
    const t = setInterval(() => {
      setNow(Date.now());
      if (Date.now() >= lockedUntil) { setLockedUntil(null); setError(null); }
    }, 1000);
    return () => clearInterval(t);
  }, [lockedUntil]);

  const locked = lockedUntil && now < lockedUntil;
  const secondsLeft = locked ? Math.ceil((lockedUntil - now) / 1000) : 0;

  async function onSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password) { setError('Enter your username and password.'); return; }
    setBusy(true);
    setError(null);
    try {
      const user = await login(username.trim(), password);
      navigate(next || HOME_BY_ROLE[user.role] || '/', { replace: true });
    } catch (err) {
      setPassword('');
      if (err.status === 429) {
        setLockedUntil(Date.now() + (err.details?.retry_after_seconds || 300) * 1000);
        setError('Too many attempts.');
      } else if (err.code === 'NETWORK_ERROR') {
        setError("Can't reach CampusGrid. Check your connection and try again.");
      } else if (err.status === 401) {
        setError('Username or password is incorrect.');
      } else {
        setError('Sign-in failed. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-white"><BatteryCharging className="h-6 w-6" aria-hidden /></span>
          <div>
            <h1 className="text-xl font-semibold text-ink">CampusGrid AI</h1>
            <p className="text-sm text-ink-2">Campus energy planning assistant</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-line bg-surface p-6" noValidate>
          <h2 className="text-lg font-semibold text-ink">Sign in</h2>
          {notice && !error && <Banner tone="info">{notice}</Banner>}
          {error && (
            <Banner tone="critical" title={error}>
              {locked && <p>Try again in {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}.</p>}
            </Banner>
          )}
          <Field label="Username" htmlFor="username">
            <TextInput id="username" ref={usernameRef} autoComplete="username" value={username} disabled={locked}
              onChange={(e) => setUsername(e.target.value)} />
          </Field>
          <Field label="Password" htmlFor="password">
            <div className="relative">
              <TextInput id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password}
                disabled={locked} onChange={(e) => setPassword(e.target.value)} className="pr-10" />
              <button type="button" onClick={() => setShowPassword((s) => !s)} aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-2 hover:text-ink">
                {showPassword ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
              </button>
            </div>
          </Field>
          <Button type="submit" className="w-full" loading={busy} disabled={locked} icon={Lock}>Sign in</Button>
          <p className="text-xs text-ink-2">Five failed attempts lock the account for five minutes. Accounts are created by an administrator.</p>
        </form>

        {SHOW_DEMO_ACCOUNTS && (
          <details className="mt-4 rounded-xl border border-dashed border-line-strong bg-surface p-4 text-sm">
            <summary className="flex cursor-pointer list-none items-center justify-between font-medium text-ink">
              Demo accounts (development build only)
              <ChevronDown className="h-4 w-4 text-ink-2" aria-hidden />
            </summary>
            <ul className="mt-3 space-y-2">
              {DEMO_ACCOUNTS.map((a) => (
                <li key={a.username} className="flex items-center justify-between gap-2">
                  <span className="text-ink-2"><span className="font-mono text-ink">{a.username}</span> · {a.role}</span>
                  <Button size="sm" variant="secondary" onClick={() => { setUsername(a.username); setPassword(a.password); }}>Fill in</Button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
