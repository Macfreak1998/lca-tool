import { FormEvent, useEffect, useState } from "react";
import { DataApi } from "../../api";
import type { Role } from "../../types";

export function RolesPage() {
  const [rows, setRows] = useState<Role[]>([]);
  const [label, setLabel] = useState("");
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const next = await DataApi.roles();
    setRows(next);
    setEdits(Object.fromEntries(next.map((row) => [row.id, row.label])));
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await DataApi.createRole(label);
      setLabel("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen.");
    }
  }

  async function rename(row: Role) {
    const next = (edits[row.id] ?? row.label).trim();
    if (!next || next === row.label) return;
    setBusy(true);
    setError("");
    try {
      await DataApi.updateRole(row.id, next);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Umbenennen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(row: Role) {
    if (!window.confirm(`Kategorie „${row.label}“ löschen?`)) return;
    setBusy(true);
    setError("");
    try {
      await DataApi.deleteRole(row.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Kategorien</h1>
      <form className="card flex gap-3" onSubmit={(event) => void onSubmit(event)}>
        <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="z. B. Stärke" required />
        <button className="btn" type="submit">
          Anlegen
        </button>
      </form>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <ul className="card divide-y text-sm">
        {rows.map((row) => {
          const count = row.dataset_count ?? 0;
          const draft = edits[row.id] ?? row.label;
          return (
            <li key={row.id} className="flex flex-wrap items-center gap-3 py-2">
              <input
                className="input max-w-xs"
                value={draft}
                onChange={(e) => setEdits((current) => ({ ...current, [row.id]: e.target.value }))}
              />
              <span className="text-slate-500">({row.slug})</span>
              <span className="text-slate-500">
                {count === 1 ? "1 Datensatz" : `${count} Datensätze`}
              </span>
              <div className="ml-auto flex gap-3">
                <button
                  className="text-forest-700 underline"
                  type="button"
                  disabled={busy || !draft.trim() || draft.trim() === row.label}
                  onClick={() => void rename(row)}
                >
                  Speichern
                </button>
                <button
                  className="text-red-700 underline"
                  type="button"
                  disabled={busy}
                  onClick={() => void remove(row)}
                >
                  Löschen
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
