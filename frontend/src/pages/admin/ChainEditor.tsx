import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { DataApi } from "../../api";
import type { Chain, Dataset, Role, Slot, Stage } from "../../types";

type DraftSlot = Omit<Slot, "id"> & { id?: number; key: string };
type DraftStage = Omit<Stage, "id" | "slots"> & { id?: number; key: string; slots: DraftSlot[] };

function toDraft(chain: Chain): DraftStage[] {
  return chain.stages.map((stage) => ({
    ...stage,
    key: `s-${stage.id}`,
    slots: stage.slots.map((slot) => ({ ...slot, key: `p-${slot.id}` })),
  }));
}

export function ChainEditorPage() {
  const { id } = useParams();
  const chainId = Number(id);
  const [chain, setChain] = useState<Chain | null>(null);
  const [stages, setStages] = useState<DraftStage[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const [c, r, d] = await Promise.all([DataApi.chain(chainId), DataApi.roles(), DataApi.datasets()]);
    setChain(c);
    setStages(toDraft(c));
    setRoles(r);
    setDatasets(d);
  }

  useEffect(() => {
    void load();
  }, [chainId]);

  function addStage() {
    setStages((current) => [
      ...current,
      {
        key: `s-${Date.now()}`,
        name: "Neue Stufe",
        sort_order: current.length,
        outgoing_stage_id: null,
        upstream_amount: 1,
        slots: [],
      },
    ]);
  }

  function addSlot(stageKey: string) {
    setStages((current) =>
      current.map((stage) =>
        stage.key === stageKey
          ? {
              ...stage,
              slots: [
                ...stage.slots,
                {
                  key: `p-${Date.now()}`,
                  role_id: roles[0]?.id || 0,
                  required: true,
                  optional_default_off: false,
                  min_count: 1,
                  specific_amount: 1,
                  unit: "kg",
                  default_dataset_id: null,
                  default_share: 1,
                },
              ],
            }
          : stage,
      ),
    );
  }

  async function save() {
    setError("");
    setMessage("");
    try {
      const saved = await DataApi.saveChain(chainId, {
        name: chain?.name,
        stages: stages.map((stage, index) => ({
          id: stage.id,
          name: stage.name,
          sort_order: index,
          upstream_amount: stage.upstream_amount,
          slots: stage.slots.map((slot) => ({
            id: slot.id,
            role_id: slot.role_id,
            required: slot.required,
            optional_default_off: slot.optional_default_off,
            min_count: slot.min_count,
            specific_amount: slot.specific_amount,
            unit: slot.unit,
            default_dataset_id: slot.default_dataset_id,
            default_share: slot.default_share,
          })),
        })),
      });
      setChain(saved);
      setStages(toDraft(saved));
      setMessage("Entwurf gespeichert.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen.");
    }
  }

  async function publish() {
    setError("");
    try {
      await save();
      const published = await DataApi.publishChain(chainId);
      setChain(published);
      setStages(toDraft(published));
      setMessage("Veröffentlicht.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Veröffentlichen fehlgeschlagen.");
    }
  }

  if (!chain) return <p>Laden …</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-forest-800">{chain.name}</h1>
        <Link className="text-sm text-forest-700 underline" to="/admin/ketten">
          Zurück
        </Link>
      </div>
      <p className="text-sm text-slate-600">
        {chain.end_product_name} · {chain.end_unit} · {chain.status === "published" ? "veröffentlicht" : "Entwurf"}.
        Stufen von vorn nach hinten. Das Zwischenprodukt fließt; `Menge Vorgänger` gilt je Einheit Stufenausgang.
      </p>
      {stages.map((stage, index) => (
        <section key={stage.key} className="card space-y-3">
          <div className="grid gap-3 md:grid-cols-[1fr_160px_auto]">
            <input
              className="input"
              value={stage.name}
              onChange={(e) =>
                setStages((current) => current.map((item) => (item.key === stage.key ? { ...item, name: e.target.value } : item)))
              }
            />
            {index > 0 && (
              <div>
                <label className="label">Menge Vorgänger</label>
                <input
                  className="input"
                  type="number"
                  step="any"
                  value={stage.upstream_amount}
                  onChange={(e) =>
                    setStages((current) =>
                      current.map((item) =>
                        item.key === stage.key ? { ...item, upstream_amount: Number(e.target.value) } : item,
                      ),
                    )
                  }
                />
              </div>
            )}
            <button className="btn-secondary h-10 self-end" type="button" onClick={() => addSlot(stage.key)}>
              Slot
            </button>
          </div>
          {stage.slots.map((slot) => (
            <div key={slot.key} className="grid gap-2 rounded-lg bg-slate-50 p-3 md:grid-cols-6">
              <select
                className="input"
                value={slot.role_id}
                onChange={(e) =>
                  setStages((current) =>
                    current.map((item) =>
                      item.key === stage.key
                        ? {
                            ...item,
                            slots: item.slots.map((s) => (s.key === slot.key ? { ...s, role_id: Number(e.target.value) } : s)),
                          }
                        : item,
                    ),
                  )
                }
              >
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.label}
                  </option>
                ))}
              </select>
              <input
                className="input"
                type="number"
                step="any"
                value={slot.specific_amount}
                onChange={(e) =>
                  setStages((current) =>
                    current.map((item) =>
                      item.key === stage.key
                        ? {
                            ...item,
                            slots: item.slots.map((s) =>
                              s.key === slot.key ? { ...s, specific_amount: Number(e.target.value) } : s,
                            ),
                          }
                        : item,
                    ),
                  )
                }
              />
              <input
                className="input"
                value={slot.unit}
                onChange={(e) =>
                  setStages((current) =>
                    current.map((item) =>
                      item.key === stage.key
                        ? { ...item, slots: item.slots.map((s) => (s.key === slot.key ? { ...s, unit: e.target.value } : s)) }
                        : item,
                    ),
                  )
                }
              />
              <select
                className="input"
                value={slot.default_dataset_id || ""}
                onChange={(e) =>
                  setStages((current) =>
                    current.map((item) =>
                      item.key === stage.key
                        ? {
                            ...item,
                            slots: item.slots.map((s) =>
                              s.key === slot.key
                                ? { ...s, default_dataset_id: e.target.value ? Number(e.target.value) : null }
                                : s,
                            ),
                          }
                        : item,
                    ),
                  )
                }
              >
                <option value="">Default-Datensatz</option>
                {datasets
                  .filter((item) => item.role_ids.includes(slot.role_id))
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                      {item.location ? ` (${item.location})` : ""}
                    </option>
                  ))}
              </select>
              <input
                className="input"
                type="number"
                step="any"
                value={slot.default_share}
                onChange={(e) =>
                  setStages((current) =>
                    current.map((item) =>
                      item.key === stage.key
                        ? {
                            ...item,
                            slots: item.slots.map((s) =>
                              s.key === slot.key ? { ...s, default_share: Number(e.target.value) } : s,
                            ),
                          }
                        : item,
                    ),
                  )
                }
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={slot.optional_default_off}
                  onChange={(e) =>
                    setStages((current) =>
                      current.map((item) =>
                        item.key === stage.key
                          ? {
                              ...item,
                              slots: item.slots.map((s) =>
                                s.key === slot.key
                                  ? { ...s, optional_default_off: e.target.checked, required: !e.target.checked }
                                  : s,
                              ),
                            }
                          : item,
                      ),
                    )
                  }
                />
                optional
              </label>
            </div>
          ))}
        </section>
      ))}
      <div className="flex flex-wrap gap-3">
        <button className="btn-secondary" type="button" onClick={addStage}>
          Stufe hinzufügen
        </button>
        <button className="btn-secondary" type="button" onClick={() => void save()}>
          Entwurf speichern
        </button>
        <button className="btn" type="button" onClick={() => void publish()}>
          Proberechnung und veröffentlichen
        </button>
        {chain.status === "published" && (
          <button className="btn-secondary" type="button" onClick={() => void DataApi.unpublishChain(chainId).then(load)}>
            Zurückziehen
          </button>
        )}
      </div>
      {message && <p className="text-sm text-forest-700">{message}</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}
    </div>
  );
}
