import { useEffect, useState } from "react";
import { AdminApi } from "../../api";
import type { User } from "../../types";

export function UsersPage() {
  const [rows, setRows] = useState<User[]>([]);

  async function load() {
    setRows(await AdminApi.users());
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Nutzer</h1>
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-slate-500">
              <th className="py-2">E-Mail</th>
              <th>Rolle</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b last:border-0">
                <td className="py-2">{row.email}</td>
                <td>{row.role === "admin" ? "Administration" : "Nutzer"}</td>
                <td className="text-right">
                  <button
                    className="text-forest-700 underline"
                    type="button"
                    onClick={() =>
                      void AdminApi.setRole(row.id, row.role === "admin" ? "user" : "admin").then(load)
                    }
                  >
                    {row.role === "admin" ? "Zum Nutzer machen" : "Zum Admin machen"}
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
