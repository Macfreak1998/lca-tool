from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbDep
from app.models import Chain, Configuration, Dataset, Role, Stage
from app.schemas import CompareIn, CompareItemOut, CompareOut, ConfigurationOut
from app.serialize import calc_input_from_config, calc_out, configuration_out
from app.services.calculate import calculate
from app.services.export import to_csv, to_xlsx

router = APIRouter()


def _load_configs(db, user_id: int, ids: list[int]) -> list[Configuration]:
    rows = (
        db.query(Configuration)
        .options(
            selectinload(Configuration.chain).selectinload(Chain.end_product),
            selectinload(Configuration.chain).selectinload(Chain.stages).selectinload(Stage.slots),
            selectinload(Configuration.selections),
            selectinload(Configuration.shares),
            selectinload(Configuration.optional_on),
            selectinload(Configuration.extra_slots),
            selectinload(Configuration.replaced_stages),
        )
        .filter(Configuration.user_id == user_id, Configuration.id.in_(ids))
        .all()
    )
    by_id = {row.id: row for row in rows}
    ordered = [by_id[item] for item in ids if item in by_id]
    if len(ordered) != len(ids):
        raise HTTPException(status_code=404, detail="Eine Konfiguration wurde nicht gefunden.")
    return ordered


def _run(db, rows: list[Configuration]) -> tuple[list[CompareItemOut], list[str], list[tuple[str, object]]]:
    blockers: list[str] = []
    if not 2 <= len(rows) <= 4:
        blockers.append("Bitte 2 bis 4 Konfigurationen wählen.")
    if rows:
        first = rows[0]
        end_product_id = first.chain.end_product_id
        amount = first.end_amount
        unit = first.chain.end_unit
        for row in rows[1:]:
            if row.chain.end_product_id != end_product_id or row.chain.end_unit != unit:
                blockers.append("Vergleich nur bei gleichem Endprodukt und gleicher Einheit.")
            if abs(row.end_amount - amount) > 1e-9:
                blockers.append("Vergleich nur bei gleicher Endmenge.")
            if row.invalid:
                blockers.append(f"„{row.name}“ ist ungültig und muss ergänzt werden.")
    datasets = {
        item.id: item
        for item in db.query(Dataset).options(
            selectinload(Dataset.factors),
            selectinload(Dataset.roles),
            selectinload(Dataset.exchanges),
        ).all()
    }
    roles = {item.id: item for item in db.query(Role).all()}
    items: list[CompareItemOut] = []
    raw: list[tuple[str, object]] = []
    if blockers:
        return [], blockers, []
    for row in rows:
        result = calculate(row.chain, calc_input_from_config(row), datasets, roles)
        if result.blockers:
            blockers.extend([f"{row.name}: {msg}" for msg in result.blockers])
            continue
        items.append(
            CompareItemOut(
                configuration=configuration_out(row),
                result=calc_out(result),
            )
        )
        raw.append((row.name, result))
    return items, blockers, raw


@router.post("", response_model=CompareOut)
def compare(payload: CompareIn, user: CurrentUser, db: DbDep) -> CompareOut:
    rows = _load_configs(db, user.id, payload.configuration_ids)
    items, blockers, _raw = _run(db, rows)
    return CompareOut(items=items, blockers=blockers)


@router.post("/export")
def compare_export(payload: CompareIn, user: CurrentUser, db: DbDep, format: str = "csv") -> Response:
    rows = _load_configs(db, user.id, payload.configuration_ids)
    items, blockers, raw = _run(db, rows)
    if blockers:
        raise HTTPException(status_code=400, detail=blockers)
    if format == "xlsx":
        data = to_xlsx(raw)  # type: ignore[arg-type]
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "vergleich.xlsx"
    else:
        data = to_csv(raw)  # type: ignore[arg-type]
        media = "text/csv; charset=utf-8"
        filename = "vergleich.csv"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
