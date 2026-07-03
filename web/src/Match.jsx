import { useEffect, useRef, useState } from "react";
import { API } from "./api.js";

// Guest entry flow for an event: take a selfie + enter email, then we POST to
// /g/{token}/match and hand the matched photos back to the gallery.
export default function Match({ token, eventName, onMatched }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [email, setEmail] = useState("");
  const [shot, setShot] = useState(null); // { blob, dataUrl }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [camError, setCamError] = useState(null);

  useEffect(() => {
    let active = true;
    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user" },
          audio: false,
        });
        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch {
        setCamError("Camera unavailable — you can upload a photo instead.");
      }
    }
    if (!shot) start();
    return () => {
      active = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [shot]);

  function capture() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => setShot({ blob, dataUrl: canvas.toDataURL("image/jpeg") }),
      "image/jpeg",
      0.9
    );
  }

  function onUpload(e) {
    const f = e.target.files?.[0];
    if (f) setShot({ blob: f, dataUrl: URL.createObjectURL(f) });
  }

  async function submit() {
    if (!shot || !email.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", shot.blob, "selfie.jpg");
      form.append("email", email.trim());
      const r = await fetch(`${API}/g/${token}/match`, { method: "POST", body: form });
      if (r.status === 422) throw new Error("We couldn't find a face. Try a clearer selfie.");
      if (!r.ok) throw new Error(`Something went wrong (${r.status}).`);
      const result = await r.json();
      onMatched(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h1>{eventName || "Find your photos"}</h1>
      <p className="muted">Take a selfie and we'll find every photo you're in.</p>

      <div className="card">
        {shot ? (
          <img className="selfie" src={shot.dataUrl} alt="Your selfie" />
        ) : camError ? (
          <p className="muted">{camError}</p>
        ) : (
          <video ref={videoRef} className="selfie" autoPlay playsInline muted />
        )}

        {shot ? (
          <button className="btn ghost" onClick={() => setShot(null)} disabled={busy}>
            Retake
          </button>
        ) : !camError ? (
          <button className="btn" onClick={capture}>Take selfie</button>
        ) : null}

        <label className="upload muted">
          Or upload a photo
          <input type="file" accept="image/*" capture="user" onChange={onUpload} hidden />
        </label>
      </div>

      <div className="card">
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <button className="btn" onClick={submit} disabled={busy || !shot || !email.trim()}>
          {busy ? "Searching…" : "Find my photos"}
        </button>
        {error && <p className="err">{error}</p>}
      </div>
    </div>
  );
}
