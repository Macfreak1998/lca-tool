import { FormEvent, useEffect, useState } from "react";
import { DataApi } from "../api";
import type { Dataset, Role } from "../types";

export function UserDatasetsPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [rows, setRows] = useState<Dataset[]>([]);
  const [name, setName] = useState("");
  const [roleId, setRoleId] = useState(0);
  const [unit, setUnit] = useState("kg");
  const [co2, setCo2] = useState("");
  const [source, setSource] = useState("");
  const [inputs, setInputs] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const [r, d] = await Promise.all([DataApi.roles(), DataApi.userDatasets()]);
    setRoles(r);
    setRows(d);
    if (!roleId && r[0]) setRoleId(r[0].id);
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await DataApi.createUserDataset({
        name,
        role_id: roleId,
        unit,
        climate_change: Number(co2),
        source_note: source,
        inputs_doc: inputs,
      });
      setName("");
      setCo2("");
      setSource("");
      setInputs("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-forest-800">Eigene Datensätze</h1>
        <p className="text-sm text-slate-600">
          Blackbox: Pflicht sind Name, Kategorie, Einheit und CO₂e. Weitere Indikatoren dürfen fehlen.
        </p>
      </div>
      <form className="card grid gap-3 md:grid-cols-2" onSubmit={(event) => void onSubmit(event)}>
        {error && <p className="md:col-span-2 text-sm text-red-700">{error}</p>}
        <div>
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div>
          <label className="label">Kategorie</label>
          <select className="input" value={roleId} onChange={(e) => setRoleId(Number(e.target.value))}>
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Einheit</label>
          <input className="input" value={unit} onChange={(e) => setUnit(e.target.value)} required />
        </div>
        <div>
          <label className="label">Klimawandel (kg CO₂-Äq. je Einheit)</label>
          <input className="input" type="number" step="any" value={co2} onChange={(e) => setCo2(e.target.value)} required />
        </div>
        <div>
          <label className="label">Quelle (optional)</label>
          <input className="input" value={source} onChange={(e) => setSource(e.target.value)} />
        </div>
        <div>
          <label className="label">Ausgangsstoffe, nur Dokumentation</label>
          <input className="input" value={inputs} onChange={(e) => setInputs(e.target.value)} />
        </div>
        <div className="md:col-span-2">
          <button className="btn" type="submit">
            Anlegen
          </button>
        </div>
      </form>
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              <th className="py-2">Name</th>
              <th>Einheit</th>
              <th>CO₂e</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const co2e = row.factors?.find((item) => item.indicator_id === "climate_change")?.value;
              return (
                <tr key={row.id} className="border-b last:border-0">
                  <td className="py-2">{row.name}</td>
                  <td>{row.unit}</td>
                  <td>{co2e ?? "—"}</td>
                  <td className="space-x-2 text-right">
                    <button className="text-forest-700 underline" type="button" onClick={() => void DataApi.proposeDataset(row.id)}>
                      Als Vorlage vorschlagen
                    </button>
                    <button
                      className="text-red-700 underline"
                      type="button"
                      onClick={() => void DataApi.deleteUserDataset(row.id).then(load)}
                    >
                      Löschen
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
