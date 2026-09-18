import { fmtQty, inr } from "../api";

export default function Receipt({ quote, title }) {
  return (
    <div className="receipt">
      <h3>{title || (quote.pooled ? `Pooled lot · ${quote.sellers} sellers` : "Your order")}</h3>
      {quote.items.map((i) => (
        <div className="r-row" key={i.listing_id}>
          <span className="row" style={{ gap: 8 }}>
            {i.color_hex && <span className="swatch" style={{ background: i.color_hex, width: 16, height: 16 }} />}
            {fmtQty(i.quantity)} × {inr(i.unit_price)} <span className="tiny muted">· {i.distance_km} km</span>
          </span>
          <span>{inr(i.line_total)}</span>
        </div>
      ))}
      <div className="r-row"><span>Subtotal</span><span>{inr(quote.subtotal)}</span></div>
      <div className="r-row"><span>{quote.sellers > 1 ? "One combined pickup" : "Pickup"}</span><span>{inr(quote.pickup_fee)}</span></div>
      <div className="r-row"><span>Platform fee</span><span>{inr(quote.platform_fee)}</span></div>
      <div className="r-row total"><span>You pay</span><span>{inr(quote.total)}</span></div>
      {quote.new_price_total && (
        <div className="r-row" style={{ borderBottom: 0 }}><span className="muted">Same thing, new</span><s className="muted">{inr(quote.new_price_total)}</s></div>
      )}
      {quote.savings_pct > 0 && <span className="save-badge">You save {Math.round(quote.savings_pct)}%</span>}
    </div>
  );
}
