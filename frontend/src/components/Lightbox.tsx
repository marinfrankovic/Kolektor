import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type ItemImage } from "../api/client";
import { useT, type TranslationKey } from "../i18n";

const MIN_ZOOM = 1;
const MAX_ZOOM = 6;
const STEP = 0.4;

const clampZoom = (value: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));

export default function Lightbox({
  images,
  index,
  onIndex,
  onClose,
}: {
  images: ItemImage[];
  index: number;
  onIndex: (next: number) => void;
  onClose: () => void;
}) {
  const t = useT();
  const count = images.length;
  const image = images[index];

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  const reset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const zoomBy = (delta: number) =>
    setZoom((current) => {
      const next = clampZoom(current + delta);
      if (next === 1) setPan({ x: 0, y: 0 });
      return next;
    });

  const show = (next: number) => {
    reset();
    onIndex(next);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") show((index - 1 + count) % count);
      if (e.key === "ArrowRight") show((index + 1) % count);
      if (e.key === "+" || e.key === "=") zoomBy(STEP);
      if (e.key === "-") zoomBy(-STEP);
      if (e.key === "0") reset();
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [index, count, onIndex, onClose]);

  if (!image) return null;

  return createPortal(
    <div className="lightbox" onClick={onClose} onWheel={(e) => zoomBy(e.deltaY < 0 ? STEP : -STEP)}>
      <button className="lightbox-close" aria-label={t("images.close")} onClick={onClose}>
        ×
      </button>

      {count > 1 && (
        <button
          className="lightbox-nav prev"
          aria-label={t("images.previous")}
          onClick={(e) => {
            e.stopPropagation();
            show((index - 1 + count) % count);
          }}
        >
          ‹
        </button>
      )}

      <figure onClick={(e) => e.stopPropagation()}>
        <div className="lightbox-stage">
          <img
            src={api.imageUrl(image.id, "display")}
            alt={image.role}
            draggable={false}
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              cursor: zoom > 1 ? "grab" : "zoom-in",
            }}
            onDoubleClick={() => (zoom > 1 ? reset() : setZoom(2))}
            onPointerDown={(e) => {
              if (zoom === 1) return;
              drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
              e.currentTarget.setPointerCapture(e.pointerId);
            }}
            onPointerMove={(e) => {
              if (!drag.current) return;
              setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
            }}
            onPointerUp={() => {
              drag.current = null;
            }}
          />
        </div>
        <figcaption>
          {t(`images.role.${image.role}` as TranslationKey)}
          {count > 1 && ` · ${index + 1}/${count}`}
        </figcaption>
      </figure>

      {count > 1 && (
        <button
          className="lightbox-nav next"
          aria-label={t("images.next")}
          onClick={(e) => {
            e.stopPropagation();
            show((index + 1) % count);
          }}
        >
          ›
        </button>
      )}

      <div className="lightbox-zoom" onClick={(e) => e.stopPropagation()}>
        <button aria-label={t("images.zoomOut")} disabled={zoom <= MIN_ZOOM} onClick={() => zoomBy(-STEP)}>
          −
        </button>
        <button className="level" aria-label={t("images.zoomReset")} onClick={reset}>
          {Math.round(zoom * 100)}%
        </button>
        <button aria-label={t("images.zoomIn")} disabled={zoom >= MAX_ZOOM} onClick={() => zoomBy(STEP)}>
          +
        </button>
      </div>
    </div>,
    document.body,
  );
}
