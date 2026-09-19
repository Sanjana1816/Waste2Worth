import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import "./styles.css";
import { PersonaProvider, ROLE_LABEL, ToastProvider, usePersona } from "./app-state";
import Home from "./pages/Home";
import Explore from "./pages/Explore";
import ListingDetail from "./pages/ListingDetail";
import Sell from "./pages/Sell";
import Pool from "./pages/Pool";
import Food from "./pages/Food";
import Impact from "./pages/Impact";
import Join from "./pages/Join";
import Dashboard from "./pages/Dashboard";

function PersonaPicker() {
  const { orgs, persona, choose, status } = usePersona();
  const nav = useNavigate();
  if (status === "loading" && !orgs.length) return <span className="chip chip-neutral">Connecting…</span>;
  if (status === "error" && !orgs.length) return <span className="chip chip-bad" title="Retrying automatically">Server unreachable · retrying</span>;
  if (!orgs.length) return null;
  const groups = Object.keys(ROLE_LABEL).map((role) => [role, orgs.filter((o) => o.role === role)]).filter(([, xs]) => xs.length);
  return (
    <label className="persona" title="Demo accounts: switch to see the platform as a seller, buyer, NGO or recycler">
      <span>Acting as</span>
      <select className="select" style={{ padding: "7px 10px", fontSize: 14 }} value={persona?.id || ""}
        onChange={(e) => (e.target.value === "new" ? nav("/join") : choose(Number(e.target.value)))}>
        {groups.map(([role, xs]) => (
          <optgroup key={role} label={ROLE_LABEL[role]}>
            {xs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </optgroup>
        ))}
        <option value="new">+ Create a new account…</option>
      </select>
    </label>
  );
}

function Nav() {
  return (
    <header className="nav">
      <div className="container nav-inner">
        <Link to="/" className="logo" aria-label="Waste2Worth home">
          <span className="logo-mark">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#17171C" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4L19 7" /></svg>
          </span>
          waste2worth
        </Link>
        <nav className="nav-links" aria-label="Main">
          <NavLink to="/explore">Explore</NavLink>
          <NavLink to="/sell">List waste</NavLink>
          <NavLink to="/pool">Pooled lots</NavLink>
          <NavLink to="/food">Food rescue</NavLink>
          <NavLink to="/impact">Impact</NavLink>
          <NavLink to="/dashboard">My dashboard</NavLink>
        </nav>
        <div className="nav-right"><PersonaPicker /><Link to="/join" className="btn btn-sm">Join</Link></div>
      </div>
    </header>
  );
}

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

function NotFound() {
  return (
    <div className="container section" style={{ textAlign: "center" }}>
      <h1 style={{ fontSize: 56 }}>Lost in the landfill.</h1>
      <p className="muted" style={{ marginTop: 12 }}>That page doesn't exist.</p>
      <Link to="/" className="btn btn-primary" style={{ marginTop: 24 }}>Back home</Link>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ScrollTop />
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/explore" element={<Explore />} />
          <Route path="/listing/:id" element={<ListingDetail />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="/sell/:id" element={<Sell />} />
          <Route path="/pool" element={<Pool />} />
          <Route path="/food" element={<Food />} />
          <Route path="/impact" element={<Impact />} />
          <Route path="/join" element={<Join />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="footer">
        <div className="container">
          <span>waste2worth · reuse, recycle, resell, donate</span>
        </div>
      </footer>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ToastProvider>
      <PersonaProvider>
        <App />
      </PersonaProvider>
    </ToastProvider>
  </StrictMode>,
);
