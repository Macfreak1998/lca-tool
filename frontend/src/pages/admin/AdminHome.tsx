import { Link } from "react-router-dom";

export function AdminHomePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Administration</h1>
      <p className="text-slate-600">
        Legen Sie Kategorien und ein Endprodukt an, importieren Sie Bausteine aus dem Archiv, modellieren Sie die Kette
        und veröffentlichen Sie sie nach erfolgreicher Proberechnung.
      </p>
      <ol className="card list-decimal space-y-2 pl-6 text-sm">
        <li>
          <Link className="text-forest-700 underline" to="/admin/archiv">
            Archiv-Pfad setzen und Datensätze importieren
          </Link>
        </li>
        <li>
          <Link className="text-forest-700 underline" to="/admin/kategorien">
            Kategorien anlegen
          </Link>
        </li>
        <li>
          <Link className="text-forest-700 underline" to="/admin/endprodukte">
            Endprodukt anlegen
          </Link>
        </li>
        <li>
          <Link className="text-forest-700 underline" to="/admin/ketten">
            Kette als Entwurf modellieren und veröffentlichen
          </Link>
        </li>
      </ol>
    </div>
  );
}
