import {
  useRef,
  type PointerEvent as ReactPointerEvent
} from "react";

export function ResizablePanel({
  orientation,
  value,
  min,
  max,
  label,
  onChange,
  invert = false,
  className = ""
}: {
  orientation: "vertical" | "horizontal";
  value: number;
  min: number;
  max: number;
  label: string;
  onChange: (value: number) => void;
  invert?: boolean;
  className?: string;
}) {
  const drag = useRef<{ coordinate: number; value: number } | null>(null);

  function clamp(next: number): number {
    return Math.max(min, Math.min(max, Math.round(next)));
  }

  function coordinate(event: ReactPointerEvent<HTMLDivElement>): number {
    return orientation === "vertical" ? event.clientX : event.clientY;
  }

  function move(event: ReactPointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    const delta = coordinate(event) - drag.current.coordinate;
    onChange(clamp(drag.current.value + delta * (invert ? -1 : 1)));
  }

  function end(event: ReactPointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    drag.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  return (
    <div
      className={"ovg-resizer " + className}
      role="separator"
      aria-label={label}
      aria-orientation={orientation}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      tabIndex={0}
      onPointerDown={(event) => {
        drag.current = { coordinate: coordinate(event), value };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
      onKeyDown={(event) => {
        const step = event.shiftKey ? 40 : 12;
        const positive =
          orientation === "vertical"
            ? event.key === "ArrowRight"
            : event.key === "ArrowDown";
        const negative =
          orientation === "vertical"
            ? event.key === "ArrowLeft"
            : event.key === "ArrowUp";

        if (event.key === "Home") {
          event.preventDefault();
          onChange(min);
          return;
        }
        if (event.key === "End") {
          event.preventDefault();
          onChange(max);
          return;
        }
        if (!positive && !negative) return;

        event.preventDefault();
        const direction = positive ? 1 : -1;
        onChange(clamp(value + direction * step * (invert ? -1 : 1)));
      }}
    />
  );
}
