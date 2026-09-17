import { FormEvent, useEffect, useState } from "react";
import { DataApi } from "../../api";
import type { Role } from "../../types";

export function RolesPage() {
  const [rows, setRows] = useState<Role[]>([]);
  const [label, setLabel] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setRows(await DataApi.roles());
  }

  useEffect(() => {
    void load();
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
        {rows.map((row) => (
          <li key={row.id} className="py-2">
            {row.label} <span className="text-slate-500">({row.slug})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
