import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { DataApi } from "../../api";
import { ChainGraph, type GraphEdge, type GraphNode } from "../../components/ChainGraph";
import type { Chain, Dataset, EdgeKind, NodeType, Role } from "../../types";

type DraftNode = GraphNode & {
  id?: number;
  role_id: number | null;
  dataset_id: number | null;
  unit: string;
  distance_km: number | null;
  datasets_differ: boolean;
};

type DraftAmount = {
  category_key: string;
  input_amount: number;
  efficiency: number;
  recovery_key: string | null;
};

type DraftCombination = {
  key: string;
  process_key: string;
  axes: { category_key: string; dataset_id: number }[];
  amounts: DraftAmount[];
};

function formatQuantity(value: number): string {
  return String(Math.round((value + Number.EPSILON) * 1000) / 1000);
}

type DraftShare = {
  category_key: string;
  dataset_id: number;
  default_share: number;
};

type DraftEdge = GraphEdge & { id?: number; allocation_share: number | null };

function reaches(start: string, goal: string, edges: DraftEdge[]): boolean {
  if (start === goal) return true;
  const outgoing = new Map<string, string[]>();
  edges.forEach((edge) => {
    if (edge.kind === "waste") return;
    const list = outgoing.get(edge.source) || [];
    list.push(edge.target);
    outgoing.set(edge.source, list);
  });
  const seen = new Set<string>();
  const stack = [start];
  while (stack.length) {
    const key = stack.pop() as string;
    if (seen.has(key)) continue;
    seen.add(key);
    if (key === goal) return true;
    stack.push(...(outgoing.get(key) || []));
  }
  return false;
}

function materialWaste(soll: number, efficiency: number): number {
  if (efficiency <= 0 || soll <= 0) return 0;
  return Math.max(0, soll * (1 / efficiency - 1));
}

const TYPE_LABEL: Record<NodeType, string> = {
  category: "Kategorie",
  product: "Produkt",
  process: "Prozess",
  transport: "Transport",
  recovery: "Verwertung",
};

function axisKey(axes: { category_key: string; dataset_id: number }[]) {
  return axes
    .map((axis) => `${axis.category_key}:${axis.dataset_id}`)
    .sort()
    .join("|");
}

function cartesian<T>(lists: T[][]): T[][] {
  return lists.reduce<T[][]>((rows, list) => rows.flatMap((row) => list.map((item) => [...row, item])), [[]]);
}

function canonicalUnit(unit: string): string {
  const text = unit.trim().toLowerCase().replace(/·/g, "*").replace(/-/g, "").replace(/\s+/g, "");
  if (text === "kilowatthour") return "kwh";
  if (text === "kilogram") return "kg";
  return text;
}

function sameUnit(left: string, right: string): boolean {
  return canonicalUnit(left) === canonicalUnit(right);
}

function categoryTitle(node: { type: string; name: string; role_id: number | null }, roles: Role[]): string {
  if (node.type !== "category") return node.name;
  const role = roles.find((item) => item.id === node.role_id)?.label;
  if (!role) return node.name;
  if (!node.name || node.name === TYPE_LABEL.category || node.name === role) return role;
  return `${node.name} (${role})`;
}

function nodeKey(id: number) {
  return `n-${id}`;
}

function toDraft(chain: Chain) {
  const nodes: DraftNode[] = chain.nodes.map((node) => ({
    id: node.id,
    key: nodeKey(node.id),
    type: node.type,
    name: node.name,
    x: node.position_x,
    y: node.position_y,
    is_functional: node.is_functional,
    optional: node.optional,
    role_id: node.role_id,
    dataset_id: node.dataset_id,
    unit: node.unit,
    distance_km: node.distance_km,
    datasets_differ: node.datasets_differ,
  }));
  const edges: DraftEdge[] = chain.edges.map((edge) => ({
    id: edge.id,
    key: `e-${edge.id}`,
    source: nodeKey(edge.source_id),
    target: nodeKey(edge.target_id),
    kind: edge.kind,
    input_amount: edge.input_amount,
    efficiency: edge.efficiency,
    allocation_share: edge.allocation_share,
  }));
  const combinations: DraftCombination[] = chain.combinations.map((combo) => {
    const axes = combo.axes
      .filter((axis) => axis.dataset_id != null)
      .map((axis) => ({ category_key: nodeKey(axis.category_node_id), dataset_id: axis.dataset_id as number }));
    return {
      key: `${nodeKey(combo.process_node_id)}::${axisKey(axes)}`,
      process_key: nodeKey(combo.process_node_id),
      axes,
      amounts: combo.amounts.map((amount) => ({
        category_key: nodeKey(amount.category_node_id),
        input_amount: amount.input_amount,
        efficiency: amount.efficiency ?? 1,
        recovery_key: amount.recovery_node_id ? nodeKey(amount.recovery_node_id) : null,
      })),
    };
  });
  const shares: DraftShare[] = chain.dataset_shares.map((share) => ({
    category_key: nodeKey(share.category_node_id),
    dataset_id: share.dataset_id,
    default_share: share.default_share,
  }));
  return { nodes, edges, combinations, shares };
}

export function ChainEditorPage() {
  const { id } = useParams();
  const chainId = Number(id);
  const [chain, setChain] = useState<Chain | null>(null);
  const [nodes, setNodes] = useState<DraftNode[]>([]);
  const [edges, setEdges] = useState<DraftEdge[]>([]);
  const [combinations, setCombinations] = useState<DraftCombination[]>([]);
  const [shares, setShares] = useState<DraftShare[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const [c, r, d] = await Promise.all([DataApi.chain(chainId), DataApi.roles(), DataApi.datasets()]);
    setChain(c);
    setRoles(r);
    setDatasets(d);
    const draft = toDraft(c);
    setNodes(draft.nodes);
    setEdges(draft.edges);
    setCombinations(draft.combinations);
    setShares(draft.shares);
  }

  useEffect(() => {
    void load();
  }, [chainId]);

  useEffect(() => {
    if (datasets.length === 0) return;
    const roleDatasets = (roleId: number | null) =>
      roleId == null ? [] : datasets.filter((item) => item.role_ids.includes(roleId));
    setCombinations((current) => {
      const next: DraftCombination[] = [];
      for (const process of nodes.filter((node) => node.type === "process")) {
        const incoming = edges
          .filter((edge) => edge.target === process.key && edge.kind !== "waste")
          .flatMap((edge) => {
            const source = nodes.find((node) => node.key === edge.source);
            if (source?.type === "category") return [source];
            if (source?.type !== "transport" || edge.kind !== "material") return [];
            return edges
              .filter((item) => item.target === source.key && item.kind === "material")
              .map((item) => nodes.find((node) => node.key === item.source && node.type === "category"))
              .filter((node): node is DraftNode => Boolean(node));
          });
        const credits = edges
          .filter((edge) => edge.source === process.key && edge.kind === "energy")
          .map((edge) => nodes.find((node) => node.key === edge.target && node.type === "category"))
          .filter((node): node is DraftNode => Boolean(node));
        const categories = [...incoming, ...credits.filter((node) => !incoming.some((item) => item.key === node.key))];
        const differing = categories.filter((node) => node.datasets_differ);
        const lists = differing.map((category) =>
          roleDatasets(category.role_id).map((dataset) => ({ category_key: category.key, dataset_id: dataset.id })),
        );
        if (categories.length === 0 || lists.some((list) => list.length === 0)) continue;
        const specs = lists.length === 0 ? [[]] : cartesian(lists);
        for (const axes of specs) {
          const key = `${process.key}::${axisKey(axes)}`;
          const previous = current.find((combo) => combo.key === key);
          const sibling = current.find((combo) => combo.process_key === process.key);
          next.push({
            key,
            process_key: process.key,
            axes,
            amounts: categories.map((category) => {
              const kept = previous?.amounts.find((amount) => amount.category_key === category.key);
              const copied = sibling?.amounts.find((amount) => amount.category_key === category.key);
              return {
                category_key: category.key,
                input_amount: kept?.input_amount ?? (category.datasets_differ ? 0 : copied?.input_amount ?? 0),
                efficiency: kept?.efficiency ?? copied?.efficiency ?? 1,
                recovery_key: kept?.recovery_key ?? null,
              };
            }),
          });
        }
      }
      const same =
        next.length === current.length &&
        next.every((combo, index) => {
          const other = current[index];
          return (
            combo.key === other.key &&
            combo.amounts.length === other.amounts.length &&
            combo.amounts.every(
              (amount, amountIndex) =>
                amount.category_key === other.amounts[amountIndex].category_key &&
                amount.input_amount === other.amounts[amountIndex].input_amount &&
                amount.efficiency === other.amounts[amountIndex].efficiency &&
                amount.recovery_key === other.amounts[amountIndex].recovery_key,
            )
          );
        });
      return same ? current : next;
    });
    setShares((current) => {
      const needed: DraftShare[] = [];
      const seen = new Set<string>();
      for (const edge of edges) {
        if (edge.kind === "waste") continue;
        const source = nodes.find((node) => node.key === edge.source);
        const target = nodes.find((node) => node.key === edge.target);
        const category = (() => {
          if (source?.type === "category" && target?.type === "process") return source;
          if (source?.type === "process" && target?.type === "category" && edge.kind === "energy") return target;
          if (source?.type === "category" && target?.type === "transport" && edge.kind === "material") {
            const onwards = edges.some(
              (item) => item.source === target.key && item.kind === "material" && nodes.some((node) => node.key === item.target && node.type === "process"),
            );
            return onwards ? source : null;
          }
          return null;
        })();
        if (!category) continue;
        const rows = roleDatasets(category.role_id);
        rows.forEach((dataset) => {
          const key = `${category.key}:${dataset.id}`;
          if (seen.has(key)) return;
          seen.add(key);
          const existing = current.find((share) => share.category_key === category.key && share.dataset_id === dataset.id);
          needed.push({
            category_key: category.key,
            dataset_id: dataset.id,
            default_share: existing?.default_share ?? (rows.length === 1 ? 1 : 0),
          });
        });
      }
      const same =
        needed.length === current.length &&
        needed.every(
          (share, index) =>
            share.category_key === current[index].category_key &&
            share.dataset_id === current[index].dataset_id &&
            share.default_share === current[index].default_share,
        );
      return same ? current : needed;
    });
  }, [edges, nodes, datasets]);

  function addNode(type: NodeType) {
    const key = `n-${Date.now()}`;
    setNodes((current) => [
      ...current,
      {
        key,
        type,
        name: TYPE_LABEL[type],
        x: 80 + current.length * 24,
        y: 80 + current.length * 24,
        is_functional: false,
        optional: type === "transport",
        role_id: type === "category" ? roles[0]?.id ?? null : null,
        dataset_id: null,
        unit: type === "transport" ? "kg·km" : "kg",
        distance_km: type === "transport" ? 100 : null,
        datasets_differ: false,
      },
    ]);
    setSelected(key);
  }

  function patchNode(key: string, patch: Partial<DraftNode>) {
    setNodes((current) => current.map((node) => (node.key === key ? { ...node, ...patch } : node)));
  }

  function patchEdge(key: string, patch: Partial<DraftEdge>) {
    setEdges((current) => current.map((edge) => (edge.key === key ? { ...edge, ...patch } : edge)));
  }

  function patchAmount(comboKey: string, categoryKey: string, patch: Partial<DraftAmount>) {
    setCombinations((current) =>
      current.map((combo) =>
        combo.key === comboKey
          ? {
              ...combo,
              amounts: combo.amounts.map((amount) =>
                amount.category_key === categoryKey ? { ...amount, ...patch } : amount,
              ),
            }
          : combo,
      ),
    );
  }

  function patchShare(categoryKey: string, datasetId: number, defaultShare: number) {
    setShares((current) =>
      current.map((share) =>
        share.category_key === categoryKey && share.dataset_id === datasetId
          ? { ...share, default_share: defaultShare }
          : share,
      ),
    );
  }

  function materialInput(processKey: string, categoryKey: string): boolean {
    return edges.some((edge) => {
      if (edge.source !== categoryKey || edge.kind !== "material") return false;
      if (edge.target === processKey) return true;
      const hop = nodes.find((node) => node.key === edge.target);
      return (
        hop?.type === "transport" &&
        edges.some((next) => next.source === hop.key && next.target === processKey && next.kind === "material")
      );
    });
  }

  function processHasWaste(processKey: string): boolean {
    const fromAmounts = combinations.some(
      (combo) =>
        combo.process_key === processKey &&
        combo.amounts.some(
          (amount) => materialInput(processKey, amount.category_key) && materialWaste(amount.input_amount, amount.efficiency) > 1e-12,
        ),
    );
    const fromEdges = edges.some((edge) => {
      if (edge.kind !== "material" || edge.target !== processKey) return false;
      const source = nodes.find((node) => node.key === edge.source);
      if (source?.type !== "product" && source?.type !== "transport") return false;
      return materialWaste(edge.input_amount, edge.efficiency) > 1e-12;
    });
    return fromAmounts || fromEdges;
  }

  function recoveryKeyOf(processKey: string): string | null {
    const direct = edges.find((edge) => edge.kind === "waste" && edge.source === processKey);
    if (direct) {
      const target = nodes.find((node) => node.key === direct.target);
      if (target?.type === "recovery") return target.key;
      if (target?.type === "transport") {
        const next = edges.find((edge) => edge.kind === "waste" && edge.source === target.key);
        if (next) return next.target;
      }
    }
    for (const combo of combinations) {
      if (combo.process_key !== processKey) continue;
      const amount = combo.amounts.find((item) => item.recovery_key);
      if (amount?.recovery_key) return amount.recovery_key;
    }
    return null;
  }

  function setProcessRecovery(processKey: string, recoveryKey: string | null) {
    setCombinations((current) =>
      current.map((combo) => {
        if (combo.process_key !== processKey) return combo;
        return {
          ...combo,
          amounts: combo.amounts.map((amount) => ({
            ...amount,
            recovery_key: materialInput(processKey, amount.category_key) ? recoveryKey : null,
          })),
        };
      }),
    );
    setEdges((current) => {
      const kept = current.filter((edge) => !(edge.kind === "waste" && edge.source === processKey));
      if (!recoveryKey) return kept;
      return [
        ...kept,
        {
          key: `e-${Date.now()}`,
          source: processKey,
          target: recoveryKey,
          kind: "waste",
          input_amount: 1,
          efficiency: 1,
          allocation_share: null,
        },
      ];
    });
  }

  function removeNode(key: string) {
    const node = nodes.find((item) => item.key === key);
    if (!node || node.is_functional) return;
    setNodes((current) => current.filter((item) => item.key !== key));
    setEdges((current) => current.filter((edge) => edge.source !== key && edge.target !== key));
    setCombinations((current) => current.filter((combo) => combo.process_key !== key));
    setShares((current) => current.filter((share) => share.category_key !== key));
    setSelected(null);
  }

  function connect(source: string, target: string) {
    const from = nodes.find((node) => node.key === source);
    const to = nodes.find((node) => node.key === target);
    if (!from || !to || source === target) return;
    let kind: EdgeKind = "material";
    if (to.type === "recovery" || from.type === "recovery") kind = "waste";
    else if (from.type === "process" && to.type === "category") kind = "energy";
    else if (from.type === "category" && to.type === "process" && from.name.toLowerCase().includes("energie")) kind = "energy";
    setEdges((current) => [
      ...current,
      {
        key: `e-${Date.now()}`,
        source,
        target,
        kind,
        input_amount: 1,
        efficiency: 1,
        allocation_share: null,
      },
    ]);
  }

  const selectedNode = nodes.find((node) => node.key === selected) || null;
  const selectedEdge = edges.find((edge) => edge.key === selected) || null;
  const processCombinations = combinations.filter((combo) => combo.process_key === selectedNode?.key);
  const categories = nodes.filter((node) => node.type === "category");
  const recoveries = nodes.filter((node) => node.type === "recovery");

  function datasetsForCategory(node: DraftNode): Dataset[] {
    if (node.role_id == null) return [];
    return datasets.filter((item) => item.role_ids.includes(node.role_id as number));
  }

  function unitPreview(node: DraftNode): string {
    if (node.type !== "category") return node.unit;
    const rows = datasetsForCategory(node);
    if (rows.length > 0) {
      const first = rows[0].unit;
      if (rows.every((row) => sameUnit(row.unit, first))) return first;
      return node.unit;
    }
    const energy = edges.some(
      (edge) => edge.kind === "energy" && (edge.source === node.key || edge.target === node.key),
    );
    if (energy && (!node.unit.trim() || sameUnit(node.unit, "kg"))) return "kWh";
    return node.unit || "kg";
  }

  function unitWarnings(node: DraftNode): string[] {
    if (node.type !== "category") return [];
    const rows = datasetsForCategory(node);
    if (rows.length === 0 || rows.every((row) => sameUnit(row.unit, rows[0].unit))) return [];
    return rows
      .filter((row) => !sameUnit(row.unit, node.unit))
      .map((row) => `Einheit von „${row.name}“ (${row.unit}) passt nicht zu „${node.name}“ (${node.unit}).`);
  }
  const graphNodes = useMemo<GraphNode[]>(
    () =>
      nodes.map((node) => ({
        key: node.key,
        type: node.type,
        name: categoryTitle(node, roles),
        x: node.x,
        y: node.y,
        is_functional: node.is_functional,
        optional: node.optional,
      })),
    [nodes, roles],
  );

  async function save(): Promise<boolean> {
    setError("");
    setMessage("");
    try {
      const saved = await DataApi.saveChain(chainId, {
        name: chain?.name,
        nodes: nodes.map((node) => ({
          id: node.id,
          client_key: node.key,
          type: node.type,
          name: node.name,
          position_x: node.x,
          position_y: node.y,
          role_id: node.role_id,
          dataset_id: node.type === "category" ? null : node.dataset_id,
          unit: node.unit,
          distance_km: node.distance_km,
          optional: node.optional,
          is_functional: node.is_functional,
          datasets_differ: node.datasets_differ,
        })),
        edges: edges.map((edge) => ({
          id: edge.id,
          source_key: edge.source,
          target_key: edge.target,
          kind: edge.kind,
          input_amount: edge.input_amount,
          efficiency: edge.efficiency,
          allocation_share: edge.allocation_share,
        })),
        combinations: combinations.map((combo) => ({
          process_key: combo.process_key,
          axes: combo.axes,
          amounts: combo.amounts,
        })),
        dataset_shares: shares,
      });
      setChain(saved);
      const draft = toDraft(saved);
      setNodes(draft.nodes);
      setEdges(draft.edges);
      setCombinations(draft.combinations);
      setShares(draft.shares);
      setSelected(null);
      setMessage("Entwurf gespeichert.");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen.");
      return false;
    }
  }

  async function publish() {
    setError("");
    try {
      const saved = await save();
      if (!saved) return;
      const published = await DataApi.publishChain(chainId);
      setChain(published);
      const draft = toDraft(published);
      setNodes(draft.nodes);
      setEdges(draft.edges);
      setCombinations(draft.combinations);
      setShares(draft.shares);
      setMessage("Veröffentlicht.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Veröffentlichen fehlgeschlagen.");
    }
  }

  if (!chain) return <p>Laden …</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-forest-800">{chain.name}</h1>
        <Link className="text-sm text-forest-700 underline" to="/admin/ketten">
          Zurück
        </Link>
      </div>
      <p className="text-sm text-slate-600">
        {chain.end_product_name} · {chain.end_unit} · {chain.status === "published" ? "veröffentlicht" : "Entwurf"}.
        Knoten verbinden. Mengen stehen in den Kombinationen des Prozesses.
      </p>
      <div className="flex flex-wrap gap-2">
        <button className="btn-secondary" type="button" onClick={() => addNode("category")}>
          Kategorie
        </button>
        <button className="btn-secondary" type="button" onClick={() => addNode("product")}>
          Produkt
        </button>
        <button className="btn-secondary" type="button" onClick={() => addNode("process")}>
          Prozess
        </button>
        <button className="btn-secondary" type="button" onClick={() => addNode("transport")}>
          Transport
        </button>
        <button className="btn-secondary" type="button" onClick={() => addNode("recovery")}>
          Verwertung
        </button>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <ChainGraph
          nodes={graphNodes}
          edges={edges}
          onMove={(key, x, y) => patchNode(key, { x, y })}
          onConnect={connect}
          onRemoveNode={removeNode}
          onRemoveEdge={(key) => setEdges((current) => current.filter((edge) => edge.key !== key))}
          onSelect={setSelected}
        />
        <aside className="card space-y-3">
          {!selectedNode && !selectedEdge && <p className="text-sm text-slate-600">Knoten oder Kante auswählen.</p>}
          {selectedNode && (
            <>
              <h2 className="font-semibold">{selectedNode.is_functional ? "Endprodukt" : TYPE_LABEL[selectedNode.type]}</h2>
              <label className="block text-sm">
                Name
                <input className="input mt-1" value={selectedNode.name} onChange={(e) => patchNode(selectedNode.key, { name: e.target.value })} />
              </label>
              {selectedNode.type === "category" && (
                <>
                  <label className="block text-sm">
                    Kategorie
                    <select
                      className="input mt-1"
                      value={selectedNode.role_id || ""}
                      onChange={(e) => {
                        const roleId = Number(e.target.value);
                        const nextRole = roles.find((item) => item.id === roleId);
                        const previousRole = roles.find((item) => item.id === selectedNode.role_id);
                        const stillGeneric =
                          !selectedNode.name ||
                          selectedNode.name === TYPE_LABEL.category ||
                          selectedNode.name === previousRole?.label;
                        patchNode(selectedNode.key, {
                          role_id: roleId,
                          name: stillGeneric && nextRole ? nextRole.label : selectedNode.name,
                        });
                      }}
                    >
                      {roles.map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedNode.datasets_differ}
                      onChange={(e) =>
                        patchNode(selectedNode.key, {
                          datasets_differ: e.target.checked,
                          optional: e.target.checked ? false : selectedNode.optional,
                        })
                      }
                    />
                    Datensätze verhalten sich unterschiedlich
                  </label>
                </>
              )}
              {(selectedNode.type === "transport" || selectedNode.type === "recovery") && (
                <label className="block text-sm">
                  Datensatz
                  <select
                    className="input mt-1"
                    value={selectedNode.dataset_id || ""}
                    onChange={(e) =>
                      patchNode(selectedNode.key, { dataset_id: e.target.value ? Number(e.target.value) : null })
                    }
                  >
                    <option value="">Bitte wählen</option>
                    {datasets
                      .filter((item) => !selectedNode.role_id || item.role_ids.includes(selectedNode.role_id))
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                          {item.location ? ` (${item.location})` : ""}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {selectedNode.type === "category" ? (
                <div className="block text-sm">
                  Einheit
                  <p className="mt-1">{unitPreview(selectedNode)}</p>
                  {unitWarnings(selectedNode).map((warning) => (
                    <p key={warning} className="mt-1 text-xs text-red-700">
                      {warning}
                    </p>
                  ))}
                </div>
              ) : (
                <label className="block text-sm">
                  Einheit
                  <input className="input mt-1" value={selectedNode.unit} onChange={(e) => patchNode(selectedNode.key, { unit: e.target.value })} />
                </label>
              )}
              {selectedNode.type === "transport" && (
                <label className="block text-sm">
                  Distanz (km)
                  <input
                    className="input mt-1"
                    type="number"
                    step="any"
                    value={selectedNode.distance_km ?? ""}
                    onChange={(e) => patchNode(selectedNode.key, { distance_km: Number(e.target.value) })}
                  />
                </label>
              )}
              {(selectedNode.type === "transport" ||
                (selectedNode.type === "category" && !selectedNode.datasets_differ)) && (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedNode.optional}
                    onChange={(e) => patchNode(selectedNode.key, { optional: e.target.checked })}
                  />
                  optional, standardmäßig aus
                </label>
              )}
              {selectedNode.type === "process" && (
                <div className="space-y-3 border-t pt-3">
                  <h3 className="font-semibold">Kombinationen</h3>
                  {categories
                    .filter((category) =>
                      edges.some((edge) => edge.source === category.key && edge.target === selectedNode.key && edge.kind !== "waste"),
                    )
                    .map((category) => {
                      const rows = shares.filter((share) => share.category_key === category.key);
                      if (rows.length < 2) return null;
                      return (
                        <div key={category.key} className="space-y-1">
                          <p className="text-xs font-medium">Anteile {categoryTitle(category, roles)}</p>
                          {rows.map((share) => {
                            const dataset = datasets.find((item) => item.id === share.dataset_id);
                            return (
                              <label key={share.dataset_id} className="block text-xs">
                                {dataset?.name || "Datensatz"}
                                <input
                                  className="input"
                                  type="number"
                                  step="any"
                                  value={share.default_share}
                                  onChange={(e) => patchShare(category.key, share.dataset_id, Number(e.target.value))}
                                />
                              </label>
                            );
                          })}
                        </div>
                      );
                    })}
                  {processCombinations.length === 0 && (
                    <p className="text-xs text-slate-500">Kategorien mit dem Prozess verbinden. Ungleiche Kategorien brauchen Datensätze.</p>
                  )}
                  <div className="space-y-3">
                    {processCombinations.map((combo) => (
                      <div key={combo.key} className="space-y-2 rounded-lg bg-slate-50 p-3">
                        <p className="text-sm font-medium">
                          {combo.axes.length
                            ? combo.axes
                                .map((axis) => datasets.find((item) => item.id === axis.dataset_id)?.name || "Datensatz")
                                .join(" × ")
                            : "eine Rezeptur"}
                        </p>
                        {combo.amounts.map((amount) => {
                          const category = nodes.find((node) => node.key === amount.category_key);
                          const productUnit =
                            nodes.find(
                              (node) =>
                                node.type === "product" &&
                                edges.some(
                                  (edge) =>
                                    edge.source === selectedNode.key &&
                                    edge.target === node.key &&
                                    edge.kind === "material",
                                ),
                            )?.unit ||
                            chain?.end_unit ||
                            "";
                          const material = materialInput(selectedNode.key, amount.category_key);
                          const credit = edges.some(
                            (edge) =>
                              edge.source === selectedNode.key &&
                              edge.target === amount.category_key &&
                              edge.kind === "energy",
                          );
                          const efficiency = amount.efficiency || 0;
                          const einsatz = efficiency > 0 ? amount.input_amount / efficiency : 0;
                          const waste = material ? materialWaste(amount.input_amount, efficiency) : 0;
                          return (
                            <div key={amount.category_key} className="space-y-1">
                              <label className="block text-xs">
                                {category ? categoryTitle(category, roles) : "Kategorie"}
                                {credit ? " · Gutschrift" : ""}
                                {category ? ` (${unitPreview(category)} je 1 ${productUnit})` : ""}
                                <input
                                  className="input"
                                  type="number"
                                  step="any"
                                  min={0}
                                  value={amount.input_amount}
                                  onChange={(e) =>
                                    patchAmount(combo.key, amount.category_key, { input_amount: Number(e.target.value) })
                                  }
                                />
                              </label>
                              {material && (
                                <label className="block text-xs">
                                  Effizienz (1 = 100 %)
                                  <input
                                    className="input"
                                    type="number"
                                    step="any"
                                    min={0}
                                    value={amount.efficiency}
                                    onChange={(e) =>
                                      patchAmount(combo.key, amount.category_key, { efficiency: Number(e.target.value) })
                                    }
                                  />
                                </label>
                              )}
                              {category &&
                                unitWarnings(category).map((warning) => (
                                  <p key={warning} className="text-xs text-red-700">
                                    {warning}
                                  </p>
                                ))}
                              <p className="text-xs text-slate-500">
                                {material
                                  ? `Einsatz ${formatQuantity(einsatz)} · Abfall ${formatQuantity(waste)}`
                                  : credit
                                    ? "wird abgezogen"
                                    : "Energie mit 100 %"}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                  {processHasWaste(selectedNode.key) && (
                    <label className="block text-sm">
                      Verwertung des Abfalls
                      <select
                        className="input mt-1"
                        value={recoveryKeyOf(selectedNode.key) || ""}
                        onChange={(e) => setProcessRecovery(selectedNode.key, e.target.value || null)}
                      >
                        <option value="">Verwertung wählen</option>
                        {recoveries.map((node) => (
                          <option key={node.key} value={node.key}>
                            {node.name}
                          </option>
                        ))}
                      </select>
                      <span className="mt-1 block text-xs text-slate-500">
                        Alle übrigen Stoffe dieses Prozesses gehen in diese Verwertung.
                      </span>
                    </label>
                  )}
                </div>
              )}
              {!selectedNode.is_functional && (
                <button className="text-sm text-red-700 underline" type="button" onClick={() => removeNode(selectedNode.key)}>
                  Knoten entfernen
                </button>
              )}
            </>
          )}
          {selectedEdge && (
            <>
              <h2 className="font-semibold">Kante</h2>
              <label className="block text-sm">
                Art
                <select
                  className="input mt-1"
                  value={selectedEdge.kind}
                  onChange={(e) => patchEdge(selectedEdge.key, { kind: e.target.value as EdgeKind })}
                >
                  <option value="material">Material</option>
                  <option value="energy">Energie</option>
                  <option value="waste">Abfall</option>
                </select>
              </label>
              {nodes.find((node) => node.key === selectedEdge.source)?.type === "category" && (
                <p className="text-sm text-slate-600">Die Menge steht in den Kombinationen des Prozesses.</p>
              )}
              {nodes.find((node) => node.key === selectedEdge.target)?.type === "category" &&
                selectedEdge.kind === "energy" && (
                  <p className="text-sm text-slate-600">Gutschrift. Die Menge steht in den Kombinationen des Prozesses.</p>
                )}
              {(() => {
                const source = nodes.find((node) => node.key === selectedEdge.source);
                const target = nodes.find((node) => node.key === selectedEdge.target);
                const functional = nodes.find((node) => node.is_functional);
                const byproduct =
                  source?.type === "process" &&
                  target?.type === "product" &&
                  selectedEdge.kind === "material" &&
                  functional != null &&
                  !reaches(target.key, functional.key, edges);
                const flowIntoProcess =
                  selectedEdge.kind === "material" &&
                  target?.type === "process" &&
                  (source?.type === "product" || source?.type === "transport");
                if (source?.type === "process" && target?.type === "product" && !byproduct) {
                  const unitsDiffer = edges.some((edge) => {
                    if (edge.source !== source.key || edge.kind !== "material" || edge.key === selectedEdge.key) return false;
                    const other = nodes.find((node) => node.key === edge.target);
                    return other?.type === "product" && other.unit !== target.unit;
                  });
                  return (
                    <>
                      <p className="text-sm text-slate-600">Der Prozess erzeugt eine Einheit dieses Produkts.</p>
                      {unitsDiffer && (
                        <label className="block text-sm">
                          Anteil (Summe der Produktausgänge = 1)
                          <input
                            className="input mt-1"
                            type="number"
                            step="any"
                            min={0}
                            value={selectedEdge.allocation_share ?? ""}
                            onChange={(e) =>
                              patchEdge(selectedEdge.key, {
                                allocation_share: e.target.value === "" ? null : Number(e.target.value),
                              })
                            }
                          />
                        </label>
                      )}
                    </>
                  );
                }
                if (!byproduct && !flowIntoProcess) return null;
                const waste = flowIntoProcess ? materialWaste(selectedEdge.input_amount, selectedEdge.efficiency) : 0;
                const einsatz =
                  selectedEdge.efficiency > 0 ? selectedEdge.input_amount / selectedEdge.efficiency : 0;
                const unitsDiffer =
                  byproduct &&
                  source?.type === "process" &&
                  edges.some((edge) => {
                    if (edge.source !== source.key || edge.kind !== "material" || edge.key === selectedEdge.key) return false;
                    const other = nodes.find((node) => node.key === edge.target);
                    return other?.type === "product" && other.unit !== target?.unit;
                  });
                return (
                  <>
                    <label className="block text-sm">
                      {byproduct ? "Menge je Einheit des fortgeführten Produkts" : "Sollmenge je Einheit Ziel"}
                      <input
                        className="input mt-1"
                        type="number"
                        step="any"
                        min={0}
                        value={selectedEdge.input_amount}
                        onChange={(e) => patchEdge(selectedEdge.key, { input_amount: Number(e.target.value) })}
                      />
                    </label>
                    {flowIntoProcess && (
                      <label className="block text-sm">
                        Effizienz (1 = 100 %)
                        <input
                          className="input mt-1"
                          type="number"
                          step="any"
                          min={0}
                          value={selectedEdge.efficiency}
                          onChange={(e) => patchEdge(selectedEdge.key, { efficiency: Number(e.target.value) })}
                        />
                        <span className="mt-1 block text-xs text-slate-500">
                          Einsatz {formatQuantity(einsatz)} · Abfall {formatQuantity(waste)}
                        </span>
                      </label>
                    )}
                    {unitsDiffer && (
                      <label className="block text-sm">
                        Anteil (Summe der Produktausgänge = 1)
                        <input
                          className="input mt-1"
                          type="number"
                          step="any"
                          min={0}
                          value={selectedEdge.allocation_share ?? ""}
                          onChange={(e) =>
                            patchEdge(selectedEdge.key, {
                              allocation_share: e.target.value === "" ? null : Number(e.target.value),
                            })
                          }
                        />
                      </label>
                    )}
                  </>
                );
              })()}
              <button
                className="text-sm text-red-700 underline"
                type="button"
                onClick={() => {
                  setEdges((current) => current.filter((edge) => edge.key !== selectedEdge.key));
                  setSelected(null);
                }}
              >
                Kante entfernen
              </button>
            </>
          )}
        </aside>
      </div>
      <div className="flex flex-wrap gap-3">
        <button className="btn-secondary" type="button" onClick={() => void save()}>
          Entwurf speichern
        </button>
        <button className="btn" type="button" onClick={() => void publish()}>
          Proberechnung und veröffentlichen
        </button>
        {chain.status === "published" && (
          <button className="btn-secondary" type="button" onClick={() => void DataApi.unpublishChain(chainId).then(load)}>
            Zurückziehen
          </button>
        )}
      </div>
      {message && <p className="text-sm text-forest-700">{message}</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}
    </div>
  );
}
