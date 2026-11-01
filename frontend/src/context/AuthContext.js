import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";

const AuthCtx = createContext(null);
const LV = { none: 0, view: 1, edit: 2 };

export function AuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);

  const refresh = useCallback(async () => {
    if (!localStorage.getItem("pa_token")) return setAdmin(false);
    try {
      const { data } = await api.get("/auth/me");
      setAdmin(data);
    } catch {
      setAdmin(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("pa_token", data.token);
    await refresh();
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("pa_token");
    setAdmin(false);
  };

  const can = (module, level = "view") => !!admin && (LV[admin.permissions?.[module]] || 0) >= LV[level];

  return <AuthCtx.Provider value={{ admin, login, logout, can, refresh }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
