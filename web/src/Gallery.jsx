import { useCallback, useEffect, useState } from "react";
import { API } from "./api.js";
import AllPhotos from "./AllPhotos.jsx";
import Match from "./Match.jsx";

// Guest gallery for one event (/g/{token}). Flow:
//   1. load event meta
//   2. guest takes a selfie + email -> /match (once)
//   3. show the personal gallery of photos they appear in
// The guest_token from /match is kept in localStorage, so a refresh or
// revisit re-fetches the current matches (including newer photos) without
// retaking the selfie. While the gallery is shown, an SSE stream pushes
// newly matched photos so they appear without any button press.
export default function Gallery({ token }) {
  const storageKey = `solna.guest.${token}`;
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // match result: { photos, match_count, guest_token }
  const [restoring, setRestoring] = useState(() => !!localStorage.getItem(storageKey));
  const [view, setView] = useState("mine"); // "mine" | "all" (only if the album is open)

  useEffect(() => {
    fetch(`${API}/g/${token}`)
      .then((r) => {
        if (!r.ok) throw new Error("Gallery not found");
        return r.json();
      })
      .then(setMeta)
      .catch((e) => setError(e.message));
  }, [token]);

  // Returning guest: re-open the matched gallery from the stored token.
  useEffect(() => {
    const guestToken = localStorage.getItem(storageKey);
    if (!guestToken) return;
    fetch(`${API}/g/${token}/matches?guest=${encodeURIComponent(guestToken)}`)
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setResult)
      .catch(() => localStorage.removeItem(storageKey)) // stale token -> selfie screen
      .finally(() => setRestoring(false));
  }, [token, storageKey]);

  // Live updates: while a matched gallery is shown, stream newly matched
  // photos. The stream resyncs from the start on every open, and the browser
  // auto-reconnects on drop; on reconnect we also re-fetch /matches once so
  // nothing is missed while disconnected. Closed on unmount / search again.
  const guestToken = result?.guest_token;
  useEffect(() => {
    if (!guestToken) return;
    let active = true;
    let opened = false;
    const es = new EventSource(
      `${API}/g/${token}/matches/stream?guest=${encodeURIComponent(guestToken)}`
    );
    es.onopen = () => {
      if (!opened) {
        opened = true;
        return;
      }
      fetch(`${API}/g/${token}/matches?guest=${encodeURIComponent(guestToken)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((res) => active && res && setResult(res));
    };
    es.onmessage = (e) => {
      const photo = JSON.parse(e.data);
      setResult((prev) => {
        if (!prev || prev.photos.some((p) => p.id === photo.id)) return prev;
        const photos = [...prev.photos, photo];
        return { ...prev, photos, match_count: photos.length };
      });
    };
    return () => {
      active = false;
      es.close();
    };
  }, [token, guestToken]);

  const onMatched = useCallback(
    (res) => {
      localStorage.setItem(storageKey, res.guest_token);
      setResult(res);
    },
    [storageKey]
  );

  function searchAgain() {
    localStorage.removeItem(storageKey);
    setResult(null);
  }

  function refresh() {
    const guestToken = localStorage.getItem(storageKey);
    if (!guestToken) return;
    fetch(`${API}/g/${token}/matches?guest=${encodeURIComponent(guestToken)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((res) => res && setResult(res));
  }

  if (error) return <div className="center muted">{error}</div>;
  if (!meta || restoring) return <div className="center muted">Loading…</div>;

  const tabs = meta.full_album ? (
    <nav className="tabs">
      <button className={view === "mine" ? "tab active" : "tab"} onClick={() => setView("mine")}>
        Your photos
      </button>
      <button className={view === "all" ? "tab active" : "tab"} onClick={() => setView("all")}>
        All photos
      </button>
    </nav>
  ) : null;

  if (meta.full_album && view === "all") {
    return (
      <div className="app">
        <header className="header">
          <h1>{meta.name}</h1>
        </header>
        {tabs}
        <AllPhotos token={token} />
      </div>
    );
  }

  if (!result) {
    return (
      <>
        {tabs}
        <Match token={token} eventName={meta.name} onMatched={onMatched} />
      </>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>{meta.name}</h1>
        <span className="count">
          {result.match_count} photo{result.match_count === 1 ? "" : "s"} of you
        </span>
      </header>
      {tabs}

      {result.photos.length === 0 ? (
        <div className="center muted">
          No matches yet. More photos may still be arriving.
          <br />
          <button className="btn" style={{ marginTop: 16 }} onClick={refresh}>
            Check again
          </button>
          <button className="btn ghost" style={{ marginTop: 8 }} onClick={searchAgain}>
            Try another selfie
          </button>
        </div>
      ) : (
        <>
          <div className="grid">
            {result.photos.map((p) => (
              <a key={p.id} className="cell" href={p.url} target="_blank" rel="noreferrer">
                <img src={p.thumb_url || p.url} loading="lazy" alt="" />
              </a>
            ))}
          </div>
          <div className="center">
            <button className="btn" onClick={refresh}>
              Check for new photos
            </button>
            <button className="btn ghost" style={{ marginLeft: 8 }} onClick={searchAgain}>
              Not you? Search again
            </button>
          </div>
        </>
      )}
    </div>
  );
}
