from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbDep
from app.models import Chain, Dataset, Role, Stage
from app.schemas import CalculateIn, CalculateOut
from app.serialize import calc_out
from app.services.calculate import CalcInput, ExtraSlot, calculate
from app.services.export import to_csv, to_xlsx

router = APIRouter()


def _datasets(db) -> dict[int, Dataset]:
    rows = db.query(Dataset).options(
        selectinload(Dataset.factors),
        selectinload(Dataset.roles),
        selectinload(Dataset.exchanges),
    ).all()
    return {row.id: row for row in rows}


def _roles(db) -> dict[int, Role]:
    return {row.id: row for row in db.query(Role).all()}


def _to_input(payload: CalculateIn) -> CalcInput:
    return CalcInput(
        end_amount=payload.end_amount,
        selections={str(key): value for key, value in payload.selections.items()},
        shares=payload.shares,
        optional_on=payload.optional_on,
        extra_slots=[
            ExtraSlot(
                key=item.key,
                stage_id=item.stage_id,
                role_id=item.role_id,
                dataset_id=item.dataset_id,
                share=item.share,
            )
            for item in payload.extra_slots
        ],
        replaced_stages={int(key): value for key, value in payload.replaced_stages.items()},
    )


@router.post("", response_model=CalculateOut)
def run_calculate(payload: CalculateIn, _user: CurrentUser, db: DbDep) -> CalculateOut:
    chain = (
        db.query(Chain)
        .options(selectinload(Chain.stages).selectinload(Stage.slots), selectinload(Chain.end_product))
        .filter(Chain.id == payload.chain_id)
        .first()
    )
    if chain is None:
        raise HTTPException(status_code=404, detail="Kette nicht gefunden.")
    result = calculate(chain, _to_input(payload), _datasets(db), _roles(db), require_published=True)
    return calc_out(result)


@router.post("/export")
def export_calculate(payload: CalculateIn, _user: CurrentUser, db: DbDep, format: str = "csv") -> Response:
    chain = (
        db.query(Chain)
        .options(selectinload(Chain.stages).selectinload(Stage.slots), selectinload(Chain.end_product))
        .filter(Chain.id == payload.chain_id)
        .first()
    )
    if chain is None:
        raise HTTPException(status_code=404, detail="Kette nicht gefunden.")
    result = calculate(chain, _to_input(payload), _datasets(db), _roles(db), require_published=True)
    if result.blockers:
        raise HTTPException(status_code=400, detail=result.blockers)
    name = chain.name
    if format == "xlsx":
        data = to_xlsx([(name, result)])
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="ergebnis.xlsx"'},
        )
    data = to_csv([(name, result)])
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ergebnis.csv"'},
    )
