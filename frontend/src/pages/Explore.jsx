import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { usePersona } from "../app-state";
import { Empty, ErrorBox, ListingCard, ROUTE_META } from "../components/ui";

export default function Explore() {
  const [params, setParams] = useSearchParams();
  const { persona } = usePersona();
  const [cats, setCats] = useState([]);
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [q, setQ] = useState(params.get("q") || "");
  const route = params.get("route") || "";
  const category = params.get("category") || "";
  const near = params.get("near") === "1";

  useEffect(() => { api.categories().then(setCats).catch(() => {}); }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      setError(null);
      api.listings({
        route, category, q: params.get("q") || "",
        ...(near && persona ? { lat: persona.lat, lng: persona.lng, radius_km: 25 } : {}),
      }).then(setItems).catch((e) => { setError(e); setItems([]); });
    }, 150);
    return () => clearTimeout(t);
  }, [params, persona, route, category, near]);

  const set = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v); else next.delete(k);
    setParams(next, { replace: true });
  };

  return (
    <div className="container">
      <div className="page-head">
        <div><p className="eyebrow">Explore</p><h1>What's up for grabs.</h1><p>Everything here has been checked: proof photos, where it came from, and why it's being passed on.</p></div>
      </div>

      <div className="card card-pad" style={{ marginBottom: 24 }}>
        <div className="row" style={{ gap: 8 }}>
          <button className="filter-chip" aria-pressed={!route} onClick={() => set("route", "")}>All</button>
          {Object.entries(ROUTE_META).map(([k, m]) => (
            <button key={k} className="filter-chip" aria-pressed={route === k} onClick={() => set("route", k)}>{m.label}</button>
          ))}
        </div>
        <div className="filters">
          <input className="input" placeholder="Search: brand, design code, colour…" value={q}
            onChange={(e) => { setQ(e.target.value); set("q", e.target.value); }} aria-label="Search listings" />
          <select className="select" value={category} onChange={(e) => set("category", e.target.value)} aria-label="Category">
            <option value="">All categories</option>
            {cats.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <button className="filter-chip" aria-pressed={near} onClick={() => set("near", near ? "" : "1")} disabled={!persona}
            title={persona ? `Within 25 km of ${persona.name}` : ""}>Near me</button>
        </div>
      </div>

      <ErrorBox error={error} />
      {items === null ? (
        <div className="grid grid-auto">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 330 }} />)}</div>
      ) : items.length === 0 ? (
        !error && <Empty title="Nothing matches yet.">Try another filter, or be the first to list something.</Empty>
      ) : (
        <div className="grid grid-auto">{items.map((li) => <ListingCard key={li.id} listing={li} />)}</div>
      )}
    </div>
  );
}
