import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText, fmtQty, inr, parseUtc } from "../api";
import { useToast } from "../app-state";
import { ErrorBox, Spinner, useAsync } from "../components/ui";
import TrackMap from "../components/TrackMap";

const time = (s) => parseUtc(s)?.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const STAGE_LABEL = { reserved: "Reserved", confirmed: "Confirmed", out_for_pickup: "Out for pickup", delivered: "Delivered", cancelled: "Cancelled", expired: "Expired" };

export default function Track() {
  const { id } = useParams();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const t = useAsync(() => api.tracking(id), [id]);
  const d = t.data;

  const act = async (fn, message) => {
    setBusy(true);
    try { await fn(); toast(message); t.reload(); }
    catch (e) { toast(errorText(e), "bad"); } finally { setBusy(false); }
  };

  if (t.loading && !d) return <div className="container section"><div className="skeleton" style={{ height: 420 }} /></div>;
  if (t.error) return <div className="container section"><ErrorBox error={errorText(t.error)} onRetry={t.reload} /></div>;

  const live = ["confirmed", "out_for_pickup"].includes(d.status);
  return (
    <div className="container">
      <div className="page-head">
        <div>
          <p className="eyebrow">Order #{d.pool_id} · tracking</p>
          <h1>{fmtQty(d.quantity)} {d.unit} from {d.total_stops} seller{d.total_stops === 1 ? "" : "s"}</h1>
          <div className="row" style={{ marginTop: 10 }}>
            <span className={`chip ${d.status === "delivered" ? "chip-ok" : live ? "chip-warn" : "chip-neutral"}`}>{STAGE_LABEL[d.stage] || d.stage}</span>
            <span className="small muted">{d.route_km} km route{d.eta_minutes != null ? ` · about ${d.eta_minutes} min left` : ""}</span>
          </div>
        </div>
        <div className="row"><Link to="/dashboard" className="btn btn-sm">My orders</Link></div>
      </div>

      <div className="grid split">
        <div className="stack" style={{ gap: 16 }}>
          <div className="card card-pad stack">
            <div className="row between">
              <b>{d.collected} of {d.total_stops} lots collected</b>
              <span className="small muted num">{d.progress_pct}%</span>
            </div>
            <div className="progress"><div style={{ width: `${d.progress_pct}%` }} /></div>
          </div>

          <div className="card">
            {d.stops.map((s) => (
              <div key={s.listing_id} className="dash-row" style={{ gridTemplateColumns: "34px minmax(0,1fr) auto" }}>
                <span className="stop-no" style={{ background: s.collected ? "var(--ok-soft)" : "var(--pink-soft)" }}>{s.collected ? "✓" : s.stop_no}</span>
                <div className="dash-main">
                  <Link to={`/listing/${s.listing_id}`} className="dash-title">{s.seller}</Link>
                  <div className="small muted">{fmtQty(s.quantity)} {s.unit} · {s.distance_km} km · {inr(s.line_total)}
                    {s.collected ? ` · picked up ${time(s.picked_up_at)}` : ""}</div>
                </div>
                <div className="dash-actions">
                  {s.color_hex && <span className="swatch" style={{ background: s.color_hex }} title="Measured colour" />}
                  {live && !s.collected && (
                    <button className="btn btn-sm" disabled={busy}
                      onClick={() => act(() => api.collectStop(d.pool_id, s.listing_id), `Stop ${s.stop_no} collected.`)}>
                      Mark collected
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="card card-pad">
            <p className="eyebrow" style={{ marginBottom: 10 }}>Timeline</p>
            <ol className="timeline">
              {d.timeline.map((step) => (
                <li key={step.key} className={step.done ? "done" : ""}>
                  <b>{step.label}</b>
                  <span className="small muted">{step.at ? time(step.at) : "Pending"}</span>
                </li>
              ))}
            </ol>
          </div>

          {live && (
            <button className="btn btn-primary" disabled={busy}
              onClick={() => act(() => api.deliverPool(d.pool_id), "Delivered. Enjoy the tiles!")}>
              {busy ? <Spinner /> : "Mark the whole order delivered"}
            </button>
          )}
          {d.status === "delivered" && <div className="alert alert-ok">Delivered {time(d.timeline.at(-1).at)}. Thanks for keeping {fmtQty(d.quantity)} {d.unit} out of a landfill.</div>}
        </div>

        <div className="stack" style={{ gap: 12 }}>
          <TrackMap tracking={d} height={460} />
          <div className="row small muted" style={{ gap: 14 }}>
            <span className="row" style={{ gap: 6 }}><span className="legend" style={{ background: "#F29AC2" }} />Waiting</span>
            <span className="row" style={{ gap: 6 }}><span className="legend" style={{ background: "#23875C" }} />Collected</span>
            <span className="row" style={{ gap: 6 }}><span className="legend" style={{ background: "#8EA3F4" }} />You</span>
            <span>One van, {d.route_km} km, {d.total_stops} stops.</span>
          </div>
          <div className="receipt">
            <div className="r-row"><span>Lots</span><span>{inr(d.money.subtotal)}</span></div>
            <div className="r-row"><span>One combined pickup</span><span>{inr(d.money.pickup_fee)}</span></div>
            <div className="r-row"><span>Platform fee</span><span>{inr(d.money.platform_fee)}</span></div>
            <div className="r-row total"><span>Paid</span><span>{inr(d.money.total)}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
