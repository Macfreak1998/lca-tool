from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8)


class PasswordResetRequestIn(BaseModel):
    email: str


class PasswordResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    email_verified: bool

    model_config = {"from_attributes": True}


class RoleIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    slug: str | None = None


class RoleUpdateIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class RoleOut(BaseModel):
    id: int
    slug: str
    label: str
    dataset_count: int = 0

    model_config = {"from_attributes": True}


class EndProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=32)


class EndProductOut(BaseModel):
    id: int
    name: str
    unit: str

    model_config = {"from_attributes": True}


class ArchivePathIn(BaseModel):
    path: str


class ArchivePathOut(BaseModel):
    path: str


class ArchiveHit(BaseModel):
    filename: str
    activity_name: str
    location: str
    reference_product: str
    likely_market: bool


class CatalogImportIn(BaseModel):
    filename: str
    role_id: int


class CatalogDatasetUpdateIn(BaseModel):
    role_ids: list[int]


class FactorOut(BaseModel):
    method_id: str
    indicator_id: str
    value: float | None


class DatasetOut(BaseModel):
    id: int
    name: str
    location: str
    unit: str
    source_kind: str
    source_id: str
    activity_name: str
    filename: str
    source_note: str
    inputs_doc: str
    owner_user_id: int | None
    role_ids: list[int]
    factors: list[FactorOut] | None = None
    exchange_count: int = 0

    model_config = {"from_attributes": True}


class UserDatasetIn(BaseModel):
    name: str = Field(min_length=1)
    role_id: int
    unit: str = Field(min_length=1)
    climate_change: float
    source_note: str = ""
    inputs_doc: str = ""
    factors: dict[str, float | None] = Field(default_factory=dict)


class UserDatasetUpdateIn(BaseModel):
    name: str | None = None
    role_id: int | None = None
    unit: str | None = None
    climate_change: float | None = None
    source_note: str | None = None
    inputs_doc: str | None = None
    factors: dict[str, float | None] | None = None


class CatalogFromProposalIn(BaseModel):
    proposal_id: int
    name: str | None = None
    role_id: int | None = None


class NodeIn(BaseModel):
    id: int | None = None
    client_key: str
    type: str
    name: str
    position_x: float = 0
    position_y: float = 0
    role_id: int | None = None
    dataset_id: int | None = None
    unit: str = ""
    distance_km: float | None = None
    optional: bool = False
    is_functional: bool = False
    datasets_differ: bool = False


class EdgeIn(BaseModel):
    id: int | None = None
    source_key: str
    target_key: str
    kind: str = "material"
    input_amount: float = 1.0
    efficiency: float = 1.0


class CombinationAxisIn(BaseModel):
    category_key: str
    dataset_id: int


class CombinationAmountIn(BaseModel):
    category_key: str
    input_amount: float = 0.0
    recovery_key: str | None = None


class CombinationIn(BaseModel):
    process_key: str
    axes: list[CombinationAxisIn] = Field(default_factory=list)
    amounts: list[CombinationAmountIn] = Field(default_factory=list)


class DatasetShareIn(BaseModel):
    category_key: str
    dataset_id: int
    default_share: float = 1.0


class ChainCreateIn(BaseModel):
    name: str
    end_product_id: int


class ChainUpdateIn(BaseModel):
    name: str | None = None
    status: str | None = None
    nodes: list[NodeIn] | None = None
    edges: list[EdgeIn] | None = None
    combinations: list[CombinationIn] | None = None
    dataset_shares: list[DatasetShareIn] | None = None


class NodeOut(BaseModel):
    id: int
    type: str
    name: str
    position_x: float
    position_y: float
    role_id: int | None
    dataset_id: int | None
    unit: str
    distance_km: float | None
    optional: bool
    is_functional: bool
    datasets_differ: bool


class EdgeOut(BaseModel):
    id: int
    source_id: int
    target_id: int
    kind: str
    input_amount: float
    efficiency: float


class CombinationAxisOut(BaseModel):
    category_node_id: int
    dataset_id: int | None


class CombinationAmountOut(BaseModel):
    category_node_id: int
    input_amount: float
    recovery_node_id: int | None


class CombinationOut(BaseModel):
    id: int
    process_node_id: int
    axes: list[CombinationAxisOut]
    amounts: list[CombinationAmountOut]


class DatasetShareOut(BaseModel):
    category_node_id: int
    dataset_id: int
    default_share: float


class ChainOut(BaseModel):
    id: int
    name: str
    status: str
    end_product_id: int
    end_unit: str
    end_product_name: str
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    combinations: list[CombinationOut]
    dataset_shares: list[DatasetShareOut]


class CalculateIn(BaseModel):
    chain_id: int
    end_amount: float | None = None
    selections: dict[str, int] = Field(default_factory=dict)
    shares: dict[str, float] = Field(default_factory=dict)
    optional_on: list[int] = Field(default_factory=list)
    replaced_nodes: dict[str, int] = Field(default_factory=dict)


class ContributionOut(BaseModel):
    node_id: int
    node_name: str
    role_id: int
    role_label: str
    use_key: str
    dataset_id: int
    dataset_name: str
    amount: float
    unit: str
    indicator_id: str
    value: float


class InventorySummaryOut(BaseModel):
    flow_count: int = 0
    catalog_dataset_count: int = 0
    user_dataset_count: int = 0
    slot_count: int = 0


class CalculateOut(BaseModel):
    totals: dict[str, float]
    contributions: list[ContributionOut]
    blockers: list[str]
    mode: str = "lcia"
    inventory_summary: InventorySummaryOut = Field(default_factory=InventorySummaryOut)


class ConfigurationIn(BaseModel):
    name: str = "Konfiguration"
    chain_id: int
    end_amount: float
    selections: dict[str, int] = Field(default_factory=dict)
    shares: dict[str, float] = Field(default_factory=dict)
    optional_on: list[int] = Field(default_factory=list)
    replaced_nodes: dict[str, int] = Field(default_factory=dict)


class ConfigurationOut(BaseModel):
    id: int
    name: str
    chain_id: int
    end_amount: float
    invalid: bool
    invalid_reason: str
    selections: dict[str, int]
    shares: dict[str, float]
    optional_on: list[int]
    replaced_nodes: dict[str, int]
    chain_name: str
    end_product_id: int
    end_product_name: str
    end_unit: str
    created_at: datetime | None = None


class CompareIn(BaseModel):
    configuration_ids: list[int]


class CompareItemOut(BaseModel):
    configuration: ConfigurationOut
    result: CalculateOut


class CompareOut(BaseModel):
    items: list[CompareItemOut]
    blockers: list[str]


class PromoteIn(BaseModel):
    role: str
