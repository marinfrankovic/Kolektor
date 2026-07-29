import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  api,
  ApiError,
  type CatalogRef,
  type ImageRole,
  type Item,
  type Kind,
  type Suggestion,
} from "../api/client";
import { useI18n, useT, type TranslationKey } from "../i18n";
import Lightbox from "../components/Lightbox";
import { toDisplayDate, toIsoDate } from "../lib/dates";

const KINDS: Kind[] = ["coin", "banknote", "token", "set", "other"];
const STATUSES = [
  "owned",
  "wish",
  "ordered",
  "duplicate",
  "for_sale",
  "sold",
  "missing",
] as const;

const COIN_ROLES: ImageRole[] = ["obverse", "reverse", "edge", "detail", "certificate", "other"];
const NOTE_ROLES: ImageRole[] = ["face", "back", "watermark", "detail", "certificate", "other"];

type Draft = Record<string, unknown>;

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label>{label}</label>
      {children}
    </div>
  );
}

function useDraft(item: Item | undefined, kind: Kind) {
  const [draft, setDraft] = useState<Draft>({});

  useEffect(() => {
    setDraft({});
  }, [item?.id]);

  const value = <T,>(path: string, fallback: T): T => {
    if (path in draft) return draft[path] as T;
    const [head, tail] = path.split(".");
    const source = tail
      ? ((item as unknown as Record<string, Record<string, unknown>> | undefined)?.[head] ?? {})
      : ((item as unknown as Record<string, unknown> | undefined) ?? {});
    const raw = tail ? source[tail] : (source as Record<string, unknown>)[head];
    return (raw ?? fallback) as T;
  };

  const set = (path: string, next: unknown) => setDraft((d) => ({ ...d, [path]: next }));

  const payload = (): Draft => {
    const body: Draft = { kind };
    const nested: Record<string, Draft> = {};

    for (const [path, raw] of Object.entries(draft)) {
      const next = raw === "" ? null : raw;
      const [head, tail] = path.split(".");
      if (tail) {
        nested[head] = { ...(nested[head] ?? {}), [tail]: next };
      } else {
        body[head] = next;
      }
    }

    for (const [group, fields] of Object.entries(nested)) {
      const existing = (item as unknown as Record<string, Draft | null> | undefined)?.[group] ?? {};
      body[group] = { ...existing, ...fields };
    }
    return body;
  };

  return { value, set, payload, dirty: Object.keys(draft).length > 0, reset: () => setDraft({}) };
}

function SuggestionList({
  suggestions,
  onAccept,
}: {
  suggestions: Suggestion[];
  onAccept: (field: string, value: string | number) => void;
}) {
  const t = useT();
  const [dismissed, setDismissed] = useState<string[]>([]);
  const visible = suggestions.filter((s) => !dismissed.includes(`${s.field}:${s.value}`));

  if (visible.length === 0) return null;

  return (
    <div className="card">
      <h3>{t("suggestions.title")}</h3>
      <p className="muted small">{t("suggestions.hint")}</p>
      <div className="stack">
        {visible.map((s) => (
          <div className="spread" key={`${s.field}:${s.value}`}>
            <span className="small">
              <code>{s.field}</code> → <strong>{String(s.value)}</strong>{" "}
              <span className="muted">({Math.round(s.confidence * 100)}%)</span>
            </span>
            <span className="row">
              <button className="small" onClick={() => onAccept(s.field, s.value)}>
                {t("suggestions.accept")}
              </button>
              <button
                className="ghost small"
                onClick={() => setDismissed((d) => [...d, `${s.field}:${s.value}`])}
              >
                {t("suggestions.dismiss")}
              </button>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ItemEdit() {
  const { id = "" } = useParams();
  const t = useT();
  const { countryName } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const itemQuery = useQuery({
    queryKey: ["item", id],
    queryFn: () => api.getItem(id),
    refetchInterval: (query) =>
      query.state.data?.images.some((image) => image.status === "pending" || image.status === "processing")
        ? 2500
        : false,
  });

  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: () => api.countries(),
    staleTime: Infinity,
  });

  const item = itemQuery.data;
  const [kind, setKind] = useState<Kind>("coin");
  useEffect(() => {
    if (item) setKind(item.kind);
  }, [item?.id, item?.kind]);

  const draft = useDraft(item, kind);
  const [catalogRefs, setCatalogRefs] = useState<CatalogRef[]>([]);
  const [photoUrl, setPhotoUrl] = useState("");
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setCatalogRefs(item?.catalog_refs ?? []);
  }, [item?.id]);

  const save = useMutation({
    mutationFn: async () => {
      const body = { ...draft.payload(), catalog_refs: catalogRefs.map((r) => ({ catalog: r.catalog, number: r.number })) };
      return api.updateItem(id, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["item", id] });
      draft.reset();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : t("common.error")),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      navigate("/");
    },
  });

  const upload = useMutation({
    mutationFn: async ({ file, role }: { file: File; role: ImageRole }) =>
      api.uploadImage(id, role, file, file.name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["item", id] }),
  });

  const importFromUrl = useMutation({
    mutationFn: async ({ url, role }: { url: string; role: ImageRole }) =>
      api.importImage(id, role, url),
    onSuccess: () => {
      setPhotoUrl("");
      queryClient.invalidateQueries({ queryKey: ["item", id] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : t("images.linkFailed")),
  });

  const imageAction = useMutation({
    mutationFn: async ({ action, imageId }: { action: "reprocess" | "delete"; imageId: string }) =>
      action === "reprocess" ? api.reprocessImage(imageId) : api.deleteImage(imageId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["item", id] }),
  });

  const roles = kind === "banknote" ? NOTE_ROLES : COIN_ROLES;

  const suggestions = useMemo(
    () => (item?.images ?? []).flatMap((image) => image.suggestions ?? []),
    [item],
  );

  if (itemQuery.isPending) return <p className="muted">{t("common.loading")}</p>;

  const text = (path: string, label: string, type = "text") => (
    <Field label={label}>
      <input
        type={type}
        value={String(draft.value(path, "") ?? "")}
        onChange={(e) => draft.set(path, e.target.value)}
      />
    </Field>
  );

  const dateField = (path: string, label: string) => (
    <Field label={`${label} (dd/mm/yyyy)`}>
      <input
        inputMode="numeric"
        placeholder="dd/mm/yyyy"
        defaultValue={toDisplayDate(String(draft.value(path, "") ?? ""))}
        onBlur={(e) => {
          const typed = e.target.value.trim();
          const iso = typed ? toIsoDate(typed) : "";
          if (iso === null) return;
          draft.set(path, iso);
          e.target.value = toDisplayDate(iso);
        }}
      />
    </Field>
  );

  const photos = item?.images ?? [];
  const viewable = photos.filter((image) => image.status === "ready");

  const photosCard = (
    <div className="card">
      <h3>{t("images.section")}</h3>
      <div className="thumbs">
        {photos.map((image) => (
          <figure key={image.id}>
            {image.status === "ready" ? (
              <button
                className="thumb-open"
                aria-label={t(`images.role.${image.role}` as TranslationKey)}
                onClick={() => setLightbox(viewable.findIndex((other) => other.id === image.id))}
              >
                <img src={api.imageUrl(image.id, "preview")} alt={image.role} loading="lazy" />
              </button>
            ) : (
              <div
                className="muted small"
                style={{ aspectRatio: 1, display: "grid", placeItems: "center" }}
              >
                {image.status === "failed" ? t("images.failed") : t("images.pending")}
              </div>
            )}
            <figcaption>
              <select
                value={image.role}
                onChange={(e) =>
                  api
                    .updateImage(image.id, { role: e.target.value as ImageRole })
                    .then(() => queryClient.invalidateQueries({ queryKey: ["item", id] }))
                }
              >
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {t(`images.role.${role}` as TranslationKey)}
                  </option>
                ))}
              </select>
              <div className="thumb-actions">
                <button
                  className="icon"
                  title={t("images.reprocess")}
                  aria-label={t("images.reprocess")}
                  onClick={() => imageAction.mutate({ action: "reprocess", imageId: image.id })}
                >
                  ↻
                </button>
                <a
                  className="icon"
                  title={t("images.original")}
                  aria-label={t("images.original")}
                  href={api.imageUrl(image.id, "original")}
                  target="_blank"
                  rel="noreferrer"
                >
                  ⤓
                </a>
                <button
                  className="icon danger"
                  title={t("action.delete")}
                  aria-label={t("action.delete")}
                  onClick={() =>
                    window.confirm(t("action.confirmDelete")) &&
                    imageAction.mutate({ action: "delete", imageId: image.id })
                  }
                >
                  ×
                </button>
              </div>
            </figcaption>
          </figure>
        ))}
      </div>
      <div className="row" style={{ marginTop: "0.75rem" }}>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate({ file, role: roles[0] });
            e.target.value = "";
          }}
        />
        {upload.isPending && <span className="muted small">{t("images.uploading")}</span>}
      </div>
      <div className="row" style={{ marginTop: "0.5rem" }}>
        <input
          style={{ flex: 1 }}
          type="url"
          inputMode="url"
          placeholder={t("images.urlPlaceholder")}
          value={photoUrl}
          onChange={(e) => setPhotoUrl(e.target.value)}
        />
        <button
          className="ghost small"
          disabled={!photoUrl.trim() || importFromUrl.isPending}
          onClick={() => {
            setError("");
            importFromUrl.mutate({ url: photoUrl.trim(), role: roles[0] });
          }}
        >
          {importFromUrl.isPending ? t("images.uploading") : t("images.addLink")}
        </button>
      </div>
    </div>
  );

  return (
    <div className="stack">
      {lightbox !== null && viewable[lightbox] && (
        <Lightbox
          images={viewable}
          index={lightbox}
          onIndex={setLightbox}
          onClose={() => setLightbox(null)}
        />
      )}

      <div className="spread">
        <h1>{item?.title}</h1>
        <div className="row">
          <button className="ghost" onClick={() => navigate("/")}>
            {t("action.back")}
          </button>
          <button
            className="danger"
            onClick={() => window.confirm(t("action.confirmDelete")) && remove.mutate()}
          >
            {t("action.delete")}
          </button>
          <button className="primary" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? t("action.saving") : t("action.save")}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {photosCard}

      {item && item.warnings.length > 0 && (
        <div className="card small muted">
          {item.warnings.map((warning) => (
            <div key={warning}>⚠ {t(`warning.${warning}` as TranslationKey)}</div>
          ))}
        </div>
      )}

      {suggestions.length > 0 && (
        <SuggestionList
          suggestions={suggestions}
          onAccept={(field, value) => draft.set(field, value)}
        />
      )}

      <div className="card">
        <h3>{t("collection.title")}</h3>
        <div className="grid">
          <Field label={t("item.kind")}>
            <select value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
              {KINDS.map((value) => (
                <option key={value} value={value}>
                  {t(`item.kind.${value}` as TranslationKey)}
                </option>
              ))}
            </select>
          </Field>

          <Field label={t("item.status")}>
            <select
              value={String(draft.value("status", "owned"))}
              onChange={(e) => draft.set("status", e.target.value)}
            >
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {t(`item.status.${value}` as TranslationKey)}
                </option>
              ))}
            </select>
          </Field>

          {text("title", t("item.title"))}

          <Field label={t("item.country")}>
            <select
              value={String(draft.value("country_code", "") ?? "")}
              onChange={(e) => draft.set("country_code", e.target.value)}
            >
              <option value="">{t("common.unknown")}</option>
              {(countries.data ?? []).map((c) => (
                <option key={c.code2} value={c.code2}>
                  {countryName(c.code2) || c.name}
                </option>
              ))}
            </select>
          </Field>

          {text("issuing_entity", t("item.issuer"))}
          {text("region", t("item.region"))}
          {text("period", t("item.period"))}
          {text("ruler", t("item.ruler"))}
          {text("denomination_value", t("item.denomination"), "number")}
          {text("currency_unit", t("item.currency"))}
          {text("year", t("item.year"), "number")}
          {text("year_text", t("item.yearText"))}
          {text("series", t("item.series"))}
          {text("subject", t("item.subject"))}
          {text("quantity", t("item.quantity"), "number")}
          {text("grade_value", t("item.grade"))}
          {text("grade_scale", t("item.gradeScale"))}
          {text("grader", t("item.grader"))}
          {text("cert_number", t("item.certNumber"))}
          {text("rarity", t("item.rarity"))}
          {text("storage", t("item.storage"))}
          {text("slot", t("item.slot"))}
          {text("barcode", t("item.barcode"))}
        </div>

        <div style={{ marginTop: "0.75rem" }}>
          <Field label={t("item.tags")}>
            <input
              value={(draft.value<string[]>("tags", item?.tags ?? []) as string[]).join(", ")}
              onChange={(e) =>
                draft.set(
                  "tags",
                  e.target.value
                    .split(",")
                    .map((tag) => tag.trim())
                    .filter(Boolean),
                )
              }
            />
          </Field>
          <Field label={t("item.notes")}>
            <textarea
              value={String(draft.value("notes", "") ?? "")}
              onChange={(e) => draft.set("notes", e.target.value)}
            />
          </Field>
        </div>
      </div>

      {kind === "coin" && (
        <div className="card">
          <h3>{t("coin.section")}</h3>
          <div className="grid">
            {text("coin.diameter_mm", t("coin.diameter"), "number")}
            {text("coin.weight_g", t("coin.weight"), "number")}
            {text("coin.thickness_mm", t("coin.thickness"), "number")}
            {text("coin.shape", t("coin.shape"))}
            {text("coin.edge_type", t("coin.edge"))}
            {text("coin.edge_lettering", t("coin.edgeLettering"))}
            {text("coin.die_axis", t("coin.dieAxis"))}
            {text("coin.composition", t("coin.composition"))}
            {text("coin.material", t("coin.material"))}
            {text("coin.fineness", t("coin.fineness"), "number")}
            {text("coin.mint", t("coin.mint"))}
            {text("coin.mintmark", t("coin.mintmark"))}
            {text("coin.mintage", t("coin.mintage"), "number")}
            {text("coin.quality", t("coin.quality"))}
          </div>
        </div>
      )}

      {kind === "banknote" && (
        <div className="card">
          <h3>{t("note.section")}</h3>
          <div className="grid">
            {text("banknote.width_mm", t("note.width"), "number")}
            {text("banknote.height_mm", t("note.height"), "number")}
            {text("banknote.substrate", t("note.substrate"))}
            {text("banknote.pick_number", t("note.pick"))}
            {text("banknote.serial_number", t("note.serial"))}
            {text("banknote.serial_prefix", t("note.serialPrefix"))}
            {text("banknote.serial_suffix", t("note.serialSuffix"))}
            {text("banknote.block", t("note.block"))}
            {text("banknote.plate", t("note.plate"))}
            {text("banknote.signature_combination", t("note.signatures"))}
            {text("banknote.signatories", t("note.signatories"))}
            {text("banknote.printer", t("note.printer"))}
            {text("banknote.watermark", t("note.watermark"))}
            {text("banknote.security_thread", t("note.thread"))}
            {text("banknote.overprint", t("note.overprint"))}
            {text("banknote.series_year", t("note.seriesYear"))}
            <Field label={t("note.replacement")}>
              <select
                value={draft.value("banknote.is_replacement", false) ? "1" : "0"}
                onChange={(e) => draft.set("banknote.is_replacement", e.target.value === "1")}
              >
                <option value="0">{t("common.no")}</option>
                <option value="1">{t("common.yes")}</option>
              </select>
            </Field>
          </div>
        </div>
      )}

      <div className="card">
        <h3>{t("money.acquisition")}</h3>
        <div className="grid">
          {dateField("acquisition.date", t("money.date"))}
          {text("acquisition.price", t("money.price"), "number")}
          {text("acquisition.currency", t("money.currency"))}
          {text("acquisition.counterparty", t("money.counterparty"))}
          {text("acquisition.place", t("money.place"))}
        </div>
        <h3 style={{ marginTop: "1rem" }}>{t("money.disposal")}</h3>
        <div className="grid">
          {dateField("disposal.date", t("money.date"))}
          {text("disposal.price", t("money.price"), "number")}
          {text("disposal.currency", t("money.currency"))}
          {text("disposal.counterparty", t("money.counterparty"))}
        </div>
      </div>

      <div className="card">
        <h3>{t("catalog.section")}</h3>
        <div className="stack">
          {catalogRefs.map((ref, index) => (
            <div className="row" key={index}>
              <input
                style={{ flex: 1 }}
                placeholder={t("catalog.name")}
                value={ref.catalog}
                onChange={(e) =>
                  setCatalogRefs((refs) =>
                    refs.map((r, i) => (i === index ? { ...r, catalog: e.target.value } : r)),
                  )
                }
              />
              <input
                style={{ flex: 1 }}
                placeholder={t("catalog.number")}
                value={ref.number}
                onChange={(e) =>
                  setCatalogRefs((refs) =>
                    refs.map((r, i) => (i === index ? { ...r, number: e.target.value } : r)),
                  )
                }
              />
              <button
                className="ghost"
                onClick={() => setCatalogRefs((refs) => refs.filter((_, i) => i !== index))}
              >
                ×
              </button>
            </div>
          ))}
          <button
            className="ghost small"
            onClick={() => setCatalogRefs((refs) => [...refs, { catalog: "", number: "" }])}
          >
            {t("action.add")}
          </button>
        </div>
      </div>
    </div>
  );
}
