from __future__ import annotations

from app.constants import METHOD_ID, SOURCE_USER
from app.models import Chain, Configuration, Dataset, DatasetFactor, User
from app.schemas import (
    CalculateOut,
    ChainOut,
    ConfigurationOut,
    ContributionOut,
    DatasetOut,
    ExtraSlotIn,
    FactorOut,
    InventorySummaryOut,
    SlotOut,
    StageOut,
    UserOut,
)
from app.services.calculate import CalcInput, CalcResult, ExtraSlot


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
    stages = []
    for stage in sorted(chain.stages, key=lambda item: item.sort_order):
        stages.append(
            StageOut(
                id=stage.id,
                name=stage.name,
                sort_order=stage.sort_order,
                outgoing_stage_id=stage.outgoing_stage_id,
                upstream_amount=stage.upstream_amount,
                slots=[
                    SlotOut(
                        id=slot.id,
                        role_id=slot.role_id,
                        required=slot.required,
                        optional_default_off=slot.optional_default_off,
                        min_count=slot.min_count,
                        specific_amount=slot.specific_amount,
                        unit=slot.unit,
                        default_dataset_id=slot.default_dataset_id,
                        default_share=slot.default_share,
                    )
                    for slot in stage.slots
                ],
            )
        )
    return ChainOut(
        id=chain.id,
        name=chain.name,
        status=chain.status,
        end_product_id=chain.end_product_id,
        end_unit=chain.end_unit,
        end_product_name=chain.end_product.name if chain.end_product else "",
        stages=stages,
    )


def configuration_out(row: Configuration) -> ConfigurationOut:
    extras = [
        ExtraSlotIn(
            key=f"extra:{item.id}",
            stage_id=item.stage_id,
            role_id=item.role_id,
            dataset_id=item.dataset_id,
            share=item.share,
        )
        for item in row.extra_slots
    ]
    return ConfigurationOut(
        id=row.id,
        name=row.name,
        chain_id=row.chain_id,
        end_amount=row.end_amount,
        invalid=row.invalid,
        invalid_reason=row.invalid_reason,
        selections={str(item.slot_id): item.dataset_id for item in row.selections},
        shares={item.slot_key: item.percent for item in row.shares},
        optional_on=[item.slot_id for item in row.optional_on],
        extra_slots=extras,
        replaced_stages={str(item.stage_id): item.dataset_id for item in row.replaced_stages},
        chain_name=row.chain.name if row.chain else "",
        end_product_id=row.chain.end_product_id if row.chain else 0,
        end_product_name=row.chain.end_product.name if row.chain and row.chain.end_product else "",
        end_unit=row.chain.end_unit if row.chain else "",
        created_at=row.created_at,
    )


def calc_input_from_config(row: Configuration) -> CalcInput:
    return CalcInput(
        end_amount=row.end_amount,
        selections={str(item.slot_id): item.dataset_id for item in row.selections},
        shares={item.slot_key: item.percent for item in row.shares},
        optional_on=[item.slot_id for item in row.optional_on],
        extra_slots=[
            ExtraSlot(
                key=f"extra:{item.id}",
                stage_id=item.stage_id,
                role_id=item.role_id,
                dataset_id=item.dataset_id,
                share=item.share,
            )
            for item in row.extra_slots
        ],
        replaced_stages={item.stage_id: item.dataset_id for item in row.replaced_stages},
    )


def calc_out(result: CalcResult) -> CalculateOut:
    summary = result.inventory_summary
    return CalculateOut(
        totals=result.totals,
        contributions=[
            ContributionOut(
                stage_id=row.stage_id,
                stage_name=row.stage_name,
                role_id=row.role_id,
                role_label=row.role_label,
                slot_key=row.slot_key,
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
