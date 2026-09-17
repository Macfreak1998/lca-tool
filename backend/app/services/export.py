from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook

from app.constants import INDICATOR_BY_ID
from app.services.calculate import MODE_INVENTORY, CalcResult


def _lcia_rows(items: list[tuple[str, CalcResult]]) -> list[list[str]]:
    header = [
        "Konfiguration",
        "Indikator",
        "Einheit",
        "Summe",
        "Stufe",
        "Kategorie",
        "Datensatz",
        "Menge",
        "Mengeneinheit",
        "Beitrag",
    ]
    rows: list[list[str]] = [header]
    for name, result in items:
        for indicator_id, total in result.totals.items():
            meta = INDICATOR_BY_ID.get(indicator_id, {"label": indicator_id, "unit": ""})
            contribs = [row for row in result.contributions if row.indicator_id == indicator_id]
            if not contribs:
                rows.append(
                    [name, meta["label"], meta["unit"], f"{total}", "", "", "", "", "", ""]
                )
                continue
            for row in contribs:
                rows.append(
                    [
                        name,
                        meta["label"],
                        meta["unit"],
                        f"{total}",
                        row.stage_name,
                        row.role_label,
                        row.dataset_name,
                        f"{row.amount}",
                        row.unit,
                        f"{row.value}",
                    ]
                )
    return rows


def _inventory_rows(items: list[tuple[str, CalcResult]]) -> list[list[str]]:
    header = [
        "Konfiguration",
        "Fluss",
        "Kompartiment",
        "Unterkompartiment",
        "Einheit",
        "Summe",
        "Stufe",
        "Kategorie",
        "Datensatz",
        "Beitrag",
    ]
    rows: list[list[str]] = [header]
    for name, result in items:
        totals: dict[tuple[str, str, str, str], float] = defaultdict(float)
        for line in result.inventory_lines:
            key = (line.flow_id, line.name, line.compartment, line.unit)
            totals[key] += line.value
        if not result.inventory_lines:
            rows.append([name, "", "", "", "", "", "", "", "", ""])
            continue
        for line in result.inventory_lines:
            key = (line.flow_id, line.name, line.compartment, line.unit)
            rows.append(
                [
                    name,
                    line.name or line.flow_id,
                    line.compartment,
                    line.subcompartment,
                    line.unit,
                    f"{totals[key]}",
                    line.stage_name,
                    line.role_label,
                    line.dataset_name,
                    f"{line.value}",
                ]
            )
    return rows


def _rows(items: list[tuple[str, CalcResult]]) -> list[list[str]]:
    if any(result.mode == MODE_INVENTORY for _name, result in items):
        return _inventory_rows(items)
    return _lcia_rows(items)


def to_csv(items: list[tuple[str, CalcResult]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerows(_rows(items))
    return buffer.getvalue().encode("utf-8-sig")


def to_xlsx(items: list[tuple[str, CalcResult]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ergebnisse"
    for row in _rows(items):
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_tmp(data: bytes, suffix: str) -> Path:
    path = Path("/tmp") / f"lca-export{suffix}"
    path.write_bytes(data)
    return path
