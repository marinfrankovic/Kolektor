import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useI18n, useT } from "../i18n";

export default function Stats() {
  const t = useT();
  const { formatNumber } = useI18n();
  const summary = useQuery({ queryKey: ["stats", "summary"], queryFn: api.summary });

  if (summary.isPending) return <p className="muted">{t("common.loading")}</p>;
  if (!summary.data) return <p className="error">{t("common.error")}</p>;

  const data = summary.data;
  const years =
    data.year_min && data.year_max ? `${data.year_min} – ${data.year_max}` : t("common.none");

  const cells: Array<[string, string]> = [
    [t("stats.items"), formatNumber(data.items)],
    [t("stats.pieces"), formatNumber(data.pieces)],
    [t("stats.coins"), formatNumber(data.coins)],
    [t("stats.banknotes"), formatNumber(data.banknotes)],
    [t("stats.countries"), formatNumber(data.countries)],
    [t("stats.images"), formatNumber(data.images)],
    [t("stats.years"), years],
    [t("stats.completeness"), `${Math.round(data.average_completeness)}%`],
  ];

  return (
    <div className="stack">
      <h1>{t("stats.title")}</h1>

      <div className="stat-grid">
        {cells.map(([label, value]) => (
          <div className="stat" key={label}>
            <b>{value}</b>
            <span>{label}</span>
          </div>
        ))}
      </div>

      {Object.keys(data.spend_by_currency).length > 0 && (
        <div className="card">
          <h3>{t("stats.spend")}</h3>
          <div className="stat-grid">
            {Object.entries(data.spend_by_currency).map(([currency, amount]) => (
              <div className="stat" key={currency}>
                <b>{amount}</b>
                <span>{currency}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
