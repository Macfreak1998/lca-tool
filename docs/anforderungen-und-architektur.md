# LCA-Tool — Erkenntnisse, Architektur und Arbeitsstand Anforderungen

**Stand:** 11. September 2026  
**Status:** Arbeitsdokument für Umsetzung; Produktregeln verbindlich in `docs/entscheidungen-mvp.md`  
**Ergänzt:** `docs/konzept-lca-tool-pitch.md` (Kurzfassung für die Leitung)  
**Erstes Lieferziel:** Admin-UI so weit, dass die Kollegin die HOF-Kette **im Tool** anlegen und rechnen kann. Daten **neu aus dem Archiv**. Altes openLCA-Modell und Sachbilanz-Excel: **ignorieren**.

Dieses Dokument beschreibt Technik, Datenhaltung und Schnittstellen. **Verbindliche Produktbeschlüsse** stehen in `docs/entscheidungen-mvp.md` und gelten bei Widerspruch vorrangig. Offene Punkte als **[OFFEN]** betreffen Betrieb (Lizenz, Hosting), nicht mehr das Produktmodell.

---

## 1. Ziel des Produkts

Ein **Web-Tool** zur Abschätzung der Umweltwirkung biobasierter Kunststoffe.

Nutzerinnen und Nutzer modellieren **nicht** in openLCA oder Brightway. Sie wählen eine Produktionskette, Mengen, Mixe und wenige Kennzahlen. Das Tool rechnet und speichert Szenarien.

Typische Ketten (fachlich klein):

```
Ausgangsmaterial + Energiemix
        → Granulat
        → Energiemix + 1–2 weitere Parameter
        → Endprodukt (Folie, Spritzguss, 3D-Druck, …)
```

Frühere Sachbilanz-/openLCA-Pfade (nur Kontext, **nicht** als Datenquelle nutzen):

| Pfad | grob |
|---|---|
| HOF / Stärke | Compound aus Stärken/Weichmachern + Energie → Folie (MVP) |
| Bio-PE / Bio-PP / PLA | später, analog über Admin-UI |

**MVP-Pfad:** **HOF / Stärke → Folie**.  
Die Kollegin legt Stufen, Slots, Mengen und Katalogbausteine **im Admin-Tool** an. Bausteine **neu aus dem Archiv** importieren. Keine Übernahme alter UUIDs, EN-15804-Faktoren oder Excel-Rezepte.

---

## 2. Getroffene Richtungsentscheidungen

Diese Punkte gelten als Stand der Planung, solange sie nicht bewusst gekippt werden.

| Nr. | Entscheidung |
|---|---|
| D1 | **openLCA ist nicht der Live-Rechenkern** und nicht die Datenquelle der HOF-Kette. Die Kette entsteht in der Admin-UI; Datensätze kommen aus dem Archiv. |
| D2 | **Keine volle ecoinvent-Rechnung** bei jedem Klick. Nur benötigte Bausteine im Katalog. |
| D3 | Hintergrundquelle: vorliegender Ordner **ecoinvent 3.10.1, Allocation cut-off, LCI, ecoSpold02** (~23.500 Datensätze, ~29 GB). |
| D4 | Drei Speicher: **Lager** (Roh-ecoinvent) / **Katalog** (SQL, klein) / **Nutzerdaten** (SQL). |
| D5 | Konkrete Lieferanten und Mixe stehen **im Katalog** (Kategorien), nicht fest im Programmcode. |
| D6 | Das **Kettengerüst legt der Admin** an (Stufen, Slots, Defaults) — nicht hart im Programm. Topologie: linear vorwärts, eine Ausgangskante, viele Eingänge. Siehe `entscheidungen-mvp.md` K1–K9. |
| D7 | Nutzer ändern im Rezept nur **Endmenge**, **Datensatzwahl**, **Anteile** und **optionale Slots**. Andere Mengen oder Faktoren = **eigener Datensatz**. |
| D8 | Eigener Datensatz: Pflicht **Name, Kategorie, Einheit, CO₂e**. Quelle optional. Blackbox, kein zweites Rezept. |
| D9 | Archiv-Suche dient der **kontrollierten Katalog-Erweiterung**, nicht dem Alltags-Dropdown. |
| D10 | Laufzeit-Rechnung: Menge × Katalog- oder Nutzerfaktor. Brightway vor allem beim **Import/Charakterisieren**. |
| D11 | Methode **EF 3.1**, Systemmodell **cut-off 3.10.1 LCI**, Import im Zweifel **Market**. |
| D12 | Keine Organisationen. Selbstregistrierung + E-Mail-Bestätigung. Öffentlicher Go-Live erst nach **Lizenzklärung**. |
| D13 | Erstes Lieferziel: **Admin kann HOF-Kette zum Test anlegen** (Archiv → Katalog → Kategorien → Kette → Proberechnung → Veröffentlichen). |

Noch **keine** finale Entscheidung, aber bevorzugte Richtung:

- Relationale SQL-DB (SQLite für den Start, später Postgres möglich).
- Backend als eigener Dienst (z. B. Python/FastAPI).
- Frontend getrennt, spricht nur die Fach-API an.

---

## 3. Architektur

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Frontend   │────▶│  Backend / API   │────▶│  SQL                │
│  (Browser)  │     │  Rechnung+Auth   │     │  Katalog + Nutzer   │
└─────────────┘     └────────┬─────────┘     └─────────────────────┘
                             │
                    nur bei Katalog-Erweiterung
                             ▼
                    ┌─────────────────────┐
                    │  Lager (Festplatte) │
                    │  ecoSpold + Lookup  │
                    │  nur lesen          │
                    └─────────────────────┘
```

### 3.1 Lager

- Pfad (lokal, Stand Abstimmung):  
  `/Volumes/SSK Drive/SKZ/ecoinvent 3.10.1_cutoff_lci_ecoSpold02`
- Inhalt: `datasets/*.spold`, `MasterData/`, `FilenameToActivityLookup.csv`
- Dateiname Dataset: `{activity-uuid}_{product-uuid}.spold`
- Lookup-Spalten: Filename, ActivityName, Location, ReferenceProduct
- **Nicht** ins Docker-Image der öffentlichen App. Volume oder interner Import-Rechner.
- LCI = bereits aggregiertes Inventar (cradle-to-gate). Keine tiefe Lieferkette mehr sichtbar.

### 3.2 Katalog (SQL)

Pro importiertem Baustein mindestens:

- stabile `dataset_id`
- Anzeigename, Location, Einheit
- Quelle (`ecoinvent` / `user` / später `own`)
- ecoinvent-Referenz: Activity-Name, Location, Product-UUID, Dateiname
- Katalogversion / Importdatum
- Zuordnung zu einer oder mehreren **Rollen** (Kategorien)
- Wirkungsfaktoren: eine Zeile je Indikator der gewählten Methode

**Nicht** die vollen XML-Inventare in SQL laden — nur Metadaten + charakterisierte Kennzahlen.

### 3.3 Nutzerdaten (SQL)

- Konto ohne Mandant/Organisation. Rolle `user` oder `admin`.
- Konfigurationen / Rezepte (Kette, Endmenge, Wahlen, Anteile, optionale Slots) — **nur privat**
- Eigene Datensätze (Blackbox: Name, Kategorie, Einheit, Faktoren; Ausgangsstoffe optional dokumentarisch)
- Keine stillen Overrides im Rezept; kein eingefrorener Berechnungslauf (Vergleich ist **live**)

### 3.4 Wo gerechnet wird

Das Backend, nicht der Browser, nicht openLCA.

Vereinfachte Formel:

```
Ergebnis(Indikator) =
    Σ  menge_i × faktor_katalog(baustein_i, indikator)
  + Σ  menge_j × faktor_nutzer(baustein_j, indikator)     // eigener Datensatz (Blackbox)
```

Mengen `menge_*` entstehen rückwärts aus der Endmenge und den Admin-Umrechnungen (ggf. × Anteil). Normativ: `docs/entscheidungen-mvp.md` Abschnitt 8.

Ziel-Latenz: **sofort** (Millisekunden bis niedriger dreistelliger ms), nicht Sekunden.

Brightway (oder ein gleichwertiges Charakterisierungs-Skript):

- liest ausgewählte `.spold`
- wendet die LCIA-Methode an
- schreibt Faktoren in den Katalog

Danach braucht ein normaler `/calculate`-Request Brightway nicht mehr.

---

## 4. Katalog und Kategorien (nicht hardcoden)

### 4.1 Kategorien

Keine fest verdrahtete Liste und keine vorab abgestimmten Slugs. Der Admin legt Kategorien in der UI an, während er die Kette baut. Typische Namen nur zur Orientierung: Stärke, Weichmacher, Additiv, Energie, Druckluft.

### 4.2 Was im Code fest bleibt

Nur die **Regeln** (eine Ausgangskante, Zwischenprodukt fließt, Anteile = 100 %, Publish-Gates).  
Welche Stufen und Slots die HOF-Kette hat, steht ausschließlich in SQL, nachdem die Kollegin sie im Tool angelegt hat. Kein Platzhalter-Rezept und keine importierten openLCA-Prozesse im Code.

### 4.3 Archiv-Suche

- Index aus `FilenameToActivityLookup.csv` (Name, Ort, Produkt).
- **Ein** Suchfeld über diese drei Spalten. Keine getrennten Filter.
- Suche **nicht** in 29 GB XML.
- Treffer → Admin: „In Katalog übernehmen“ → Charakterisieren (EF 3.1) → Kategorie zuweisen.
- Im Zweifel **Market**. Kein freies Stöbern in der normalen Nutzer-UI.
- Archiv-Pfad: eine Einstellung. Datenmodell trotzdem `quelle + id`.

---

## 5. Nutzerfunktionen (fachlich)

### 5.1 Konfiguration

Endprodukt wählen, bei mehreren Pfaden die Kette, Endmenge in der Admin-Einheit, Blätter aus dem Katalog oder aus eigenen Datensätzen. Anteile bei mehreren Slots derselben Kategorie. Optionale Slots einschalten. Speichern (privat), laden, live rechnen und vergleichen (2–4 Konfigurationen, gleiches Endprodukt/Menge/Einheit).

### 5.2 Keine stillen Mengen- oder Faktoränderungen

Effizientere Maschine oder andere Emissionen: **eigener Datensatz** (kategorisiert, Einheit, mindestens CO₂e). Nicht kWh/kg oder einen Faktor im Rezept überschreiben.

### 5.3 Eigener Datensatz (Blackbox)

Ersetzt den Katalog-Baustein in einem Blatt-Slot oder eine **Zwischenstufe** (dann entfällt die Vorstrecke). Pflicht: Name, Kategorie, Einheit, CO₂e. Quelle und Ausgangsstoffe optional (nur Dokumentation). Weitere EF-3.1-Indikatoren dürfen fehlen — dann nicht als 0 rechnen oder zeichnen.

Sichtbarkeit: nur Eigentümer, oder dem Admin als **Vorlage** vorschlagen. Der Admin legt daraus einen neuen Katalogeintrag an; der Nutzerdatensatz wird nie 1:1 öffentlich.

### 5.4 Vergleich und Export

Diagramm: Summen je Indikator. Tabelle und CSV/Excel: zusätzlich Beiträge je Stufe/Kategorie. Kein Annahmenblatt, kein PDF.

---

## 6. Parametrisierung (MVP)

Im MVP **linear** aus Admin-Defaults und Endmenge. Keine Grundlast-/Kennlinien-Formeln.

| Typ | UI | Beispiel |
|---|---|---|
| `number` | nur Endmenge | Folie in der Admin-Einheit |
| `choice` | genau eine Option je Slot | Stärkelieferant, Strommix |
| `share` | Anteile, Summe 100 % | zwei Stärken in einer Stufe |
| `toggle` | optionaler Slot an/aus | z. B. Transport, wenn der Admin den Slot optional setzt |

Defaults, optionale Slots und spezifische Mengen trägt die Kollegin in der Admin-UI ein. Nicht vorab in diesem Dokument.

---

## 7. Bewertungsmethode

Festgelegt: **EF 3.1 (PEF)**. Eine Methode, Nutzer können nicht wechseln.

- Katalog: eine Zeile je Indikator der Methode, nicht nur CO₂.
- `method_id` z. B. `EF3.1`. Methodenwechsel später = Katalog neu charakterisieren; Konfigurationen können ungültig werden.
- Keine gewichtete Einzelnote im MVP.

**[OFFEN]** EF-3.1-Methodendatei im Import-Job hinterlegen (Technik; Kollegin bestätigt bei Bedarf). Ohne sie kann der Archiv-Import nicht charakterisieren.

---

## 8. Prüfungen und Fehlerentdeckung

ecoinvent/Brightway warnt nicht von selbst vor unplausiblen Nutzerwerten.

Im MVP nur **harte Blocker**. Warnungen (Min/Max, Masse, Energie) sind zurückgestellt.

| Klasse | Beispiel | Verhalten MVP |
|---|---|---|
| Pflicht | fehlende Endmenge, fehlender Pflicht-Slot, Eigendaten ohne CO₂e/Einheit | blockieren |
| Anteile | Slots einer Kategorie summieren nicht auf 100 % | blockieren |
| Ungültige Konfiguration | Kette geändert/depubliziert oder Eigendatensatz gelöscht | blockieren |
| Bereich / Masse / Energie | — | nicht im MVP |
| Unvollständiges Profil | nur CO₂ bei Eigendaten | erlaubt; andere Indikatoren weglassen, nicht 0 |

Heizwerte stehen in vielen ecoinvent-Datensätzen als Eigenschaft — beim Import optional mit ins Katalog-Metadatenfeld übernehmen, wenn Energie-Checks gewünscht sind.

---

## 9. Archiv → Katalog (kein Mapping aus openLCA)

Das alte openLCA-Modell, die Sachbilanz-Excel und deren Process-UUIDs (oft EN15804) werden **nicht** übernommen und **nicht** nachgebaut. Zahlen und IDs daraus sind für das Tool irrelevant.

Die Kollegin sucht im Archiv über **Name, Ort, Referenzprodukt** (Lookup-CSV), importiert den Treffer und weist eine Kategorie zu. Charakterisierung: **EF 3.1** auf **cut-off 3.10.1 LCI**. Im Zweifel **Market**.

Abweichungen zu früheren openLCA-Läufen sind erwartet. Es gibt keine Soll-Zahlen aus dem Altsystem, gegen die das Tool „richtig“ sein muss.

---

## 10. Lizenz (nicht technisch lösbar)

- Roh-ecoinvent (auch LCI) auf einem Server für Dritte: typischerweise **zusätzliche ecoinvent-Lizenz** (Tool/Developer/Sublicensing).
- Auch vorkalkulierte Kennzahlen in einem interaktiven Tool können darunter fallen.
- Statische PDF-Ergebnisse sind lizenzlich oft unkritischer als Live-Rechnung für viele Nutzer.
- Vor Produktivbetrieb: interne Klärung + ggf. `sales@ecoinvent.org`.
- Nutzer dürfen ecoinvent-Datensätze nicht ins Lager zurückschreiben.

Produktseitig: Selbstregistrierung ist vorgesehen. **[OFFEN]** Lizenzklärung vor öffentlichem Produktivbetrieb (intern / ecoinvent Sales). Bis dahin intern oder Zugangsschutz.

---

## 11. Zusammenarbeit Modellierung

Die Kollegin ist **Admin im Tool**. Sie legt die HOF-Kette dort an und zieht Bausteine aus dem Archiv. Sie liefert kein Excel-Rezept und keine Runtime-DB.

Ablauf nach dem ersten Lieferziel:

1. Archiv-Pfad prüfen  
2. Kategorien anlegen  
3. Benötigte Datensätze suchen und importieren (EF 3.1, Kategorie, im Zweifel Market)  
4. Endprodukt „Folie“ (Einheit z. B. kg) und Kette als Entwurf  
5. Stufen, Slots, Mengen, Defaults, optionale Slots  
6. Proberechnung, bei Erfolg veröffentlichen  
7. Als Nutzer den Pfad durchrechnen  

Die Excel-Vorlage `docs/lca-dokumentation-vorlage.xlsx` ist **nicht** der Weg für die HOF-Kette. openLCA-Desktop ist optional, der Server braucht sie nicht.

---

## 12. Was bewusst nicht zum Scope gehört (vorerst)

Vollständige Liste: `docs/entscheidungen-mvp.md` Abschnitt 7.

- Live-Auswahl beliebiger ecoinvent-Datensätze durch Endnutzer
- Sankey/Hotspots **innerhalb** der ecoinvent-Vorkette (LCI ist schon aggregiert)
- Schreiben in die 29-GB-Ablage
- 1:1-Nachbau von GaBi/openLCA; freier Graph; Verzweigungen
- gdt-server / openLCA-IPC als Produktions-API
- Organisationen, Teilen von Konfigurationen, Versionshistorie, PDF/Annahmen-Export
- Inline-Overrides, Grundlast-Kennlinien, Methodenwahl durch Nutzer

---

## 13. Logisches Datenmodell (zum Festigen)

Keine Implementierung, nur die Entitäten, über die ihr sprechen solltet:

```
Chain
  id, name, status            // draft | published
  end_product_id, end_unit
  stages[]

Stage
  id, chain_id, name
  outgoing_stage_id           // höchstens eine
  slots[]

Slot
  role_id, required, optional_default_off
  min_count                   // Nutzer darf weitere Slots derselben Rolle ergänzen
  specific_amount, unit       // je Einheit Stufenausgang; bei n Slots × Anteil

Role
  slug, label                 // nur Admin legt an

Dataset
  id, name, location, unit, source_kind   // ecoinvent | catalog_manual | user
  source_id                   // für spätere mehrere Archive
  ecoinvent_ref
  roles[]
  factors[]                   // (EF3.1, indicator, value | null)
  inputs_doc[]                // optional, nicht gerechnet
  owner_user_id               // bei user-Datensätzen

Configuration (Nutzer, privat)
  user_id, chain_id
  end_amount
  selections[]                // slot → dataset_id
  shares[]                    // slot → percent, Summe 100 je Rolle/Stufe
  optional_on[]
  replaced_stages[]           // Zwischenstufe → user dataset
```

Kein `overrides[]` mehr. Kein gespeichertes `Calculation`-Ergebnis als Quelle für den Vergleich (live).

---

## 14. Vorgeschlagene API-Schnittstellen (grob)

Zum Anforderungsworkshop, nicht als finale Spezifikation:

| Methode | Zweck |
|---|---|
| `GET/POST /roles` | Kategorien lesen / Admin anlegen |
| `GET /datasets?role=` | Auswahl für ein Dropdown |
| `GET/POST /end-products` | Endprodukte (Name, Einheit) |
| `GET/POST /chains` | Ketten; Admin legt Entwurf an |
| `PATCH /chains/{id}` | Stufen, Slots, Defaults |
| `POST /chains/{id}/publish` | Proberechnung + Veröffentlichen |
| `GET /chains/{id}` | Stufen, Slots, Default-Parameter |
| `POST /calculate` | Konfiguration → Ergebnisse (Blocker oder Zahlen) |
| `GET/POST /configurations` | speichern / laden (privat) |
| `POST /compare` | 2–4 Konfigurations-IDs, gleiche Einheit/Menge/Endprodukt |
| `GET/POST /user-datasets` | eigene Blackbox-Datensätze |
| `POST /user-datasets/{id}/propose` | Vorlage an Admin |
| `GET /archive/search?q=` | Admin: ein Suchfeld |
| `POST /catalog/import` | Admin: Dataset aus Lager in Katalog |

`POST /calculate` (Idee der Nutzlast):

```json
{
  "chain_id": "hof_folie",
  "functional_unit": { "amount": 1, "unit": "kg" },
  "selections": { "energy": "elec_lv_de", "starch_1": "maize_starch_de" },
  "shares": { "starch_1": 0.6, "starch_2": 0.4 },
  "optional_on": [],
  "replaced_stages": {}
}
```

---

## 15. Offene Anforderungen (Checkliste)

Produktregeln: erledigt, siehe `docs/entscheidungen-mvp.md`.  
Fachmodell HOF: **kein** Dokumentations-To-do — entsteht in der Admin-UI.

### Erstes Lieferziel (Technik)

- [ ] Admin-Konto (Config-E-Mail) + Archiv-Pfad
- [ ] Kategorien anlegen
- [ ] Archivsuche + Import inkl. EF-3.1-Charakterisierung
- [ ] Endprodukt + Ketten-Editor (Stufen, Slots, Mengen, Defaults, optional, Anteile)
- [ ] Proberechnung und Veröffentlichen
- [ ] Nutzerfluss: Endprodukt → Kette → Blätter → rechnen

### Danach

- [ ] Eigene Datensätze, Vergleich 2–4, CSV-Export, Selbstregistrierung
- [ ] ecoinvent-Lizenz vor öffentlichem Server
- [ ] SQL-Engine, Hosting, Mailversand

---

## 16. Vorgeschlagene Reihenfolge der Umsetzung

Ziel der ersten Lieferung: die Kollegin kann die HOF-Kette **im Tool testweise anlegen**. Kein Warten auf Excel, kein Mapping aus openLCA.

1. **Auth minimal** — Admin aus Server-Config, Login.  
2. **Archiv-Pfad + Suche** — Lookup-CSV, ein Suchfeld.  
3. **Import-Job** — gewähltes `.spold` mit EF 3.1 charakterisieren, in den Katalog, Kategorie zuweisen.  
4. **Admin-Stammdaten** — Kategorien, Endprodukt.  
5. **Ketten-Editor** — Stufen, eine Kante, Slots, Mengen, Defaults, optional, Anteile; Entwurf.  
6. **`POST /calculate` + Publish-Gate** — Proberechnung 1 Einheit; bei Erfolg veröffentlichen.  
7. **Nutzer-UI** — von hinten: Endprodukt → Kette → Blätter → Endmenge → Ergebnis.  
8. **Danach** — eigene Datensätze, Vergleich, CSV, Selbstregistrierung.

Erst wenn Schritt 6–7 mit einer von der Kollegin angelegten Kette verzögerungsfrei laufen, weitere Pfade.

---

## 17. Begriffe

| Begriff | Bedeutung |
|---|---|
| Lager | Große ecoinvent-Ablage auf der Festplatte |
| Katalog | Kleine SQL-Liste importierter Bausteine + Faktoren |
| Rolle / Kategorie | Energie, Ethanol, Stärke, … — steuert Dropdowns |
| LCI | Fertig aggregiertes Inventar (dieser ecoinvent-Ordner) |
| UPR | Einzelprozess mit Vorkette (haben wir im Lager nicht) |
| Eigener Datensatz | Blackbox mit mindestens CO₂e; ersetzt Blatt oder Zwischenstufe |
| Anteil | Prozent eines Slots an der Admin-Gesamtmenge einer Kategorie |
| Charakterisieren | Inventar × EF 3.1 → Wirkungszahl |
| funktionelle Einheit | Endmenge in der vom Admin je Endprodukt festgelegten Einheit |
| EF 3.1 / PEF | Festgelegte Bewertungsmethode |

---

## 18. Verweise

| Dokument / Ort | Rolle |
|---|---|
| `docs/entscheidungen-mvp.md` | Verbindliche Produktbeschlüsse + erstes Lieferziel |
| `docs/konzept-lca-tool-pitch.md` | Kurzfassung für Vorgesetzte |
| `docs/lca-dokumentation-vorlage.xlsx` | Alt / nicht der Weg für die HOF-Kette |
| Sachbilanz-Excel / openLCA-Modell | **Ignorieren** — keine Datenquelle |
| ecoinvent-Ordner (SSK/SKZ) | Lager cut-off 3.10.1 LCI, einzige Hintergrundquelle |

---

*Nächster Schritt: Abschnitt 16, Schritte 1–7 bauen, dann die Kollegin die HOF-Kette im Tool anlegen lassen.*
