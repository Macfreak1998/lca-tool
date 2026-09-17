export type User = {
  id: number;
  email: string;
  role: "user" | "admin";
  email_verified: boolean;
};

export type Role = { id: number; slug: string; label: string };
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

export type Slot = {
  id: number;
  role_id: number;
  required: boolean;
  optional_default_off: boolean;
  min_count: number;
  specific_amount: number;
  unit: string;
  default_dataset_id: number | null;
  default_share: number;
};

export type Stage = {
  id: number;
  name: string;
  sort_order: number;
  outgoing_stage_id: number | null;
  upstream_amount: number;
  slots: Slot[];
};

export type Chain = {
  id: number;
  name: string;
  status: "draft" | "published";
  end_product_id: number;
  end_unit: string;
  end_product_name: string;
  stages: Stage[];
};

export type ExtraSlot = {
  key: string;
  stage_id: number;
  role_id: number;
  dataset_id: number | null;
  share: number;
};

export type CalculatePayload = {
  chain_id: number;
  end_amount: number | null;
  selections: Record<string, number>;
  shares: Record<string, number>;
  optional_on: number[];
  extra_slots: ExtraSlot[];
  replaced_stages: Record<string, number>;
};

export type Contribution = {
  stage_id: number;
  stage_name: string;
  role_id: number;
  role_label: string;
  slot_key: string;
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
  extra_slots: ExtraSlot[];
  replaced_stages: Record<string, number>;
  chain_name: string;
  end_product_id: number;
  end_product_name: string;
  end_unit: string;
};
