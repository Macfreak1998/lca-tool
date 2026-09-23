import { useEffect, useMemo, useState } from "react";
import { AdminApi, DataApi } from "../../api";
import type { Dataset, Role } from "../../types";

const SOURCE_LABEL: Record<Dataset["source_kind"], string> = {
  ecoinvent: "ecoinvent",
  catalog_manual: "manuell",
  user: "Nutzer",
};

function sameIds(left: number[], right: number[]) {
  if (left.length !== right.length) return false;
  const a = [...left].sort();
  const b = [...right].sort();
  return a.every((id, index) => id === b[index]);
}

export function CatalogPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [rows, setRows] = useState<Dataset[]>([]);
  const [drafts, setDrafts] = useState<Record<number, number[]>>({});
  const [filterRole, setFilterRole] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const [r, d] = await Promise.all([DataApi.roles(), DataApi.datasets()]);
    setRoles(r);
    setRows(d);
    setDrafts({});
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  const visible = useMemo(
    () => (filterRole ? rows.filter((row) => row.role_ids.includes(filterRole)) : rows),
    [filterRole, rows],
  );

  function draftIds(row: Dataset) {
    return drafts[row.id] ?? row.role_ids;
  }

  function toggleRole(row: Dataset, roleId: number) {
    const current = draftIds(row);
    const next = current.includes(roleId) ? current.filter((id) => id !== roleId) : [...current, roleId];
    setDrafts((prev) => ({ ...prev, [row.id]: next }));
  }

  async function save(row: Dataset) {
    const roleIds = draftIds(row);
    setBusy(true);
    setError("");
    try {
      await AdminApi.updateCatalogDataset(row.id, roleIds);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(row: Dataset) {
    if (!window.confirm(`„${row.name}“ aus dem Katalog entfernen?`)) return;
    setBusy(true);
    setError("");
    try {
      await AdminApi.deleteCatalogDataset(row.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-forest-800">Katalog</h1>
        <p className="text-sm text-slate-600">
          Importierte Bausteine Kategorien zuordnen. Ein Datensatz braucht mindestens eine Kategorie.
        </p>
      </div>
      <div className="card max-w-xs space-y-2">
        <label className="label">Filter nach Kategorie</label>
        <select className="input" value={filterRole} onChange={(e) => setFilterRole(Number(e.target.value))}>
          <option value={0}>Alle</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.label}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              <th className="py-2">Name</th>
              <th>Ort</th>
              <th>Einheit</th>
              <th>Quelle</th>
              <th>Flüsse</th>
              <th>Kategorien</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const ids = draftIds(row);
              const dirty = !sameIds(ids, row.role_ids);
              return (
                <tr key={row.id} className="border-b align-top last:border-0">
                  <td className="py-3 font-medium">{row.name}</td>
                  <td className="py-3">{row.location || "—"}</td>
                  <td className="py-3">{row.unit}</td>
                  <td className="py-3">{SOURCE_LABEL[row.source_kind]}</td>
                  <td className="py-3">{row.exchange_count ?? 0}</td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-x-3 gap-y-1">
                      {roles.map((role) => (
                        <label key={role.id} className="flex items-center gap-1.5 whitespace-nowrap">
                          <input
                            type="checkbox"
                            checked={ids.includes(role.id)}
                            onChange={() => toggleRole(row, role.id)}
                          />
                          {role.label}
                        </label>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 text-right">
                    <div className="flex flex-col items-end gap-2">
                      <button
                        className="text-forest-700 underline"
                        type="button"
                        disabled={busy || !dirty || ids.length === 0}
                        onClick={() => void save(row)}
                      >
                        Speichern
                      </button>
                      <button
                        className="text-red-700 underline"
                        type="button"
                        disabled={busy}
                        onClick={() => void remove(row)}
                      >
                        Entfernen
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {visible.length === 0 && (
              <tr>
                <td className="py-3 text-slate-500" colSpan={7}>
                  Keine Katalogdatensätze. Importieren Sie zuerst Bausteine aus dem Archiv.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
