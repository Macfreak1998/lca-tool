from __future__ import annotations

from fastapi import APIRouter

from app.deps import AdminUser, DbDep
from app.schemas import ArchivePathIn, ArchivePathOut
from app.services.archive import get_archive_path, set_archive_path

router = APIRouter()


@router.get("/archive-path", response_model=ArchivePathOut)
def read_archive_path(_admin: AdminUser, db: DbDep) -> ArchivePathOut:
    path = get_archive_path(db)
    return ArchivePathOut(path=str(path) if path else "")


@router.put("/archive-path", response_model=ArchivePathOut)
def write_archive_path(payload: ArchivePathIn, _admin: AdminUser, db: DbDep) -> ArchivePathOut:
    return ArchivePathOut(path=set_archive_path(db, payload.path.strip()))
