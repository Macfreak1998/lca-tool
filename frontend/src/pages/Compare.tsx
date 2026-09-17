import { useEffect, useMemo, useState } from "react";
import { DataApi, download } from "../api";
import { MetaApi } from "../api";
import type { CalcResult, Configuration, Indicator } from "../types";

export function ComparePage() {
  const [rows, setRows] = useState<Configuration[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [items, setItems] = useState<{ configuration: Configuration; result: CalcResult }[]>([]);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([DataApi.configurations(), MetaApi.indicators()]).then(([c, i]) => {
      setRows(c);
      setIndicators(i);
    });
  }, []);

  function toggle(id: number) {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= 4) return current;
      return [...current, id];
    });
  }

  async function run() {
    setError("");
    try {
      const data = await DataApi.compare(selected);
      setItems(data.items);
      setBlockers(data.blockers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vergleich fehlgeschlagen.");
    }
  }

  const maxClimate = useMemo(() => {
    return Math.max(0, ...items.map((item) => item.result.totals.climate_change || 0));
  }, [items]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-forest-800">Vergleich</h1>
        <p className="text-sm text-slate-600">2 bis 4 Konfigurationen, gleiches Endprodukt, Menge und Einheit. Diagramm zeigt nur Summen.</p>
      </div>
      <div className="card space-y-2">
        {rows.map((row) => (
          <label key={row.id} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={selected.includes(row.id)} onChange={() => toggle(row.id)} />
            {row.name} · {row.chain_name} · {row.end_amount} {row.end_unit}
            {row.invalid ? " (ungültig)" : ""}
          </label>
        ))}
        <div className="flex gap-2 pt-2">
          <button className="btn" type="button" onClick={() => void run()}>
            Vergleichen
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={() => void download("/api/compare/export?format=csv", { configuration_ids: selected }, "vergleich.csv")}
          >
            CSV
          </button>
          <button
            className="btn-secondary"
            type="button"
            onClick={() => void download("/api/compare/export?format=xlsx", { configuration_ids: selected }, "vergleich.xlsx")}
          >
            Excel
          </button>
        </div>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {blockers.length > 0 && (
        <ul className="card text-sm text-red-700">
          {blockers.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      {items.length > 0 && items.every((item) => item.result.mode === "inventory") && (
        <div className="card space-y-3">
          <h2 className="font-semibold">Inventar</h2>
          <p className="text-sm text-slate-600">
            Noch keine LCIA-Datei — Vergleich der Inventar-Kurzfassung. Die volle Flussliste steht im Export.
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-slate-500">
                <th className="py-2">Konfiguration</th>
                <th>Flüsse</th>
                <th>Katalog</th>
                <th>Eigene</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.configuration.id} className="border-b last:border-0">
                  <td className="py-2">{item.configuration.name}</td>
                  <td>{item.result.inventory_summary?.flow_count ?? 0}</td>
                  <td>{item.result.inventory_summary?.catalog_dataset_count ?? 0}</td>
                  <td>{item.result.inventory_summary?.user_dataset_count ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {items.length > 0 && items.some((item) => item.result.mode !== "inventory") && (
        <div className="card space-y-4">
          <h2 className="font-semibold">Klimawandel</h2>
          {items.map((item) => {
            const value = item.result.totals.climate_change || 0;
            const width = maxClimate ? (value / maxClimate) * 100 : 0;
            return (
              <div key={item.configuration.id}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>{item.configuration.name}</span>
                  <span>{value.toPrecision(4)} kg CO₂-Äq.</span>
                </div>
                <div className="h-3 rounded bg-slate-100">
                  <div className="h-3 rounded bg-forest-600" style={{ width: `${width}%` }} />
                </div>
              </div>
            );
          })}
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-slate-500">
                <th className="py-2">Indikator</th>
                {items.map((item) => (
                  <th key={item.configuration.id}>{item.configuration.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {indicators
                .filter((indicator) => items.some((item) => item.result.totals[indicator.id] != null))
                .map((indicator) => (
                  <tr key={indicator.id} className="border-b last:border-0">
                    <td className="py-2">{indicator.label}</td>
                    {items.map((item) => (
                      <td key={item.configuration.id}>
                        {item.result.totals[indicator.id] != null ? item.result.totals[indicator.id].toPrecision(4) : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
