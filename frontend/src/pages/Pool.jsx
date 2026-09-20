import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorText, fmtQty, inr, parseUtc } from "../api";
import { usePersona, useToast } from "../app-state";
import Receipt from "../components/Receipt";
import { Field, NeedAccount, Spinner } from "../components/ui";

const MATCH_FIELDS = {
  brand: ["Brand", "Terrano Tiles"], model_sku: ["Design code / SKU", "TR-6060-MW"],
  manufacturer_color: ["Manufacturer's colour name", "Arctic Matte White"], size_mm: ["Size (mm)", "600x600"], finish: ["Finish", "matte"],
};

function PoolDiagram({ quote }) {
  return (
    <div className="pool-diagram" style={{ margin: "8px 0 4px" }}>
      <div className="pool-sellers">
        {quote.items.map((i) => (
          <Link to={`/listing/${i.listing_id}`} className="pool-seller" key={i.listing_id} style={{ textDecoration: "none" }}>
            {i.color_hex && <span className="swatch" style={{ background: i.color_hex }} />}
            <div style={{ minWidth: 0 }}><b>{fmtQty(i.quantity)} × {inr(i.unit_price)}</b>
              <div className="tiny muted">{i.distance_km} km{i.delta_e != null ? ` · ΔE ${i.delta_e}` : ""}</div></div>
          </Link>
        ))}
        {quote.excluded.slice(0, 3).map((x) => (
          <div className="pool-seller excluded" key={x.listing_id} title={x.reason}>
            <span className="chip chip-bad">✕</span><div className="tiny">#{x.listing_id}: {x.reason}</div>
          </div>
        ))}
      </div>
      <div className="connector" />
      <div className="pool-hub"><div><b>{fmtQty(quote.allocated)}</b><span>{quote.unit}{quote.shade_match_pct != null ? ` · ${Math.round(quote.shade_match_pct)}% shade match` : ""}</span></div></div>
      <div className="connector" />
      <div className="pool-buyer"><b style={{ fontFamily: "var(--display)", fontSize: 20 }}>You</b><div className="tiny">{quote.sellers} {quote.sellers === 1 ? "seller" : "sellers"} · 1 pickup</div></div>
    </div>
  );
}

function ReservationTimer({ until }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const ms = Math.max(0, parseUtc(until) - now);
  return <span className="chip chip-warn num">Held for {Math.floor(ms / 60000)}:{String(Math.floor((ms % 60000) / 1000)).padStart(2, "0")}</span>;
}

export default function Pool() {
  const [params] = useSearchParams();
  const { persona, status } = usePersona();
  const toast = useToast();
  const listingId = params.get("listing");
  const [mode, setMode] = useState(listingId ? "listing" : "need");
  const [ref, setRef] = useState(null);
  const [match, setMatch] = useState({ brand: "Terrano Tiles", model_sku: "TR-6060-MW", manufacturer_color: "Arctic Matte White", size_mm: "600x600", finish: "matte" });
  const [qty, setQty] = useState(200);
  const [radius, setRadius] = useState(15);
  const [quote, setQuote] = useState(null);
  const [pool, setPool] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => { if (listingId) api.listing(listingId).then(setRef).catch(() => setMode("need")); }, [listingId]);

  const body = () => (mode === "listing" && ref
    ? { buyer_id: persona.id, listing_id: ref.id, quantity: Number(qty), radius_km: Number(radius) }
    : { buyer_id: persona.id, category: "tiles", match, unit: "pieces", quantity: Number(qty), radius_km: Number(radius) });

  const run = async (fn) => { setBusy(true); setErr(null); try { await fn(); } catch (e) { setErr(errorText(e)); } finally { setBusy(false); } };
  const getQuote = () => run(async () => { setPool(null); setQuote(await api.quote(body())); });
  const reserve = () => run(async () => setPool(await api.reserve(body())));
  const confirm = () => run(async () => { setPool(await api.confirmPool(pool.id)); toast("Pooled order confirmed. One truck, one delivery."); });
  const cancel = () => run(async () => { setPool(await api.cancelPool(pool.id)); setQuote(null); });

  return (
    <div className="container">
      <div className="page-head">
        <div><p className="eyebrow">Pooled lots</p><h1>Small leftovers, one big order.</h1>
          <p>We combine identical stock from nearby sellers and check the shade from white-sheet photos, so you get one consistent batch for less than new.</p></div>
      </div>

      <div className="grid split">
        <div className="card card-pad stack" style={{ gap: 16 }}>
          <div className="toggle" role="group" aria-label="How to find stock">
            <button aria-pressed={mode === "need"} onClick={() => { setMode("need"); setQuote(null); }}>I need…</button>
            <button aria-pressed={mode === "listing"} onClick={() => { setMode("listing"); setQuote(null); }} disabled={!ref}>More of a listing</button>
          </div>
          {mode === "listing" && ref ? (
            <div className="card-soft"><div className="tiny muted">Matching</div><b>{ref.title}</b>
              <div className="small muted">{ref.brand} · {ref.model_sku} · {ref.manufacturer_color}</div></div>
          ) : (
            <div className="form-grid">
              {Object.entries(MATCH_FIELDS).map(([k, [label, ph]]) => (
                <Field key={k} label={label} required><input className="input" value={match[k]} placeholder={ph} onChange={(e) => setMatch((m) => ({ ...m, [k]: e.target.value }))} /></Field>
              ))}
            </div>
          )}
          <div className="form-grid">
            <Field label={`Quantity (${mode === "listing" && ref ? ref.unit : "pieces"})`} required><input className="input" type="number" min="1" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
            <Field label="Within (km)"><input className="input" type="number" min="1" max="50" value={radius} onChange={(e) => setRadius(e.target.value)} /></Field>
          </div>
          {!persona && <NeedAccount status={status}>Choose an account to buy as.</NeedAccount>}
          {persona && !["buyer", "business", "individual"].includes(persona.role) && <div className="alert alert-warn small">You're acting as a {persona.role}. Buyers usually do this, but you can still try it.</div>}
          <button className="btn btn-primary" onClick={getQuote} disabled={busy || !persona || !(qty > 0)}>{busy && !quote ? <Spinner /> : "Find matching stock"}</button>
          {err && <div className="alert alert-bad">{err}</div>}
        </div>

        <div className="stack" style={{ gap: 16 }}>
          {!quote && <div className="empty"><p style={{ fontWeight: 700, color: "var(--ink)" }}>Your pooled lot will appear here</p><p className="small">Try 200 pieces with the example details. Three sellers will match, and a different batch gets filtered out.</p></div>}
          {quote && quote.status !== "ok" && (
            <div className="alert alert-warn">
              {quote.message}
              {quote.excluded?.length > 0 && <ul>{quote.excluded.map((x) => <li key={x.listing_id}>Listing #{x.listing_id}: {x.reason}</li>)}</ul>}
            </div>
          )}
          {quote?.status === "ok" && (
            <>
              <div className="card card-pad"><PoolDiagram quote={quote} /></div>
              <Receipt quote={quote} />
              {!pool && <button className="btn btn-pink" onClick={reserve} disabled={busy}>Reserve all {quote.sellers} lots</button>}
              {pool?.status === "reserved" && (
                <div className="row"><ReservationTimer until={pool.reserved_until} />
                  <button className="btn btn-primary" onClick={confirm} disabled={busy}>Confirm · {inr(pool.total)}</button>
                  <button className="btn" onClick={cancel} disabled={busy}>Release</button></div>
              )}
              {pool?.status === "confirmed" && (
                <div className="alert alert-ok row between">
                  <span>Pooled order #{pool.id} confirmed: {fmtQty(pool.quantity)} {pool.unit} for {inr(pool.total)}.</span>
                  <Link to={`/track/${pool.id}`} className="btn btn-sm btn-primary">Track pickup</Link>
                </div>
              )}
              {pool?.status === "cancelled" && <div className="alert alert-warn">Reservation released.</div>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
