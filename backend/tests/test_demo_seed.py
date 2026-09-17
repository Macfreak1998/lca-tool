from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.models import Chain, Dataset
from app.services.demo import seed_demo


def test_seed_demo_creates_published_chain(db, fixtures_dir: Path, tmp_path: Path, monkeypatch):
    archive = tmp_path / "demo-archive"
    (archive / "datasets").mkdir(parents=True)
    (archive / "FilenameToActivityLookup.csv").write_text(
        "Filename,ActivityName,Location,ReferenceProduct\n"
        "aaa-111_bbb-222.spold,market for maize starch,DE,maize starch\n",
        encoding="utf-8",
    )
    (archive / "datasets" / "aaa-111_bbb-222.spold").write_text(
        (fixtures_dir / "sample.spold").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "demo_seed", True)
    monkeypatch.setattr(settings, "archive_path", str(archive))
    seed_demo(db)
    chain = db.query(Chain).first()
    assert chain is not None
    assert chain.status == "published"
    assert db.query(Dataset).count() == 1
    seed_demo(db)
    assert db.query(Chain).count() == 1


def test_seed_demo_off_by_default(db, monkeypatch):
    monkeypatch.setattr(settings, "demo_seed", False)
    seed_demo(db)
    assert db.query(Chain).count() == 0
