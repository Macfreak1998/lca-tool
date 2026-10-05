import type {
  ArchiveHit,
  CalcResult,
  CalculatePayload,
  Chain,
  ChainNode,
  Configuration,
  Dataset,
  EndProduct,
  Indicator,
  Role,
  User,
} from "./types";

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (Array.isArray(data.detail)) return data.detail.join(" ");
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((item: { msg?: string }) => item.msg || "").join(" ");
    }
    return JSON.stringify(data.detail ?? data);
  } catch {
    return res.statusText;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const AuthApi = {
  me: () => api<User>("/api/auth/me"),
  login: (email: string, password: string) =>
    api<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => api("/api/auth/logout", { method: "POST" }),
  register: (email: string, password: string) =>
    api<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  confirm: (token: string) => api("/api/auth/confirm", { method: "POST", body: JSON.stringify({ token }) }),
  requestReset: (email: string) =>
    api("/api/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email }) }),
  reset: (token: string, password: string) =>
    api("/api/auth/password-reset", { method: "POST", body: JSON.stringify({ token, password }) }),
  deleteMe: () => api("/api/auth/me", { method: "DELETE" }),
};

export const MetaApi = {
  public: () => api<{ public_signup: boolean; language?: string; lcia_available?: boolean }>("/api/meta/public"),
  indicators: () => api<Indicator[]>("/api/meta/indicators"),
};

export const AdminApi = {
  archivePath: () => api<{ path: string }>("/api/settings/archive-path"),
  setArchivePath: (path: string) =>
    api<{ path: string }>("/api/settings/archive-path", { method: "PUT", body: JSON.stringify({ path }) }),
  searchArchive: (q: string) => api<ArchiveHit[]>(`/api/archive/search?q=${encodeURIComponent(q)}`),
  importDataset: (filename: string, role_id: number) =>
    api<Dataset>("/api/catalog/import", { method: "POST", body: JSON.stringify({ filename, role_id }) }),
  proposals: () => api<{ id: number; status: string; note: string; dataset: Dataset }[]>("/api/catalog/proposals"),
  acceptProposal: (proposal_id: number, role_id?: number, name?: string) =>
    api<Dataset>("/api/catalog/from-proposal", {
      method: "POST",
      body: JSON.stringify({ proposal_id, role_id, name }),
    }),
  users: () => api<User[]>("/api/users"),
  setRole: (userId: number, role: string) =>
    api<User>(`/api/users/${userId}`, { method: "PATCH", body: JSON.stringify({ role }) }),
  updateCatalogDataset: (id: number, role_ids: number[]) =>
    api<Dataset>(`/api/catalog/datasets/${id}`, { method: "PATCH", body: JSON.stringify({ role_ids }) }),
  deleteCatalogDataset: (id: number) => api(`/api/catalog/datasets/${id}`, { method: "DELETE" }),
};

export const DataApi = {
  roles: () => api<Role[]>("/api/roles"),
  createRole: (label: string) =>
    api<Role>("/api/roles", { method: "POST", body: JSON.stringify({ label }) }),
  updateRole: (id: number, label: string) =>
    api<Role>(`/api/roles/${id}`, { method: "PATCH", body: JSON.stringify({ label }) }),
  deleteRole: (id: number) => api(`/api/roles/${id}`, { method: "DELETE" }),
  endProducts: () => api<EndProduct[]>("/api/end-products"),
  createEndProduct: (name: string, unit: string) =>
    api<EndProduct>("/api/end-products", { method: "POST", body: JSON.stringify({ name, unit }) }),
  datasets: (role?: number) =>
    api<Dataset[]>(role ? `/api/catalog/datasets?role=${role}` : "/api/catalog/datasets"),
  chains: () => api<Chain[]>("/api/chains"),
  chain: (id: number) => api<Chain>(`/api/chains/${id}`),
  createChain: (name: string, end_product_id: number) =>
    api<Chain>("/api/chains", { method: "POST", body: JSON.stringify({ name, end_product_id }) }),
  saveChain: (id: number, body: unknown) =>
    api<Chain>(`/api/chains/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  publishChain: (id: number) => api<Chain>(`/api/chains/${id}/publish`, { method: "POST" }),
  unpublishChain: (id: number) => api<Chain>(`/api/chains/${id}/unpublish`, { method: "POST" }),
  calculate: (payload: CalculatePayload) =>
    api<CalcResult>("/api/calculate", { method: "POST", body: JSON.stringify(payload) }),
  configurations: () => api<Configuration[]>("/api/configurations"),
  configuration: (id: number) => api<Configuration>(`/api/configurations/${id}`),
  saveConfiguration: (body: unknown) =>
    api<Configuration>("/api/configurations", { method: "POST", body: JSON.stringify(body) }),
  updateConfiguration: (id: number, body: unknown) =>
    api<Configuration>(`/api/configurations/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteConfiguration: (id: number) => api(`/api/configurations/${id}`, { method: "DELETE" }),
  userDatasets: () => api<Dataset[]>("/api/user-datasets"),
  createUserDataset: (body: unknown) =>
    api<Dataset>("/api/user-datasets", { method: "POST", body: JSON.stringify(body) }),
  updateUserDataset: (id: number, body: unknown) =>
    api<Dataset>(`/api/user-datasets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteUserDataset: (id: number) => api(`/api/user-datasets/${id}`, { method: "DELETE" }),
  proposeDataset: (id: number) => api(`/api/user-datasets/${id}/propose`, { method: "POST" }),
  compare: (ids: number[]) =>
    api<{ items: { configuration: Configuration; result: CalcResult }[]; blockers: string[] }>(
      "/api/compare",
      { method: "POST", body: JSON.stringify({ configuration_ids: ids }) },
    ),
};

export async function download(path: string, body: unknown, filename: string) {
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function byName(a: Dataset, b: Dataset) {
  if (a.name < b.name) return -1;
  if (a.name > b.name) return 1;
  return a.id - b.id;
}

export function datasetsForCategory(chain: Chain, category: ChainNode, catalog: Dataset[], own: Dataset[]): Dataset[] {
  if (category.datasets_differ) {
    const ids = new Set(
      chain.combinations.flatMap((combo) =>
        combo.axes
          .filter((axis) => axis.category_node_id === category.id && axis.dataset_id != null)
          .map((axis) => axis.dataset_id as number),
      ),
    );
    const pool = [...catalog, ...own].filter((item) => ids.has(item.id));
    return [
      ...pool.filter((item) => item.source_kind !== "user").sort(byName),
      ...pool.filter((item) => item.source_kind === "user").sort(byName),
    ];
  }
  const roleId = category.role_id;
  return [
    ...catalog.filter((item) => roleId != null && item.role_ids.includes(roleId)).sort(byName),
    ...own.filter((item) => roleId != null && item.role_ids.includes(roleId)).sort(byName),
  ];
}

export function defaultPayload(chain: Chain, catalog: Dataset[] = [], own: Dataset[] = []): CalculatePayload {
  const selections: Record<string, number> = {};
  chain.nodes.forEach((node) => {
    if (node.dataset_id) selections[String(node.id)] = node.dataset_id;
    if (node.type !== "category") return;
    const first = datasetsForCategory(chain, node, catalog, own)[0];
    if (first) selections[String(node.id)] = first.id;
  });
  return {
    chain_id: chain.id,
    end_amount: 1,
    selections,
    shares: {},
    optional_on: [],
    replaced_nodes: {},
  };
}

export function payloadFromConfiguration(
  chain: Chain,
  config: Configuration,
  catalog: Dataset[],
  own: Dataset[],
): { payload: CalculatePayload; missing: string[] } {
  const payload = defaultPayload(chain, catalog, own);
  const missing: string[] = [];
  const selections = { ...payload.selections };
  for (const node of chain.nodes) {
    if (node.type !== "category") continue;
    const saved = config.selections[String(node.id)];
    const options = datasetsForCategory(chain, node, catalog, own);
    if (saved != null && options.some((item) => item.id === saved)) selections[String(node.id)] = saved;
    else if (saved != null) missing.push(node.name);
  }
  for (const [nodeId, datasetId] of Object.entries(config.selections)) {
    const node = chain.nodes.find((item) => String(item.id) === nodeId);
    if (node && node.type !== "category") selections[nodeId] = datasetId;
  }
  return {
    payload: {
      ...payload,
      end_amount: config.end_amount,
      selections,
      shares: config.shares,
      optional_on: config.optional_on,
      replaced_nodes: config.replaced_nodes,
    },
    missing,
  };
}
