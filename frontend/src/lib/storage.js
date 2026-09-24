// Browser storage can be unavailable (private mode, blocked site data), so every access is guarded
// and callers always get a usable default.

function read(store, key, fallback) {
  try {
    const raw = store.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function write(store, key, value) {
  try {
    if (value === undefined || value === null) store.removeItem(key);
    else store.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: the app keeps working from memory */
  }
}

const session = () => (typeof window !== 'undefined' ? window.sessionStorage : null);
const local = () => (typeof window !== 'undefined' ? window.localStorage : null);

export const sessionStore = {
  get: (key, fallback = null) => (session() ? read(session(), key, fallback) : fallback),
  set: (key, value) => session() && write(session(), key, value),
};

export const localStore = {
  get: (key, fallback = null) => (local() ? read(local(), key, fallback) : fallback),
  set: (key, value) => local() && write(local(), key, value),
};
