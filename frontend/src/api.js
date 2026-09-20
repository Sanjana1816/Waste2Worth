const RAW_API = (import.meta.env.VITE_API_URL || "http://localhost:8000").trim().replace(/\/+$/, "");
// Accept "my-api.up.railway.app" as well as "https://my-api.up.railway.app".
export const API_BASE = /^https?:\/\//i.test(RAW_API) ? RAW_API
  : `${/^(localhost|127\.0\.0\.1)(:|$)/.test(RAW_API) ? "http" : "https"}://${RAW_API}`;

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : detail?.message || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }

  /** {field: message} from our validation errors or FastAPI's pydantic errors. */
  get fields() {
    const d = Array.isArray(this.detail) ? this.detail : [];
    const out = {};
    for (const e of d) {
      if (e.field) out[e.field] = e.message;
      else if (e.loc) out[e.loc.filter((p) => p !== "body").join(".")] = e.msg;
    }
    return out;
  }
}

export function errorText(err) {
  if (!(err instanceof ApiError)) return err?.message || "Something went wrong. Check your connection and try again.";
  if (err.status === 0) return err.message;
  const fields = err.fields;
  const n = Object.keys(fields).length;
  if (n) return n === 1 ? Object.values(fields)[0] : `${n} fields need attention.`;
  return err.message;
}

async function request(path, { method = "GET", body, form, raw } = {}) {
  const opts = { method, headers: {} };
  if (form) opts.body = form;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(API_BASE + path, opts);
  } catch {
    throw new ApiError(0, `Can't reach the server at ${API_BASE}. Is the backend running?`);
  }
  const type = res.headers.get("content-type") || "";
  const data = raw && res.ok ? await res.blob() : type.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data);
  if (!raw && !type.includes("json")) {
    // e.g. the frontend host answered with its own index.html because the API URL is wrong
    throw new ApiError(0, `The server at ${API_BASE} didn't return data. Check VITE_API_URL points to the backend.`);
  }
  return data;
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  categories: () => request("/api/categories"),
  category: (key) => request(`/api/categories/${key}`),
  listings: (params) => request(`/api/listings${qs(params)}`),
  listing: (id) => request(`/api/listings/${id}`),
  createListing: (body) => request("/api/listings", { method: "POST", body }),
  updateListing: (id, body) => request(`/api/listings/${id}`, { method: "PATCH", body }),
  uploadImage: (id, shot, file) => {
    const f = new FormData();
    f.append("shot_type", shot);
    f.append("file", file);
    return request(`/api/listings/${id}/images`, { method: "POST", form: f });
  },
  readiness: (id) => request(`/api/listings/${id}/readiness`),
  publish: (id) => request(`/api/listings/${id}/publish`, { method: "POST" }),
  matches: (id) => request(`/api/listings/${id}/matches`),
  quote: (body) => request("/api/pools/quote", { method: "POST", body }),
  reserve: (body) => request("/api/pools", { method: "POST", body }),
  confirmPool: (id) => request(`/api/pools/${id}/confirm`, { method: "POST" }),
  cancelPool: (id) => request(`/api/pools/${id}/cancel`, { method: "POST" }),
  analyze: (files, hint, manufacturerColor) => {
    const f = new FormData();
    files.forEach((file) => f.append("files", file));
    if (hint) f.append("hint_category", hint);
    if (manufacturerColor) f.append("manufacturer_color", manufacturerColor);
    return request("/api/ai/analyze", { method: "POST", form: f });
  },
  speak: (text) => request("/api/ai/speak", { method: "POST", body: { text }, raw: true }),
  textDraft: (text) => request("/api/food/text-draft", { method: "POST", body: { text } }),
  voiceDraft: (sellerId, blob) => {
    const f = new FormData();
    f.append("seller_id", sellerId);
    f.append("audio", blob, "clip.webm");
    return request("/api/food/voice-draft", { method: "POST", form: f });
  },
  claim: (id, orgId, quantity) => request(`/api/listings/${id}/claim`, { method: "POST", body: { org_id: orgId, quantity } }),
  dispatchLog: (id) => request(`/api/listings/${id}/dispatch`),
  redispatch: (id) => request(`/api/listings/${id}/dispatch`, { method: "POST" }),
  impact: () => request("/api/impact/summary"),
  certificate: (orgId) => request(`/api/impact/orgs/${orgId}/certificate`),
  orgs: () => request("/api/orgs"),
  createOrg: (body) => request("/api/orgs", { method: "POST", body }),
  dashboard: (orgId) => request(`/api/orgs/${orgId}/dashboard`),
  withdraw: (id) => request(`/api/listings/${id}/withdraw`, { method: "POST" }),
  tracking: (poolId) => request(`/api/pools/${poolId}/tracking`),
  collectStop: (poolId, listingId) => request(`/api/pools/${poolId}/stops/${listingId}/collected`, { method: "POST" }),
  deliverPool: (poolId) => request(`/api/pools/${poolId}/delivered`, { method: "POST" }),
  inspectImage: (listingId, imageId) => request(`/api/listings/${listingId}/images/${imageId}/inspect`, { method: "POST" }),
  integrations: () => request("/api/integrations/status"),
};

export const imgUrl = (u) => (!u ? null : u.startsWith("http") ? u : API_BASE + u);

export const inr = (n, digits = 0) =>
  n === null || n === undefined ? "–" : "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: digits });

export const fmtQty = (n) => Number(n).toLocaleString("en-IN", { maximumFractionDigits: 1 });

export const pretty = (s) => (s ? String(s).replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "");

/** Server datetimes are naive UTC. */
export const parseUtc = (s) => (s ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + "Z") : null);
