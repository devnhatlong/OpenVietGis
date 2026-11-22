import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import "./ui/tokens.css";
import "./ui/tailwind.css";
import "./ui/global.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

if (import.meta.env.PROD && "serviceWorker" in navigator && window.isSecureContext) {
  void navigator.serviceWorker.register("/offline-shell-sw.js").catch(error => {
    console.warn("Offline shell unavailable", error);
  });
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>
);
