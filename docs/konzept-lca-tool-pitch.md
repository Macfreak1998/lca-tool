# Konzept: LCA-Tool — Rechenkern und Datenhaltung

**Stand:** 11. September 2026 (Verweis nachgezogen)  
**Zweck:** Entscheidungsgrundlage für die technische Ausrichtung  
**Adressaten:** Projektleitung / fachliche Leitung (keine Programmierkenntnisse nötig)  
**Verbindliche Produktbeschlüsse (MVP):** `docs/entscheidungen-mvp.md`  
**Vertiefung für die Umsetzung:** `docs/anforderungen-und-architektur.md`

---

## 1. Worum es geht

Wir bauen ein **Anwendungstool**, mit dem Nutzerinnen und Nutzer die Umweltwirkung biobasierter Kunststoffe abschätzen können — zum Beispiel Stärke-Compound, Bio-PE, Bio-PP oder PLA, jeweils bis zum Endprodukt (Folie, Spritzgussteil, …).

Die Nutzerinnen und Nutzer modellieren nicht selbst in einer LCA-Software. Sie wählen Materialien, Mengen und wenige Kennzahlen. Das Tool rechnet und zeigt Ergebnisse (z. B. Treibhauspotenzial).

Die fachliche Modellierung liegt bei der Kollegin — **im Tool**, nicht in openLCA und nicht in einer Excel-Vorlage. Unsere Aufgabe ist die **Anwendung**: Admin-Oberfläche zum Anlegen von Ketten, Archivimport, Nutzerrechnung.

---

## 2. Die Ausgangslage in einfachen Worten

Eine Ökobilanz (LCA) braucht zwei Dinge:

1. **Ein Rezept** — was geht in das Produkt, in welchen Mengen (Stärke, Ethanol, Strom, …).
2. **Hintergrunddaten** — für jeden Stoff und jede Kilowattstunde Strom die zugehörigen Umweltwirkungen. Diese Zahlen kommen vor allem aus der Datenbank **ecoinvent**.

ecoinvent ist sehr groß: In der uns vorliegenden Fassung (Version 3.10.1, Systemmodell „cut-off“) sind das **rund 23.500 Datensätze** und **etwa 29 GB** auf der Festplatte. Ein einzelner Datensatz ist oft schon eine fertige „Ökobilanz in einer Datei“ (vom Acker bzw. Kraftwerk bis zum Werkstor).

Bisher war der Plan, die Desktop-Software **openLCA** als Rechenmaschine zu nutzen: Das Tool fragt openLCA, openLCA rechnet, das Tool zeigt die Zahl. Dafür müsste praktisch die ganze oder ein sehr großer Teil der Datenbank an der Rechnung hängen.

---

## 3. Warum wir die Richtung ändern wollen

### 3.1 Wartezeit

Wenn jedes Mal „live“ mit der großen Datenbank gerechnet wird, dauert ein Klick auf *Berechnen* leicht **Sekunden bis Minuten**. Für ein Werkzeug, das man im Browser bedient und in dem man Szenarien vergleicht, ist das zu langsam.

openLCA ist dafür gebaut, komplexe Modelle in der Fachsoftware zu rechnen — nicht, viele Nutzeranfragen in einem Web-Tool in Bruchteilen einer Sekunde zu beantworten.

### 3.2 Unser Modell ist klein

Die Ketten, die wir abbilden wollen, sind überschaubar:

```
Ausgangsmaterial + Energiemix
        →  Granulat
        →  Energiemix + ein bis zwei weitere Angaben
        →  Endprodukt
```

Wir brauchen **nicht** bei jedem Klick die kompletten 23.500 Datensätze. Wir brauchen nur die Bausteine, die in genau diesen Ketten vorkommen — typischerweise **eine handvoll bis wenige Dutzend**, nicht die ganze Bibliothek.

### 3.3 Nutzer wollen eigene Werte einbringen

Zwei häufige Wünsche:

- *„Meine Maschine ist effizienter“* — z. B. weniger Strom pro Kilogramm.
- *„Mein Bioethanol aus Kartoffelstärke verursacht XX Emissionen pro Kilogramm“* — eigene Zahl statt Katalogwert.

Das erste ist eine Mengenänderung im Rezept. Das zweite ersetzt die Hintergrundzahl für einen Stoff. Beides ist in einem schlanken, eigenen Rechenweg einfacher und schneller als in einer vollen openLCA-Live-Kopplung.

### 3.4 Lizenz von ecoinvent

Die Rohdatenbank darf nicht einfach auf einen Server für beliebige Dritte kopiert werden. Das gilt für openLCA-Images genauso wie für jede andere Software. Ein **kleiner Katalog nur der benötigten, aufbereiteten Kennzahlen** plus Klärung mit ecoinvent (internes Werkzeug vs. externes Tool) ist der sauberere Weg. Das ersetzen wir nicht durch Technik — das bleibt eine **rechtliche Klärung**.

---

## 4. Der vorgeschlagene Weg

Wir trennen drei Speicher. Jeder hat eine klare Aufgabe.

### 4.1 Das Lager (große Datenbank, nur Festplatte)

- Der vorhandene ecoinvent-Ordner bleibt liegen, **nur zum Lesen**.
- Er wird **nicht** bei jeder Nutzerrechnung angefasst.
- Er wird nur gebraucht, wenn wir den Katalog **erweitern**: z. B. ein weiterer Strommix oder ein weiterer Stärkelieferant.

Vergleich: ein Archiv im Keller. Man holt sich bei Bedarf einen Ordner, man trägt nicht das ganze Archiv an jeden Schreibtisch.

### 4.2 Der Katalog (kleine Datenbank)

Aus dem Lager ziehen wir nur die benötigten Bausteine und legen sie in einer **kleinen, übersichtlichen Datenbank** ab (SQL — das übliche Format für solche Listen).

Dort steht zum Beispiel:

- Name und Herkunft des Datensatzes (z. B. Strom, Niederspannung, Deutschland)
- Einheit (kg, kWh)
- **Kategorie** (Energie, Ethanol, Stärkelieferant, Polymer, …)
- Die **Umweltkennzahl** je Einheit für die vereinbarte Bewertungsmethode (z. B. Kilogramm CO₂-Äquivalent)

Die Benutzeroberfläche liest diese Listen. Ein neuer Stärkelieferant wird eingepflegt und einer Kategorie zugeordnet — **ohne** die Anwendung neu zu programmieren.

### 4.3 Die Nutzerdaten (ebenfalls in der kleinen Datenbank)

Nutzerinnen und Nutzer können:

- eigene Rezepte anlegen und speichern
- Standardwerte überschreiben (effizientere Maschine, eigene Emissionszahl)
- eigene Materialien anlegen, **wenn** sie ein Wirkungsprofil mitliefern (mindestens: Emissionen pro Kilogramm und Einheit)
- damit rechnen und Ergebnisse wiederfinden

Ohne Zahl oder ohne Einheit ist ein „eigenes Material“ nicht rechenbar. Ein bloßer Name reicht nicht.

---

## 5. Wo die Rechnung stattfindet

Bisher kam das Ergebnis „aus openLCA“. Darum musste sich die Anwendung nicht kümmern.

Künftig rechnet **unser eigenes Backend** — der Dienst hinter der Webseite. Die Fachlogik bleibt dieselbe: Rezept × Kennzahlen = Ergebnis.

In einfachen Worten:

> 0,36 kg Maisstärke × Kennzahl Maisstärke  
> \+ 0,36 kg Kartoffelstärke × Kennzahl Kartoffelstärke  
> \+ 0,9 kWh Strom × Kennzahl Strommix  
> = Ergebnis für das Granulat

*„Maschine effizienter“* ändert die 0,9 in z. B. 0,4.  
*„Mein Ethanol verursacht XX“* ersetzt die Katalog-Kennzahl für Ethanol durch die Nutzerzahl.

Die große ecoinvent-Bibliothek muss dafür nicht jedes Mal durchsucht oder komplett durchgerechnet werden. Deshalb bleibt die Antwortzeit kurz — Ziel: **sofort**, nicht „bitte warten“.

Als Werkzeug im Hintergrund eignet sich dafür **Brightway** (eine etablierte Open-Source-Bibliothek für Ökobilanzen) vor allem beim **einmaligen Aufbereiten** der Katalogzahlen aus den ecoinvent-Dateien. Die laufende Nutzerrechnung kann danach mit den fertigen Zahlen in der kleinen Datenbank erfolgen.

openLCA kann bei der Kollegin für die **fachliche Modellierung** bleiben. Für den Server und den Browser ist sie nicht mehr die Rechenmaschine.

---

## 6. Was Nutzerinnen und Nutzer im Tool tun

| Aktion | Bedeutung |
|---|---|
| Kette und Mengen wählen | z. B. Stärke-Pfad oder Bio-PE-Pfad, Kilogramm Folie |
| Energiemix wählen | aus dem Katalog, Kategorie „Energie“ |
| Lieferant wählen | z. B. Stärkelieferant, Ethanol-Rohstoff |
| Maschine anpassen | weniger Strom, weniger Ausschuss |
| Eigene Emissionen angeben | eigene Kennzahl statt Katalog, mit Quelle |
| Speichern | Rezept und Ergebnis gehören zum Konto |

Nicht vorgesehen: In der ganzen ecoinvent-Bibliothek frei stöbern. Neue ecoinvent-Bausteine kommen über eine **kontrollierte Ergänzung** (Fachseite / Administration) aus dem Lager in den Katalog.

---

## 7. Katalog statt fest einprogrammierter Listen

Ohne Katalog müsste in der Software stehen: „Es gibt genau diese drei Stromarten, diese Ethanol-Sorten, diese Stärkelieferanten.“ Jede Änderung wäre ein Eingriff ins Programm.

Mit Katalog gilt:

- **Fest** bleibt nur das Gerüst der Kette: *Material + Energie → Granulat → Energie + wenige Parameter → Endprodukt*.
- **Flexibel** sind alle konkreten Lieferanten und Mixe. Sie liegen in der Datenbank und haben eine Kategorie.

Die Oberfläche fragt: „Zeig mir alles mit der Kategorie Energie“ — und baut die Auswahl selbst.

---

## 8. Zusammenarbeit mit der Modellierung

Die Kollegin legt die erste Kette (**HOF / Stärke → Folie**) **selbst in der Administration** an: Kategorien, Stufen, Mengen, Defaults. Die Hintergrunddaten holt sie **neu aus dem ecoinvent-Archiv** (Name, Ort, Produkt suchen, importieren). Das alte openLCA-Modell und die Sachbilanz-Excel werden **nicht** übernommen — andere Systemmodelle, andere Zahlen, andere IDs.

openLCA kann bei ihr optional bleiben. Für Server und Browser ist sie weder Rechenkern noch Datenquelle.

Festgelegt: Systemmodell **cut-off 3.10.1**, Methode **EF 3.1**.

---

## 9. Chancen und Risiken

**Chancen**

- Rechenzeit passt zu einem Web-Tool.
- Eigene Maschinen- und Lieferantendaten sind ein echtes Unterscheidungsmerkmal.
- Der Katalog wächst, ohne jedes Mal die Software umzubauen.
- Das Docker-/Server-Image bleibt klein. Die 29 GB müssen nicht ins auszuliefernde Programm.

**Risiken und offene Punkte**

- **ecoinvent-Lizenz:** Auch ein kleiner Katalog und ein interaktives Tool können lizenzpflichtig sein, sobald Dritte damit rechnen. Vor dem Produktivbetrieb: Abstimmung (intern / ecoinvent Sales).
- **Qualität eigener Zahlen:** Nutzerwerte können wir nicht gegen ecoinvent prüfen. Quelle und Einheit müssen Pflichtfelder sein.
- **Abdeckung:** Was nicht im Katalog ist, kann niemand wählen. Ergänzung ist ein bewusster Schritt, kein Automatismus.
- **Kein Blick in die tiefe Lieferkette:** Die vorliegenden Datensätze sind bereits zusammengefasst. Man sieht den Beitrag „Ethanol“ oder „Strom“, nicht jedes einzelne Kraftwerk hinter dem Mix.

---

## 10. Empfehlung

1. **openLCA nicht als Live-Rechenkern** des Web-Tools verwenden.
2. **Kleine Katalog- und Nutzerdatenbank** aufbauen; die große ecoinvent-Ablage nur als Nachschub nutzen.
3. **Kategorien** (Energie, Ethanol, Stärke, …) in der Datenbank führen, nicht fest im Programm.
4. Nutzerinnen und Nutzer **Rezepte und eigene Kennzahlen** speichern und damit rechnen lassen.
5. **Lizenz und Systemmodell** vor dem ersten produktiven Server klären.
6. Als Nächstes die **Admin-Strecke** bauen, bis die Kollegin die HOF-Kette im Tool anlegen, aus dem Archiv befüllen und einmal rechnen kann.

---

## 11. Satz zum Mitnehmen

Wir rechnen nicht jedes Mal die ganze Welt. Wir pflegen einen **kleinen, klar sortierten Katalog** der Stoffe und Energien, die unser Tool wirklich braucht. Die große Datenbank bleibt das Archiv. Nutzerinnen und Nutzer ergänzen **ihre** Rezepte und Kennzahlen. Die Rechnung selbst ist dann einfach, schnell und erklärbar — so wie ein Rezept mal die Nährwerte der Zutaten.

---

*Ansprechpartner Technik: Jan*  
*Bezug: interne Abstimmung LCA-Tool, September 2026*
