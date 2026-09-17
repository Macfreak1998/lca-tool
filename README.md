# LCA-Tool

Web-Tool zur Abschätzung der Umweltwirkung biobasierter Kunststoffe. Nutzerinnen und Nutzer wählen Endprodukt, Kette und Endmenge. Die Administration pflegt Kategorien, Katalog und Ketten und importiert Bausteine aus einem ecoinvent-Archiv (cut-off 3.10.1 LCI). Bewertungsmethode: **EF 3.1**, sofern eine LCIA-Datei hinterlegt ist.

Verbindliche Produktregeln: [`docs/entscheidungen-mvp.md`](docs/entscheidungen-mvp.md).

In diesem Repository liegt **kein lizenziertes ecoinvent-Archiv**, nur ein kleines Demo-Archiv für den Start.

## Schnellstart mit Docker

Voraussetzung: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

Öffnen: [http://localhost:5173](http://localhost:5173)

| | |
|---|---|
| E-Mail | `admin@localhost` |
| Passwort | `admin` |

Docker startet mit Demo-Daten: Kategorie *Stärke*, Endprodukt *Folie*, Katalogeintrag *maize starch*, veröffentlichte Demo-Kette. Unter **Rechnen** einmal *Berechnen* klicken.

Die Demo-LCIA-Datei passt nur zu den Demo-Flüssen (`flow-co2`, `flow-so2`). Für das echte ecoinvent-Archiv eine gemappte EF-3.1-Datei setzen und den Archiv-Pfad in der Admin-Oberfläche eintragen. Das 29-GB-Archiv nicht ins Image kopieren, sondern als Volume mounten.

Stoppen: `Ctrl+C`, danach optional `docker compose down`. Die SQLite-Datei liegt im Docker-Volume `lca-data`. Neu aufsetzen: `docker compose down -v`.

## Lokal ohne Docker

```bash
cp .env.example .env
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p data
uvicorn app.main:app --reload --app-dir .
```

Zweites Terminal:

```bash
cd frontend
npm install
npm run dev
```

Ohne SMTP erscheinen Bestätigungs- und Reset-Links in der Serverkonsole.

## Tests

```bash
cd backend
pytest
```

Die Tests nutzen kleine Fixtures, nicht das 29-GB-Archiv.

## Demo-Kette selbst nachbauen

1. Als Admin anmelden
2. Archiv-Pfad setzen (Docker: Demo-Archiv ist schon gesetzt)
3. Kategorien und Endprodukt anlegen
4. Datensätze suchen, importieren, Kategorie zuweisen
5. Kette als Entwurf modellieren, Proberechnung, veröffentlichen
6. Unter **Rechnen** durchrechnen

Es gibt kein fest verdrahtetes HOF-Rezept. `DEMO_SEED=true` legt nur die kleine Docker-Demo an.
