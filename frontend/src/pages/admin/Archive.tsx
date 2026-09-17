import { FormEvent, useEffect, useState } from "react";
import { AdminApi, DataApi } from "../../api";
import type { ArchiveHit, Dataset, Role } from "../../types";

export function ArchivePage() {
  const [path, setPath] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ArchiveHit[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [roleId, setRoleId] = useState(0);
  const [imported, setImported] = useState<Dataset | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [pathSaved, setPathSaved] = useState("");

  useEffect(() => {
    void Promise.all([AdminApi.archivePath(), DataApi.roles()]).then(([p, r]) => {
      setPath(p.path);
      setRoles(r);
      if (r[0]) setRoleId(r[0].id);
    });
  }, []);

  async function savePath(event: FormEvent) {
    event.preventDefault();
    setError("");
    setPathSaved("");
    try {
      const saved = await AdminApi.setArchivePath(path);
      setPath(saved.path);
      setPathSaved("Pfad gespeichert. Danach über Name, Ort oder Referenzprodukt suchen.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pfad konnte nicht gespeichert werden.");
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSearched(true);
    try {
      setHits(await AdminApi.searchArchive(query));
    } catch (err) {
      setHits([]);
      setError(err instanceof Error ? err.message : "Suche fehlgeschlagen.");
    }
  }

  async function importHit(filename: string) {
    setBusy(true);
    setError("");
    try {
      setImported(await AdminApi.importDataset(filename, roleId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-forest-800">Archiv und Import</h1>
      <form className="card space-y-3" onSubmit={(event) => void savePath(event)}>
        <label className="label">Archiv-Pfad (ein Pfad, nur lesen)</label>
        <input className="input" value={path} onChange={(e) => setPath(e.target.value)} />
        <button className="btn" type="submit">
          Pfad speichern
        </button>
        {pathSaved && <p className="text-sm text-forest-700">{pathSaved}</p>}
      </form>
      <form className="card space-y-3" onSubmit={(event) => void search(event)}>
        <label className="label">Suche über Name, Ort und Referenzprodukt</label>
        <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="z. B. maize starch DE" />
        <div className="flex flex-wrap gap-3">
          <select className="input max-w-xs" value={roleId} onChange={(e) => setRoleId(Number(e.target.value))}>
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.label}
              </option>
            ))}
          </select>
          <button className="btn" type="submit">
            Suchen
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Im Zweifel Market-Datensätze bevorzugen. Der Import speichert das Inventar. EF 3.1 wird erst beim Rechnen angewendet, wenn eine LCIA-Datei gesetzt ist.
        </p>
      </form>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {imported && (
        <p className="card text-sm">
          Übernommen: {imported.name} ({imported.location}, {imported.unit}
          {imported.exchange_count != null ? `, ${imported.exchange_count} Flüsse` : ""})
        </p>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              <th className="py-2">Aktivität</th>
              <th>Ort</th>
              <th>Produkt</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {hits.map((hit) => (
              <tr key={hit.filename} className="border-b last:border-0">
                <td className="py-2">
                  {hit.activity_name}
                  {hit.likely_market && <span className="ml-2 text-xs text-forest-700">Market</span>}
                </td>
                <td>{hit.location}</td>
                <td>{hit.reference_product}</td>
                <td className="text-right">
                  <button className="text-forest-700 underline" type="button" disabled={busy} onClick={() => void importHit(hit.filename)}>
                    In Katalog
                  </button>
                </td>
              </tr>
            ))}
            {searched && hits.length === 0 && !error && (
              <tr>
                <td className="py-3 text-slate-500" colSpan={4}>
                  Keine Treffer. Beispiele: maize, maize starch, maize starch DE.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
