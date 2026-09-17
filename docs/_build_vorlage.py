#!/usr/bin/env python3
"""Erzeugt die OpenLCA-Dokumentationsvorlage für die Modellierung."""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chartsheet import Chartsheet
from openpyxl.workbook.protection import WorkbookProtection
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.comments import Comment
from openpyxl.worksheet.page import PageMargins
from openpyxl.formatting.rule import CellIsRule
from openpyxl.workbook.child import _WorkbookChild
from openpyxl.utils.cell import range_boundaries
from copy import copy

OUT = "/Users/jan/Projects/LCA-Tool/docs/lca-dokumentation-vorlage.xlsx"

# --- Farben ---
NAVY = "1B4332"
TEAL = "2D6A4F"
HEADER_FG = "FFFFFF"
EXAMPLE = "E9ECEF"
EXAMPLE_FG = "495057"
HINT = "FFF3BF"
WHITE = "FFFFFF"
ZEBRA = "F8F9FA"
REQ = "D8F3DC"
INPUT = "E7F5FF"
OWN = "FFF4E6"
BORDER_C = "CED4DA"
LINK = "1B4332"

thin = Border(
    left=Side(style="thin", color=BORDER_C),
    right=Side(style="thin", color=BORDER_C),
    top=Side(style="thin", color=BORDER_C),
    bottom=Side(style="thin", color=BORDER_C),
)
thick_bottom = Border(
    left=Side(style="thin", color=BORDER_C),
    right=Side(style="thin", color=BORDER_C),
    top=Side(style="thin", color=BORDER_C),
    bottom=Side(style="medium", color=NAVY),
)

font_title = Font(name="Calibri", size=18, bold=True, color=NAVY)
font_h2 = Font(name="Calibri", size=13, bold=True, color=TEAL)
font_body = Font(name="Calibri", size=11, color="212529")
font_small = Font(name="Calibri", size=10, italic=True, color="6C757D")
font_header = Font(name="Calibri", size=11, bold=True, color=HEADER_FG)
font_example = Font(name="Calibri", size=11, italic=True, color=EXAMPLE_FG)
font_code = Font(name="Consolas", size=10, color="212529")

fill_header = PatternFill("solid", fgColor=NAVY)
fill_header2 = PatternFill("solid", fgColor=TEAL)
fill_example = PatternFill("solid", fgColor=EXAMPLE)
fill_hint = PatternFill("solid", fgColor=HINT)
fill_req = PatternFill("solid", fgColor=REQ)
fill_white = PatternFill("solid", fgColor=WHITE)
fill_zebra = PatternFill("solid", fgColor=ZEBRA)
fill_legend_cat = PatternFill("solid", fgColor="D8F3DC")

wrap = Alignment(wrap_text=True, vertical="center")
wrap_top = Alignment(wrap_text=True, vertical="top")
center = Alignment(wrap_text=True, vertical="center", horizontal="center")


def style_header_row(ws, row, ncols):
    ws.row_dimensions[row].height = 28
    for col in range(1, ncols + 1):
        cell = ws.cell(row, col)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = thin


def style_example_row(ws, row, ncols):
    ws.row_dimensions[row].height = 36
    for col in range(1, ncols + 1):
        cell = ws.cell(row, col)
        cell.font = font_example
        cell.fill = fill_example
        cell.alignment = wrap
        cell.border = thin


def style_empty_rows(ws, start, end, ncols, height=22):
    for r in range(start, end + 1):
        ws.row_dimensions[r].height = height
        for c in range(1, ncols + 1):
            cell = ws.cell(r, c)
            cell.font = font_body
            cell.alignment = wrap
            cell.border = thin
            if (r - start) % 2 == 1:
                cell.fill = fill_zebra


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def add_title_block(ws, title, subtitle, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncols)
    c1 = ws.cell(1, 1, title)
    c1.font = font_title
    c1.alignment = Alignment(vertical="center")
    c2 = ws.cell(2, 1, subtitle)
    c2.font = font_small
    c2.alignment = wrap
    hint = ws.cell(
        3,
        1,
        "Graue Zeile = Beispiel (stehen lassen als Muster). Ab der nächsten Zeile ausfüllen. "
        "Pflichtfelder stehen in der Legende. Technische IDs nach dem ersten Speichern nicht mehr umbenennen.",
    )
    hint.font = Font(name="Calibri", size=10, italic=True, color="856404")
    hint.fill = fill_hint
    hint.alignment = wrap
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 32
    ws.row_dimensions[3].height = 32


def comment(cell, text):
    cell.comment = Comment(text, "Vorlage")
    cell.comment.width = 280
    cell.comment.height = 80


def add_dv(ws, formula, cells, allow_blank=True):
    dv = DataValidation(
        type="list",
        formula1=formula,
        allow_blank=allow_blank,
        showDropDown=False,
        showErrorMessage=True,
        errorTitle="Ungültiger Wert",
        error="Bitte einen Wert aus der Liste wählen.",
        showInputMessage=True,
        promptTitle="Auswahl",
        prompt="Wert aus der Liste wählen.",
    )
    ws.add_data_validation(dv)
    dv.add(cells)
    return dv


wb = Workbook()

# =============================================================================
# LISTEN (versteckt)
# =============================================================================
ws_lists = wb.active
ws_lists.title = "Listen"
lists = {
    "A": ["entwurf", "offen", "fertig"],
    "B": ["ja", "nein"],
    "C": ["number", "choice", "toggle"],
    "D": ["input", "output"],
    "E": ["ecoinvent", "own"],
    "F": ["EN15804GD", "APOS", "Cutoff", "Consequential", "sonstige"],
    "G": ["kg", "g", "kWh", "MJ", "Nm3", "m3", "m2", "km", "tkm", "Item(s)", "l"],
    "H": ["Lkw", "Bahn", "Schiff", "Flug", "kein Transport"],
}
headers_l = [
    "status",
    "ja_nein",
    "param_type",
    "direction",
    "source",
    "system_model",
    "unit",
    "transport",
]
for i, h in enumerate(headers_l, 1):
    ws_lists.cell(1, i, h)
for col, values in lists.items():
    for i, v in enumerate(values, 2):
        ws_lists[f"{col}{i}"] = v
ws_lists.sheet_state = "hidden"

# Named ranges via table-like references for DV
# We'll use absolute sheet refs

# =============================================================================
# ANLEITUNG
# =============================================================================
ws = wb.create_sheet("Anleitung", 0)
ws.sheet_properties.tabColor = NAVY
set_widths(ws, [4, 38, 92])
ws.row_dimensions[1].height = 28
ws.merge_cells("B1:C1")
ws["B1"] = "Dokumentationsvorlage LCA-Tool — Anleitung für die Modellierung"
ws["B1"].font = font_title

intro = [
    (
        "Wozu diese Datei?",
        "Sie ersetzt die bisherige Sachbilanz-Excel als gemeinsame Schnittstelle zwischen Modellierung (OpenLCA) und Umsetzung (Frontend/Connector). "
        "Jedes Blatt hat genau einen Zweck. Bitte nichts untereinander auf demselben Blatt stapeln.",
    ),
    (
        "Reihenfolge",
        "1) Prozesse anlegen  →  2) Parameter für die Benutzeroberfläche  →  3) Exchanges (Inputs/Outputs)  →  "
        "4) Rohdaten nur wenn Laborwerte dokumentiert werden  →  5) Jede Änderung ins Blatt Änderungen.",
    ),
    (
        "Was der Entwickler braucht",
        "Blatt Prozesse + Blatt Parameter + Blatt Exchanges. Rohdaten sind optional. "
        "Nur Zeilen mit status = fertig werden ins Tool übernommen.",
    ),
    (
        "Stabile IDs",
        "process_id und param_id sind technische Schlüssel. Nach dem ersten Eintrag nicht mehr umbenennen. "
        "Anzeigenamen (name, label) dürfen sich ändern. UUIDs nicht löschen und neu vergeben, wenn dasselbe gemeint ist.",
    ),
    (
        "Alternativen (choice)",
        "Strommix, Ethanol-Rohstoff, Folienstärke: nicht als acht Mengen-Zeilen mit 0/1,75 modellieren. "
        "Ein Parameter vom Typ choice, die Optionen stehen in Exchanges mit param_id + choice_value.",
    ),
    (
        "Ecoinvent vs. eigenes Modell",
        "source = ecoinvent nur für Hintergrunddatensätze. Eigene Prozesse (Compound, Bio-PE-Granulat, Folie) haben source = own und oft provider_uuid leer bzw. „-“.",
    ),
    (
        "Unfertiges markieren",
        "status = entwurf oder offen. Pflicht-UUIDs nicht leer lassen und trotzdem fertig setzen. Lieber offen lassen.",
    ),
    (
        "Beispielzeilen",
        "Graue Zeilen sind Muster aus dem HOF-/BioPE-Modell. Stehen lassen. Eure echten Daten darunter eintragen.",
    ),
    (
        "Version",
        "Oben rechts bzw. im Blatt Änderungen: modell-v0.1, dann hochzählen. Bei UUID-Wechsel immer eine Zeile in Änderungen.",
    ),
]
ws.merge_cells("B2:C2")
ws["B2"] = "Bitte zuerst die Legende lesen. Danach die Blätter von links nach rechts ausfüllen."
ws["B2"].font = font_small
ws["B2"].fill = fill_hint
ws["B2"].alignment = wrap
ws.row_dimensions[2].height = 22

r = 4
for title, text in intro:
    ws.cell(r, 2, title).font = font_h2
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=3)
    ws.cell(r, 3, text).font = font_body
    ws.cell(r, 3).alignment = wrap_top
    ws.row_dimensions[r].height = 56
    r += 1

ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=3)
ws.cell(r + 1, 2, "Fragen zur Vorlage: zuerst Blatt Legende, Spalte „Typischer Fehler“.").font = font_small

ws.page_setup.fitToPage = True
ws.page_setup.fitToWidth = 1
ws.page_setup.orientation = "landscape"
ws.print_title_rows = "1:1"
ws.sheet_view.showGridLines = False
ws.freeze_panes = "B4"

# =============================================================================
# LEGENDE
# =============================================================================
ws = wb.create_sheet("Legende", 1)
ws.sheet_properties.tabColor = TEAL
set_widths(ws, [22, 22, 16, 14, 62, 48])
ws.merge_cells("A1:F1")
ws["A1"] = "Legende — alle Begriffe dieser Vorlage"
ws["A1"].font = font_title
ws.merge_cells("A2:F2")
ws["A2"] = (
    "Wenn ein Feld unklar ist: hier nachschlagen. Pflicht = muss für status „fertig“ gefüllt sein. "
    "Werte in Klammern sind erlaubte Auswahlen."
)
ws["A2"].font = font_small
ws["A2"].fill = fill_hint
ws["A2"].alignment = wrap
ws.row_dimensions[1].height = 26
ws.row_dimensions[2].height = 28

legend_headers = ["Blatt", "Feld", "Pflicht", "Erlaubte Werte", "Bedeutung", "Typischer Fehler"]
for i, h in enumerate(legend_headers, 1):
    ws.cell(4, i, h)
style_header_row(ws, 4, 6)
ws.freeze_panes = "A5"
ws.auto_filter.ref = "A4:F80"

legend_rows = [
    # Prozesse
    ("Prozesse", "process_id", "ja", "klein, ohne Leerzeichen", "Stabiler technischer Name des Prozesses. Der Entwickler verwendet genau diesen Schlüssel.", "Nicht „HOF Compound v2“ schreiben. Lieber hof_compound, Version ins Blatt Änderungen."),
    ("Prozesse", "name", "ja", "freier Text", "Anzeigename für Menschen und für die Benutzeroberfläche.", "Darf sich ändern. process_id dann nicht mitändern."),
    ("Prozesse", "uuid", "ja, wenn fertig", "OpenLCA-UUID des Process", "ID des Prozesses in OpenLCA (nicht die Flow-ID).", "Flow-UUID hier eintragen. Process und Flow sind zwei verschiedene IDs."),
    ("Prozesse", "ref_flow_name", "ja", "freier Text", "Name des Referenzprodukts (funktionelle Einheit), z. B. staerkebasiertes Compound.", "Mehrere Produkte als Referenz — nur eines ist die quantitative Referenz."),
    ("Prozesse", "ref_flow_uuid", "ja, wenn fertig", "OpenLCA-UUID des Flow", "ID des Referenz-Stoffes in OpenLCA.", "Dieselbe UUID für Folie, Spritzguss und 3D-Druck wiederverwenden, obwohl es verschiedene Produkte sind."),
    ("Prozesse", "ref_amount", "ja", "Zahl", "Menge der funktionellen Einheit, meist 1.", "Laboransatz 6000 g hier eintragen. Hier gehört die Modell-Einheit (meist 1 kg)."),
    ("Prozesse", "ref_unit", "ja", "kg, kWh, …", "Einheit zur ref_amount.", "g und kg mischen ohne Umrechnung."),
    ("Prozesse", "parent_process_id", "nein", "eine process_id oder leer", "Vorgänger in der Kette. Folie bioPE hat parent biope_granulate.", "Langen Process-Namen statt der process_id eintragen."),
    ("Prozesse", "in_ui", "ja", "ja / nein", "Soll Nutzerinnen diesen Prozess im Tool auswählen können?", "Alle Prozesse auf ja — interne Zwischenstufen oft nein."),
    ("Prozesse", "status", "ja", "entwurf / offen / fertig", "Nur fertig geht ins Tool. offen = UUIDs oder Mengen fehlen noch.", "fertig setzen, obwohl UUIDs leer sind."),
    ("Prozesse", "note", "nein", "freier Text", "Kurzkommentar, Annahmen, offene Punkte.", "Ganze Methodik hier abladen — dafür Rohdaten oder ein separates Dokument."),
    # Parameter
    ("Parameter", "param_id", "ja", "klein, ohne Leerzeichen", "Stabiler technischer Name des Hebels. Bleibt im Code für immer so.", "Umbenennen von ethanol_maize in ethanol_mais, nachdem schon entwickelt wurde."),
    ("Parameter", "label", "ja", "freier Text", "Text, den Nutzerinnen sehen, z. B. „Ethanol-Rohstoff“.", "Den ecoinvent-Prozessnamen als Label verwenden."),
    ("Parameter", "process_id", "ja", "muss in Prozesse vorkommen", "In welchem Prozess dieser Hebel gilt.", "Tippfehler, der auf keinen Prozess zeigt."),
    ("Parameter", "type", "ja", "number / choice / toggle", "number = Zahl tippen. choice = genau eine Option aus einer Liste. toggle = an/aus.", "Acht Ethanol-Zeilen als number statt einer choice-Gruppe."),
    ("Parameter", "group", "bei choice ja", "gemeinsamer Name", "Welche choice-Optionen zusammengehören. Alle Ethanol-Quellen dieselbe group, z. B. pe_ethanol_source.", "Jede Option eine eigene group — dann ist es keine Gruppe mehr."),
    ("Parameter", "default", "ja", "Zahl, Optionswert oder ja/nein", "Startwert. Bei choice der choice_value der Default-Option. Bei toggle ja oder nein.", "Bei choice die Menge 1,75 als default statt des Optionsschlüssels mix."),
    ("Parameter", "min / max", "bei number empfohlen", "Zahlen", "Erlaubter Bereich für die Oberfläche und den Connector.", "Leer lassen und später 1000 km Lkw ungeprüft durchreichen."),
    ("Parameter", "unit", "bei number ja", "kg, kWh, km, …", "Einheit, die Nutzerinnen eingeben.", "Andere Einheit als in Exchanges ohne Hinweis."),
    ("Parameter", "formula", "nein", "OpenLCA-Formel oder leer", "Nur wenn der Wert berechnet wird, nicht getippt. z. B. 1.05 * foil_kg.", "Formel und getippte Default-Menge widersprechen sich, ohne das zu sagen."),
    ("Parameter", "user_visible", "ja", "ja / nein", "ja = Feld in der Oberfläche. nein = nur intern / berechnet.", "Berechnete Abfallmenge als sichtbares Zahlenfeld."),
    ("Parameter", "note", "nein", "freier Text", "Hinweis für Entwicklung oder Modellierung.", ""),
    # Exchanges
    ("Exchanges", "process_id", "ja", "muss in Prozesse vorkommen", "Zu welchem Prozess dieser Input oder Output gehört.", "Prozessname statt process_id."),
    ("Exchanges", "direction", "ja", "input / output", "input = geht in den Prozess. output = kommt heraus (Produkt oder Abfall).", "Abfall als input; Referenzprodukt vergessen."),
    ("Exchanges", "flow_name", "ja", "OpenLCA-Flussname", "Name des Stoffes oder der Energie.", ""),
    ("Exchanges", "flow_uuid", "ja, wenn fertig", "UUID des Flow", "Nur die Stoff-ID. Nicht die Prozess-ID.", "Dieselbe UUID in flow_uuid und provider_uuid kopieren."),
    ("Exchanges", "amount", "ja", "Zahl oder „siehe param_id“", "Default-Menge bezogen auf die funktionelle Einheit des Prozesses. Bei choice-Optionen die Menge, wenn diese Option gewählt ist. Bei inaktiven Optionen 0.", "Labor-Gramm für 6 kg Ansatz statt kg je 1 kg Produkt."),
    ("Exchanges", "unit", "ja", "kg, kWh, MJ, …", "Einheit zur Menge.", ""),
    ("Exchanges", "provider_name", "bei ecoinvent ja", "OpenLCA-Prozessname", "Lieferprozess, z. B. market for electricity, low voltage | … | EN15804GD, S - DE.", ""),
    ("Exchanges", "provider_uuid", "bei ecoinvent ja", "UUID des Process", "Nur die Prozess-ID des Lieferanten. Bei eigenen Produkten leer oder „-“.", "UUID vom Ethanol-Datensatz in die Strom-Zeile kopieren."),
    ("Exchanges", "source", "ja", "ecoinvent / own", "ecoinvent = Hintergrunddatenbank. own = euer Vordergrund (Compound, Granulat, Folie).", "Eigenes Granulat als ecoinvent markieren."),
    ("Exchanges", "system_model", "bei ecoinvent ja", "EN15804GD / APOS / Cutoff / …", "Welches ecoinvent-Systemmodell. Im Projekt möglichst durchgängig dasselbe.", "EN15804GD und APOS in einem Prozess mischen, ohne das zu kennzeichnen."),
    ("Exchanges", "param_id", "nein", "eine param_id oder leer", "Wenn Menge oder Auswahl über einen Parameter gesteuert wird.", "Parameter nennen, der nicht im Blatt Parameter steht."),
    ("Exchanges", "choice_value", "bei choice-Optionen ja", "kurzer Schlüssel", "Welche Option diese Zeile ist, z. B. maize, mix, pv. Muss zum default der Parameter-Gruppe passen.", "Leer lassen — dann weiß das Tool nicht, welche Zeile zu welcher Auswahl gehört."),
    ("Exchanges", "note", "nein", "freier Text", "Proxy-Hinweis, Annahme, z. B. „Sorbitol als polyol“.", ""),
    # Rohdaten
    ("Rohdaten", "rohdaten_id", "ja", "klein, ohne Leerzeichen", "Interne ID der Mess- oder Rezeptzeile.", ""),
    ("Rohdaten", "material", "ja", "freier Text", "Stoffname aus Labor / Betrieb, z. B. Kartoffelstärke.", ""),
    ("Rohdaten", "amount_min / max / mean", "nein", "Zahlen", "Spanne und Mittelwert aus der Erhebung. Noch nicht die OpenLCA-Menge.", "Diese Werte als amount in Exchanges kopieren, ohne auf 1 kg zu skalieren."),
    ("Rohdaten", "unit", "ja", "g, kg, …", "Einheit der Erhebung (oft g pro Ansatz).", ""),
    ("Rohdaten", "transport_km", "nein", "Zahl", "Transportdistanz der Zutat.", "Im Modell vergessen, obwohl hier eingetragen."),
    ("Rohdaten", "transport_mode", "nein", "Lkw / Bahn / …", "Verkehrsmittel.", ""),
    ("Rohdaten", "maps_to_process_id", "nein", "process_id", "Welcher Modell-Prozess diesen Wert nutzt.", ""),
    ("Rohdaten", "maps_to_flow_name", "nein", "Flussname", "Welcher Exchange daraus wird.", ""),
    ("Rohdaten", "note", "nein", "freier Text", "Quelle, Datum, Skalierungshinweis (z. B. Ansatz 6000 g + 5 % Abfall).", ""),
    # Änderungen
    ("Aenderungen", "date", "ja", "JJJJ-MM-TT", "Datum der Änderung.", ""),
    ("Aenderungen", "version", "ja", "z. B. v0.2", "Modellversion nach der Änderung.", "UUID ändern und Version nicht hochzählen."),
    ("Aenderungen", "process_id / param_id", "wenn betroffen", "IDs", "Was sich geändert hat.", ""),
    ("Aenderungen", "field", "ja", "Feldname", "Welches Feld, z. B. provider_uuid.", ""),
    ("Aenderungen", "old_value / new_value", "ja", "Text oder UUID", "Vorher → nachher.", "Nur „korrigiert“ schreiben ohne alte UUID."),
    ("Aenderungen", "author", "ja", "Name", "Wer geändert hat.", ""),
    # Typen extra
    ("Begriff", "UUID", "—", "8-4-4-4-12 Hex", "Eindeutige ID in OpenLCA. Process-UUID und Flow-UUID sind immer verschieden.", "Aus einer anderen Zeile kopieren, weil „sieht ähnlich aus“."),
    ("Begriff", "type = number", "—", "—", "Nutzer tippt eine Zahl (kg Folie, km Transport).", "—"),
    ("Begriff", "type = choice", "—", "—", "Nutzer wählt genau eine Option (Strommix, Ethanol-Pflanze, Folienstärke).", "—"),
    ("Begriff", "type = toggle", "—", "—", "Nur an oder aus (Transport ja/nein).", "—"),
    ("Begriff", "funktionelle Einheit", "—", "—", "Bezugsgröße des Prozesses, meist 1 kg Produkt. Alle Mengen in Exchanges beziehen sich darauf.", "Mengen auf 6 kg Ansatz beziehen und 1 kg als ref_amount stehen lassen."),
    ("Begriff", "System Process", "—", "—", "Fertig gerechnetes ecoinvent-Inventar (nur Elementarflüsse). In Namen oft „, S“.", "—"),
    ("Begriff", "Unit Process", "—", "—", "Einzelner Prozess mit Vorprodukten. In Namen oft „, U“.", "—"),
]

for i, row in enumerate(legend_rows):
    r = 5 + i
    for c, val in enumerate(row, 1):
        cell = ws.cell(r, c, val)
        cell.font = font_body
        cell.alignment = wrap_top
        cell.border = thin
        if c == 1:
            cell.fill = fill_legend_cat
            cell.font = Font(name="Calibri", size=11, bold=True, color=NAVY)
        elif row[2] == "ja" and c == 3:
            cell.fill = fill_req
            cell.alignment = center
        elif c == 3:
            cell.alignment = center
    ws.row_dimensions[r].height = 48

ws.auto_filter.ref = f"A4:F{4 + len(legend_rows)}"

# =============================================================================
# PROZESSE
# =============================================================================
ws = wb.create_sheet("Prozesse", 2)
ws.sheet_properties.tabColor = "40916C"
ncols = 11
add_title_block(
    ws,
    "Prozesse — ein Prozess pro Zeile",
    "Landkarte des Modells. Keine Inputs hier. Die Kette steht über parent_process_id.",
    ncols,
)
headers = [
    "process_id",
    "name",
    "uuid",
    "ref_flow_name",
    "ref_flow_uuid",
    "ref_amount",
    "ref_unit",
    "parent_process_id",
    "in_ui",
    "status",
    "note",
]
for i, h in enumerate(headers, 1):
    ws.cell(4, i, h)
style_header_row(ws, 4, ncols)

examples = [
    [
        "hof_compound",
        "Stärkebasiertes Compound",
        "af6d4d27-d3ba-4427-a935-c8f349471004",
        "staerkebasiertes Compound",
        "4e96a449-4549-4874-a6b9-d921937e59e0",
        1,
        "kg",
        "",
        "nein",
        "fertig",
        "Beispiel: Zwischenprodukt, Nutzer wählen später die Weiterverarbeitung.",
    ],
    [
        "hof_folie",
        "Stärkebasierte Extrusionsfolie",
        "",
        "stärkebasierte Extrusionsfolie",
        "c91e0e3b-4340-43d9-a90a-aaf62f40cd21",
        1,
        "kg",
        "hof_compound",
        "ja",
        "offen",
        "Beispiel: uuid des Process noch eintragen. Flow-UUID nicht für Spritzguss wiederverwenden.",
    ],
]
for i, row in enumerate(examples):
    r = 5 + i
    for c, v in enumerate(row, 1):
        ws.cell(r, c, v)
    style_example_row(ws, r, ncols)

style_empty_rows(ws, 7, 40, ncols)
set_widths(ws, [22, 36, 40, 32, 40, 14, 12, 22, 10, 12, 48])
ws.freeze_panes = "A5"
ws.auto_filter.ref = "A4:K40"

add_dv(ws, "Listen!$B$2:$B$3", "I7:I40")
add_dv(ws, "Listen!$A$2:$A$4", "J7:J40")
add_dv(ws, "Listen!$G$2:$G$12", "G7:G40")

for col, text in {
    "A4": "Technischer Schlüssel, nie umbenennen. z. B. hof_compound",
    "C4": "OpenLCA Process-UUID, nicht Flow-UUID",
    "E4": "OpenLCA Flow-UUID des Referenzprodukts",
    "H4": "process_id des Vorgängers oder leer",
    "I4": "Soll der Prozess in der Oberfläche wählbar sein?",
    "J4": "Nur fertig wird ins Tool übernommen",
}.items():
    comment(ws[col], text)

# =============================================================================
# PARAMETER
# =============================================================================
ws = wb.create_sheet("Parameter", 3)
ws.sheet_properties.tabColor = "52B788"
ncols = 12
add_title_block(
    ws,
    "Parameter — Hebel für Oberfläche und Rechnung",
    "Eine Zeile = ein Hebel. choice = eine Gruppe, mehrere Optionen (die Optionen selbst stehen in Exchanges).",
    ncols,
)
headers = [
    "param_id",
    "label",
    "process_id",
    "type",
    "group",
    "default",
    "min",
    "max",
    "unit",
    "formula",
    "user_visible",
    "note",
]
for i, h in enumerate(headers, 1):
    ws.cell(4, i, h)
style_header_row(ws, 4, ncols)

examples = [
    [
        "pe_ethanol_source",
        "Ethanol-Rohstoff",
        "biope_granulate",
        "choice",
        "pe_ethanol_source",
        "mix",
        "",
        "",
        "",
        "",
        "ja",
        "Beispiel: Dropdown. Optionen in Exchanges mit derselben param_id und choice_value mix/maize/…",
    ],
    [
        "foil_kg",
        "Folienmenge",
        "hof_folie",
        "number",
        "",
        1,
        0,
        1000,
        "kg",
        "",
        "ja",
        "Beispiel: Zahl. Inputs können per Formel daran hängen.",
    ],
    [
        "include_transport",
        "Anlieferung einrechnen",
        "hof_compound",
        "toggle",
        "",
        "ja",
        "",
        "",
        "",
        "",
        "ja",
        "Beispiel: an/aus. Kein Dropdown.",
    ],
]
for i, row in enumerate(examples):
    r = 5 + i
    for c, v in enumerate(row, 1):
        ws.cell(r, c, v)
    style_example_row(ws, r, ncols)

style_empty_rows(ws, 8, 50, ncols)
set_widths(ws, [24, 32, 22, 12, 22, 14, 10, 10, 10, 28, 14, 52])
ws.freeze_panes = "A5"
ws.auto_filter.ref = "A4:L50"

add_dv(ws, "Listen!$C$2:$C$4", "D8:D50")
add_dv(ws, "Listen!$B$2:$B$3", "K8:K50")
add_dv(ws, "Listen!$G$2:$G$12", "I8:I50")

for col, text in {
    "A4": "Technischer Schlüssel, nie umbenennen.",
    "D4": "number = Zahl, choice = eine Option, toggle = an/aus",
    "E4": "Bei choice: gleicher group-Name für alle zusammengehörigen Optionen",
    "F4": "Bei choice: der choice_value der Default-Option, nicht die Menge",
    "J4": "Nur ausfüllen, wenn der Wert berechnet wird",
}.items():
    comment(ws[col], text)

# =============================================================================
# EXCHANGES
# =============================================================================
ws = wb.create_sheet("Exchanges", 4)
ws.sheet_properties.tabColor = "74C69D"
ncols = 13
add_title_block(
    ws,
    "Exchanges — Inputs und Outputs",
    "Eine Zeile = ein Fluss. provider_uuid = Prozess, flow_uuid = Stoff. Niemals dieselben Werte in beide Spalten kopieren.",
    ncols,
)
headers = [
    "process_id",
    "direction",
    "flow_name",
    "flow_uuid",
    "amount",
    "unit",
    "provider_name",
    "provider_uuid",
    "source",
    "system_model",
    "param_id",
    "choice_value",
    "note",
]
for i, h in enumerate(headers, 1):
    ws.cell(4, i, h)
style_header_row(ws, 4, ncols)

examples = [
    [
        "hof_compound",
        "input",
        "maize starch",
        "c4ed73ce-ed64-4823-96d9-5661c11c6941",
        0.36,
        "kg",
        "maize starch production | maize starch | EN15804GD, S - DE",
        "c8b6c205-c867-4c21-aa66-a065d082831c",
        "ecoinvent",
        "EN15804GD",
        "",
        "",
        "Beispiel: fester Input, skaliert auf 1 kg Compound.",
    ],
    [
        "hof_compound",
        "output",
        "staerkebasiertes Compound",
        "4e96a449-4549-4874-a6b9-d921937e59e0",
        1,
        "kg",
        "",
        "-",
        "own",
        "",
        "",
        "",
        "Beispiel: eigenes Referenzprodukt. Kein ecoinvent-Provider.",
    ],
    [
        "biope_granulate",
        "input",
        "ethanol, without water, in 99.7% solution state, from fermentation",
        "508155f4-0601-4a0b-be0f-9ac7d558605a",
        1.75,
        "kg",
        "market for ethanol … | EN15804GD, S - GLO",
        "afd9e8f8-4fea-406f-97fa-d325a0296cc0",
        "ecoinvent",
        "EN15804GD",
        "pe_ethanol_source",
        "mix",
        "Beispiel: Default-Option der choice. Andere Rohstoffe: amount 1.75, anderes choice_value.",
    ],
    [
        "biope_granulate",
        "input",
        "ethanol, without water, in 95% solution state, from fermentation",
        "ffcb8cbb-77ab-4f87-8a94-87ca5b8ea79e",
        1.75,
        "kg",
        "ethanol production from maize | … | EN15804GD, S - RoW",
        "ac1e8c18-e3fe-452f-b459-cad7ecd07c34",
        "ecoinvent",
        "EN15804GD",
        "pe_ethanol_source",
        "maize",
        "Beispiel: Alternative. Im Modell oft amount 0, bis maize gewählt wird.",
    ],
]
for i, row in enumerate(examples):
    r = 5 + i
    for c, v in enumerate(row, 1):
        ws.cell(r, c, v)
    style_example_row(ws, r, ncols)

style_empty_rows(ws, 9, 80, ncols, height=24)
set_widths(ws, [20, 12, 42, 40, 12, 10, 46, 40, 12, 14, 22, 14, 44])
ws.freeze_panes = "A5"
ws.auto_filter.ref = "A4:M80"

add_dv(ws, "Listen!$D$2:$D$3", "B9:B80")
add_dv(ws, "Listen!$G$2:$G$12", "F9:F80")
add_dv(ws, "Listen!$E$2:$E$3", "I9:I80")
add_dv(ws, "Listen!$F$2:$F$6", "J9:J80")

for col, text in {
    "B4": "input = rein, output = raus (Produkt oder Abfall)",
    "D4": "Nur Flow-UUID",
    "H4": "Nur Process-UUID des Lieferanten. Bei own: - oder leer",
    "I4": "ecoinvent = Hintergrund, own = euer Prozess",
    "K4": "Wenn ein Parameter die Menge oder die Auswahl steuert",
    "L4": "Bei type=choice: welcher Optionswert diese Zeile ist (mix, maize, pv, …)",
}.items():
    comment(ws[col], text)

# =============================================================================
# ROHDATEN
# =============================================================================
ws = wb.create_sheet("Rohdaten", 5)
ws.sheet_properties.tabColor = "B7E4C7"
ncols = 11
add_title_block(
    ws,
    "Rohdaten — nur Labor- und Betriebswerte",
    "Keine UUIDs. Keine OpenLCA-Namen erzwingen. Verknüpfung zum Modell über maps_to_process_id.",
    ncols,
)
headers = [
    "rohdaten_id",
    "material",
    "amount_min",
    "amount_max",
    "amount_mean",
    "unit",
    "transport_km",
    "transport_mode",
    "maps_to_process_id",
    "maps_to_flow_name",
    "note",
]
for i, h in enumerate(headers, 1):
    ws.cell(4, i, h)
style_header_row(ws, 4, ncols)

examples = [
    [
        "hof_kartoffelstaerke",
        "Kartoffelstärke",
        2275,
        2520,
        2397.5,
        "g",
        240,
        "Lkw",
        "hof_compound",
        "potato starch",
        "Beispiel: Ansatz vor Skalierung. Im Modell 0,36 kg / kg Produkt.",
    ],
]
for i, row in enumerate(examples):
    r = 5 + i
    for c, v in enumerate(row, 1):
        ws.cell(r, c, v)
    style_example_row(ws, r, ncols)

style_empty_rows(ws, 6, 40, ncols)
set_widths(ws, [24, 28, 14, 14, 14, 10, 14, 16, 22, 22, 48])
ws.freeze_panes = "A5"
ws.auto_filter.ref = "A4:K40"
add_dv(ws, "Listen!$H$2:$H$6", "H6:H40")
add_dv(ws, "Listen!$G$2:$G$12", "F6:F40")

# =============================================================================
# AENDERUNGEN
# =============================================================================
ws = wb.create_sheet("Aenderungen", 6)
ws.sheet_properties.tabColor = "95D5B2"
ncols = 9
add_title_block(
    ws,
    "Änderungen — jede relevante Anpassung eine Zeile",
    "Pflicht bei UUID-Wechsel, umbenannten IDs, geänderten Defaults oder neuen Prozessen.",
    ncols,
)
headers = [
    "date",
    "version",
    "process_id",
    "param_id",
    "field",
    "old_value",
    "new_value",
    "author",
    "note",
]
for i, h in enumerate(headers, 1):
    ws.cell(4, i, h)
style_header_row(ws, 4, ncols)

examples = [
    [
        "2026-08-24",
        "v0.1",
        "biope_granulate",
        "",
        "provider_uuid",
        "(Stromzeile hatte Ethanol-UUID)",
        "f904981f-3c9e-4d4a-ae43-29769597dd97",
        "Vorname Nachname",
        "Beispiel: Copy-Paste-Fehler korrigiert.",
    ],
]
for i, row in enumerate(examples):
    r = 5 + i
    for c, v in enumerate(row, 1):
        ws.cell(r, c, v)
    style_example_row(ws, r, ncols)

style_empty_rows(ws, 6, 40, ncols)
set_widths(ws, [14, 12, 22, 22, 18, 42, 42, 20, 40])
ws.freeze_panes = "A5"
ws.auto_filter.ref = "A4:I40"

# Print / view
for name in ["Prozesse", "Parameter", "Exchanges", "Rohdaten", "Aenderungen", "Legende"]:
    s = wb[name]
    s.page_setup.orientation = "landscape"
    s.page_setup.fitToPage = True
    s.page_setup.fitToWidth = 1
    s.page_setup.fitToHeight = 0
    s.page_setup.paperSize = s.PAPERSIZE_A4
    s.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6)
    s.sheet_view.zoomScale = 110 if name != "Legende" else 100

wb.active = 0
wb.save(OUT)
print("wrote", OUT)
