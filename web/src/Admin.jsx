import { useCallback, useEffect, useState } from "react";
import { API } from "./api.js";

// Admin flow (docs/design/photographer-accounts.md):
//   1. First run: create the photographer account -> stable FTP creds, shown ONCE.
//   2. Then: create events, press "Go live" on the one being shot,
//      and claim any photos that landed in the unassigned tray.
//
// The account id and this browser's events are kept in localStorage so the
// admin page survives refreshes. (There are no list endpoints yet; the server
// remains the source of truth for photos/routing.)

const LS_KEY = "solna.admin";

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY)) || {};
  } catch {
    return {};
  }
}

function saveState(state) {
  localStorage.setItem(LS_KEY, JSON.stringify(state));
}

async function post(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} failed (${r.status})`);
  return r.json();
}

// --- Step 1: once-only account creation ---------------------------------------

function CreateAccount({ onCreated }) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [account, setAccount] = useState(null); // holds the one-time creds view

  async function submit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setAccount(await post("/photographers", { name: name.trim() }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (account) {
    const f = account.ftp;
    return (
      <div className="panel">
        <h1>Camera FTP settings</h1>
        <p className="muted">
          Enter these into your camera <strong>once</strong> — they never change.
          The password is shown only now.
        </p>
        <div className="card">
          <dl className="kv">
            <dt>Host</dt><dd>{f.host}</dd>
            <dt>Port</dt><dd>{f.port}</dd>
            <dt>Username</dt><dd><code>{f.username}</code></dd>
            <dt>Password</dt><dd><code>{f.password}</code></dd>
            <dt>Mode</dt><dd>Passive</dd>
          </dl>
          <p className="muted">
            For a real camera, use your computer's LAN IP as the host (not
            localhost), and make sure <code>FTP_PASV_ADDRESS</code> is set to that IP.
          </p>
        </div>
        <button className="btn" onClick={() => onCreated(account)}>
          I've saved these — continue
        </button>
      </div>
    );
  }

  return (
    <div className="panel">
      <h1>Solna · Photographer account</h1>
      <p className="muted">
        One account per camera. You'll get FTP settings to enter once; after
        that, you just pick which event is live.
      </p>
      <form className="card" onSubmit={submit}>
        <label className="field">
          <span>Your name / studio</span>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ana Lens Photography"
          />
        </label>
        <button className="btn" type="submit" disabled={loading || !name.trim()}>
          {loading ? "Creating…" : "Create account"}
        </button>
        {error && <p className="err">{error}</p>}
      </form>
    </div>
  );
}

// --- Step 2: events, go-live, unassigned tray ----------------------------------

function EventCard({ event, isLive, onGoLive, onStop, onClaim, trayCount }) {
  const [showQr, setShowQr] = useState(false);
  return (
    <div className="card">
      <div className="row">
        <h2>
          {event.name} {isLive && <span className="badge live">LIVE</span>}
        </h2>
        {isLive ? (
          <button className="btn ghost" onClick={() => onStop(event)}>Stop</button>
        ) : (
          <button className="btn" onClick={() => onGoLive(event)}>Go live</button>
        )}
      </div>
      <a className="link" href={event.gallery_url} target="_blank" rel="noreferrer">
        {event.gallery_url}
      </a>
      <button className="btn ghost" onClick={() => setShowQr((s) => !s)}>
        {showQr ? "Hide QR" : "Show QR"}
      </button>
      {showQr && (
        <img
          className="qr"
          src={`data:image/png;base64,${event.qr_png_base64}`}
          alt="Gallery QR code"
        />
      )}
      {trayCount > 0 && (
        <button className="btn ghost" onClick={() => onClaim(event)}>
          Claim {trayCount} unassigned photo{trayCount > 1 ? "s" : ""} into this event
        </button>
      )}
    </div>
  );
}

function Dashboard({ photographer, events, onAddEvent }) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeEventId, setActiveEventId] = useState(null);
  const [tray, setTray] = useState([]);

  const refreshTray = useCallback(async () => {
    try {
      const r = await fetch(`${API}/photographers/${photographer.id}/unassigned`);
      if (r.ok) setTray((await r.json()).photos);
    } catch {
      /* tray is advisory; ignore fetch hiccups */
    }
  }, [photographer.id]);

  useEffect(() => {
    refreshTray();
    const t = setInterval(refreshTray, 10000);
    return () => clearInterval(t);
  }, [refreshTray]);

  async function createEvent(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const event = await post("/events", {
        name: name.trim(),
        photographer_id: photographer.id,
      });
      onAddEvent(event);
      setName("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function goLive(event) {
    const s = await post(`/events/${event.id}/go-live`);
    setActiveEventId(s.active_event_id);
  }

  async function stop(event) {
    const s = await post(`/events/${event.id}/stop`);
    setActiveEventId(s.active_event_id);
  }

  async function claim(event) {
    await post(`/events/${event.id}/claim-unassigned`);
    refreshTray();
  }

  return (
    <div className="panel">
      <h1>Solna · {photographer.name}</h1>

      {tray.length > 0 && (
        <p className="muted">
          {tray.length} photo{tray.length > 1 ? "s" : ""} in the unassigned tray
          (uploaded while no event was live) — claim them from an event below.
        </p>
      )}

      <form className="card" onSubmit={createEvent}>
        <label className="field">
          <span>New event</span>
          <input
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

      {[...events].reverse().map((ev) => (
        <EventCard
          key={ev.id}
          event={ev}
          isLive={ev.id === activeEventId}
          onGoLive={goLive}
          onStop={stop}
          onClaim={claim}
          trayCount={tray.length}
        />
      ))}
    </div>
  );
}

export default function Admin() {
  const [state, setState] = useState(loadState);

  function update(next) {
    setState(next);
    saveState(next);
  }

  if (!state.photographer) {
    return (
      <CreateAccount
        onCreated={(account) =>
          // Deliberately drop the plaintext password before persisting.
          update({
            photographer: { id: account.id, name: account.name },
            events: [],
          })
        }
      />
    );
  }

  return (
    <Dashboard
      photographer={state.photographer}
      events={state.events || []}
      onAddEvent={(event) => update({ ...state, events: [...(state.events || []), event] })}
    />
  );
}
