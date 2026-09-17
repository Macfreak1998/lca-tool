import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DataApi } from "../api";
import type { Configuration } from "../types";

export function ConfigurationsPage() {
  const [rows, setRows] = useState<Configuration[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setRows(await DataApi.configurations());
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Meine Konfigurationen</h1>
      <p className="text-sm text-slate-600">Nur privat. Der Vergleich rechnet immer live mit aktuellen Katalogen.</p>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              <th className="py-2">Name</th>
              <th>Kette</th>
              <th>Menge</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b last:border-0">
                <td className="py-2">{row.name}</td>
                <td>{row.chain_name}</td>
                <td>
                  {row.end_amount} {row.end_unit}
                </td>
                <td>{row.invalid ? row.invalid_reason || "ungültig" : "gültig"}</td>
                <td className="space-x-3 text-right">
                  <Link className="text-forest-700 underline" to={`/?chain=${row.chain_id}`}>
                    Öffnen
                  </Link>
                  <button
                    className="text-red-700 underline"
                    type="button"
                    onClick={() => void DataApi.deleteConfiguration(row.id).then(load)}
                  >
                    Löschen
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
