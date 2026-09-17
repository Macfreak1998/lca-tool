from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.deps import AdminUser, DbDep
from app.schemas import ArchiveHit
from app.services.archive import get_archive_path, search_archive

router = APIRouter()


@router.get("/search", response_model=list[ArchiveHit])
def search(
    _admin: AdminUser,
    db: DbDep,
    q: str = Query(min_length=1),
    limit: int = Query(default=40, le=100),
) -> list[ArchiveHit]:
    archive = get_archive_path(db)
    if archive is None or not archive.exists():
        raise HTTPException(status_code=400, detail="Archiv-Pfad ist nicht gesetzt oder existiert nicht.")
    try:
        hits = search_archive(archive, q, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lookup-Datei kann nicht gelesen werden: {exc}",
        ) from exc
    return [
        ArchiveHit(
            filename=hit.filename,
            activity_name=hit.activity_name,
            location=hit.location,
            reference_product=hit.reference_product,
            likely_market=hit.likely_market,
        )
        for hit in hits
    ]
