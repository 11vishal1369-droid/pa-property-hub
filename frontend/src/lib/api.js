import axios from "axios";

export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

api.interceptors.request.use((c) => {
  const t = localStorage.getItem("pa_token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && !e.config.url.includes("/auth/login")) {
      localStorage.removeItem("pa_token");
      const login = "/admin/login";
      if (window.location.pathname !== login) window.location.href = login;
    }
    return Promise.reject(e);
  }
);

export function formatDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export async function errMsg(e) {
  const d = e.response?.data;
  if (d instanceof Blob) {
    try { return formatDetail(JSON.parse(await d.text()).detail); } catch { return e.message; }
  }
  return d?.detail ? formatDetail(d.detail) : e.message;
}

async function getBlob(path, params) {
  const r = await api.get(path, { params, responseType: "blob" });
  const cd = r.headers["content-disposition"] || "";
  const name = (cd.match(/filename="?([^"]+)"?/) || [])[1] || "download";
  return { blob: r.data, name };
}

export async function download(path, params) {
  const { blob, name } = await getBlob(path, params);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function openPdf(path, params) {
  const { blob } = await getBlob(path, params);
  window.open(URL.createObjectURL(new Blob([blob], { type: "application/pdf" })), "_blank");
}

export const inr = (v) => (v == null ? "—" : `₹${Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
export const fmtDate = (v) => (v ? new Date(v.length <= 10 ? v + "T00:00:00" : v).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const fmtDateTime = (v) => (v ? new Date(v).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
export const label = (s) => (s ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "—");
export const dispId = (r) => (r && (r.code || r.id)) || "—";
export const roomLabel = (room) => (!room ? "—" : /^room\b/i.test(room) ? room : `Room ${room}`);
