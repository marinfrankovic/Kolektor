import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ItemRow } from "../api/client";
import { useI18n, useT } from "../i18n";
import type { TranslationKey } from "../i18n";

const KINDS = ["coin", "banknote", "token", "set", "other"] as const;
const STATUSES = [
  "owned",
  "wish",
  "ordered",
  "duplicate",
  "for_sale",
  "sold",
  "missing",
] as const;

function ItemCard({ row }: { row: ItemRow }) {
  const t = useT();
  const { countryName } = useI18n();

  return (
    <Link className="item-card" to={`/items/${row.id}`}>
      <div className="thumb">
        {row.thumb_image_id ? (
          <img src={api.imageUrl(row.thumb_image_id, "thumb")} alt="" loading="lazy" />
        ) : (
          <span className="muted small">{t("images.section")}</span>
        )}
      </div>
      <div className="body">
        <strong>{row.title}</strong>
        <div className="row small muted" style={{ gap: "0.35rem", marginTop: "0.25rem" }}>
          <span className="badge">{t(`item.kind.${row.kind}` as TranslationKey)}</span>
          {row.country_code && <span>{countryName(row.country_code)}</span>}
          {row.quantity > 1 && <span>×{row.quantity}</span>}
        </div>
        <div className="meter" title={`${row.completeness}%`}>
          <span style={{ width: `${row.completeness}%` }} />
        </div>
      </div>
    </Link>
  );
}

export default function Collection() {
  const t = useT();
  const { formatNumber, countryName } = useI18n();

  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [country, setCountry] = useState("");
  const [sort, setSort] = useState("updated_at");
  const [page, setPage] = useState(1);

  const countries = useQuery({
    queryKey: ["countries", "used"],
    queryFn: () => api.countries(true),
  });

  const items = useQuery({
    queryKey: ["items", { q, kind, status, country, sort, page }],
    queryFn: () => api.listItems({ q, kind, status, country, sort, page, page_size: 60 }),
  });

  const clear = () => {
    setQ("");
    setKind("");
    setStatus("");
    setCountry("");
    setPage(1);
  };

  const total = items.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / (items.data?.page_size ?? 60)));

  return (
    <div className="stack">
      <div className="spread">
        <h1>{t("collection.title")}</h1>
        <Link to="/items/new">
          <button className="primary">{t("action.addItem")}</button>
        </Link>
      </div>

      <div className="card">
        <div className="grid">
          <div>
            <label htmlFor="f-q">{t("collection.search")}</label>
            <input
              id="f-q"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <div>
            <label htmlFor="f-kind">{t("item.kind")}</label>
            <select
              id="f-kind"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setPage(1);
              }}
            >
              <option value="">{t("common.all")}</option>
              {KINDS.map((value) => (
                <option key={value} value={value}>
                  {t(`item.kind.${value}` as TranslationKey)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-status">{t("item.status")}</label>
            <select
              id="f-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">{t("common.all")}</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {t(`item.status.${value}` as TranslationKey)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-country">{t("item.country")}</label>
            <select
              id="f-country"
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setPage(1);
              }}
            >
              <option value="">{t("common.all")}</option>
              <option value="none">{t("item.noCountry")}</option>
              {(countries.data ?? []).map((c) => (
                <option key={c.code2} value={c.code2}>
                  {countryName(c.code2) || c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-sort">{t("collection.filters")}</label>
            <select id="f-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="updated_at">{t("collection.filters")}</option>
              <option value="title">{t("item.title")}</option>
              <option value="year">{t("item.year")}</option>
              <option value="country_code">{t("item.country")}</option>
              <option value="completeness">{t("item.completeness")}</option>
            </select>
          </div>
        </div>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <span className="muted small">{t("collection.results", { count: formatNumber(total) })}</span>
          <button className="ghost small" onClick={clear}>
            {t("collection.clearFilters")}
          </button>
        </div>
      </div>

      {items.isPending && <p className="muted">{t("common.loading")}</p>}
      {items.isError && <p className="error">{t("common.error")}</p>}

      {items.data && items.data.rows.length === 0 && (
        <div className="card muted">{t("collection.empty")}</div>
      )}

      <div className="item-grid">
        {(items.data?.rows ?? []).map((row) => (
          <ItemCard key={row.id} row={row} />
        ))}
      </div>

      {pages > 1 && (
        <div className="row">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ←
          </button>
          <span className="muted small">
            {page} / {pages}
          </span>
          <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
            →
          </button>
        </div>
      )}
    </div>
  );
}
