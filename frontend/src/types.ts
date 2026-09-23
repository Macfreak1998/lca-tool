export type User = {
  id: number;
  email: string;
  role: "user" | "admin";
  email_verified: boolean;
};

export type Role = { id: number; slug: string; label: string; dataset_count?: number };
export type EndProduct = { id: number; name: string; unit: string };
export type Indicator = { id: string; label: string; unit: string };

export type Factor = { method_id: string; indicator_id: string; value: number | null };

export type Dataset = {
  id: number;
  name: string;
  location: string;
  unit: string;
  source_kind: "ecoinvent" | "catalog_manual" | "user";
  source_id: string;
  activity_name: string;
  filename: string;
  source_note: string;
  inputs_doc: string;
  owner_user_id: number | null;
  role_ids: number[];
  factors?: Factor[] | null;
  exchange_count?: number;
};

export type ArchiveHit = {
  filename: string;
  activity_name: string;
  location: string;
  reference_product: string;
  likely_market: boolean;
};

export type NodeType = "category" | "product" | "process" | "transport" | "recovery";
export type EdgeKind = "material" | "energy" | "waste";

export type ChainNode = {
  id: number;
  type: NodeType;
  name: string;
  position_x: number;
  position_y: number;
  role_id: number | null;
  dataset_id: number | null;
  unit: string;
  distance_km: number | null;
  optional: boolean;
  is_functional: boolean;
  datasets_differ: boolean;
};

export type ChainEdge = {
  id: number;
  source_id: number;
  target_id: number;
  kind: EdgeKind;
  input_amount: number;
  efficiency: number;
};

export type CombinationAxis = { category_node_id: number; dataset_id: number | null };
export type CombinationAmount = {
  category_node_id: number;
  input_amount: number;
  recovery_node_id: number | null;
};
export type ChainCombination = {
  id: number;
  process_node_id: number;
  axes: CombinationAxis[];
  amounts: CombinationAmount[];
};
export type DatasetShare = { category_node_id: number; dataset_id: number; default_share: number };

export type Chain = {
  id: number;
  name: string;
  status: "draft" | "published";
  end_product_id: number;
  end_unit: string;
  end_product_name: string;
  nodes: ChainNode[];
  edges: ChainEdge[];
  combinations: ChainCombination[];
  dataset_shares: DatasetShare[];
};

export type CalculatePayload = {
  chain_id: number;
  end_amount: number | null;
  selections: Record<string, number>;
  shares: Record<string, number>;
  optional_on: number[];
  replaced_nodes: Record<string, number>;
};

export type Contribution = {
  node_id: number;
  node_name: string;
  role_id: number;
  role_label: string;
  use_key: string;
  dataset_id: number;
  dataset_name: string;
  amount: number;
  unit: string;
  indicator_id: string;
  value: number;
};

export type InventorySummary = {
  flow_count: number;
  catalog_dataset_count: number;
  user_dataset_count: number;
  slot_count: number;
};

export type CalcResult = {
  totals: Record<string, number>;
  contributions: Contribution[];
  blockers: string[];
  mode?: "lcia" | "inventory";
  inventory_summary?: InventorySummary;
};

export type Configuration = {
  id: number;
  name: string;
  chain_id: number;
  end_amount: number;
  invalid: boolean;
  invalid_reason: string;
  selections: Record<string, number>;
  shares: Record<string, number>;
  optional_on: number[];
  replaced_nodes: Record<string, number>;
  chain_name: string;
  end_product_id: number;
  end_product_name: string;
  end_unit: string;
};
