import { listSpatialCrsProfiles } from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "../../app/api";

export interface DisplayCrsOption {
  code: number;
  label: string;
  unit: "°" | "m";
  centralMeridian?: number;
  scaleFactor?: number;
  kind: "geographic" | "mercator" | "tm";
}

export const VIETNAM_CRS_PRESETS: DisplayCrsOption[] = [
  { code: 4326, label: "WGS 84 (Địa lý kinh/vĩ độ)", unit: "°", kind: "geographic" },
  { code: 3857, label: "WGS 84 / Pseudo-Mercator (Bản đồ Web)", unit: "m", kind: "mercator" },
  { code: 5899, label: "VN-2000 / TM-3 105°00' (Hà Nội, Bắc Bộ)", unit: "m", centralMeridian: 105.0, scaleFactor: 0.9999, kind: "tm" },
  { code: 5897, label: "VN-2000 / TM-3 105°45' (TP.HCM, Nam Bộ)", unit: "m", centralMeridian: 105.75, scaleFactor: 0.9999, kind: "tm" },
  { code: 5898, label: "VN-2000 / TM-3 107°45' (Đà Nẵng, Trung Bộ)", unit: "m", centralMeridian: 107.75, scaleFactor: 0.9999, kind: "tm" },
  { code: 3405, label: "VN-2000 / UTM Zone 48N (Toàn quốc 6°)", unit: "m", centralMeridian: 105.0, scaleFactor: 0.9996, kind: "tm" },
  { code: 3406, label: "VN-2000 / UTM Zone 49N (Biển Đông / Trung-Nam)", unit: "m", centralMeridian: 111.0, scaleFactor: 0.9996, kind: "tm" },
  { code: 9210, label: "VN-2000 / TM-3 105°30' (Hải Phòng / Quảng Ninh)", unit: "m", centralMeridian: 105.5, scaleFactor: 0.9999, kind: "tm" }
];

/** Fast WGS84 -> Web Mercator or Transverse Mercator (VN-2000 approx) coordinate readout */
export function formatCoordinateInCrs(
  lon: number,
  lat: number,
  crs: DisplayCrsOption
): string {
  if (crs.kind === "geographic") {
    return `${lon.toFixed(5)}°E, ${lat.toFixed(5)}°N`;
  }
  if (crs.kind === "mercator") {
    const R = 6378137;
    const x = (lon * Math.PI * R) / 180;
    const clampedLat = Math.max(-85.051129, Math.min(85.051129, lat));
    const y = R * Math.log(Math.tan(Math.PI / 4 + (clampedLat * Math.PI) / 360));
    return `X ${x.toFixed(1)} m, Y ${y.toFixed(1)} m`;
  }
  // Transverse Mercator (WGS84 ellipsoid approximation for live status-bar readout)
  const a = 6378137.0;
  const f = 1 / 298.257223563;
  const e2 = 2 * f - f * f;
  const ep2 = e2 / (1 - e2);
  const k0 = crs.scaleFactor ?? 0.9999;
  const lon0 = ((crs.centralMeridian ?? 105.0) * Math.PI) / 180;
  const phi = (lat * Math.PI) / 180;
  const lam = (lon * Math.PI) / 180;
  const sinP = Math.sin(phi);
  const cosP = Math.cos(phi);
  const tanP = Math.tan(phi);
  const N = a / Math.sqrt(1 - e2 * sinP * sinP);
  const T = tanP * tanP;
  const C = ep2 * cosP * cosP;
  const A = cosP * (lam - lon0);
  const M =
    a *
    ((1 - e2 / 4 - (3 * e2 * e2) / 64 - (5 * e2 * e2 * e2) / 256) * phi -
      ((3 * e2) / 8 + (3 * e2 * e2) / 32 + (45 * e2 * e2 * e2) / 1024) * Math.sin(2 * phi) +
      ((15 * e2 * e2) / 256 + (45 * e2 * e2 * e2) / 1024) * Math.sin(4 * phi) -
      ((35 * e2 * e2 * e2) / 3072) * Math.sin(6 * phi));
  const easting =
    500000 +
    k0 *
      N *
      (A +
        ((1 - T + C) * A * A * A) / 6 +
        ((5 - 18 * T + T * T + 72 * C - 58 * ep2) * Math.pow(A, 5)) / 120);
  const northing =
    k0 *
    (M +
      N *
        tanP *
        ((A * A) / 2 +
          ((5 - T + 9 * C + 4 * C * C) * Math.pow(A, 4)) / 24 +
          ((61 - 58 * T + T * T + 600 * C - 330 * ep2) * Math.pow(A, 6)) / 720));
  return `X(E) ${easting.toFixed(1)} m, Y(N) ${northing.toFixed(1)} m`;
}

interface MapCrsPickerProps {
  organizationId: string;
  projectId: string;
  selectedCode: number;
  onSelect: (crs: DisplayCrsOption) => void;
  onOpenFullCrsDock: () => void;
}

export function MapCrsPicker({
  organizationId,
  projectId,
  selectedCode,
  onSelect,
  onOpenFullCrsDock
}: MapCrsPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);

  const registryQ = useQuery({
    queryKey: ["map-crs-profiles", organizationId, projectId],
    queryFn: () => listSpatialCrsProfiles(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });

  const options = useMemo<DisplayCrsOption[]>(() => {
    const map = new Map<number, DisplayCrsOption>();
    for (const preset of VIETNAM_CRS_PRESETS) {
      map.set(preset.code, preset);
    }
    for (const item of registryQ.data?.profiles ?? []) {
      if (!map.has(item.code)) {
        map.set(item.code, {
          code: item.code,
          label: item.name,
          unit: item.unit === "metre" ? "m" : "°",
          kind: item.code === 4326 ? "geographic" : item.code === 3857 ? "mercator" : "tm",
          centralMeridian: 105.0,
          scaleFactor: 0.9999
        });
      }
    }
    return [...map.values()];
  }, [registryQ.data]);

  const current = options.find((o) => o.code === selectedCode) ?? VIETNAM_CRS_PRESETS[0]!;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) => String(o.code).includes(q) || o.label.toLowerCase().includes(q)
    );
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={wrapRef} className="qgis-crs-wrap">
      {open ? (
        <div className="qgis-crs-popover" role="dialog" aria-label="Chọn hệ tọa độ hiển thị (CRS)">
          <div className="qgis-crs-head">
            <strong>Hệ tọa độ hiển thị (CRS / EPSG)</strong>
            <button type="button" onClick={() => setOpen(false)} aria-label="Đóng">✕</button>
          </div>
          <input
            type="text"
            className="qgis-crs-search"
            placeholder="Tìm mã EPSG hoặc tỉnh/vùng (VD: 5899, 3405, Hà Nội, 4326)…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <ul className="qgis-crs-list" role="listbox">
            {filtered.map((opt) => (
              <li key={opt.code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={opt.code === current.code}
                  className={opt.code === current.code ? "is-selected" : undefined}
                  onClick={() => {
                    onSelect(opt);
                    setOpen(false);
                    setQuery("");
                  }}
                >
                  <kbd>EPSG:{opt.code}</kbd>
                  <span>{opt.label}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="qgis-crs-foot">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onOpenFullCrsDock();
              }}
            >
              Mở Danh mục CRS đầy đủ →
            </button>
          </div>
        </div>
      ) : null}

      <button
        type="button"
        className="qgis-crs-trigger"
        data-testid="qgis-crs-picker"
        title="Bấm để đổi Hệ tọa độ hiển thị (giống QGIS)"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        🌐 EPSG:{current.code} ▾
      </button>
    </div>
  );
}
