import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText, fmtQty, imgUrl, inr, pretty } from "../api";
import { usePersona, useToast } from "../app-state";
import Illo, { CATEGORY_ILLO, CATEGORY_TINT } from "../components/Illo";
import { Countdown, ErrorBox, RouteChip, SpeakButton, Spinner, Verified, useAsync } from "../components/ui";
import Receipt from "../components/Receipt";
import DefectMap, { DefectSummary } from "../components/DefectMap";

function Gallery({ listing }) {
  const toast = useToast();
  const [i, setI] = useState(0);
  const [showDamage, setShowDamage] = useState(true);
  const [scans, setScans] = useState({});          // scans run on this page, before a reload
  const [scanning, setScanning] = useState(false);
  const imgs = listing.images || [];
  const cur = imgs[i];
  const map = cur && (scans[cur.id] || cur.defect_map);
  const damage = showDamage && map?.regions?.length ? map : null;

  const scan = async () => {
    setScanning(true);
    try {
      const result = await api.inspectImage(listing.id, cur.id);
      setScans((s) => ({ ...s, [cur.id]: result }));
      setShowDamage(true);
      if (!result.regions.length) toast(result.warnings?.[0] || "The AI found nothing wrong in this photo.");
    } catch (e) { toast(errorText(e), "bad"); } finally { setScanning(false); }
  };

  return (
    <div>
      {damage ? <DefectMap image={cur} map={damage} /> : (
      <div className="gallery-main" style={{ background: CATEGORY_TINT[listing.category] }}>
        {cur ? <img src={imgUrl(cur.url)} alt={pretty(cur.shot_type)} /> : <Illo name={CATEGORY_ILLO[listing.category]} className="illo" />}
      </div>)}
      {cur && (
        <div className="row between" style={{ marginTop: 10 }}>
          {map?.regions?.length > 0 ? (
            <>
              <span className="row" style={{ gap: 8 }}><span className="chip chip-neutral">AI damage scan</span><DefectSummary map={map} /></span>
              <span className="row" style={{ gap: 8 }}>
                <button className="btn btn-sm" onClick={() => setShowDamage((v) => !v)}>{showDamage ? "Hide marks" : "Show marks"}</button>
                <button className="btn btn-sm" onClick={scan} disabled={scanning}>{scanning ? <Spinner /> : "Rescan"}</button>
              </span>
            </>
          ) : (
            <>
              <span className="small muted">Not sure about its condition? Let the AI mark the damage on this photo.</span>
              <button className="btn btn-sm btn-dark" onClick={scan} disabled={scanning}>
                {scanning ? <><Spinner /> Scanning…</> : "Scan for damage"}
              </button>
            </>
          )}
        </div>
      )}
      {map?.summary && !damage && <p className="small" style={{ marginTop: 8 }}>{map.summary}</p>}
      {imgs.length > 1 && (
        <div className="thumbs" role="group" aria-label="Photos">
          {imgs.map((img, k) => (
            <button key={img.id} className="thumb" aria-pressed={k === i} onClick={() => setI(k)}>
              <img src={imgUrl(img.url)} alt="" /><span>{pretty(img.shot_type)}{(scans[img.id] || img.defect_map)?.regions?.length ? " · scanned" : ""}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function OrderPanel({ listing }) {
  const { persona } = usePersona();
  const toast = useToast();
  const [qty, setQty] = useState(Math.min(listing.available, listing.unit === "kg" ? 50 : 10));
  const [quote, setQuote] = useState(null);
  const [pool, setPool] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const own = persona?.id === listing.seller.id;

  const run = async (fn) => {
    setBusy(true); setErr(null);
    try { await fn(); } catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  };
  const getQuote = () => run(async () => { setPool(null); setQuote(await api.quote({ buyer_id: persona.id, listing_id: listing.id, quantity: Number(qty) })); });
  const reserve = () => run(async () => { setPool(await api.reserve({ buyer_id: persona.id, listing_id: listing.id, quantity: Number(qty) })); });
  const confirm = () => run(async () => { setPool(await api.confirmPool(pool.id)); toast("Order confirmed. The seller will arrange pickup."); });

  if (own) return <div className="alert alert-warn">This is your listing. Switch accounts to see it as a buyer.</div>;
  return (
    <div className="card card-pad stack">
      <h3 style={{ fontSize: 20 }}>{listing.route === "recycle" ? "Book this for recycling" : "Buy this lot"}</h3>
      <div className="row">
        <input className="input" type="number" min="1" max={listing.available} value={qty} style={{ maxWidth: 140 }}
          onChange={(e) => { setQty(e.target.value); setQuote(null); }} aria-label="Quantity" />
        <span className="muted">{listing.unit} of {fmtQty(listing.available)}</span>
        <button className="btn btn-dark" onClick={getQuote} disabled={busy || !persona || !(qty > 0)}>{busy && !quote ? <Spinner /> : "Get price"}</button>
      </div>
      {err && <div className="alert alert-bad">{err}</div>}
      {quote?.status === "ok" && <Receipt quote={quote} />}
      {quote && quote.status !== "ok" && <div className="alert alert-warn">{quote.message}</div>}
      {quote?.status === "ok" && !pool && <button className="btn btn-primary" onClick={reserve} disabled={busy}>Reserve for 30 min</button>}
      {pool?.status === "reserved" && (
        <div className="row"><button className="btn btn-primary" onClick={confirm} disabled={busy}>Confirm order · {inr(pool.total)}</button>
          <button className="btn" onClick={() => run(async () => { setPool(await api.cancelPool(pool.id)); setQuote(null); })}>Cancel</button></div>
      )}
      {pool?.status === "confirmed" && (
        <div className="alert alert-ok row between">
          <span>Order #{pool.id} confirmed · {inr(pool.total)}.</span>
          <Link to={`/track/${pool.id}`} className="btn btn-sm btn-primary">Track pickup</Link>
        </div>
      )}
    </div>
  );
}

function ClaimPanel({ listing, onDone }) {
  const { persona } = usePersona();
  const toast = useToast();
  const [qty, setQty] = useState(listing.available);
  const [busy, setBusy] = useState(false);
  const log = useAsync(() => api.dispatchLog(listing.id), [listing.id]);
  const canClaim = persona?.role === "ngo" && persona.verified;
  const claim = async () => {
    setBusy(true);
    try { const r = await api.claim(listing.id, persona.id, Number(qty)); toast(r.message); onDone(); }
    catch (e) { toast(errorText(e), "bad"); } finally { setBusy(false); }
  };
  return (
    <div className="card card-pad stack">
      <div className="row between"><h3 style={{ fontSize: 20 }}>Claim this donation</h3>{listing.pickup_by && <Countdown until={listing.pickup_by} />}</div>
      {canClaim ? (
        <div className="row">
          <input className="input" type="number" min="1" max={listing.available} value={qty} onChange={(e) => setQty(e.target.value)} style={{ maxWidth: 120 }} aria-label="Quantity" />
          <span className="muted">{listing.unit}</span>
          <button className="btn btn-orange" onClick={claim} disabled={busy || listing.status !== "published"}>{busy ? <Spinner /> : "Claim for free"}</button>
        </div>
      ) : (
        <div className="alert alert-warn">Only verified NGOs can claim donations. Switch to an NGO account, e.g. Full Plate Foundation, to try it.</div>
      )}
      {log.data?.length > 0 && (
        <div className="card-soft">
          <p className="eyebrow" style={{ marginBottom: 8 }}>Who we alerted</p>
          <div className="stack" style={{ gap: 8 }}>
            {log.data.map((d) => (
              <div key={d.id} className="small row" style={{ alignItems: "start", flexWrap: "nowrap" }}>
                <span className={`chip ${d.status === "sent" ? "chip-ok" : d.status === "failed" ? "chip-bad" : "chip-neutral"}`}>{d.channel === "vakh" ? "Vakh" : "Call"} · {d.status}</span>
                <span className="muted" style={{ flex: 1 }}>{d.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ListingDetail() {
  const { id } = useParams();
  const listing = useAsync(() => api.listing(id), [id]);
  const li = listing.data;
  const spec = useAsync(() => (li ? api.category(li.category) : Promise.resolve(null)), [li?.category]);
  const matches = useAsync(() => (li ? api.matches(li.id) : Promise.resolve(null)), [li?.id]);

  if (listing.loading && !li) return <div className="container section"><div className="skeleton" style={{ height: 420 }} /></div>;
  if (listing.error) return <div className="container section"><ErrorBox error={errorText(listing.error)} onRetry={listing.reload} /></div>;

  const attrs = [...(spec.data?.attributes || []), ...(spec.data?.brand_second_extras?.attributes || [])];
  const labelOf = (k) => attrs.find((a) => a.key === k)?.label || pretty(k);
  const showVal = (v) => (v === true ? "Yes" : v === false ? "No" : typeof v === "string" && /^\d{4}-\d\d-\d\dT/.test(v) ? new Date(v + "Z").toLocaleString("en-IN") : pretty(String(v)));
  const reason = spec.data?.reasons?.find((r) => r.key === li.reason_code)?.label;
  const ideas = li.route_suggestion?.reuse_ideas || [];
  const hasProvenance = ["brand", "product_name", "model_sku", "purchased_from", "purchase_year", "manufacturer_color"].some((k) => li[k]) || li.has_invoice;

  return (
    <div className="container section-tight">
      <Link to="/explore" className="linkish small">← Back to explore</Link>
      <div className="detail" style={{ marginTop: 20 }}>
        <div className="stack" style={{ gap: 20 }}>
          <Gallery listing={li} />
          <div className="why-box">
            <p className="eyebrow">Why it's here · {reason || pretty(li.reason_code)}</p>
            <p>“{li.reason_detail}”</p>
          </div>
          {ideas.length > 0 && (
            <div className="stack">
              <div className="row between"><h3 style={{ fontSize: 22 }}>Or reuse it yourself</h3><SpeakButton text={`Here are some ways to reuse ${li.title}: ${ideas.join(". ")}.`} label="Listen to all" /></div>
              {ideas.map((idea) => <div className="idea" key={idea}><span>{idea}</span><SpeakButton text={idea} /></div>)}
            </div>
          )}
        </div>

        <div className="stack" style={{ gap: 20 }}>
          <div className="row"><RouteChip route={li.route} />{li.source_type === "brand_second" && <span className="chip chip-neutral">Brand second</span>}
            <span className="chip chip-neutral">{pretty(li.condition)}</span>{li.status !== "published" && <span className="chip chip-warn">{pretty(li.status)}</span>}</div>
          <h1 style={{ fontSize: "clamp(28px, 4vw, 40px)", fontWeight: 800 }}>{li.title}</h1>
          <div className="row small muted"><span>{li.seller.name}</span><Verified org={li.seller} />{li.seller.badges?.map((b) => <span key={b} className="chip chip-neutral">{b}</span>)}</div>

          <div className="row" style={{ alignItems: "baseline", gap: 12 }}>
            <span className="price-big">{li.route === "donate" ? "Free" : li.asking_price_per_unit != null ? inr(li.asking_price_per_unit) : "–"}</span>
            {li.route !== "donate" && <span className="muted">per {li.unit.replace(/s$/, "")}</span>}
            {li.new_price_per_unit && <s className="muted">{inr(li.new_price_per_unit)} new</s>}
          </div>
          <div className="grid grid-3" style={{ gap: 10 }}>
            <div className="card-soft"><div className="tiny muted">Available</div><b className="num">{fmtQty(li.available)} {li.unit}</b></div>
            <div className="card-soft"><div className="tiny muted">Lot value (est.)</div><b className="num">{li.est_value_high ? `${inr(li.est_value_low)}–${inr(li.est_value_high)}` : li.route === "donate" ? "Donated" : "–"}</b></div>
            <div className="card-soft"><div className="tiny muted">CO₂e saved (est.)</div><b className="num">{fmtQty(li.co2_saved_kg)} kg</b></div>
          </div>

          {li.status === "published" && (li.route === "donate" ? <ClaimPanel listing={li} onDone={listing.reload} /> : ["resell", "recycle"].includes(li.route) ? <OrderPanel listing={li} /> : null)}
          {li.route === "resell" && spec.data?.poolable && li.status === "published" && (
            <Link to={`/pool?listing=${li.id}`} className="card card-pad row between" style={{ textDecoration: "none", background: "var(--pink-soft)" }}>
              <span><b>Need more than {fmtQty(li.available)}?</b><br /><span className="small muted">Combine identical stock from other sellers into one pooled lot.</span></span>
              <span className="btn btn-sm btn-pink">Pool it</span>
            </Link>
          )}

          {hasProvenance && <div>
            <h3 style={{ fontSize: 20, marginBottom: 6 }}>Where it came from</h3>
            <dl className="kv">
              {[["Brand", li.brand], ["Product", li.product_name], ["Model / design code", li.model_sku], ["Bought from", li.purchased_from],
                ["Year bought", li.purchase_year], ["Invoice available", li.has_invoice ? "Yes" : null]].filter(([, v]) => v).map(([k, v]) => (
                <div key={k} style={{ display: "contents" }}><dt>{k}</dt><dd>{v}</dd></div>
              ))}
              {li.manufacturer_color && <><dt>Manufacturer's colour</dt><dd>{li.manufacturer_color}</dd></>}
              {li.measured_color_hex && (
                <><dt>Measured colour</dt><dd><span className="swatch" style={{ background: li.measured_color_hex }} /> <span className="mono small">{li.measured_color_hex}</span> <span className="tiny muted">(lighting-corrected from the white-sheet photo)</span></dd></>
              )}
            </dl>
          </div>}
          <div>
            <h3 style={{ fontSize: 20, marginBottom: 6 }}>Details</h3>
            <dl className="kv">
              {Object.entries(li.attributes || {}).map(([k, v]) => <div key={k} style={{ display: "contents" }}><dt>{labelOf(k)}</dt><dd>{showVal(v)}</dd></div>)}
              {li.weight_kg && <><dt>Approx. weight</dt><dd>{fmtQty(li.weight_kg)} kg</dd></>}
            </dl>
          </div>
          {matches.data?.matches?.length > 0 && (
            <div>
              <h3 style={{ fontSize: 20, marginBottom: 10 }}>Who nearby can use this</h3>
              <div className="stack" style={{ gap: 8 }}>
                {matches.data.matches.slice(0, 5).map((m) => (
                  <div key={m.org_id} className="row between card-soft" style={{ padding: "10px 14px" }}>
                    <span className="row" style={{ gap: 8 }}><b>{m.name}</b>{m.verified && <span style={{ color: "var(--ok)" }}>✓</span>}{m.certified_recycler && <span className="chip chip-recycle">Certified</span>}</span>
                    <span className="small muted num">{m.distance_km} km · {pretty(m.role)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
