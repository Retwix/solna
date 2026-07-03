import Admin from "./Admin.jsx";
import Gallery from "./Gallery.jsx";

// Tiny path-based router:
//   /g/{token}  -> live guest gallery
//   anything else -> admin (photographer account + events) page
function tokenFromPath() {
  const m = window.location.pathname.match(/\/g\/([^/]+)/);
  return m ? m[1] : null;
}

export default function App() {
  const token = tokenFromPath();
  return token ? <Gallery token={token} /> : <Admin />;
}
