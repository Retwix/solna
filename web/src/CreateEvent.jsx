import { useState } from "react";
import { API } from "./api.js";

// Minimal admin page: create an event, then show its QR + FTP credentials.
export default function CreateEvent() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [event, setEvent] = useState(null);

  async function submit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/events`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!r.ok) throw new Error(`Create failed (${r.status})`);
      setEvent(await r.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setEvent(null);
    setName("");
  }

  if (event) {
    const f = event.ftp;
    return (
      <div className="panel">
        <h1>{event.name}</h1>
        <p className="muted">Event created. Keep these details — the FTP password is shown only once.</p>

        <div className="card">
          <h2>Guest gallery</h2>
          <img className="qr" src={`data:image/png;base64,${event.qr_png_base64}`} alt="Gallery QR code" />
          <p className="muted">Guests scan this QR, or open the link:</p>
          <a className="link" href={event.gallery_url} target="_blank" rel="noreferrer">
            {event.gallery_url}
          </a>
        </div>

        <div className="card">
          <h2>Camera FTP settings</h2>
          <dl className="kv">
            <dt>Host</dt><dd>{f.host}</dd>
            <dt>Port</dt><dd>{f.port}</dd>
            <dt>Username</dt><dd><code>{f.username}</code></dd>
            <dt>Password</dt><dd><code>{f.password}</code></dd>
            <dt>Mode</dt><dd>Passive</dd>
          </dl>
          <p className="muted">
            For a real camera, use your computer's LAN IP as the host (not localhost),
            and make sure <code>FTP_PASV_ADDRESS</code> is set to that IP.
          </p>
        </div>

        <button className="btn" onClick={reset}>Create another event</button>
      </div>
    );
  }

  return (
    <div className="panel">
      <h1>Solna · New event</h1>
      <form className="card" onSubmit={submit}>
        <label className="field">
          <span>Event name</span>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Summer Wedding"
          />
        </label>
        <button className="btn" type="submit" disabled={loading || !name.trim()}>
          {loading ? "Creating…" : "Create event"}
        </button>
        {error && <p className="err">{error}</p>}
      </form>
    </div>
  );
}
