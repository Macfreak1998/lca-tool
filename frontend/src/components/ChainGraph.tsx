import { useMemo, type MouseEvent } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { EdgeKind, NodeType } from "../types";

export type GraphNode = {
  key: string;
  type: NodeType;
  name: string;
  x: number;
  y: number;
  is_functional: boolean;
  optional: boolean;
};

export type GraphEdge = {
  key: string;
  source: string;
  target: string;
  kind: EdgeKind;
  input_amount: number;
  efficiency: number;
  allocation_share?: number | null;
};

const KIND_LABEL: Record<NodeType, string> = {
  category: "Kategorie",
  product: "Produkt",
  process: "Prozess",
  transport: "Transport",
  recovery: "Verwertung",
};

const KIND_CLASS: Record<NodeType, string> = {
  category: "border-amber-300 bg-amber-50",
  product: "border-emerald-400 bg-emerald-50",
  process: "border-violet-400 bg-violet-50",
  transport: "border-sky-300 bg-sky-50",
  recovery: "border-rose-300 bg-rose-50",
};

function FlowNode({ data }: NodeProps) {
  const kind = data.kind as NodeType;
  return (
    <div className={`min-w-[140px] rounded-lg border px-3 py-2 shadow-sm ${KIND_CLASS[kind]} ${data.functional ? "ring-2 ring-forest-700" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="text-[10px] uppercase tracking-wide text-slate-500">
        {data.functional ? "Endprodukt" : KIND_LABEL[kind]}
        {data.optional ? " · optional" : ""}
      </div>
      <div className="font-semibold text-slate-800">{String(data.label)}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { chain: FlowNode };

function edgeLabel(edge: GraphEdge, nodes: GraphNode[]) {
  if (edge.kind === "waste") return "Abfall";
  const source = nodes.find((node) => node.key === edge.source);
  const target = nodes.find((node) => node.key === edge.target);
  if (edge.kind === "energy" && source?.type === "process") return "Gutschrift";
  if (edge.kind === "energy") return "Energie";
  if (source?.type === "process" && target?.type === "product" && edge.input_amount !== 1) {
    return String(edge.input_amount);
  }
  if (target?.type === "process" && edge.efficiency !== 1) return `${Math.round(edge.efficiency * 100)} %`;
  return "";
}

export function ChainGraph({
  nodes,
  edges,
  readOnly = false,
  onMove,
  onConnect,
  onRemoveNode,
  onRemoveEdge,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  readOnly?: boolean;
  onMove?: (key: string, x: number, y: number) => void;
  onConnect?: (source: string, target: string) => void;
  onRemoveNode?: (key: string) => void;
  onRemoveEdge?: (key: string) => void;
  onSelect?: (key: string | null) => void;
}) {
  const rfNodes = useMemo<Node[]>(
    () =>
      nodes.map((node) => ({
        id: node.key,
        type: "chain",
        position: { x: node.x, y: node.y },
        data: {
          label: node.name,
          kind: node.type,
          functional: node.is_functional,
          optional: node.optional,
        },
        deletable: !readOnly && !node.is_functional,
      })),
    [nodes, readOnly],
  );
  const rfEdges = useMemo<Edge[]>(
    () =>
      edges.map((edge) => ({
        id: edge.key,
        source: edge.source,
        target: edge.target,
        label: edgeLabel(edge, nodes),
        markerEnd: { type: MarkerType.ArrowClosed },
        deletable: !readOnly,
      })),
    [edges, nodes, readOnly],
  );

  return (
    <div className="h-[640px] w-full overflow-hidden rounded-xl border border-slate-200 bg-white">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        fitView
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable={!readOnly}
        onNodeClick={(_event: MouseEvent, node: Node) => onSelect?.(node.id)}
        onEdgeClick={(_event: MouseEvent, edge: Edge) => onSelect?.(edge.id)}
        onPaneClick={() => onSelect?.(null)}
        onNodeDragStop={(_event, node) => onMove?.(node.id, node.position.x, node.position.y)}
        onConnect={(connection: Connection) => {
          if (connection.source && connection.target) onConnect?.(connection.source, connection.target);
        }}
        onNodesDelete={(deleted: Node[]) => deleted.forEach((node) => onRemoveNode?.(node.id))}
        onEdgesDelete={(deleted: Edge[]) => deleted.forEach((edge) => onRemoveEdge?.(edge.id))}
      >
        <Background />
        <Controls showInteractive={!readOnly} />
      </ReactFlow>
    </div>
  );
}
