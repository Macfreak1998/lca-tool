import { FormEvent, useEffect, useState } from "react";
import { DataApi } from "../../api";
import type { EndProduct } from "../../types";

export function EndProductsPage() {
  const [rows, setRows] = useState<EndProduct[]>([]);
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("kg");

  async function load() {
    setRows(await DataApi.endProducts());
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await DataApi.createEndProduct(name, unit);
    setName("");
    await load();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Endprodukte</h1>
      <form className="card grid gap-3 md:grid-cols-[1fr_120px_auto]" onSubmit={(event) => void onSubmit(event)}>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, z. B. Folie" required />
        <input className="input" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Einheit" required />
        <button className="btn" type="submit">
          Anlegen
        </button>
      </form>
      <ul className="card divide-y text-sm">
        {rows.map((row) => (
          <li key={row.id} className="py-2">
            {row.name} ({row.unit})
          </li>
        ))}
      </ul>
    </div>
  );
}
