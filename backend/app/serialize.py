from __future__ import annotations

from app.constants import METHOD_ID, SOURCE_USER
from app.models import Chain, Configuration, Dataset, DatasetFactor, Role, User
from app.schemas import (
    CalculateOut,
    ChainOut,
    ConfigurationOut,
    ContributionOut,
    DatasetOut,
    EdgeOut,
    FactorOut,
    InventorySummaryOut,
    NodeOut,
    RoleOut,
    UserOut,
    CombinationAmountOut,
    CombinationAxisOut,
    CombinationOut,
    DatasetShareOut,
)
from app.services.calculate import CalcInput, CalcResult


def role_out(role: Role, dataset_count: int = 0) -> RoleOut:
    return RoleOut(id=role.id, slug=role.slug, label=role.label, dataset_count=dataset_count)


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified_at is not None,
    )


def dataset_out(dataset: Dataset, *, include_factors: bool = False) -> DatasetOut:
    factors = None
    if include_factors or dataset.source_kind == SOURCE_USER:
        factors = [
            FactorOut(method_id=row.method_id, indicator_id=row.indicator_id, value=row.value)
            for row in dataset.factors
        ]
    return DatasetOut(
        id=dataset.id,
        name=dataset.name,
        location=dataset.location,
        unit=dataset.unit,
        source_kind=dataset.source_kind,
        source_id=dataset.source_id,
        activity_name=dataset.activity_name,
        filename=dataset.filename,
        source_note=dataset.source_note,
        inputs_doc=dataset.inputs_doc,
        owner_user_id=dataset.owner_user_id,
        role_ids=[row.role_id for row in dataset.roles],
        factors=factors,
        exchange_count=len(dataset.exchanges) if dataset.exchanges is not None else 0,
    )


def chain_out(chain: Chain) -> ChainOut:
    return ChainOut(
        id=chain.id,
        name=chain.name,
        status=chain.status,
        end_product_id=chain.end_product_id,
        end_unit=chain.end_unit,
        end_product_name=chain.end_product.name if chain.end_product else "",
        nodes=[
            NodeOut(
                id=node.id,
                type=node.type,
                name=node.name,
                position_x=node.position_x,
                position_y=node.position_y,
                role_id=node.role_id,
                dataset_id=node.dataset_id,
                unit=node.unit,
                distance_km=node.distance_km,
                optional=node.optional,
                is_functional=node.is_functional,
                datasets_differ=node.datasets_differ,
            )
            for node in chain.nodes
        ],
        edges=[
            EdgeOut(
                id=edge.id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                kind=edge.kind,
                input_amount=edge.input_amount,
                efficiency=edge.efficiency,
            )
            for edge in chain.edges
        ],
        combinations=[
            CombinationOut(
                id=combo.id,
                process_node_id=combo.process_node_id,
                axes=[
                    CombinationAxisOut(
                        category_node_id=axis.category_node_id,
                        dataset_id=axis.dataset_id,
                    )
                    for axis in combo.axes
                ],
                amounts=[
                    CombinationAmountOut(
                        category_node_id=amount.category_node_id,
                        input_amount=amount.input_amount,
                        recovery_node_id=amount.recovery_node_id,
                    )
                    for amount in combo.amounts
                ],
            )
            for combo in chain.combinations
        ],
        dataset_shares=[
            DatasetShareOut(
                category_node_id=share.category_node_id,
                dataset_id=share.dataset_id,
                default_share=share.default_share,
            )
            for share in chain.dataset_shares
        ],
    )


def configuration_out(row: Configuration) -> ConfigurationOut:
    return ConfigurationOut(
        id=row.id,
        name=row.name,
        chain_id=row.chain_id,
        end_amount=row.end_amount,
        invalid=row.invalid,
        invalid_reason=row.invalid_reason,
        selections={str(item.node_id): item.dataset_id for item in row.selections},
        shares={f"{item.category_node_id}:{item.dataset_id}": item.percent for item in row.shares},
        optional_on=[item.node_id for item in row.optional_on],
        replaced_nodes={str(item.node_id): item.dataset_id for item in row.replaced_nodes},
        chain_name=row.chain.name if row.chain else "",
        end_product_id=row.chain.end_product_id if row.chain else 0,
        end_product_name=row.chain.end_product.name if row.chain and row.chain.end_product else "",
        end_unit=row.chain.end_unit if row.chain else "",
        created_at=row.created_at,
    )


def calc_input_from_config(row: Configuration) -> CalcInput:
    return CalcInput(
        end_amount=row.end_amount,
        selections={str(item.node_id): item.dataset_id for item in row.selections},
        shares={f"{item.category_node_id}:{item.dataset_id}": item.percent for item in row.shares},
        optional_on=[item.node_id for item in row.optional_on],
        replaced_nodes={item.node_id: item.dataset_id for item in row.replaced_nodes},
    )


def calc_out(result: CalcResult) -> CalculateOut:
    summary = result.inventory_summary
    return CalculateOut(
        totals=result.totals,
        contributions=[
            ContributionOut(
                node_id=row.node_id,
                node_name=row.node_name,
                role_id=row.role_id,
                role_label=row.role_label,
                use_key=row.use_key,
                dataset_id=row.dataset_id,
                dataset_name=row.dataset_name,
                amount=row.amount,
                unit=row.unit,
                indicator_id=row.indicator_id,
                value=row.value,
            )
            for row in result.contributions
        ],
        blockers=result.blockers,
        mode=result.mode,
        inventory_summary=InventorySummaryOut(
            flow_count=summary.flow_count,
            catalog_dataset_count=summary.catalog_dataset_count,
            user_dataset_count=summary.user_dataset_count,
            slot_count=summary.slot_count,
        ),
    )


def replace_factors(dataset: Dataset, values: dict[str, float | None]) -> None:
    dataset.factors.clear()
    for indicator_id, value in values.items():
        dataset.factors.append(
            DatasetFactor(
                method_id=METHOD_ID,
                indicator_id=indicator_id,
                value=value,
            )
        )
