import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DataApi, MetaApi, datasetsForCategory, defaultPayload, download, payloadFromConfiguration } from "../api";
import { ChainGraph, type GraphEdge, type GraphNode } from "../components/ChainGraph";
import type { CalcResult, CalculatePayload, Chain, Dataset, EndProduct, Indicator, Role } from "../types";

function asGraph(chain: Chain): { nodes: GraphNode[]; edges: GraphEdge[] } {
  return {
    nodes: chain.nodes.map((node) => ({
      key: String(node.id),
      type: node.type,
      name: node.name,
      x: node.position_x,
      y: node.position_y,
      is_functional: node.is_functional,
      optional: node.optional,
    })),
    edges: chain.edges.map((edge) => ({
      key: String(edge.id),
      source: String(edge.source_id),
      target: String(edge.target_id),
      kind: edge.kind,
      input_amount: edge.input_amount,
      efficiency: edge.efficiency,
    })),
  };
}

function skippedNodes(chain: Chain, replaced: Record<string, number>) {
  const incoming = new Map<number, number[]>();
  chain.edges.forEach((edge) => {
    const list = incoming.get(edge.target_id) || [];
    list.push(edge.source_id);
    incoming.set(edge.target_id, list);
  });
  const seen = new Set<number>();
  const stack = Object.keys(replaced).flatMap((id) => incoming.get(Number(id)) || []);
  while (stack.length) {
    const id = stack.pop() as number;
    if (seen.has(id)) continue;
    seen.add(id);
    stack.push(...(incoming.get(id) || []));
  }
  return seen;
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
  const [notice, setNotice] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

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
    ]).then(async ([p, c, r, d, u, i]) => {
      setProducts(p);
      setChains(c);
      setRoles(r);
      setCatalog(d);
      setOwn(u);
      setIndicators(i);
      const configId = Number(params.get("config") || 0);
      if (configId) {
        try {
          const config = await DataApi.configuration(configId);
          const match = c.find((item) => item.id === config.chain_id);
          if (!match) {
            setError("Die Kette dieser Konfiguration ist nicht verfügbar.");
          } else {
            setProductId(match.end_product_id);
            setChain(match);
            setSaveName(config.name);
            const loaded = payloadFromConfiguration(match, config, d, u);
            setPayload(loaded.payload);
            if (loaded.missing.length) {
              setNotice(`Für ${loaded.missing.join(", ")} gilt wieder der erste Datensatz.`);
            }
            return;
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Konfiguration konnte nicht geladen werden.");
        }
      }
      const fromQuery = Number(params.get("chain") || 0);
      const first = c.find((item) => item.id === fromQuery && item.status === "published") || c.find((item) => item.status === "published");
      if (first) {
        setProductId(first.end_product_id);
        setChain(first);
        setPayload(defaultPayload(first, d, u));
      } else if (p[0]) {
        setProductId(p[0].id);
      }
    });
  }, []);

  function pickChain(id: number) {
    const next = chains.find((item) => item.id === id) || null;
    setChain(next);
    setPayload(next ? defaultPayload(next, catalog, own) : null);
    setResult(null);
    setNotice("");
    setSelectedCategory(null);
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

  const skipped = useMemo(() => (chain && payload ? skippedNodes(chain, payload.replaced_nodes) : new Set<number>()), [chain, payload]);
  const graph = useMemo(() => {
    if (!chain) return null;
    const base = asGraph(chain);
    if (!payload) return base;
    return {
      ...base,
      nodes: base.nodes.map((node) => {
        if (node.type !== "category") return node;
        const category = chain.nodes.find((item) => String(item.id) === node.key);
        if (!category) return node;
        const options = datasetsForCategory(chain, category, catalog, own);
        const chosen = options.find((item) => item.id === (payload.selections[node.key] ?? options[0]?.id));
        return {
          ...node,
          datasetLabel: chosen ? `${chosen.name}${chosen.location ? `, ${chosen.location}` : ""}` : "",
        };
      }),
    };
  }, [chain, payload, catalog, own]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-forest-800">Rechnen</h1>
        <p className="text-sm text-slate-600">Endprodukt, Kette und Menge wählen. Je Kategorie gilt ein Datensatz.</p>
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
              else {
                setChain(null);
                setPayload(null);
              }
            }}
          >
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
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

      {graph && chain && payload && (
        <div className="space-y-2">
          <h2 className="font-semibold">Kette</h2>
          <p className="text-sm text-slate-600">Kategorie anklicken, dann den Datensatz wählen.</p>
          <div className="relative">
            <ChainGraph
              nodes={graph.nodes}
              edges={graph.edges}
              readOnly
              selectedKey={selectedCategory}
              onSelect={(key) => {
                if (!key) {
                  setSelectedCategory(null);
                  return;
                }
                const node = chain.nodes.find((item) => String(item.id) === key);
                setSelectedCategory(node?.type === "category" ? key : null);
              }}
            />
            {selectedCategory &&
              (() => {
                const category = chain.nodes.find((item) => String(item.id) === selectedCategory && item.type === "category");
                if (!category) return null;
                const options = datasetsForCategory(chain, category, catalog, own);
                const selectedId = payload.selections[selectedCategory] ?? options[0]?.id;
                return (
                  <aside className="card absolute right-3 top-3 z-10 w-72 space-y-2 shadow-lg">
                    <h3 className="font-semibold">{roleById[category.role_id || 0]?.label || category.name}</h3>
                    <p className="text-xs text-slate-600">Datensatz für die Rechnung</p>
                    <div className="max-h-64 space-y-1 overflow-y-auto">
                      {options.length === 0 && <p className="text-sm text-slate-600">Kein Datensatz.</p>}
                      {options.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          className={`block w-full rounded-lg border px-3 py-2 text-left text-sm ${
                            item.id === selectedId ? "border-forest-700 bg-emerald-50" : "border-slate-200 bg-white"
                          }`}
                          onClick={() =>
                            setPayload({
                              ...payload,
                              selections: { ...payload.selections, [selectedCategory]: item.id },
                            })
                          }
                        >
                          {item.name}
                          {item.location ? `, ${item.location}` : ""}
                        </button>
                      ))}
                    </div>
                  </aside>
                );
              })()}
          </div>
        </div>
      )}

      {chain &&
        payload &&
        chain.nodes
          .filter((node) => node.type === "product" && !node.is_functional && !skipped.has(node.id))
          .map((node) => (
            <section key={node.id} className="card space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">{node.name}</h2>
                <select
                  className="input max-w-md"
                  value={payload.replaced_nodes[String(node.id)] || ""}
                  onChange={(e) => {
                    const next = { ...payload.replaced_nodes };
                    if (e.target.value) next[String(node.id)] = Number(e.target.value);
                    else delete next[String(node.id)];
                    setPayload({ ...payload, replaced_nodes: next });
                  }}
                >
                  <option value="">Produktfluss (kein Ersatz)</option>
                  {own.map((item) => (
                    <option key={item.id} value={item.id}>
                      Ersetzen: {item.name}
                    </option>
                  ))}
                </select>
              </div>
              {payload.replaced_nodes[String(node.id)] && (
                <p className="text-sm text-slate-600">Vorgänger, Abfall und Energie dieses Produkts entfallen.</p>
              )}
            </section>
          ))}

      {chain &&
        payload &&
        chain.nodes
          .filter((node) => node.type === "process" && !skipped.has(node.id))
          .map((process) => {
            const productEdge = chain.edges.find(
              (edge) => edge.kind === "material" && edge.source_id === process.id && chain.nodes.some((node) => node.id === edge.target_id && node.type === "product"),
            );
            const product = chain.nodes.find((node) => node.id === productEdge?.target_id);
            if (product && (skipped.has(product.id) || payload.replaced_nodes[String(product.id)])) return null;
            const categories = chain.nodes.filter((node) => {
              if (node.type !== "category") return false;
              return chain.edges.some((edge) => {
                if (edge.kind === "waste") return false;
                if (edge.kind === "energy" && edge.source_id === process.id && edge.target_id === node.id) return true;
                if (edge.source_id !== node.id) return false;
                if (edge.target_id === process.id) return true;
                const hop = chain.nodes.find((item) => item.id === edge.target_id);
                if (hop?.type !== "transport") return false;
                return chain.edges.some(
                  (next) => next.source_id === hop.id && next.target_id === process.id && next.kind === "material",
                );
              });
            });
            const combos = chain.combinations.filter((combo) => combo.process_node_id === process.id);
            const named = (datasetId: number | null) => {
              const dataset = [...catalog, ...own].find((item) => item.id === datasetId);
              return dataset ? `${dataset.name}${dataset.location ? `, ${dataset.location}` : ""}` : "Datensatz";
            };
            return (
              <section key={process.id} className="card space-y-4">
                <h2 className="font-semibold">
                  {process.name}
                  {product ? ` → ${product.name}` : ""}
                </h2>
                {chain.edges
                  .filter((edge) => edge.kind === "material" && edge.target_id === process.id && edge.efficiency > 0 && edge.efficiency !== 1)
                  .map((edge) => {
                    const source = chain.nodes.find((node) => node.id === edge.source_id);
                    const origin =
                      source?.type === "transport"
                        ? chain.nodes.find((node) =>
                            chain.edges.some(
                              (item) => item.kind === "material" && item.target_id === source.id && item.source_id === node.id && node.type === "product",
                            ),
                          )
                        : source;
                    const soll = edge.input_amount;
                    const waste = Math.max(0, soll * (1 / edge.efficiency - 1));
                    return (
                      <p key={edge.id} className="text-sm text-slate-600">
                        {origin?.name || source?.name} · Sollmenge {soll} · {Math.round(edge.efficiency * 100)} % · Abfall{" "}
                        {Math.round((waste + Number.EPSILON) * 1000) / 1000} {origin?.unit || "kg"} je 1 {product?.unit || chain.end_unit}
                      </p>
                    );
                  })}
                {categories.map((category) => {
                  const optional = category.optional && !category.datasets_differ;
                  const on = !optional || payload.optional_on.includes(category.id);
                  const options = datasetsForCategory(chain, category, catalog, own);
                  const selectedId = payload.selections[String(category.id)] ?? options[0]?.id ?? "";
                  return (
                    <div
                      key={category.id}
                      id={`category-${category.id}`}
                      className={`space-y-2 rounded-lg ${selectedCategory === String(category.id) ? "ring-2 ring-amber-400" : ""}`}
                    >
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium">
                          {roleById[category.role_id || 0]?.label || category.name}
                          {category.datasets_differ ? "" : " · gleicher Einsatz"}
                        </h3>
                        {optional && (
                          <label className="text-sm">
                            <input
                              type="checkbox"
                              className="mr-2"
                              checked={on}
                              onChange={(e) => {
                                const set = new Set(payload.optional_on);
                                if (e.target.checked) set.add(category.id);
                                else set.delete(category.id);
                                setPayload({ ...payload, optional_on: [...set] });
                              }}
                            />
                            einschalten
                          </label>
                        )}
                      </div>
                      <label className="block text-sm">
                        Datensatz
                        <select
                          className="input mt-1"
                          value={selectedId}
                          disabled={!on || options.length === 0}
                          onChange={(e) => {
                            const datasetId = Number(e.target.value);
                            setPayload({
                              ...payload,
                              selections: { ...payload.selections, [String(category.id)]: datasetId },
                            });
                          }}
                        >
                          {options.length === 0 && <option value="">Kein Datensatz</option>}
                          {options.map((item) => (
                            <option key={item.id} value={item.id}>
                              {named(item.id)}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  );
                })}
                {combos.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="text-slate-500">
                          <th className="py-1 pr-3">Kombination</th>
                          {categories.map((category) => (
                            <th key={category.id} className="py-1 pr-3">
                              {roleById[category.role_id || 0]?.label || category.name}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {combos.map((combo) => (
                          <tr key={combo.id}>
                            <td className="py-1 pr-3">
                              {combo.axes.length
                                ? combo.axes.map((axis) => named(axis.dataset_id)).join(" × ")
                                : "eine Rezeptur"}
                            </td>
                            {categories.map((category) => {
                              const amount = combo.amounts.find((item) => item.category_node_id === category.id);
                              const soll = amount?.input_amount ?? 0;
                              const material = chain.edges.some(
                                (edge) => edge.source_id === category.id && edge.kind === "material" && (edge.target_id === process.id || chain.nodes.some((node) => node.id === edge.target_id && node.type === "transport")),
                              );
                              const credit = chain.edges.some(
                                (edge) => edge.source_id === process.id && edge.target_id === category.id && edge.kind === "energy",
                              );
                              const efficiency = material ? (amount?.efficiency ?? 1) : 1;
                              const einsatz = material && efficiency > 0 ? soll / efficiency : soll;
                              const waste = material && efficiency > 0 ? Math.max(0, soll * (1 / efficiency - 1)) : 0;
                              const perUnit = product?.unit || chain.end_unit;
                              return (
                                <td key={category.id} className="py-1 pr-3">
                                  {Math.round((einsatz + Number.EPSILON) * 1000) / 1000} {category.unit} je 1 {perUnit}
                                  {credit ? " · Gutschrift" : ""}
                                  {material && efficiency !== 1 ? ` · ${Math.round(efficiency * 100)} %` : ""}
                                  {waste > 1e-9 ? ` · Abfall ${Math.round((waste + Number.EPSILON) * 1000) / 1000}` : ""}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            );
          })}

      {chain &&
        payload &&
        chain.nodes
          .filter((node) => node.type === "transport" && node.optional)
          .map((node) => (
            <section key={node.id} className="card">
              <label className="text-sm">
                <input
                  type="checkbox"
                  className="mr-2"
                  checked={payload.optional_on.includes(node.id)}
                  onChange={(e) => {
                    const set = new Set(payload.optional_on);
                    if (e.target.checked) set.add(node.id);
                    else set.delete(node.id);
                    setPayload({ ...payload, optional_on: [...set] });
                  }}
                />
                {node.name} einschalten ({node.distance_km ?? 0} km)
              </label>
            </section>
          ))}

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn" type="button" onClick={() => void run()}>
          Rechnen
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
      {notice && <p className="text-sm text-amber-800">{notice}</p>}
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
              <th className="py-2">Knoten</th>
              <th>Kategorie</th>
              <th>Datensatz</th>
              <th>Menge</th>
            </tr>
          </thead>
          <tbody>
            {result.contributions.map((row) => (
              <tr key={row.use_key} className="border-b last:border-0">
                <td className="py-2">{row.node_name}</td>
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
      {indicators
        .filter((item) => result.contributions.some((row) => row.indicator_id === item.id))
        .map((item) => (
          <div key={item.id} className="mb-6">
            <h4 className="mb-1 text-sm font-semibold">
              {item.label} ({item.unit})
            </h4>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-slate-500">
                  <th className="py-2">Knoten</th>
                  <th>Kategorie</th>
                  <th>Datensatz</th>
                  <th>Menge</th>
                  <th>Beitrag</th>
                </tr>
              </thead>
              <tbody>
                {result.contributions
                  .filter((row) => row.indicator_id === item.id)
                  .map((row) => (
                    <tr key={`${row.use_key}-${row.indicator_id}`} className="border-b last:border-0">
                      <td className="py-2">{row.node_name}</td>
                      <td>{row.role_label}</td>
                      <td>{row.dataset_name}</td>
                      <td>
                        {row.amount.toPrecision(4)} {row.unit}
                      </td>
                      <td>{row.value.toPrecision(4)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  );
}
