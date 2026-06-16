import { useEffect, useState } from "react";
import { API } from "./api.js";
import Match from "./Match.jsx";

// Guest gallery for one event (/g/{token}). V1 flow:
//   1. load event meta
//   2. guest takes a selfie + email -> /match
//   3. show the personal gallery of photos they appear in
export default function Gallery({ token }) {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // match result: { photos, match_count }

  useEffect(() => {
    fetch(`${API}/g/${token}`)
      .then((r) => {
        if (!r.ok) throw new Error("Gallery not found");
        return r.json();
      })
      .then(setMeta)
      .catch((e) => setError(e.message));
  }, [token]);

  if (error) return <div className="center muted">{error}</div>;
  if (!meta) return <div className="center muted">Loading…</div>;

  if (!result) {
    return <Match token={token} eventName={meta.name} onMatched={setResult} />;
  }

  return (
    <div className="app">
      <header className="header">
        <h1>{meta.name}</h1>
        <span className="count">
          {result.match_count} photo{result.match_count === 1 ? "" : "s"} of you
        </span>
      </header>

      {result.photos.length === 0 ? (
        <div className="center muted">
          No matches yet. More photos may still be arriving — try again in a bit.
          <br />
          <button className="btn" style={{ marginTop: 16 }} onClick={() => setResult(null)}>
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
            <button className="btn ghost" onClick={() => setResult(null)}>
              Search again
            </button>
          </div>
        </>
      )}
    </div>
  );
}
