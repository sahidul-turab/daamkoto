import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { SNAPSHOT_BASE } from "./lib/bootstrap";

/**
 * Open the connection to the API before React needs it.
 *
 * In production the API is on a different origin, so the first product request
 * pays DNS + TCP + TLS before a single byte moves — easily 300ms from
 * Bangladesh. Starting that handshake here lets it run in parallel with React
 * mounting, so the socket is already open when the first fetch fires.
 *
 * No-ops in dev, where /api is proxied through the page's own origin.
 */
function addPreconnect(base: string | undefined): void {
  if (!base) return;
  try {
    const origin = new URL(base, window.location.origin).origin;
    if (origin === window.location.origin) return;
    // Two hints: the bare one warms DNS/TCP/TLS, the crossorigin one is the
    // pool an actual CORS fetch draws from. Browsers keep them separate.
    for (const crossorigin of [false, true]) {
      const link = document.createElement("link");
      link.rel = "preconnect";
      link.href = origin;
      if (crossorigin) link.crossOrigin = "anonymous";
      document.head.appendChild(link);
    }
  } catch {
    // A malformed VITE_API_BASE must not stop the app from booting.
  }
}

addPreconnect(import.meta.env.VITE_API_BASE as string | undefined);
addPreconnect(SNAPSHOT_BASE);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
