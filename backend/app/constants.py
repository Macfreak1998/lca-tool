from __future__ import annotations

METHOD_ID = "EF3.1"

CLIMATE_CHANGE = "climate_change"

INDICATORS: list[dict[str, str]] = [
    {"id": "climate_change", "label": "Klimawandel", "unit": "kg CO₂-Äq."},
    {"id": "climate_change_fossil", "label": "Klimawandel, fossil", "unit": "kg CO₂-Äq."},
    {"id": "climate_change_biogenic", "label": "Klimawandel, biogen", "unit": "kg CO₂-Äq."},
    {"id": "climate_change_luluc", "label": "Klimawandel, Landnutzung", "unit": "kg CO₂-Äq."},
    {"id": "ozone_depletion", "label": "Ozonabbau", "unit": "kg CFC-11-Äq."},
    {"id": "human_toxicity_cancer", "label": "Humantoxizität, kanzerogen", "unit": "CTUh"},
    {"id": "human_toxicity_non_cancer", "label": "Humantoxizität, nicht kanzerogen", "unit": "CTUh"},
    {"id": "particulate_matter", "label": "Feinstaub", "unit": "disease inc."},
    {"id": "ionising_radiation", "label": "Ionisierende Strahlung", "unit": "kBq U-235-Äq."},
    {"id": "photochemical_ozone", "label": "Photochemische Ozonbildung", "unit": "kg NMVOC-Äq."},
    {"id": "acidification", "label": "Versauerung", "unit": "mol H⁺-Äq."},
    {"id": "eutrophication_terrestrial", "label": "Eutrophierung, terrestrisch", "unit": "mol N-Äq."},
    {"id": "eutrophication_freshwater", "label": "Eutrophierung, Süßwasser", "unit": "kg P-Äq."},
    {"id": "eutrophication_marine", "label": "Eutrophierung, Meer", "unit": "kg N-Äq."},
    {"id": "ecotoxicity_freshwater", "label": "Ökotoxizität, Süßwasser", "unit": "CTUe"},
    {"id": "land_use", "label": "Landnutzung", "unit": "Pt"},
    {"id": "water_use", "label": "Wasserverbrauch", "unit": "m³ Welt-Äq."},
    {"id": "resource_use_minerals", "label": "Ressourcen, Mineralien und Metalle", "unit": "kg Sb-Äq."},
    {"id": "resource_use_fossils", "label": "Ressourcen, Fossilien", "unit": "MJ"},
]

INDICATOR_IDS = [item["id"] for item in INDICATORS]
INDICATOR_BY_ID = {item["id"]: item for item in INDICATORS}

SOURCE_ECOINVENT = "ecoinvent"
SOURCE_CATALOG_MANUAL = "catalog_manual"
SOURCE_USER = "user"

ROLE_USER = "user"
ROLE_ADMIN = "admin"

CHAIN_DRAFT = "draft"
CHAIN_PUBLISHED = "published"

SETTING_ARCHIVE_PATH = "archive_path"
