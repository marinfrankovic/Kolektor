import { useEffect } from "react";
import { createPortal } from "react-dom";
import { api, type ItemImage } from "../api/client";
import { useT, type TranslationKey } from "../i18n";

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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onIndex((index - 1 + count) % count);
      if (e.key === "ArrowRight") onIndex((index + 1) % count);
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
    <div className="lightbox" onClick={onClose}>
      <button className="lightbox-close" aria-label={t("images.close")} onClick={onClose}>
        ×
      </button>

      {count > 1 && (
        <button
          className="lightbox-nav prev"
          aria-label={t("images.previous")}
          onClick={(e) => {
            e.stopPropagation();
            onIndex((index - 1 + count) % count);
          }}
        >
          ‹
        </button>
      )}

      <figure onClick={(e) => e.stopPropagation()}>
        <img src={api.imageUrl(image.id, "display")} alt={image.role} />
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
            onIndex((index + 1) % count);
          }}
        >
          ›
        </button>
      )}
    </div>,
    document.body,
  );
}
