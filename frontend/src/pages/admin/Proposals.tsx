import { useEffect, useState } from "react";
import { AdminApi, DataApi } from "../../api";
import type { Dataset, Role } from "../../types";

type Proposal = { id: number; status: string; note: string; dataset: Dataset };

export function ProposalsPage() {
  const [rows, setRows] = useState<Proposal[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState("");

  async function load() {
    const [p, r] = await Promise.all([AdminApi.proposals(), DataApi.roles()]);
    setRows(p);
    setRoles(r);
  }

  useEffect(() => {
    void load().catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Vorschläge</h1>
      <p className="text-sm text-slate-600">Ein Vorschlag wird nie 1:1 öffentlich. Sie legen daraus einen neuen Katalogeintrag an.</p>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.id} className="card flex flex-wrap items-center justify-between gap-3">
            <div>
              <strong>{row.dataset.name}</strong>
              <p className="text-sm text-slate-600">
                {row.dataset.unit}
                {row.dataset.source_note ? ` · ${row.dataset.source_note}` : ""}
              </p>
            </div>
            <button
              className="btn"
              type="button"
              onClick={() =>
                void AdminApi.acceptProposal(row.id, row.dataset.role_ids[0] || roles[0]?.id).then(load)
              }
            >
              Als Katalogeintrag anlegen
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
