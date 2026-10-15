import { useEffect, useState } from "react";
import { API } from "./api.js";

// The whole event album — only reachable when the photographer opened it
// (otherwise the API answers 404). The stream replays every photo on open,
// then pushes new ones as they arrive.
export default function AllPhotos({ token }) {
  const [photos, setPhotos] = useState([]);

  useEffect(() => {
    setPhotos([]);
    const es = new EventSource(`${API}/g/${token}/stream`);
    es.onmessage = (e) => {
      const photo = JSON.parse(e.data);
      setPhotos((prev) => (prev.some((p) => p.id === photo.id) ? prev : [...prev, photo]));
    };
    return () => es.close();
  }, [token]);

  if (photos.length === 0) {
    return <div className="center muted">No photos yet. They appear here as they're taken.</div>;
  }

  return (
    <div className="grid">
      {photos.map((p) => (
        <a key={p.id} className="cell" href={p.url} target="_blank" rel="noreferrer">
          <img src={p.thumb_url || p.url} loading="lazy" alt="" />
        </a>
      ))}
    </div>
  );
}
