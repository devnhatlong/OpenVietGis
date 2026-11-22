import { useEffect, useState } from "react";

type Scheme = "light" | "dark";

function systemScheme(): Scheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readStoredScheme(): Scheme | null {
  try {
    const value = window.localStorage.getItem("color-scheme");
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function applyMetaScheme(stored: Scheme | null) {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
  if (meta) {
    meta.content = stored ?? "light dark";
  }
}

export function ThemeToggle() {
  const [stored, setStored] = useState<Scheme | null>(() =>
    typeof window === "undefined" ? null : readStoredScheme()
  );
  const [resolved, setResolved] = useState<Scheme>(() => stored ?? systemScheme());

  useEffect(() => {
    const nextResolved = stored ?? systemScheme();
    setResolved(nextResolved);
    applyMetaScheme(stored);
  }, [stored]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === "color-scheme") {
        const next = readStoredScheme();
        setStored(next);
        applyMetaScheme(next);
      }
    };
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onMediaChange = () => {
      const currentStored = readStoredScheme();
      if (!currentStored) {
        setResolved(systemScheme());
      }
    };
    window.addEventListener("storage", onStorage);
    media.addEventListener("change", onMediaChange);
    return () => {
      window.removeEventListener("storage", onStorage);
      media.removeEventListener("change", onMediaChange);
    };
  }, []);

  function handleToggle() {
    const currentRendered = stored ?? systemScheme();
    const target: Scheme = currentRendered === "dark" ? "light" : "dark";
    const osScheme = systemScheme();

    if (target === osScheme) {
      try {
        window.localStorage.removeItem("color-scheme");
      } catch {
        // Apply even when storage is blocked
      }
      setStored(null);
      setResolved(osScheme);
      applyMetaScheme(null);
    } else {
      try {
        window.localStorage.setItem("color-scheme", target);
      } catch {
        // Apply even when storage is blocked
      }
      setStored(target);
      setResolved(target);
      applyMetaScheme(target);
    }
  }

  const isDark = resolved === "dark";
  return (
    <button
      type="button"
      className="ovg-theme-toggle"
      onClick={handleToggle}
      aria-label={isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      title={isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
    >
      {isDark ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2" /><path d="M12 20v2" />
          <path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" />
          <path d="M2 12h2" /><path d="M20 12h2" />
          <path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
        </svg>
      )}
    </button>
  );
}
