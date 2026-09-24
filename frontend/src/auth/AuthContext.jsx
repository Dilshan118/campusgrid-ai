import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { api, setAccessToken, setUnauthorizedHandler } from '../api/client';
import { sessionStore } from '../lib/storage';
import { navigate, buildPath, parseHash } from '../lib/router';
import { setAnalyticsUser } from '../lib/analytics';

// The token lives in memory plus sessionStorage (cleared when the tab closes), never localStorage — spec §4.2.
const SESSION_KEY = 'cg-session';
const WARN_BEFORE_MS = 5 * 60_000;

export const HOME_BY_ROLE = { FACILITY_MANAGER: '/', OPERATOR: '/ask', ENERGY_AUDITOR: '/audit' };

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('checking'); // checking | signed_out | signed_in
  const [user, setUser] = useState(null);
  const [expiresAt, setExpiresAt] = useState(null);
  const [expiringSoon, setExpiringSoon] = useState(false);
  const [notice, setNotice] = useState(null);
  const [abVariant, setAbVariant] = useState(null);
  const signedIn = useRef(false);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    sessionStore.set(SESSION_KEY, null);
    setAnalyticsUser(null);
    signedIn.current = false;
    setUser(null);
    setExpiresAt(null);
    setExpiringSoon(false);
    setAbVariant(null);
    setStatus('signed_out');
  }, []);

  const startSession = useCallback((session) => {
    setAccessToken(session.token);
    sessionStore.set(SESSION_KEY, session);
    setAnalyticsUser(session.user.user_id);
    signedIn.current = true;
    setUser(session.user);
    setExpiresAt(session.expiresAt);
    setStatus('signed_in');
    api.abAssignment().then((d) => setAbVariant(d.ab_variant)).catch(() => {});
  }, []);

  const endSessionAndRedirect = useCallback((message) => {
    const current = parseHash(window.location.hash).full;
    clearSession();
    setNotice(message);
    const next = current.startsWith('/login') ? undefined : current;
    navigate(buildPath('/login', { next }), { replace: true });
  }, [clearSession]);

  // Restore a session from this tab, re-validating it with the server.
  useEffect(() => {
    const saved = sessionStore.get(SESSION_KEY);
    if (!saved || !saved.token || saved.expiresAt <= Date.now()) {
      clearSession();
      return;
    }
    setAccessToken(saved.token);
    api.me()
      .then((me) => startSession({ ...saved, user: { ...saved.user, ...me } }))
      .catch(() => clearSession());
  }, [clearSession, startSession]);

  // Any 401 after sign-in means the session is over (spec §4.2).
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (signedIn.current) endSessionAndRedirect('Your session has ended. Please sign in again.');
    });
  }, [endSessionAndRedirect]);

  // Five-minute warning, then sign-out at expiry.
  useEffect(() => {
    if (!expiresAt) return undefined;
    const now = Date.now();
    const warn = setTimeout(() => setExpiringSoon(true), Math.max(0, expiresAt - WARN_BEFORE_MS - now));
    const end = setTimeout(() => endSessionAndRedirect('Your session expired after 8 hours. Please sign in again.'), Math.max(0, expiresAt - now));
    return () => { clearTimeout(warn); clearTimeout(end); };
  }, [expiresAt, endSessionAndRedirect]);

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password);
    setNotice(null);
    const session = {
      token: data.access_token,
      expiresAt: Date.now() + data.expires_in_minutes * 60_000,
      user: { user_id: data.user_id, role: data.role, full_name: data.full_name, permissions: data.permissions || [] },
    };
    startSession(session);
    return session.user;
  }, [startSession]);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch { /* sign-out must work even offline */ }
    clearSession();
    navigate('/login', { replace: true });
  }, [clearSession]);

  const can = useCallback((permission) => !permission || Boolean(user?.permissions?.includes(permission)), [user]);

  const value = useMemo(() => ({
    status, user, expiresAt, expiringSoon, notice, abVariant, login, logout, can,
    dismissExpiryWarning: () => setExpiringSoon(false),
    homePath: user ? HOME_BY_ROLE[user.role] || '/' : '/login',
  }), [status, user, expiresAt, expiringSoon, notice, abVariant, login, logout, can]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
