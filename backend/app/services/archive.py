from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SETTING_ARCHIVE_PATH
from app.models import Setting


@dataclass
class ArchiveHit:
    filename: str
    activity_name: str
    location: str
    reference_product: str

    @property
    def likely_market(self) -> bool:
        name = self.activity_name.lower()
        return name.startswith("market for") or "market for" in name


def get_archive_path(db: Session) -> Path | None:
    row = db.get(Setting, SETTING_ARCHIVE_PATH)
    raw = (row.value if row else "") or settings.archive_path
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else path


def set_archive_path(db: Session, path: str) -> str:
    row = db.get(Setting, SETTING_ARCHIVE_PATH)
    if row is None:
        row = Setting(key=SETTING_ARCHIVE_PATH, value=path)
        db.add(row)
    else:
        row.value = path
    db.commit()
    return path


def lookup_csv_path(archive: Path) -> Path:
    direct = archive / "FilenameToActivityLookup.csv"
    if direct.exists():
        return direct
    matches = list(archive.glob("**/FilenameToActivityLookup.csv"))
    if matches:
        return matches[0]
    return direct


def dataset_file(archive: Path, filename: str) -> Path:
    name = Path(filename).name
    direct = archive / "datasets" / name
    if direct.exists():
        return direct
    matches = list(archive.glob(f"**/{name}"))
    if matches:
        return matches[0]
    return direct


def _lookup_field(row: dict[str, str | None], *names: str) -> str:
    mapped = {((key or "").strip().lower()): (value or "") for key, value in row.items()}
    for name in names:
        value = mapped.get(name.lower())
        if value:
            return value.strip()
    return ""


def _lookup_delimiter(sample: str) -> str:
    header = sample.splitlines()[0] if sample else ""
    if header.count(";") > header.count(","):
        return ";"
    if header.count("\t") > header.count(","):
        return "\t"
    return ","


def search_archive(archive: Path, query: str, limit: int = 50) -> list[ArchiveHit]:
    csv_path = lookup_csv_path(archive)
    if not csv_path.exists():
        raise FileNotFoundError(f"Lookup-Datei nicht gefunden: {csv_path}")
    terms = [part.lower() for part in query.split() if part.strip()]
    hits: list[ArchiveHit] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        sample = handle.readline()
        handle.seek(0)
        reader = csv.DictReader(handle, delimiter=_lookup_delimiter(sample))
        for row in reader:
            filename = _lookup_field(row, "Filename")
            activity = _lookup_field(row, "ActivityName")
            location = _lookup_field(row, "Location")
            product = _lookup_field(row, "ReferenceProduct")
            blob = f"{activity} {location} {product}".lower()
            if terms and not all(term in blob for term in terms):
                continue
            hits.append(
                ArchiveHit(
                    filename=filename,
                    activity_name=activity,
                    location=location,
                    reference_product=product,
                )
            )
    hits.sort(key=lambda item: (not item.likely_market, item.activity_name.lower()))
    return hits[:limit]
