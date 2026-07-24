/**
 * Client-side response cache for GET requests.
 *
 * Three things this buys, none of which HTTP caching alone gives us:
 *
 *  1. Instant re-renders. Flipping back to a category you already viewed, or
 *     paging back, resolves from memory in the same tick — no skeleton flash,
 *     no request. Even a 200ms round trip is visible as a stutter when you are
 *     clicking through tabs.
 *
 *  2. Request de-duplication. React strict mode double-invokes effects, and
 *     prefetch can race a real navigation. Without dedupe those become two
 *     identical in-flight requests; with it, the second caller subscribes to
 *     the first one's promise.
 *
 *  3. Survives a reload. Entries are mirrored into sessionStorage, so a refresh
 *     or a return through the back button paints from cache while the network
 *     revalidates behind it.
 *
 * Freshness is deliberately loose. Prices only change when the scraper pipeline
 * runs, so showing a two-minute-old list for the instant before revalidation
 * lands is never wrong in a way a user would notice.
 */

const FRESH_MS = 2 * 60 * 1000; // serve without revalidating
const STALE_MS = 30 * 60 * 1000; // serve immediately, but refresh in background

const STORAGE_PREFIX = "dk:swr:";
const MAX_ENTRIES = 120;

interface Entry<T> {
  ts: number;
  data: T;
}

const memory = new Map<string, Entry<unknown>>();
const inflight = new Map<string, Promise<unknown>>();

/** sessionStorage is unavailable in private modes and some embedded webviews. */
function safeSession(): Storage | null {
  try {
    const s = window.sessionStorage;
    s.getItem(STORAGE_PREFIX); // touch it — throws in the blocked cases
    return s;
  } catch {
    return null;
  }
}

function readPersisted<T>(key: string): Entry<T> | null {
  const store = safeSession();
  if (!store) return null;
  try {
    const raw = store.getItem(STORAGE_PREFIX + key);
    if (!raw) return null;
    const entry = JSON.parse(raw) as Entry<T>;
    if (Date.now() - entry.ts > STALE_MS) {
      store.removeItem(STORAGE_PREFIX + key);
      return null;
    }
    return entry;
  } catch {
    return null;
  }
}

function persist<T>(key: string, entry: Entry<T>): void {
  const store = safeSession();
  if (!store) return;
  try {
    store.setItem(STORAGE_PREFIX + key, JSON.stringify(entry));
  } catch {
    // Quota exceeded — drop our own keys and retry once. Failing to persist is
    // never fatal; the in-memory copy still serves this session.
    try {
      for (const k of Object.keys(store)) {
        if (k.startsWith(STORAGE_PREFIX)) store.removeItem(k);
      }
      store.setItem(STORAGE_PREFIX + key, JSON.stringify(entry));
    } catch {
      /* give up quietly */
    }
  }
}

function remember<T>(key: string, data: T): void {
  if (memory.size >= MAX_ENTRIES) {
    // Map preserves insertion order, so the first key is the oldest write.
    const oldest = memory.keys().next().value;
    if (oldest !== undefined) memory.delete(oldest);
  }
  const entry: Entry<T> = { ts: Date.now(), data };
  memory.set(key, entry);
  persist(key, entry);
}

function lookup<T>(key: string): Entry<T> | null {
  const hit = memory.get(key) as Entry<T> | undefined;
  if (hit) return hit;
  const persisted = readPersisted<T>(key);
  if (persisted) {
    memory.set(key, persisted);
    return persisted;
  }
  return null;
}

/** Read cached data for `key` without triggering a fetch. */
export function peek<T>(key: string): T | null {
  const entry = lookup<T>(key);
  return entry ? entry.data : null;
}

/**
 * Fetch `key` through the cache.
 *
 * `onData` may be called twice: once synchronously-ish with stale data, then
 * again with the revalidated response. Callers that only want the final value
 * can ignore it and use the returned promise.
 */
export function swr<T>(
  key: string,
  fetcher: () => Promise<T>,
  onData?: (data: T, isStale: boolean) => void,
): Promise<T> {
  const entry = lookup<T>(key);
  const age = entry ? Date.now() - entry.ts : Infinity;

  if (entry && age < FRESH_MS) {
    onData?.(entry.data, false);
    return Promise.resolve(entry.data);
  }

  // Stale but usable — hand it over now, refresh underneath.
  if (entry) onData?.(entry.data, true);

  const existing = inflight.get(key) as Promise<T> | undefined;
  const request =
    existing ??
    fetcher()
      .then((data) => {
        remember(key, data);
        return data;
      })
      .finally(() => {
        inflight.delete(key);
      });

  if (!existing) inflight.set(key, request);

  if (onData) {
    request.then((data) => onData(data, false)).catch(() => void 0);
  }
  return request;
}

/**
 * Populate the cache for `key` if it is missing, without any UI wired up.
 * Used to warm categories and the next page before the user asks for them.
 */
export function prefetch<T>(key: string, fetcher: () => Promise<T>): void {
  const entry = lookup<T>(key);
  if (entry && Date.now() - entry.ts < FRESH_MS) return;
  if (inflight.has(key)) return;
  swr(key, fetcher).catch(() => void 0);
}

/** Drop everything. Exposed for tests and for a hard refresh action. */
export function clearSwrCache(): void {
  memory.clear();
  inflight.clear();
  const store = safeSession();
  if (!store) return;
  try {
    for (const k of Object.keys(store)) {
      if (k.startsWith(STORAGE_PREFIX)) store.removeItem(k);
    }
  } catch {
    /* nothing to clean up */
  }
}
