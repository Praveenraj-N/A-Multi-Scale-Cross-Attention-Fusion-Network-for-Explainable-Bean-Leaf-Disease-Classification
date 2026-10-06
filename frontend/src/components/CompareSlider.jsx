import { useId, useState } from "react";
import { MoveHorizontal } from "lucide-react";

// Wipes between the leaf and its Grad-CAM overlay. The original is stretched to
// a square on purpose: the model sees a 224x224 resize, so this keeps the two
// images pixel-aligned. Driven by a native range input (keyboard accessible).
export default function CompareSlider({ before, after, beforeLabel = "Leaf", afterLabel = "Grad-CAM overlay" }) {
  const [position, setPosition] = useState(50);
  const id = useId();

  return (
    <div className="relative aspect-square w-full select-none overflow-hidden rounded-xl border border-line bg-raised">
      <img src={after} alt={afterLabel} className="absolute inset-0 size-full object-fill" draggable={false} />
      <img
        src={before}
        alt={beforeLabel}
        className="absolute inset-0 size-full object-fill"
        style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
        draggable={false}
      />

      <div className="pointer-events-none absolute inset-y-0" style={{ left: `${position}%` }} aria-hidden>
        <div className="absolute inset-y-0 -translate-x-1/2 border-l-2 border-white/90 shadow-[0_0_0_1px_rgba(0,0,0,0.25)]" />
        <div className="absolute top-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-white/80 bg-ground/80 text-white backdrop-blur">
          <MoveHorizontal className="size-4" />
        </div>
      </div>

      <span className="pointer-events-none absolute left-3 top-3 rounded-md bg-ground/75 px-2 py-1 text-xs text-ink backdrop-blur">{beforeLabel}</span>
      <span className="pointer-events-none absolute right-3 top-3 rounded-md bg-ground/75 px-2 py-1 text-xs text-ink backdrop-blur">{afterLabel}</span>

      <label htmlFor={id} className="sr-only">
        Reveal position between {beforeLabel} and {afterLabel}
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        value={position}
        onChange={(e) => setPosition(Number(e.target.value))}
        className="absolute inset-0 size-full cursor-ew-resize opacity-0"
      />
    </div>
  );
}
