import { useEffect, useState } from "react";
import { API } from "./api.js";

// Live gallery for one event, keyed by the token in the URL (/g/{token}).
export default function Gallery({ token }) {
  const [meta, setMeta] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cursor = null;
    let pollMs = 3000;
    let timer;
    let cancelled = false;

    async function loadMeta() {
      const r = await fetch(`${API}/g/${token}`);
      if (!r.ok) throw new Error("Gallery not found");
      const m = await r.json();
      setMeta(m);
      pollMs = m.poll_interval_ms || 3000;
    }

    async function poll() {
      try {
        const url = new URL(`/g/${token}/photos`, API);
        if (cursor) url.searchParams.set("since", cursor);
        const r = await fetch(url);
        if (!r.ok) throw new Error("Failed to load photos");
        const page = await r.json();
        if (page.photos.length) {
          setPhotos((prev) => [...page.photos.slice().reverse(), ...prev]);
          cursor = page.cursor;
        }
      } catch (e) {
        // keep polling; transient errors are expected during an event
        console.warn(e);
      } finally {
        if (!cancelled) timer = setTimeout(poll, pollMs);
      }
    }

    loadMeta()
      .then(poll)
      .catch((e) => setError(e.message));

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [token]);

  if (error) return <div className="center muted">{error}</div>;

  return (
    <div className="app">
      <header className="header">
        <h1>{meta?.name ?? "Solna"}</h1>
        <span className="count">{photos.length || meta?.photo_count || 0} photos · live</span>
      </header>

      {photos.length === 0 ? (
        <div className="center muted">Waiting for the first photos…</div>
      ) : (
        <div className="grid">
          {photos.map((p) => (
            <a key={p.id} className="cell" href={p.url} target="_blank" rel="noreferrer">
              <img src={p.thumb_url || p.url} loading="lazy" alt="" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
