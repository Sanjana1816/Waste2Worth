import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtQty, inr } from "../api";
import Illo, { Arrow } from "../components/Illo";
import { ListingCard, ROUTE_META } from "../components/ui";

const WORDS = ["reuse", "recycle", "resell", "donate"];

function Rotator() {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setI((x) => (x + 1) % WORDS.length), 1900);
    return () => clearInterval(t);
  }, []);
  const w = WORDS[i];
  return (
    <div className="rotator" aria-live="polite">
      Give it a second life:
      <span className="rot-word" style={{ background: ROUTE_META[w].soft }}>{w}</span>
    </div>
  );
}

function Showcase() {
  return (
    <div className="showcase" aria-hidden="true">
      <div className="showcase-bg" />
      <div className="floaty" style={{ left: "0%", top: "6%" }}><Illo name="chair" /></div>
      <div className="floaty" style={{ right: "2%", top: "2%", animationDelay: "-1.5s" }}><Illo name="bowl" /></div>
      <div className="floaty" style={{ left: "3%", bottom: "4%", animationDelay: "-3s" }}><Illo name="hoodie" /></div>
      <div className="floaty" style={{ right: "0%", bottom: "8%", animationDelay: "-4.5s" }}><Illo name="laptop" /></div>
      <div className="scan">
        <div className="scan-shot"><Illo name="tiles" /><div className="scanline" /></div>
        <div className="scan-rows">
          <div><span className="muted">Identified</span><b>Vitrified tiles · 600×600</b></div>
          <div><span className="muted">Condition</span><b>Good</b></div>
          <div><span className="muted">Est. value</span><b>₹28k – 35k</b></div>
          <div><span className="muted">Best route</span><span className="chip chip-resell"><span className="dot" />Resell</span></div>
        </div>
      </div>
      <div className="sticker" style={{ left: "30%", top: "3%", background: "var(--pink-soft)", transform: "rotate(-6deg)" }}>500 kg saved</div>
      <div className="sticker" style={{ right: "4%", top: "46%", background: "var(--mint-soft)", transform: "rotate(5deg)" }}>4 buyers nearby</div>
    </div>
  );
}

function Stats() {
  const [s, setS] = useState(null);
  useEffect(() => { api.impact().then(setS).catch(() => setS(false)); }, []);
  if (s === false) return null;
  const items = [
    ["var(--lime)", s ? `${fmtQty(s.kg_diverted)} kg` : "–", "kept out of landfill"],
    ["var(--orange)", s ? fmtQty(s.meals_rescued) : "–", "meals rescued"],
    ["var(--mint)", s ? `${fmtQty(s.co2e_avoided_kg)} kg` : "–", "CO₂e avoided (est.)"],
    ["var(--pink)", s ? inr(s.value_recovered_inr) : "–", "recovered for sellers"],
  ];
  return (
    <div className="stats">
      {items.map(([c, n, u]) => (
        <div className="stat" key={u}><div className="bar" style={{ background: c }} /><div className="n">{n}</div><div className="u">{u}</div></div>
      ))}
    </div>
  );
}

const STEPS = [
  ["Snap", "Take a photo and enter a rough quantity. That's all you need to start."],
  ["Identify", "Vision AI works out the material, its condition and its colour."],
  ["Value", "A transparent, rule-based price range, always below the new price."],
  ["Route", "The option that wastes least: reuse, recycle, resell or donate."],
  ["Match", "Nearby buyers, certified recyclers or verified NGOs who can use it."],
];

const ROUTES = [
  ["reuse", "chair", "DIY ideas for your exact item, with the steps read aloud.", "Everyone", "Free"],
  ["recycle", "recycle", "Metal, e-waste and packaging go to certified recyclers, with one pickup.", "Recyclers", "5–10% fee"],
  ["resell", "tiles", "Second-hand stock, pooled lots and brand seconds, priced below new.", "Buyers", "5–10% fee"],
  ["donate", "bowl", "Surplus food and clothes go free to verified NGOs within hours.", "NGOs", "Always 0%"],
];

function Seconds() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.listings({ source_type: "brand_second", limit: 3 }).then(setItems).catch(() => {}); }, []);
  if (!items.length) return null;
  return (
    <section className="container section" style={{ paddingTop: 0 }}>
      <div className="sec-title">
        <div><p className="eyebrow">Brand seconds</p><h2>Flawed, not finished.</h2></div>
        <p>Big brands write off stock over a shifted print or a dented box. We sell it for less, with cosmetic flaws only and a photo of every defect.</p>
      </div>
      <div className="grid grid-3">{items.map((li) => <ListingCard key={li.id} listing={li} />)}</div>
    </section>
  );
}

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <p className="eyebrow">Reuse · Recycle · Resell · Donate</p>
            <h1 style={{ marginTop: 14 }}><span className="strike">Trash?</span><br />Nah, it's <span className="hl">inventory.</span></h1>
            <p className="hero-sub">Snap your leftover tiles, surplus biryani, misprinted hoodies or old office laptops. We work out what they're worth and who nearby can use them.</p>
            <Rotator />
            <div className="hero-cta">
              <Link to="/sell" className="btn btn-primary">List your waste <Arrow /></Link>
              <Link to="/explore" className="btn">Browse what's available</Link>
            </div>
          </div>
          <Showcase />
        </div>
      </section>

      <div className="marquee" aria-hidden="true">
        <div className="marquee-track">
          {[0, 1].map((k) => (
            <span key={k}>
              40 plates of biryani claimed in 6 min <i>✦</i> 200 tiles pooled from 3 sellers <i>✦</i> 12 laptops refurbished for a school lab <i>✦</i> 60 misprinted hoodies at 73% off <i>✦</i> 90 kg of fabric off-cuts turned into tote bags <i>✦</i>
            </span>
          ))}
        </div>
      </div>

      <section className="container section-tight"><Stats /></section>

      <section className="container section">
        <div className="sec-title">
          <div><p className="eyebrow">How it works</p><h2>One photo in. A second life out.</h2></div>
          <p>The AI identifies the item; clear, visible rules set the price. Every listing shows why it's being given away, where it came from and photos that prove its condition.</p>
        </div>
        <div className="steps">
          {STEPS.map(([t, d], i) => (
            <div className="step" key={t}><div className="step-n">0{i + 1}</div><h3>{t}</h3><p>{d}</p></div>
          ))}
        </div>
      </section>

      <section className="container section" style={{ paddingTop: 0 }}>
        <div className="sec-title">
          <div><p className="eyebrow">Four routes, one app</p><h2>Not another resale app.</h2></div>
          <p>Resale apps only resell. We send every item down the route that wastes least, and never charge on donations.</p>
        </div>
        <div className="grid grid-4">
          {ROUTES.map(([r, illo, text, who, fee]) => (
            <div className="route-card" key={r}>
              <div className="ico" style={{ background: ROUTE_META[r].soft }}><Illo name={illo} /></div>
              <h3>{ROUTE_META[r].label}</h3>
              <p>{text}</p>
              <div className="foot"><span>{who}</span><span>{fee}</span></div>
            </div>
          ))}
        </div>
      </section>

      <section className="container section" style={{ paddingTop: 0 }}>
        <div className="band band-pink band-grid">
          <div>
            <p className="eyebrow">Pooled lots</p>
            <h2>Small leftovers, one big order.</h2>
            <p>No single seller has 200 tiles, but three together do. We match identical stock by brand, design code and the manufacturer's colour name. We also check each lot's true colour from a photo on white paper, so a different batch never slips in.</p>
            <ul className="checklist">
              <li>One order, one pickup, and all-or-nothing checkout</li>
              <li>Shade check that cancels out lighting differences</li>
              <li>Always cheaper than buying new, or we don't create the pool</li>
            </ul>
            <Link to="/pool" className="btn btn-pink" style={{ marginTop: 22 }}>Build a pooled lot <Arrow /></Link>
          </div>
          <div className="pool-diagram" aria-label="Three sellers pooled into one order">
            <div className="pool-sellers">
              {[["Seller A", "40 tiles · ₹95"], ["Seller B", "70 tiles · ₹90"], ["Seller C", "90 tiles · ₹100"]].map(([a, b]) => (
                <div className="pool-seller" key={a}><span className="swatch" style={{ background: "#E3DFDA" }} /><div><b>{a}</b><div className="tiny muted">{b}</div></div></div>
              ))}
            </div>
            <div className="connector" />
            <div className="pool-hub"><div><b>200</b><span>tiles · 98% shade match</span></div></div>
            <div className="connector" />
            <div className="pool-buyer"><b style={{ fontFamily: "var(--display)", fontSize: 20 }}>You</b><div className="tiny">33% below new</div></div>
          </div>
        </div>
      </section>

      <section className="container section" style={{ paddingTop: 0 }}>
        <div className="band band-orange">
          <div className="sec-title" style={{ marginBottom: 24 }}>
            <div><p className="eyebrow">Food rescue · free, always</p><h2>From the kitchen to a plate while it's still fresh.</h2></div>
            <p>Kitchen staff say what's left in Hindi or English. An AI voice agent rings the nearest verified NGOs, one claims it, and the donor gets a CSR impact certificate.</p>
          </div>
          <div className="flow">
            {[["mic", "var(--pink-soft)", "Say it", "“40 plates veg biryani”"], ["bowl", "var(--sun-soft)", "Posted", "with a pickup deadline"],
              ["phone", "var(--violet-soft)", "NGOs called", "by ElevenLabs voice agent"], ["leaf", "var(--mint-soft)", "Claimed", "by a verified NGO"],
              ["certificate", "var(--lime-soft)", "Certificate", "meals + CO₂ for CSR"]].map(([illo, bg, t, d], i, arr) => (
              <div key={t} style={{ display: "contents" }}>
                <div className="flow-node"><div className="ico" style={{ background: bg }}><Illo name={illo} /></div><b>{t}</b><span>{d}</span></div>
                {i < arr.length - 1 && <div className="flow-arrow"><Arrow /></div>}
              </div>
            ))}
          </div>
          <div className="row" style={{ marginTop: 24 }}>
            <Link to="/food" className="btn btn-orange">Open food rescue <Arrow /></Link>
            <span className="small muted">Also posted to community rescue boards on Vakh.</span>
          </div>
        </div>
      </section>

      <Seconds />

      <section className="container section" style={{ textAlign: "center" }}>
        <h2 style={{ fontSize: "clamp(40px, 7vw, 84px)", fontWeight: 800 }}>Waste less. <span className="hl" style={{ background: "var(--pink)" }}>Earn more.</span></h2>
        <p className="muted" style={{ marginTop: 16 }}>Businesses, NGOs, recyclers and bargain hunters, all on one platform.</p>
        <div className="hero-cta" style={{ justifyContent: "center" }}>
          <Link to="/sell" className="btn btn-primary">List your waste <Arrow /></Link>
          <Link to="/impact" className="btn">See the impact</Link>
        </div>
      </section>
    </>
  );
}
