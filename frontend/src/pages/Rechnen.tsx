import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DataApi, MetaApi, defaultPayload, download } from "../api";
import type {
  CalcResult,
  CalculatePayload,
  Chain,
  Dataset,
  EndProduct,
  Slot,
  Indicator,
  Role,
} from "../types";

function sourceLabel(kind: string) {
  if (kind === "ecoinvent") return "ecoinvent";
  if (kind === "catalog_manual") return "Katalog";
  return "eigen";
}

export function RechnenPage() {
  const [params, setParams] = useSearchParams();
  const [products, setProducts] = useState<EndProduct[]>([]);
  const [chains, setChains] = useState<Chain[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [catalog, setCatalog] = useState<Dataset[]>([]);
  const [own, setOwn] = useState<Dataset[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [productId, setProductId] = useState<number | "">("");
  const [chain, setChain] = useState<Chain | null>(null);
  const [payload, setPayload] = useState<CalculatePayload | null>(null);
  const [result, setResult] = useState<CalcResult | null>(null);
  const [saveName, setSaveName] = useState("Konfiguration");
  const [error, setError] = useState("");

  const productChains = useMemo(
    () => chains.filter((item) => item.status === "published" && (productId === "" || item.end_product_id === productId)),
    [chains, productId],
  );
  const roleById = useMemo(() => Object.fromEntries(roles.map((role) => [role.id, role])), [roles]);

  useEffect(() => {
    void Promise.all([
      DataApi.endProducts(),
      DataApi.chains(),
      DataApi.roles(),
      DataApi.datasets(),
      DataApi.userDatasets(),
      MetaApi.indicators(),
    ]).then(([p, c, r, d, u, i]) => {
      setProducts(p);
      setChains(c);
      setRoles(r);
      setCatalog(d);
      setOwn(u);
      setIndicators(i);
      const fromQuery = Number(params.get("chain") || 0);
      const first = c.find((item) => item.id === fromQuery && item.status === "published") || c.find((item) => item.status === "published");
      if (first) {
        setProductId(first.end_product_id);
        setChain(first);
        setPayload(defaultPayload(first));
      } else if (p[0]) {
        setProductId(p[0].id);
      }
    });
  }, []);

  function optionsFor(roleId: number) {
    return [...catalog.filter((item) => item.role_ids.includes(roleId)), ...own.filter((item) => item.role_ids.includes(roleId))];
  }

  function pickChain(id: number) {
    const next = chains.find((item) => item.id === id) || null;
    setChain(next);
    setPayload(next ? defaultPayload(next) : null);
    setResult(null);
    setParams(id ? { chain: String(id) } : {});
  }

  async function run() {
    if (!payload) return;
    setError("");
    try {
      const data = await DataApi.calculate(payload);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rechnung fehlgeschlagen.");
    }
  }

  async function save() {
    if (!payload || payload.end_amount == null) return;
    await DataApi.saveConfiguration({ name: saveName, ...payload });
  }

  const leafStages = useMemo(() => {
    if (!chain) return [];
    const skipped = new Set<number>();
    const incoming: Record<number, number[]> = {};
    chain.stages.forEach((stage) => {
      if (stage.outgoing_stage_id) {
        incoming[stage.outgoing_stage_id] = incoming[stage.outgoing_stage_id] || [];
        incoming[stage.outgoing_stage_id].push(stage.id);
      }
    });
    function walk(id: number) {
      (incoming[id] || []).forEach((prev) => {
        skipped.add(prev);
        walk(prev);
      });
    }
    Object.keys(payload?.replaced_stages || {}).forEach((id) => walk(Number(id)));
    return [...chain.stages].sort((a, b) => b.sort_order - a.sort_order).filter((stage) => !skipped.has(stage.id));
  }, [chain, payload]);

  if (!products.length) {
    return <p>Noch kein veröffentlichtes Endprodukt. Die Administration muss zuerst eine Kette anlegen.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-forest-800">Rechnung</h1>
        <p className="text-sm text-slate-600">Zuerst Endprodukt, dann Kette, dann nur die Blätter. Faktoren erscheinen erst nach der Rechnung.</p>
      </div>
      <div className="card grid gap-4 md:grid-cols-3">
        <div>
          <label className="label">Endprodukt</label>
          <select
            className="input"
            value={productId}
            onChange={(e) => {
              const id = Number(e.target.value);
              setProductId(id);
              const next = chains.find((item) => item.end_product_id === id && item.status === "published");
              if (next) pickChain(next.id);
            }}
          >
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.unit})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Kette</label>
          <select className="input" value={chain?.id || ""} onChange={(e) => pickChain(Number(e.target.value))}>
            {productChains.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Endmenge ({chain?.end_unit || "—"})</label>
          <input
            className="input"
            type="number"
            step="any"
            value={payload?.end_amount ?? ""}
            onChange={(e) =>
              payload && setPayload({ ...payload, end_amount: e.target.value === "" ? null : Number(e.target.value) })
            }
          />
        </div>
      </div>

      {chain && payload &&
        leafStages.map((stage) => {
          const replaced = payload.replaced_stages[String(stage.id)];
          const isEnd = stage.outgoing_stage_id == null;
          return (
            <section key={stage.id} className="card space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">{stage.name}</h2>
                {!isEnd && (
                  <select
                    className="input max-w-md"
                    value={replaced || ""}
                    onChange={(e) => {
                      const next = { ...payload.replaced_stages };
                      if (e.target.value) next[String(stage.id)] = Number(e.target.value);
                      else delete next[String(stage.id)];
                      setPayload({ ...payload, replaced_stages: next });
                    }}
                  >
                    <option value="">Zwischenprodukt fließt (kein Ersatz)</option>
                    {own.map((item) => (
                      <option key={item.id} value={item.id}>
                        Stufe ersetzen: {item.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {replaced ? (
                <p className="text-sm text-slate-600">Vorstrecke entfällt. Es gilt der eigene Datensatz.</p>
              ) : (
                groupedSlots(stage.slots).map(([roleId, slots]) => {
                  const extras = payload.extra_slots.filter((item) => item.stage_id === stage.id && item.role_id === roleId);
                  return (
                    <div key={roleId} className="space-y-2 rounded-lg bg-slate-50 p-3">
                      <div className="flex items-center justify-between">
                        <strong className="text-sm">{roleById[roleId]?.label || "Kategorie"}</strong>
                        <button
                          className="text-sm text-forest-700 underline"
                          type="button"
                          onClick={() =>
                            setPayload({
                              ...payload,
                              extra_slots: [
                                ...payload.extra_slots,
                                {
                                  key: `new-${Date.now()}`,
                                  stage_id: stage.id,
                                  role_id: roleId,
                                  dataset_id: optionsFor(roleId)[0]?.id ?? null,
                                  share: 0,
                                },
                              ],
                            })
                          }
                        >
                          Slot ergänzen
                        </button>
                      </div>
                      {slots.map((slot) => {
                        const optional = !slot.required || slot.optional_default_off;
                        const on = !optional || payload.optional_on.includes(slot.id);
                        return (
                          <div key={slot.id} className="grid gap-2 md:grid-cols-[1fr_120px_auto] md:items-center">
                            {optional && (
                              <label className="text-sm">
                                <input
                                  type="checkbox"
                                  className="mr-2"
                                  checked={on}
                                  onChange={(e) => {
                                    const set = new Set(payload.optional_on);
                                    if (e.target.checked) set.add(slot.id);
                                    else set.delete(slot.id);
                                    setPayload({ ...payload, optional_on: [...set] });
                                  }}
                                />
                                optional
                              </label>
                            )}
                            <select
                              className="input md:col-span-1"
                              disabled={optional && !on}
                              value={payload.selections[String(slot.id)] || ""}
                              onChange={(e) =>
                                setPayload({
                                  ...payload,
                                  selections: { ...payload.selections, [String(slot.id)]: Number(e.target.value) },
                                })
                              }
                            >
                              <option value="">Bitte wählen</option>
                              {optionsFor(roleId).map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.name}
                                  {item.location ? `, ${item.location}` : ""} · {item.unit} · {sourceLabel(item.source_kind)}
                                </option>
                              ))}
                            </select>
                            <input
                              className="input"
                              type="number"
                              step="any"
                              disabled={optional && !on}
                              value={payload.shares[String(slot.id)] ?? slot.default_share}
                              onChange={(e) =>
                                setPayload({
                                  ...payload,
                                  shares: { ...payload.shares, [String(slot.id)]: Number(e.target.value) },
                                })
                              }
                            />
                            <span className="text-xs text-slate-500">Anteil (1 = 100 %)</span>
                          </div>
                        );
                      })}
                      {extras.map((extra, index) => (
                        <div key={extra.key} className="grid gap-2 md:grid-cols-[1fr_120px]">
                          <select
                            className="input"
                            value={extra.dataset_id || ""}
                            onChange={(e) => {
                              const next = payload.extra_slots.map((item) =>
                                item.key === extra.key ? { ...item, dataset_id: Number(e.target.value) } : item,
                              );
                              setPayload({ ...payload, extra_slots: next });
                            }}
                          >
                            {optionsFor(roleId).map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name} · {sourceLabel(item.source_kind)}
                              </option>
                            ))}
                          </select>
                          <input
                            className="input"
                            type="number"
                            step="any"
                            value={extra.share}
                            onChange={(e) => {
                              const next = payload.extra_slots.map((item, i) =>
                                i === index ? { ...item, share: Number(e.target.value) } : item,
                              );
                              setPayload({ ...payload, extra_slots: next });
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  );
                })
              )}
            </section>
          );
        })}

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn" type="button" onClick={() => void run()}>
          Berechnen
        </button>
        <input className="input max-w-xs" value={saveName} onChange={(e) => setSaveName(e.target.value)} />
        <button className="btn-secondary" type="button" onClick={() => void save()}>
          Speichern
        </button>
        {payload && (
          <>
            <button className="btn-secondary" type="button" onClick={() => void download("/api/calculate/export?format=csv", payload, "ergebnis.csv")}>
              CSV
            </button>
            <button className="btn-secondary" type="button" onClick={() => void download("/api/calculate/export?format=xlsx", payload, "ergebnis.xlsx")}>
              Excel
            </button>
          </>
        )}
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {result && result.blockers.length > 0 && (
        <ul className="card text-sm text-red-700">
          {result.blockers.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
      {result && !result.blockers.length && <ResultView result={result} indicators={indicators} />}
    </div>
  );
}

function groupedSlots(slots: Slot[]) {
  const map = new Map<number, Slot[]>();
  slots.forEach((slot) => {
    const list = map.get(slot.role_id) || [];
    list.push(slot);
    map.set(slot.role_id, list);
  });
  return [...map.entries()];
}

function ResultView({ result, indicators }: { result: CalcResult; indicators: Indicator[] }) {
  const summary = result.inventory_summary;
  if (result.mode === "inventory") {
    return (
      <div className="card overflow-x-auto space-y-3">
        <h2 className="font-semibold">Ergebnis (Inventar)</h2>
        <p className="text-sm text-slate-600">
          Noch keine LCIA-Datei — Ergebnis ist das Inventar. Die volle Flussliste steht im Export.
        </p>
        <table className="w-full text-left text-sm">
          <tbody>
            <tr className="border-b">
              <td className="py-2 text-slate-500">Elementarflüsse</td>
              <td>{summary?.flow_count ?? 0}</td>
            </tr>
            <tr className="border-b">
              <td className="py-2 text-slate-500">Katalog-Datensätze</td>
              <td>{summary?.catalog_dataset_count ?? 0}</td>
            </tr>
            <tr className="border-b">
              <td className="py-2 text-slate-500">Eigene Datensätze</td>
              <td>{summary?.user_dataset_count ?? 0}</td>
            </tr>
          </tbody>
        </table>
        <h3 className="font-semibold">Verwendete Mengen</h3>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              <th className="py-2">Stufe</th>
              <th>Kategorie</th>
              <th>Datensatz</th>
              <th>Menge</th>
            </tr>
          </thead>
          <tbody>
            {result.contributions.map((row) => (
              <tr key={row.slot_key} className="border-b last:border-0">
                <td className="py-2">{row.stage_name}</td>
                <td>{row.role_label}</td>
                <td>{row.dataset_name}</td>
                <td>
                  {row.amount.toPrecision(4)} {row.unit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return (
    <div className="card overflow-x-auto">
      <h2 className="mb-3 font-semibold">Ergebnis (EF 3.1)</h2>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-slate-500">
            <th className="py-2">Indikator</th>
            <th>Summe</th>
            <th>Einheit</th>
          </tr>
        </thead>
        <tbody>
          {indicators
            .filter((item) => result.totals[item.id] != null)
            .map((item) => (
              <tr key={item.id} className="border-b last:border-0">
                <td className="py-2">{item.label}</td>
                <td>{result.totals[item.id].toPrecision(4)}</td>
                <td>{item.unit}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <h3 className="mb-2 mt-6 font-semibold">Beiträge</h3>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-slate-500">
            <th className="py-2">Stufe</th>
            <th>Kategorie</th>
            <th>Datensatz</th>
            <th>Indikator</th>
            <th>Beitrag</th>
          </tr>
        </thead>
        <tbody>
          {result.contributions
            .filter((row) => row.indicator_id === "climate_change")
            .map((row) => (
              <tr key={`${row.slot_key}-${row.indicator_id}`} className="border-b last:border-0">
                <td className="py-2">{row.stage_name}</td>
                <td>{row.role_label}</td>
                <td>{row.dataset_name}</td>
                <td>Klimawandel</td>
                <td>{row.value.toPrecision(4)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
