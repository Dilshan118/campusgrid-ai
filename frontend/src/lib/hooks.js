import { useCallback, useEffect, useRef, useState } from 'react';
import { sessionStore } from './storage';

/**
 * Loads data and keeps the previous result on screen while reloading (no skeleton flash).
 * `loader` receives an AbortSignal-free call; stale responses are ignored.
 */
export function useAsync(loader, deps = [], { immediate = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: immediate });
  const callId = useRef(0);

  const run = useCallback(async () => {
    const id = ++callId.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loader();
      if (id === callId.current) setState({ data, error: null, loading: false });
      return data;
    } catch (error) {
      if (id === callId.current) setState((s) => ({ ...s, error, loading: false }));
      return undefined;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { if (immediate) run(); }, [run, immediate]);

  return { ...state, reload: run, setData: (data) => setState((s) => ({ ...s, data })) };
}

/** Text the user is writing, kept for this tab so it survives a forced re-login (spec §4.2). */
export function useDraft(key, initial = '') {
  const storageKey = `cg-draft:${key}`;
  const [value, setValue] = useState(() => sessionStore.get(storageKey, initial));
  useEffect(() => { sessionStore.set(storageKey, value === initial ? null : value); }, [storageKey, value, initial]);
  const clear = useCallback(() => { setValue(initial); sessionStore.set(storageKey, null); }, [initial, storageKey]);
  return [value, setValue, clear];
}

/** Re-renders every `ms` so countdowns stay current. */
export function useNow(ms = 30_000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

export const PLANS_CHANGED = 'cg:plans-changed';
export const announcePlansChanged = () => window.dispatchEvent(new Event(PLANS_CHANGED));
