import React, { useSyncExternalStore } from 'react';

// Minimal hash router: "#/plans/42?tab=x". Hash routing needs no server configuration,
// so deep links (for example an approval link) work from the Vite dev server and any static host.

function subscribe(callback) {
  window.addEventListener('hashchange', callback);
  return () => window.removeEventListener('hashchange', callback);
}

const snapshot = () => window.location.hash || '#/';

export function parseHash(hash) {
  const raw = hash.replace(/^#/, '') || '/';
  const [path, query = ''] = raw.split('?');
  return { path: path || '/', query: Object.fromEntries(new URLSearchParams(query)), full: raw };
}

export function useRoute() {
  const hash = useSyncExternalStore(subscribe, snapshot, () => '#/');
  return parseHash(hash);
}

export function navigate(to, { replace = false } = {}) {
  const target = `#${to.startsWith('/') ? to : `/${to}`}`;
  if (replace) window.location.replace(target);
  else window.location.hash = target;
}

export function buildPath(path, query = {}) {
  const params = new URLSearchParams(
    Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
  ).toString();
  return params ? `${path}?${params}` : path;
}

/** Matches '/plans/:id' against '/plans/42' → { id: '42' }, or null. */
export function matchPath(pattern, path) {
  const p = pattern.split('/').filter(Boolean);
  const a = path.split('/').filter(Boolean);
  if (p.length !== a.length) return null;
  const params = {};
  for (let i = 0; i < p.length; i += 1) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

export function Link({ to, children, className, ...rest }) {
  return (
    <a href={`#${to}`} className={className} {...rest}>
      {children}
    </a>
  );
}
