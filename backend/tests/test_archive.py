from __future__ import annotations

from pathlib import Path

from app.services.archive import search_archive


def test_search_matches_name_location_product(fixtures_dir: Path, tmp_path: Path):
    archive = tmp_path / "ecoinvent"
    archive.mkdir()
    (archive / "FilenameToActivityLookup.csv").write_text(
        (fixtures_dir / "lookup.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    hits = search_archive(archive, "maize DE")
    assert hits
    assert all("maize" in hit.activity_name.lower() or "maize" in hit.reference_product.lower() for hit in hits)
    assert hits[0].likely_market


def test_single_field_requires_all_terms(fixtures_dir: Path, tmp_path: Path):
    archive = tmp_path / "ecoinvent"
    archive.mkdir()
    (archive / "FilenameToActivityLookup.csv").write_text(
        (fixtures_dir / "lookup.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    hits = search_archive(archive, "electricity FR")
    assert hits == []
    hits = search_archive(archive, "electricity DE")
    assert len(hits) == 1


def test_search_reads_ecoinvent_semicolon_csv(tmp_path: Path):
    archive = tmp_path / "ecoinvent"
    archive.mkdir()
    (archive / "FilenameToActivityLookup.csv").write_text(
        "Filename;ActivityName;Location;ReferenceProduct\r\n"
        "aaa.spold;plastic tunnel construction;FR;plastic tunnel\r\n"
        "bbb.spold;market for maize starch;DE;maize starch\r\n"
        "ccc.spold;maize starch production;DE;maize starch\r\n",
        encoding="utf-8",
    )
    hits = search_archive(archive, "maize")
    assert [hit.activity_name for hit in hits] == [
        "market for maize starch",
        "maize starch production",
    ]
    assert hits[0].likely_market
