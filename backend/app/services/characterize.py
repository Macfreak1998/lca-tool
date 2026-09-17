from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from app.config import settings
from app.constants import INDICATOR_IDS

NS = {"es": "http://www.EcoInvent.org/EcoSpold02"}


@dataclass
class ParsedExchange:
    flow_id: str
    amount: float
    name: str = ""
    unit: str = "kg"
    compartment: str = ""
    subcompartment: str = ""


@dataclass
class Characterized:
    name: str
    location: str
    unit: str
    activity_name: str
    activity_uuid: str
    product_uuid: str
    filename: str
    factors: dict[str, float]


def method_path(path: Path | None = None) -> Path | None:
    if path is not None:
        return path
    if settings.ef31_method_path:
        return Path(settings.ef31_method_path)
    return None


def load_method(path: Path | None = None) -> dict:
    resolved = method_path(path)
    if resolved is None or not resolved.exists():
        raise FileNotFoundError(
            "EF-3.1-Methodendatei fehlt. Bitte EF31_METHOD_PATH setzen "
            "(JSON mit factors: flow_id, indicator, value)."
        )
    data = json.loads(resolved.read_text(encoding="utf-8"))
    mapping: dict[str, dict[str, float]] = {}
    for row in data.get("factors", []):
        flow_id = str(row.get("flow_id") or row.get("elementaryExchangeId") or "").lower()
        indicator = str(row.get("indicator") or row.get("indicator_id") or "")
        if not flow_id or indicator not in INDICATOR_IDS:
            continue
        mapping.setdefault(flow_id, {})[indicator] = float(row["value"])
    return mapping


def try_load_method(path: Path | None = None) -> dict[str, dict[str, float]] | None:
    try:
        mapping = load_method(path)
    except FileNotFoundError:
        return None
    return mapping or None


def method_available() -> bool:
    return try_load_method() is not None


def apply_lcia(
    inventory: dict[str, float],
    mapping: dict[str, dict[str, float]],
) -> tuple[dict[str, float], bool]:
    totals: dict[str, float] = {}
    matched = False
    for flow_id, amount in inventory.items():
        factors = mapping.get(flow_id)
        if not factors:
            continue
        matched = True
        for indicator, factor in factors.items():
            totals[indicator] = totals.get(indicator, 0.0) + amount * factor
    return totals, matched


def _text(node, xpath: str) -> str:
    found = node.xpath(xpath, namespaces=NS)
    if not found:
        return ""
    value = found[0]
    if hasattr(value, "text"):
        return (value.text or "").strip()
    return str(value).strip()


def parse_spold(path: Path) -> tuple[dict, list[ParsedExchange]]:
    tree = etree.parse(str(path))
    root = tree.getroot()
    activity = root.find(".//es:activity", NS)
    activity_name = _text(root, ".//es:activityName/text()") or _text(root, ".//es:activity/@activityName")
    if not activity_name and activity is not None:
        activity_name = activity.get("activityName") or ""
    activity_uuid = ""
    if activity is not None:
        activity_uuid = activity.get("id") or ""
    location = _text(root, ".//es:geography/es:shortname/text()") or _text(
        root, ".//es:geography/es:location/text()"
    )
    ref = None
    for exchange in root.findall(".//es:intermediateExchange", NS):
        if exchange.find("es:outputGroup", NS) is not None and (
            exchange.findtext("es:outputGroup", namespaces=NS) == "0"
            or exchange.get("intermediateExchangeId")
        ):
            if exchange.find("es:outputGroup", NS) is not None:
                ref = exchange
                break
    if ref is None:
        for exchange in root.findall(".//es:intermediateExchange", NS):
            if exchange.find("es:outputGroup", NS) is not None:
                ref = exchange
                break
    unit = "kg"
    product_uuid = ""
    name = activity_name
    if ref is not None:
        unit = ref.findtext("es:unitName", default="kg", namespaces=NS) or "kg"
        product_uuid = ref.get("intermediateExchangeId") or ref.get("id") or ""
        name = ref.findtext("es:name", default=activity_name, namespaces=NS) or activity_name
    flows: list[ParsedExchange] = []
    for el in root.findall(".//es:elementaryExchange", NS):
        flow_id = (el.get("elementaryExchangeId") or el.get("id") or "").lower()
        amount_raw = el.get("amount")
        if amount_raw is None:
            continue
        try:
            amount = float(amount_raw)
        except ValueError:
            continue
        compartment = el.find("es:compartment", NS)
        flows.append(
            ParsedExchange(
                flow_id=flow_id,
                amount=amount,
                name=el.findtext("es:name", default="", namespaces=NS) or "",
                unit=el.findtext("es:unitName", default="kg", namespaces=NS) or "kg",
                compartment=(
                    compartment.findtext("es:compartment", default="", namespaces=NS) or ""
                    if compartment is not None
                    else ""
                ),
                subcompartment=(
                    compartment.findtext("es:subcompartment", default="", namespaces=NS) or ""
                    if compartment is not None
                    else ""
                ),
            )
        )
    meta = {
        "name": name,
        "location": location,
        "unit": unit,
        "activity_name": activity_name,
        "activity_uuid": activity_uuid,
        "product_uuid": product_uuid,
        "filename": path.name,
    }
    return meta, flows


def characterize_spold(spold_path: Path, method_path: Path | None = None) -> Characterized:
    mapping = load_method(method_path)
    meta, flows = parse_spold(spold_path)
    totals, matched = apply_lcia({item.flow_id: item.amount for item in flows}, mapping)
    if not matched:
        raise ValueError(
            "Keine Elementarflüsse der Datei passen zur EF-3.1-Methodendatei."
        )
    for indicator in INDICATOR_IDS:
        totals.setdefault(indicator, 0.0)
    return Characterized(
        name=meta["name"],
        location=meta["location"],
        unit=meta["unit"],
        activity_name=meta["activity_name"],
        activity_uuid=meta["activity_uuid"],
        product_uuid=meta["product_uuid"],
        filename=meta["filename"],
        factors=totals,
    )
