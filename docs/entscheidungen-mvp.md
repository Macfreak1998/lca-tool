# LCA-Tool — Verbindliche Produktentscheidungen (MVP)

**Stand:** 11. September 2026  
**Status:** Beschlossen in der Anforderungsrunde (Fragen 1–48); erstes Lieferziel nachgezogen  
**Gilt vor:** abweichenden Formulierungen in älteren Abschnitten von `docs/anforderungen-und-architektur.md`  
**HOF-Kette:** wird **nicht** vorab spezifiziert oder aus dem alten openLCA-Modell übernommen. Die Kollegin legt sie **im Tool** an; Bausteine kommen **frisch aus dem Archiv**.

Kurz für die Leitung: `docs/konzept-lca-tool-pitch.md`  
Technik und Datenhaltung: `docs/anforderungen-und-architektur.md`

---

## 1. Produkt in einem Satz

Web-Tool: Nutzer wählen ein Endprodukt und ggf. eine Kette, geben eine Menge ein und vergleichen 2–4 Konfigurationen. Admins pflegen Katalog, Kategorien und Ketten. Gerechnet wird im Backend aus Katalog- oder Nutzerfaktoren × rückwärts aufgelösten Mengen. Methode: **EF 3.1**. Hintergrund: **ecoinvent 3.10.1 cut-off LCI**.

---

## 2. Modell der Kette

| ID | Beschluss |
|---|---|
| K1 | Admin modelliert **Stufen mit Slots**, keinen freien Graphen wie in GaBi. |
| K2 | Die Kette läuft nur **vorwärts**. Pro Knoten **höchstens eine** ausgehende Kante, **beliebig viele** eingehende. Keine Verzweigung (ein Zwischenprodukt geht nicht in zwei Endprodukte). |
| K3 | Das **Zwischenprodukt fließt** in die nächste Stufe. Es ist **kein** Katalog-Dropdown. |
| K4 | Der Nutzer arbeitet **von hinten**: zuerst Endprodukt → bei mehreren Pfaden die Kette → rekursiv nur noch **Blätter** wählbar (Ausgangsstoffe, Energie, Vergleichbares). |
| K5 | Nutzer geben **eine Endmenge** ein. Alle anderen Mengen berechnet das Tool. Umrechnungen: zuerst Datenbank, sonst Admin-Default. |
| K6 | Die **Einheit der funktionellen Einheit** legt der Admin **je Endprodukt** fest. Keine Umrechnung zwischen Einheiten (kein kg ↔ m²). |
| K7 | Eine Stufe darf **mehrere Slots derselben Kategorie** haben. Der Admin setzt das **Minimum**. Der Nutzer darf Slots derselben Kategorie **ergänzen**. |
| K8 | Zusatz-Slots bekommen **keine eigenen kg**. Der Admin gibt die **Gesamtmenge der Kategorie** je Einheit Stufenausgang vor. Der Nutzer verteilt **Anteile in Prozent** (Summe **100 %**, sonst Blocker). |
| K9 | Der Admin kann Slots als **optional** markieren. Optional ist **standardmäßig aus**. Einschalten nutzt Admin-Default und normale Datensatzwahl. |
| K10 | Mengen, Ausbeuten und Wirkungszahlen ändert der Nutzer **nicht** im Rezept. Dafür legt er einen **eigenen Datensatz** an. |

---

## 3. Eigene Datensätze

| ID | Beschluss |
|---|---|
| E1 | Eigener Datensatz = **Blackbox**. Die **Faktoren** gehen in die Rechnung. Ausgangsstoffe sind **Dokumentation**, nicht ein zweites Rezept. |
| E2 | Pflicht: **Name, Kategorie, Einheit, mindestens Climate Change (CO₂e)**. Quelle und Ausgangsstoffe **optional**. |
| E3 | Weitere EF-3.1-Indikatoren dürfen fehlen. In Rechnung, Diagramm und Tabelle: Lücken **ausblenden**, **nicht als 0**. |
| E4 | Ein eigener Datensatz darf **jede Zwischenstufe** ersetzen. Diese Stufe wird zum Blatt, alle Vorstufen entfallen. Das **Endprodukt** ist nicht ersetzbar (keine Blackbox-Folie ohne Admin-Kette). |
| E5 | **Nur der Admin** legt Kategorien an. Nutzer ordnen einer bestehenden Kategorie zu. |
| E6 | Sichtbarkeit: **nur ich** oder **dem Admin als Vorlage vorschlagen**. Keine Organisationen, kein Teilen mit anderen Nutzern. |
| E7 | Ein Vorschlag wird **nie 1:1 öffentlich**. Der Admin legt daraus einen **neuen Katalogeintrag** an (Archiv-Import oder eigene Pflege). Der private Datensatz bleibt beim Eigentümer. |
| E8 | **Ändern** wirkt sofort auf alle Live-Rechnungen. **Löschen** macht betroffene Konfigurationen ungültig (bleiben gespeichert, Rechnen blockiert). |

---

## 4. Katalog, Methode, Archiv

| ID | Beschluss |
|---|---|
| C1 | Genau **eine** Bewertungsmethode: **EF 3.1 (PEF)**. Nutzer können sie nicht wechseln. Methodenwechsel später = Katalog neu charakterisieren. |
| C2 | Der Katalog wird **vollständig** nach EF 3.1 charakterisiert. Die UI zeigt **immer alle Indikatoren**. |
| C3 | Systemmodell fest: **ecoinvent 3.10.1, Allocation cut-off, LCI**. Abweichungen zu EN 15804 / älteren openLCA-Zahlen sind erwartet. |
| C4 | Import **im Zweifel Market**. Production nur, wenn die Fachseite sie ausdrücklich wählt. |
| C5 | MVP: **ein Archiv-Pfad** in den Admin-Einstellungen. Jeder Datensatz speichert trotzdem **Quelle + ID** (mehrere Archive später möglich). |
| C6 | Archivsuche: **ein Suchfeld** über Name, Ort und Referenzprodukt (Lookup-CSV). Keine getrennten Filter. |
| C7 | Dropdowns zeigen **keine Faktoren**, nur Name, Ort, Einheit, Quelle. Zahlen erst nach der Rechnung. |
| C8 | Ketten haben **Entwurf** und **veröffentlicht**. Keine Versionshistorie. Nutzer sehen nur Veröffentlichtes. |
| C9 | Veröffentlichen nur mit vollständiger Struktur, Defaults je Blatt-Slot **und** erfolgreicher **Proberechnung** (1 Einheit Endprodukt). |
| C10 | Nach Strukturänderung oder Depublish: abhängige Konfigurationen **ungültig**, bis der Nutzer sie vervollständigt. Rechnung und Vergleich blockieren. |

---

## 5. Vergleich und Export

| ID | Beschluss |
|---|---|
| V1 | Vergleich erlaubt **verschiedene Ketten**, wenn **Endprodukt, Menge und Einheit** gleich sind. |
| V2 | Der Vergleich rechnet **immer live** (aktueller Katalog, aktuelle Eigendaten). Gespeichert werden die **Eingaben**, keine eingefrorenen Ergebnisberichte. |
| V3 | **2 bis 4** Konfigurationen pro Vergleich. |
| V4 | Balkendiagramm: nur die **Summe** je Indikator und Konfiguration. |
| V5 | **Zerlegung** nach Stufe/Kategorie nur in der **Tabelle** und im Export. |
| V6 | Export: **CSV/Excel nur Ergebnistabelle** (Summen und Beiträge). Kein Annahmenblatt, kein PDF. |
| V7 | Konfigurationen sind **nur privat**. Kein Teilen, kein Link, kein Übertragen. |

---

## 6. Konto, Rollen, Betrieb

| ID | Beschluss |
|---|---|
| B1 | **Keine Organisationen**, keine Mandanten. |
| B2 | Zwei Rollen: **Nutzer** und **Admin**. Admin darf alles (Katalog, Ketten, Archiv-Pfad, Vorschläge, Nutzer zu Admin machen). |
| B3 | **Selbstregistrierung** mit **E-Mail-Bestätigung**. Ohne Bestätigung kein Login. Keine zusätzliche Admin-Freischaltung. |
| B4 | **Passwort-Reset** per E-Mail-Link. |
| B5 | Erster Admin: E-Mail-Adresse in der **Serverkonfiguration**. Weitere Admins ernennt ein bestehender Admin in der UI. |
| B6 | Oberfläche und Export-Überschriften: **nur Deutsch**. |
| B7 | Nutzer können Konto **vollständig löschen** (Konto, Konfigurationen, eigene Datensätze). Bereits vom Admin angelegte Katalogkopien bleiben. |
| B8 | Registrierung bleibt funktional offen. **Öffentlicher Produktivbetrieb erst nach ecoinvent-Lizenzklärung**. Bis dahin intern oder Zugangsschutz vor der App. |

---

## 7. MVP-Scope

| ID | Beschluss |
|---|---|
| S1 | Ein Beweis-Pfad: **HOF / Stärke → Folie**. |
| S2 | Die Kollegin **legt die Kette selbst im Admin-Tool an** (Kategorien, Stufen, Slots, Defaults, Mengen). Keine Vorab-Spezifikation in Excel, kein Übernehmen des alten openLCA-Modells. |
| S3 | Katalogdaten **neu aus dem Archiv** (cut-off 3.10.1): suchen, importieren, EF 3.1 charakterisieren, Kategorie zuweisen. Alte UUIDs, EN-15804-Zahlen und die Sachbilanz-Excel werden **ignoriert**. |
| S4 | Weitere Ketten erst, wenn die HOF-Kette im Tool angelegt, veröffentlicht und nachgerechnet werden kann. |
| S5 | Prüfungen im MVP: nur **harte Blocker** (unvollständig, Anteile ≠ 100 %, ungültige Kette, fehlendes CO₂e bei Eigendaten). Keine Min/Max-Warnungen, keine Masse-/Energiebilanz. |

### Bewusst nicht im MVP

- Freier Graph-Editor, Verzweigungen, Zyklen
- Zwischenprodukt als Katalogwahl (außer Ersatz durch eigenen Datensatz)
- Blackbox für das Endprodukt
- Organisationen, Teilen von Konfigurationen oder Eigendaten
- Versionshistorie von Ketten oder Datensätzen
- Snapshot-/Berichtsläufe, PDF, Annahmenblatt im Export
- Nutzer wählt die Bewertungsmethode
- Mehrere Archive in der UI (nur vorbereitet im Datenmodell)
- Grundlast-/Kennlinien-Energie, freie kg-Mengen je Zusatz-Slot
- Inline-Override von kWh/kg oder Faktoren ohne eigenen Datensatz
- Gewichtete Einzelnote, Sankey in der ecoinvent-Vorkette, Unsicherheit
- Englische Oberfläche
- Übernahme des alten openLCA-Modells, der Sachbilanz-Excel oder deren UUIDs/Faktoren
- Excel-Vorlage als Pflichtweg, bevor die Kollegin die Kette anlegen kann

---

## 8. Rechnung (normativ)

```
menge_end = Nutzereingabe in der Admin-Einheit des Endprodukts

Für jede Stufe von hinten nach vorn:
  ausgang_stufe = (bei letzter Stufe) menge_end
                  sonst berechneter Input der Folgestufe
  für jeden aktiven Slot:
    menge_slot = ausgang_stufe × admin_spezifische_menge
                 bei mehreren Slots derselben Kategorie: × anteil_slot
    faktor     = faktor_katalog oder faktor_eigendaten (Blackbox)
    beitrag    = menge_slot × faktor   // je EF-3.1-Indikator; fehlend = weglassen

Ergebnis(Indikator) = Summe aller Beiträge dieses Indikators
```

Ersetzt der Nutzer eine Zwischenstufe durch Eigendaten, entfallen alle Slots und Vorstufen dieser Stufe. Nachfolgende Stufen (z. B. Energie der Folie) bleiben.

---

## 9. Erstes Lieferziel und offene Betriebsfragen

### 9.1 Was die Technik zuerst bauen muss

Ziel: Die Kollegin kann sich als Admin anmelden und die HOF-Kette **zum Test direkt anlegen** — ohne Excel-Vorlage und ohne übernommene openLCA-Daten.

Dafür muss im Tool funktionieren:

1. Archiv-Pfad setzen  
2. Archiv durchsuchen (ein Suchfeld)  
3. Treffer in den Katalog übernehmen (EF 3.1 charakterisieren, Kategorie zuweisen; im Zweifel Market)  
4. Kategorien anlegen  
5. Endprodukt anlegen (Name, Einheit)  
6. Kette als Entwurf modellieren (Stufen, eine Ausgangskante, Slots, Minima, optionale Slots, spezifische Mengen, Default-Datensätze, Default-Anteile)  
7. Proberechnung (1 Einheit) und **Veröffentlichen**  
8. Als Nutzer: Endprodukt → Kette → Blätter wählen, Endmenge, rechnen  

Vergleich, CSV-Export, eigene Datensätze und Selbstregistrierung können **direkt danach** folgen; sie sind nicht nötig, damit die Kollegin die Kette erstmals einträgt.

### 9.2 Was danach noch offen ist

| Was | Wer |
|---|---|
| HOF-Kette fachlich im Tool anlegen und Defaults justieren | Kollegin (Admin-UI) |
| EF-3.1-Faktoren-/Methodendatei, falls nicht schon im Import-Job hinterlegt | Technik + Kollegin |
| ecoinvent-Lizenz vor öffentlichem Server | Projektleitung / ecoinvent Sales |
| SQL-Engine, Hosting, Mailversand | Technik |

---

## 10. Index der Anforderungsrunde

| Nr. | Thema | Wahl |
|---|---|---|
| 1 | Admin-Editor | Stufen mit Slots; linear; 1 Ausgang, n Eingänge |
| 2 | Stufenausgang | Zwischenprodukt fließt; Nutzer von hinten |
| 3 | Einstieg | Endprodukt, dann Kette |
| 4–5 | Mengen / eigene Werte | Eine Endmenge; sonst eigener Datensatz |
| 6 | Eigendaten-Rechnung | Blackbox |
| 7–8 | Einsatz Eigendaten | Zwischenstufe ja, Endprodukt nein |
| 9–10 | Indikatoren | CO₂e Pflicht beim Nutzer; Katalog voll EF 3.1 |
| 11–12 | Sichtbarkeit / Orgs | Nur ich oder Vorschlag; keine Organisationen |
| 13–16 | Vergleich / Export | Kettenübergreifend, live, 2–4, Summe im Diagramm, CSV-Tabelle |
| 17–18 | Kettenleben | Entwurf/veröffentlicht; bei Bruch ungültig |
| 19–20 | Archiv / Kategorien | Ein Pfad; nur Admin-Kategorien |
| 21–23 | Pflichtfelder / Publish / Einheit | Minimum ohne Quelle; Proberechnung; Einheit je Endprodukt |
| 24, 41 | Methode | Eine, fest EF 3.1 |
| 25–27 | Slots | Min + Nutzer-Slots; Anteile 100 %; optional aus |
| 28–32 | Live / UI / Teilen / Vorschlag | Sofort; Faktoren erst nach Rechnung; privat; Vorlage für Admin |
| 33–36 | Rollen / Checks / Scope | Nutzer+Admin; nur Blocker; ein Pfad HOF → Folie (im Tool anlegen, nicht aus Excel/openLCA) |
| 38–40 | Betrieb | Registrierung offen (Lizenz vor Go-Live); E-Mail-Confirm; nur Deutsch |
| 42–44 | Modell / Löschen / Market | cut-off 3.10.1; Konto vollständig löschen; Market |
| 46–48 | Kleinigkeiten | Passwort-Reset; Admin aus Config; ein Suchfeld |

Fragen 37, 45 und 49 waren Ablauf (weiter / Liste), keine Produktbeschlüsse.
