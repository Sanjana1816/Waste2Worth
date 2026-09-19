import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText, fmtQty, inr, parseUtc, pretty } from "../api";
import { ROLE_LABEL, usePersona, useToast } from "../app-state";
import { Empty, ErrorBox, ListingImage, NeedAccount, RouteChip, Spinner, Verified, useAsync } from "../components/ui";

const STATUS_CHIP = {
  draft: ["chip-neutral", "Draft"], published: ["chip-ok", "Live"], sold_out: ["chip-resell", "Sold out"],
  claimed: ["chip-donate", "Claimed"], expired: ["chip-bad", "Expired"], withdrawn: ["chip-neutral", "Withdrawn"],
};
const ORDER_CHIP = { reserved: "chip-warn", confirmed: "chip-ok", cancelled: "chip-neutral", expired: "chip-neutral", claimed: "chip-ok", picked_up: "chip-ok" };
const FILTERS = [["all", "All"], ["draft", "Drafts"], ["published", "Live"], ["closed", "Closed"]];
const date = (s) => parseUtc(s)?.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

function ListingRow({ li, onWithdraw }) {
  const [chip, label] = STATUS_CHIP[li.status] || ["chip-neutral", pretty(li.status)];
  const r = li.readiness;
  const todo = r ? r.missing_shots.length + r.retake_shots.length + r.field_errors.length : 0;
  return (
    <div className="dash-row">
      <Link to={li.status === "draft" ? `/sell/${li.id}` : `/listing/${li.id}`} className="dash-thumb"><ListingImage listing={li} /></Link>
      <div className="dash-main">
        <div className="row" style={{ gap: 6 }}><span className={`chip ${chip}`}>{label}</span><RouteChip route={li.route} /></div>
        <Link to={li.status === "draft" ? `/sell/${li.id}` : `/listing/${li.id}`} className="dash-title">{li.title}</Link>
        <div className="small muted">
          {li.status === "draft"
            ? (todo ? `${r.image_count} of ${r.min_images} photos · ${todo} thing${todo === 1 ? "" : "s"} left to do` : "Ready to publish")
            : `${fmtQty(li.available)} of ${fmtQty(li.quantity)} ${li.unit} left · ${li.route === "donate" ? "Free" : li.asking_price_per_unit != null ? `${inr(li.asking_price_per_unit)} per ${li.unit.replace(/s$/, "")}` : "No price"}`}
        </div>
      </div>
      <div className="dash-actions">
        {li.status === "draft" && <Link to={`/sell/${li.id}`} className="btn btn-sm btn-primary">{todo ? "Continue" : "Publish"}</Link>}
        {li.status === "published" && <>
          <Link to={`/listing/${li.id}`} className="btn btn-sm">View</Link>
          <button className="btn btn-sm" onClick={() => onWithdraw(li)}>Withdraw</button>
        </>}
        {!["draft", "published"].includes(li.status) && <Link to={`/listing/${li.id}`} className="btn btn-sm">View</Link>}
      </div>
    </div>
  );
}

function Table({ rows, cols, empty }) {
  if (!rows.length) return <Empty illo="leaf" title={empty} />;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr>{cols.map(([h]) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{cols.map(([h, f]) => <td key={h}>{f(r)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export default function Dashboard() {
  const { persona, status } = usePersona();
  const toast = useToast();
  const dash = useAsync(() => (persona ? api.dashboard(persona.id) : Promise.resolve(null)), [persona?.id]);
  const [tab, setTab] = useState("listings");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);

  if (!persona) return <div className="container section"><NeedAccount status={status}>Choose an account to see its dashboard.</NeedAccount></div>;
  const d = dash.data;
  const seller = ["business", "brand", "individual"].includes(persona.role);
  const tabs = [
    ...(seller ? [["listings", "My listings", d?.listings.length], ["sales", "Orders received", d?.sales.length],
      ["claims_received", "Donations claimed", d?.claims_received.length]] : []),
    ["purchases", "My purchases", d?.purchases.length],
    ...(persona.role === "ngo" ? [["claims_made", "My claims", d?.claims_made.length]] : []),
  ];
  const current = tabs.find((t) => t[0] === tab) ? tab : tabs[0][0];

  const withdraw = async (li) => {
    if (!window.confirm(`Withdraw "${li.title}"? It will disappear from Explore.`)) return;
    setBusy(true);
    try { await api.withdraw(li.id); toast("Listing withdrawn."); dash.reload(); }
    catch (e) { toast(errorText(e), "bad"); } finally { setBusy(false); }
  };

  const listings = (d?.listings || []).filter((li) => filter === "all" || (filter === "closed"
    ? !["draft", "published"].includes(li.status) : li.status === filter));

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <p className="eyebrow">My dashboard · {ROLE_LABEL[persona.role]}</p>
          <h1>{persona.name}</h1>
          <div className="row" style={{ marginTop: 10 }}>
            {persona.verified ? <Verified org={persona} /> : <span className="chip chip-warn">Not verified yet</span>}
            {persona.badges?.map((b) => <span key={b} className="chip chip-neutral">{b}</span>)}
          </div>
        </div>
        <div className="row">
          {seller && <Link to="/sell" className="btn btn-primary">+ New listing</Link>}
          {seller && persona.role !== "brand" && <Link to="/food" className="btn btn-orange">Post surplus food</Link>}
          {!seller && <Link to="/explore" className="btn btn-primary">Browse listings</Link>}
        </div>
      </div>

      <ErrorBox error={dash.error && errorText(dash.error)} onRetry={dash.reload} />

      {d && seller && (
        <div className="stats" style={{ marginBottom: 28 }}>
          {[["var(--lime)", d.totals.live, "live listings"], ["var(--sun)", d.totals.drafts, "drafts to finish"],
            ["var(--pink)", inr(d.totals.earned_inr), `earned from ${d.totals.orders} order${d.totals.orders === 1 ? "" : "s"}`],
            ["var(--mint)", `${fmtQty(d.totals.co2e_avoided_kg)} kg`, "CO₂e avoided (est.)"]].map(([c, n, u]) => (
            <div className="stat" key={u}><div className="bar" style={{ background: c }} /><div className="n">{n}</div><div className="u">{u}</div></div>
          ))}
        </div>
      )}

      <div className="row" style={{ gap: 8, marginBottom: 18 }} role="tablist">
        {tabs.map(([k, label, n]) => (
          <button key={k} role="tab" aria-selected={current === k} className="filter-chip" aria-pressed={current === k} onClick={() => setTab(k)}>
            {label}{n ? ` · ${n}` : ""}
          </button>
        ))}
        {busy && <Spinner />}
      </div>

      {!d ? <div className="skeleton" style={{ height: 260 }} /> : (
        <>
          {current === "listings" && (
            <div className="stack">
              <div className="row" style={{ gap: 6 }}>
                {FILTERS.map(([k, l]) => <button key={k} className="btn btn-sm" aria-pressed={filter === k}
                  style={filter === k ? { background: "var(--ink)", color: "var(--bg)", borderColor: "var(--ink)" } : undefined} onClick={() => setFilter(k)}>{l}</button>)}
              </div>
              {listings.length === 0
                ? <Empty illo="tiles" title={d.listings.length ? "Nothing in this filter." : "You haven't listed anything yet."}>
                    {!d.listings.length && <Link to="/sell" className="btn btn-primary" style={{ marginTop: 12 }}>List your first item</Link>}
                  </Empty>
                : <div className="card">{listings.map((li) => <ListingRow key={li.id} li={li} onWithdraw={withdraw} />)}</div>}
            </div>
          )}
          {current === "sales" && <Table rows={d.sales} empty="No orders yet. They'll show up here when buyers reserve your stock." cols={[
            ["Listing", (r) => <Link to={`/listing/${r.listing_id}`} className="linkish">{r.title}</Link>],
            ["Buyer", (r) => r.buyer], ["Quantity", (r) => `${fmtQty(r.quantity)} ${r.unit}`],
            ["Amount", (r) => inr(r.amount)], ["Type", (r) => (r.pooled ? "Pooled lot" : "Direct")],
            ["Status", (r) => <span className={`chip ${ORDER_CHIP[r.status]}`}>{pretty(r.status)}</span>], ["When", (r) => date(r.created_at)]]} />}
          {current === "claims_received" && <Table rows={d.claims_received} empty="No NGO claims yet." cols={[
            ["Donation", (r) => <Link to={`/listing/${r.listing_id}`} className="linkish">{r.title}</Link>],
            ["Claimed by", (r) => r.ngo], ["Quantity", (r) => `${fmtQty(r.quantity)} ${r.unit}`],
            ["Status", (r) => <span className={`chip ${ORDER_CHIP[r.status]}`}>{pretty(r.status)}</span>], ["When", (r) => date(r.created_at)]]} />}
          {current === "purchases" && <Table rows={d.purchases} empty="You haven't bought anything yet." cols={[
            ["Order", (r) => `#${r.pool_id} · ${r.title}${r.sellers > 1 ? ` + ${r.sellers - 1} more` : ""}`],
            ["Quantity", (r) => `${fmtQty(r.quantity)} ${r.unit}`], ["Total", (r) => inr(r.total)],
            ["Status", (r) => <span className={`chip ${ORDER_CHIP[r.status]}`}>{pretty(r.status)}</span>], ["When", (r) => date(r.created_at)]]} />}
          {current === "claims_made" && <Table rows={d.claims_made} empty="You haven't claimed anything yet." cols={[
            ["Donation", (r) => <Link to={`/listing/${r.listing_id}`} className="linkish">{r.title}</Link>],
            ["From", (r) => r.donor], ["Quantity", (r) => `${fmtQty(r.quantity)} ${r.unit}`],
            ["Pick up before", (r) => (r.pickup_by ? date(r.pickup_by) : "–")],
            ["Status", (r) => <span className={`chip ${ORDER_CHIP[r.status]}`}>{pretty(r.status)}</span>]]} />}
        </>
      )}
    </div>
  );
}
