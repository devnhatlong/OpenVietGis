import { useEffect, useState } from "react";

type Scheme = "light" | "dark";

function readStoredScheme(): Scheme {
  try {
    return window.localStorage.getItem("color-scheme") === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function applyMetaScheme(scheme: Scheme) {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
  if (meta) {
    meta.content = scheme;
  }
}

export function ThemeToggle() {
  const [scheme, setScheme] = useState<Scheme>(() =>
    typeof window === "undefined" ? "light" : readStoredScheme()
  );

  useEffect(() => {
    applyMetaScheme(scheme);
  }, [scheme]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === "color-scheme") {
        const next = readStoredScheme();
        setScheme(next);
        applyMetaScheme(next);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function handleToggle() {
    const next: Scheme = scheme === "dark" ? "light" : "dark";
    try {
      window.localStorage.setItem("color-scheme", next);
    } catch {
      // Apply even when storage is blocked
    }
    setScheme(next);
    applyMetaScheme(next);
  }

  const isDark = scheme === "dark";
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
