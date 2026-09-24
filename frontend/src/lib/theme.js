import { useEffect, useState } from 'react';
import { localStore } from './storage';

const KEY = 'cg-theme';
const media = () => window.matchMedia('(prefers-color-scheme: dark)');

function apply(pref) {
  const dark = pref === 'dark' || (pref === 'system' && media().matches);
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
}

/** 'system' | 'light' | 'dark' — a per-viewer convenience, so browser storage is fine here. */
export function useTheme() {
  const [pref, setPref] = useState(() => {
    try { return localStorage.getItem(KEY) || 'system'; } catch { return 'system'; }
  });

  useEffect(() => {
    apply(pref);
    try { localStorage.setItem(KEY, pref); } catch { /* ignore */ }
    if (pref !== 'system') return undefined;
    const mq = media();
    const onChange = () => apply('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [pref]);

  return [pref, setPref];
}

export { localStore };
