from __future__ import annotations

_SYNONYMS = {
    "kilowatthour": "kwh",
    "kilogram": "kg",
}


def canonical_unit(unit: str | None) -> str:
    text = (unit or "").strip().lower().replace("·", "*").replace("-", "")
    text = "".join(text.split())
    return _SYNONYMS.get(text, text)


def same_unit(left: str | None, right: str | None) -> bool:
    return canonical_unit(left) == canonical_unit(right)


def resolve_category_unit(sent_unit: str, dataset_units: list[str], *, energy: bool) -> str:
    if dataset_units and all(same_unit(unit, dataset_units[0]) for unit in dataset_units):
        return dataset_units[0]
    if dataset_units:
        return sent_unit
    if energy and (not sent_unit.strip() or same_unit(sent_unit, "kg")):
        return "kWh"
    return sent_unit


def unit_mismatch_message(dataset_name: str, dataset_unit: str, category_name: str, category_unit: str) -> str:
    return f"Einheit von „{dataset_name}“ ({dataset_unit}) passt nicht zu „{category_name}“ ({category_unit})."
