import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

/* ---------- acting-as account (demo personas; swap for real auth later) ---------- */

const PersonaCtx = createContext(null);
const KEY = "w2w.persona";

export function PersonaProvider({ children }) {
  const [orgs, setOrgs] = useState([]);
  const [id, setId] = useState(() => {
    try { return Number(localStorage.getItem(KEY)) || null; } catch { return null; }
  });
  const [error, setError] = useState(null);

  const reload = useCallback(() => api.orgs().then(setOrgs).catch((e) => setError(e)), []);
  useEffect(() => { reload(); }, [reload]);

  const choose = useCallback((next) => {
    setId(next);
    try { localStorage.setItem(KEY, String(next)); } catch { /* private mode */ }
  }, []);

  const persona = orgs.find((o) => o.id === id) || orgs.find((o) => o.role === "business") || null;
  const value = useMemo(() => ({ orgs, persona, choose, error, reload }), [orgs, persona, choose, error, reload]);
  return <PersonaCtx.Provider value={value}>{children}</PersonaCtx.Provider>;
}

export const usePersona = () => useContext(PersonaCtx);

export const ROLE_LABEL = {
  business: "Business", brand: "Brand", buyer: "Buyer", recycler: "Recycler", ngo: "NGO", individual: "Individual",
};

/* ---------- toasts ---------- */

const ToastCtx = createContext(() => {});

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, tone = "info") => {
    const t = { id: Math.random(), text, tone };
    setItems((xs) => [...xs, t]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== t.id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.tone === "bad" ? "bad" : ""}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
