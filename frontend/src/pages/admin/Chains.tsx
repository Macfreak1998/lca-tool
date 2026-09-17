import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DataApi } from "../../api";
import type { Chain, EndProduct } from "../../types";

export function ChainsPage() {
  const [rows, setRows] = useState<Chain[]>([]);
  const [products, setProducts] = useState<EndProduct[]>([]);
  const [name, setName] = useState("");
  const [productId, setProductId] = useState(0);

  async function load() {
    const [c, p] = await Promise.all([DataApi.chains(), DataApi.endProducts()]);
    setRows(c);
    setProducts(p);
    if (!productId && p[0]) setProductId(p[0].id);
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await DataApi.createChain(name, productId);
    setName("");
    await load();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-forest-800">Ketten</h1>
      <form className="card grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={(event) => void onSubmit(event)}>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name der Kette" required />
        <select className="input" value={productId} onChange={(e) => setProductId(Number(e.target.value))}>
          {products.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} ({item.unit})
            </option>
          ))}
        </select>
        <button className="btn" type="submit">
          Entwurf anlegen
        </button>
      </form>
      <ul className="card divide-y text-sm">
        {rows.map((row) => (
          <li key={row.id} className="flex items-center justify-between py-2">
            <span>
              {row.name} · {row.end_product_name} · {row.status === "published" ? "veröffentlicht" : "Entwurf"}
            </span>
            <Link className="text-forest-700 underline" to={`/admin/ketten/${row.id}`}>
              Bearbeiten
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
