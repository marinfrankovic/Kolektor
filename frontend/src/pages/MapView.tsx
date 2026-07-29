import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography, ZoomableGroup } from "react-simple-maps";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useI18n, useT } from "../i18n";

const GEO_URL = "/geo/countries-110m.json";

// Sequential ramp from "nothing yet" to "well covered".
const STEPS = [
  { min: 1, colour: "#3d4a3a" },
  { min: 3, colour: "#4f6440" },
  { min: 6, colour: "#6b7f42" },
  { min: 11, colour: "#96934a" },
  { min: 21, colour: "#c2a054" },
  { min: 51, colour: "#d8a657" },
];

function colourFor(total: number): string {
  if (!total) return "#26303c";
  let colour = STEPS[0].colour;
  for (const step of STEPS) if (total >= step.min) colour = step.colour;
  return colour;
}

export default function MapView() {
  const t = useT();
  const { countryName, formatNumber } = useI18n();
  const navigate = useNavigate();
  const [hover, setHover] = useState<{ x: number; y: number; label: string } | null>(null);

  const stats = useQuery({ queryKey: ["stats", "map"], queryFn: api.mapStats });

  const byNumeric = useMemo(() => {
    const map = new Map<string, (typeof rows)[number]>();
    const rows = stats.data?.countries ?? [];
    for (const row of rows) map.set(row.numeric3, row);
    return map;
  }, [stats.data]);

  return (
    <div className="stack">
      <div className="spread">
        <h1>{t("map.title")}</h1>
        {stats.data && (
          <span className="muted">
            {t("map.covered", {
              covered: formatNumber(stats.data.covered),
              total: formatNumber(stats.data.sovereign_total),
            })}
          </span>
        )}
      </div>

      <div className="map-wrap">
        <ComposableMap
          projection="geoEqualEarth"
          projectionConfig={{ scale: 165 }}
          width={900}
          height={460}
          style={{ background: "#151d26" }}
        >
          <ZoomableGroup center={[10, 15]} maxZoom={8}>
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies.map((geo) => {
                  const row = byNumeric.get(String(geo.id).padStart(3, "0"));
                  const total = row?.total ?? 0;
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={colourFor(total)}
                      stroke="#12181f"
                      strokeWidth={0.4}
                      onMouseMove={(event) =>
                        setHover({
                          x: event.clientX,
                          y: event.clientY,
                          label: `${row ? countryName(row.code2) || row.name : geo.properties?.name}: ${formatNumber(total)}`,
                        })
                      }
                      onMouseLeave={() => setHover(null)}
                      onClick={() => row && total > 0 && navigate(`/?country=${row.code2}`)}
                      style={{
                        default: { outline: "none" },
                        hover: { outline: "none", fill: "#f0c274", cursor: total ? "pointer" : "default" },
                        pressed: { outline: "none" },
                      }}
                    />
                  );
                })
              }
            </Geographies>
          </ZoomableGroup>
        </ComposableMap>
      </div>

      <div className="legend">
        <span>{t("map.legend")}</span>
        <i style={{ background: "#26303c" }} /> 0
        {STEPS.map((step) => (
          <span key={step.min} className="row" style={{ gap: "0.25rem" }}>
            <i style={{ background: step.colour }} /> {step.min}+
          </span>
        ))}
      </div>

      {stats.data && stats.data.countries.length === 0 && (
        <p className="muted">{t("map.noData")}</p>
      )}

      {stats.data && Object.keys(stats.data.by_continent).length > 0 && (
        <div className="stat-grid">
          {Object.entries(stats.data.by_continent).map(([continent, count]) => (
            <div className="stat" key={continent}>
              <b>{formatNumber(count)}</b>
              <span>{continent}</span>
            </div>
          ))}
        </div>
      )}

      {hover && (
        <div className="tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>
          {hover.label}
        </div>
      )}
    </div>
  );
}
