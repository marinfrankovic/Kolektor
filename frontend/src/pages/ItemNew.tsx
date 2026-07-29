import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type ImageRole, type Kind } from "../api/client";
import { BLUR_THRESHOLD, blurScore } from "../lib/blur";
import { useI18n, useT, type TranslationKey } from "../i18n";

type Photo = { file: File; preview: string } | { url: string };

const KINDS: Kind[] = ["coin", "banknote", "token", "set", "other"];

function rolesFor(kind: Kind): [ImageRole, ImageRole] {
  return kind === "banknote" ? ["face", "back"] : ["obverse", "reverse"];
}

function PhotoSlot({
  label,
  photo,
  onPick,
}: {
  label: string;
  photo: Photo | null;
  onPick: (photo: Photo | null) => void;
}) {
  const t = useT();
  const input = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [broken, setBroken] = useState(false);

  const choose = async (file: File) => {
    if ((await blurScore(file)) < BLUR_THRESHOLD && !window.confirm(t("images.blurry"))) return;
    onPick({ file, preview: URL.createObjectURL(file) });
  };

  const source = photo && ("file" in photo ? photo.preview : photo.url);

  return (
    <div className="photo-slot">
      <label>{label}</label>
      <div className="photo-frame">
        {source && !broken ? (
          <img src={source} alt={label} onError={() => setBroken(true)} />
        ) : (
          <span className="muted small">{broken ? t("images.linkFailed") : "—"}</span>
        )}
      </div>

      <input
        ref={input}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            setBroken(false);
            choose(file);
          }
          e.target.value = "";
        }}
      />

      <div className="row">
        <button className={photo ? "ghost small" : "small"} onClick={() => input.current?.click()}>
          {photo ? t("new.replace") : t("new.choose")}
        </button>
        {photo && (
          <button className="ghost small" onClick={() => onPick(null)}>
            ×
          </button>
        )}
      </div>

      <div className="row">
        <input
          style={{ flex: 1 }}
          type="url"
          inputMode="url"
          placeholder={t("images.urlPlaceholder")}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button
          className="ghost small"
          disabled={!url.trim()}
          onClick={() => {
            setBroken(false);
            onPick({ url: url.trim() });
          }}
        >
          {t("images.addLink")}
        </button>
      </div>
    </div>
  );
}

export default function ItemNew() {
  const t = useT();
  const { countryName } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<1 | 2>(1);
  const [kind, setKind] = useState<Kind>("coin");
  const [front, setFront] = useState<Photo | null>(null);
  const [back, setBack] = useState<Photo | null>(null);

  const [title, setTitle] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [denomination, setDenomination] = useState("");
  const [year, setYear] = useState("");
  const [error, setError] = useState("");

  // Kept so a failed photo upload retries against the item instead of creating a second one.
  const createdId = useRef<string | null>(null);
  const uploaded = useRef<Set<ImageRole>>(new Set());

  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: api.countries,
    staleTime: Infinity,
  });

  const [frontRole, backRole] = rolesFor(kind);
  const ready = front !== null && back !== null;
  const complete = title.trim() && country && currency.trim() && denomination.trim();

  const create = useMutation({
    mutationFn: async () => {
      if (!createdId.current) {
        const item = await api.createItem({
          kind,
          title: title.trim(),
          country_code: country,
          currency_unit: currency.trim(),
          denomination_value: denomination.trim(),
          year: year.trim() ? Number(year) : null,
        });
        createdId.current = item.id;
      }

      const id = createdId.current;
      for (const [role, photo] of [
        [frontRole, front],
        [backRole, back],
      ] as [ImageRole, Photo | null][]) {
        if (!photo || uploaded.current.has(role)) continue;
        if ("file" in photo) await api.uploadImage(id, role, photo.file, photo.file.name);
        else await api.importImage(id, role, photo.url);
        uploaded.current.add(role);
      }
      return id;
    },
    onSuccess: (id) => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      navigate(`/items/${id}`, { replace: true });
    },
    onError: (err) => {
      const detail = err instanceof ApiError ? String(err.detail ?? err.message) : t("common.error");
      setError(createdId.current ? `${t("new.uploadFailed")} ${detail}` : detail);
    },
  });

  return (
    <div className="stack">
      <div className="spread">
        <h1>{t("new.title")}</h1>
        <button className="ghost" onClick={() => navigate("/")}>
          {t("action.back")}
        </button>
      </div>

      <ol className="steps">
        <li className={step === 1 ? "active" : "done"}>1. {t("new.stepPhotos")}</li>
        <li className={step === 2 ? "active" : ""}>2. {t("new.stepDetails")}</li>
      </ol>

      {error && <p className="error">{error}</p>}

      {step === 1 ? (
        <div className="card stack">
          <p className="muted small">{t("new.photosHint")}</p>

          <div>
            <label htmlFor="n-kind">{t("item.kind")}</label>
            <select id="n-kind" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
              {KINDS.map((value) => (
                <option key={value} value={value}>
                  {t(`item.kind.${value}` as TranslationKey)}
                </option>
              ))}
            </select>
          </div>

          <div className="photo-slots">
            <PhotoSlot
              label={t(`images.role.${frontRole}` as TranslationKey)}
              photo={front}
              onPick={setFront}
            />
            <PhotoSlot
              label={t(`images.role.${backRole}` as TranslationKey)}
              photo={back}
              onPick={setBack}
            />
          </div>

          <div className="row">
            <button
              className="primary"
              disabled={!ready}
              onClick={() => {
                setError("");
                setStep(2);
              }}
            >
              {t("new.next")}
            </button>
            {!ready && <span className="muted small">{t("new.needBothPhotos")}</span>}
          </div>
        </div>
      ) : (
        <div className="card stack">
          <p className="muted small">{t("new.detailsHint")}</p>

          <div className="grid">
            <div>
              <label htmlFor="n-title">{t("item.title")}</label>
              <input id="n-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div>
              <label htmlFor="n-country">{t("item.country")}</label>
              <select id="n-country" value={country} onChange={(e) => setCountry(e.target.value)}>
                <option value="">{t("common.unknown")}</option>
                {(countries.data ?? []).map((c) => (
                  <option key={c.code2} value={c.code2}>
                    {countryName(c.code2) || c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="n-currency">{t("item.currency")}</label>
              <input id="n-currency" value={currency} onChange={(e) => setCurrency(e.target.value)} />
            </div>
            <div>
              <label htmlFor="n-denomination">{t("item.denomination")}</label>
              <input
                id="n-denomination"
                type="number"
                step="any"
                value={denomination}
                onChange={(e) => setDenomination(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="n-year">{t("new.yearOptional")}</label>
              <input
                id="n-year"
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </div>
          </div>

          <div className="row">
            <button className="ghost" onClick={() => setStep(1)}>
              {t("action.back")}
            </button>
            <button
              className="primary"
              disabled={!complete || create.isPending}
              onClick={() => {
                setError("");
                create.mutate();
              }}
            >
              {create.isPending ? t("new.creating") : t("new.create")}
            </button>
            {!complete && <span className="muted small">{t("new.missingFields")}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
