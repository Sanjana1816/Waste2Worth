import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtQty, imgUrl, inr, parseUtc, pretty } from "../api";
import { useToast } from "../app-state";
import Illo, { CATEGORY_ILLO, CATEGORY_TINT } from "./Illo";

export const ROUTE_META = {
  reuse: { label: "Reuse", color: "var(--lime)", soft: "var(--lime-soft)" },
  recycle: { label: "Recycle", color: "var(--blue)", soft: "var(--blue-soft)" },
  resell: { label: "Resell", color: "var(--pink)", soft: "var(--pink-soft)" },
  donate: { label: "Donate", color: "var(--orange)", soft: "var(--orange-soft)" },
};

export function RouteChip({ route }) {
  return <span className={`chip chip-${route}`}><span className="dot" />{ROUTE_META[route]?.label || route}</span>;
}

export function Verified({ org }) {
  if (!org?.verified) return null;
  return <span className="chip chip-ok" title="Verified by Waste2Worth">✓ Verified</span>;
}

export function Spinner() {
  return <span className="spinner" aria-label="Loading" />;
}

export function Empty({ illo = "leaf", title, children }) {
  return (
    <div className="empty">
      <Illo name={illo} />
      <p style={{ fontWeight: 700, color: "var(--ink)" }}>{title}</p>
      {children && <div className="small" style={{ marginTop: 6 }}>{children}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="alert alert-bad row between">
      <span>{typeof error === "string" ? error : error.message}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function ListingImage({ listing, className = "" }) {
  const img = listing.images?.find((i) => i.shot_type === "full_lot" || i.shot_type === "front" || i.shot_type === "food")
    || listing.images?.[0];
  const [failed, setFailed] = useState(false);
  return (
    <div className={`l-img ${className}`} style={{ background: CATEGORY_TINT[listing.category] }}>
      {img && !failed && !listing.ai_summary?.demo_photos
        ? <img src={imgUrl(img.url)} alt="" loading="lazy" onError={() => setFailed(true)} />
        : <Illo name={CATEGORY_ILLO[listing.category]} className="illo" />}
    </div>
  );
}

export function priceLine(li) {
  if (li.route === "donate") return { main: "Free", sub: null };
  if (li.asking_price_per_unit == null) return { main: "Make an offer", sub: null };
  const newPrice = li.new_price_per_unit;
  return { main: `${inr(li.asking_price_per_unit)}`, per: `/${li.unit.replace(/s$/, "")}`, sub: newPrice ? inr(newPrice) : null };
}

export function ListingCard({ listing }) {
  const p = priceLine(listing);
  return (
    <Link to={`/listing/${listing.id}`} className="l-card">
      <div style={{ position: "relative" }}>
        <ListingImage listing={listing} />
        <span style={{ position: "absolute", left: 12, top: 12 }}><RouteChip route={listing.route} /></span>
        {listing.source_type === "brand_second" && <span className="chip chip-neutral" style={{ position: "absolute", right: 12, top: 12 }}>Brand second</span>}
        {listing.pickup_by && <span style={{ position: "absolute", right: 12, top: 12 }}><Countdown until={listing.pickup_by} compact /></span>}
      </div>
      <div className="l-body">
        <div className="l-title">{listing.title}</div>
        <div className="l-meta">
          <span>{fmtQty(listing.available)} {listing.unit} left</span>
          {listing.distance_km != null && <span>· {listing.distance_km} km</span>}
          <span>· {pretty(listing.condition)}</span>
        </div>
        <div className="l-meta">
          <span>{listing.seller.name}</span>{listing.seller.verified && <span style={{ color: "var(--ok)", fontWeight: 700 }}>✓</span>}
          {listing.measured_color_hex && <span className="swatch" style={{ background: listing.measured_color_hex, width: 16, height: 16 }} title="Measured colour" />}
        </div>
        <div className="l-price">
          {p.main}{p.per && <span className="tiny muted" style={{ fontFamily: "var(--body)", fontWeight: 600 }}>{p.per}</span>}
          {p.sub && <s>{p.sub}</s>}
        </div>
      </div>
    </Link>
  );
}

export function Countdown({ until, compact }) {
  const target = parseUtc(until);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!target) return null;
  const ms = target - now;
  if (ms <= 0) return <span className="chip chip-bad">Pickup window closed</span>;
  const h = Math.floor(ms / 3.6e6), m = Math.floor((ms % 3.6e6) / 6e4), s = Math.floor((ms % 6e4) / 1000);
  const text = `${h}h ${String(m).padStart(2, "0")}m${compact ? "" : ` ${String(s).padStart(2, "0")}s`}`;
  return <span className={`chip ${h < 1 ? "chip-bad" : "chip-warn"} num`}>⏱ {compact ? text : `Pickup within ${text}`}</span>;
}

/** Reads text aloud with ElevenLabs; falls back to the browser's voice if the key isn't set. */
export function SpeakButton({ text, label = "Listen" }) {
  const toast = useToast();
  const [state, setState] = useState("idle");
  const audio = useRef(null);
  const play = async () => {
    if (state === "playing") {
      audio.current?.pause();
      window.speechSynthesis?.cancel();
      setState("idle");
      return;
    }
    setState("loading");
    try {
      const blob = await api.speak(text);
      const a = new Audio(URL.createObjectURL(blob));
      audio.current = a;
      a.onended = () => setState("idle");
      await a.play();
      setState("playing");
    } catch (e) {
      if (window.speechSynthesis) {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = "en-IN";
        u.onend = () => setState("idle");
        window.speechSynthesis.speak(u);
        setState("playing");
        if (e.status === 503) toast("Using your browser's voice. Add an ElevenLabs key for the real one.");
      } else {
        setState("idle");
        toast("Voice isn't available right now.", "bad");
      }
    }
  };
  return (
    <button className="btn btn-sm" onClick={play} aria-label={`${label}: ${text.slice(0, 40)}`}>
      {state === "loading" ? <Spinner /> : state === "playing" ? <span className="eq"><i /><i /><i /><i /></span> : "▶"}
      {state === "playing" ? "Stop" : label}
    </button>
  );
}

export function Field({ label, required, hint, error, children, className = "", group = false }) {
  const Tag = group ? "div" : "label";  // button groups must not sit inside a <label>
  return (
    <Tag className={`field ${error ? "has-error" : ""} ${className}`} role={group ? "group" : undefined} aria-label={group ? label : undefined}>
      <span className="label">{label}{required && <span className="req">*</span>}</span>
      {children}
      {error ? <span className="error-text">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </Tag>
  );
}

export function useAsync(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const run = () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(run, deps);
  return { ...state, reload: run };
}
