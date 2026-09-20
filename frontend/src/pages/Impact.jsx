import { useEffect, useState } from "react";
import { api, errorText, fmtQty, inr } from "../api";
import { usePersona } from "../app-state";
import { ErrorBox, Field, useAsync } from "../components/ui";

const INTEGRATIONS = [
  ["Vision AI", (s) => (s.groq ? `Groq · ${s.vision_provider}` : s.gemini ? "Gemini" : "offline guess"), (s) => s.groq || s.gemini],
  ["Voice", (s) => (s.elevenlabs ? (s.elevenlabs_calls ? "ElevenLabs + phone calls" : "ElevenLabs speech") : "browser voice"), (s) => s.elevenlabs],
  ["Community board", (s) => (s.vakh_connected ? `Vakh · ${s.vakh_post_tool || "connected"}` : "not connected"), (s) => s.vakh_connected],
  ["Database & photos", (s) => (s.storage === "supabase" ? "Supabase" : "local disk"), (s) => s.database === "connected"],
];

function LiveIntegrations() {
  const st = useAsync(() => api.integrations(), []);
  const s = st.data;
  if (!s) return null;
  return (
    <section className="no-print" style={{ marginTop: 48 }}>
      <h2 style={{ fontSize: 24 }}>What's actually running</h2>
      <p className="small muted" style={{ marginTop: 6, marginBottom: 14 }}>
        Read live from the backend, so it shows the services this deployment is really calling.
      </p>
      <div className="grid grid-4">
        {INTEGRATIONS.map(([label, value, ok]) => (
          <div key={label} className="card card-pad">
            <div className="tiny muted">{label}</div>
            <div className="row" style={{ gap: 8, marginTop: 6 }}>
              <span className={`chip ${ok(s) ? "chip-ok" : "chip-warn"}`}>{ok(s) ? "live" : "fallback"}</span>
              <b>{value(s)}</b>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Impact() {
  const { orgs, persona } = usePersona();
  const summary = useAsync(() => api.impact(), []);
  const donors = orgs.filter((o) => ["business", "brand", "individual"].includes(o.role));
  const [orgId, setOrgId] = useState(null);
  useEffect(() => {
    if (orgId || !donors.length) return;
    setOrgId(donors.find((o) => o.id === persona?.id)?.id || donors.find((o) => o.name === "Spice Route Kitchen")?.id || donors[0].id);
  }, [donors, persona, orgId]);
  const cert = useAsync(() => (orgId ? api.certificate(orgId) : Promise.resolve(null)), [orgId]);
  const s = summary.data;
  const c = cert.data;

  return (
    <div className="container">
      <div className="page-head no-print">
        <div><p className="eyebrow">Impact</p><h1>Receipts for the planet.</h1>
          <p>Every completed order and claim adds up here. These are estimates based on per-material emission factors, not audited figures.</p></div>
      </div>

      {summary.error && <ErrorBox error={errorText(summary.error)} onRetry={summary.reload} />}
      <div className="stats no-print" style={{ marginBottom: 40 }}>
        {[["var(--lime)", s ? `${fmtQty(s.kg_diverted)} kg` : "–", "kept out of landfill"],
          ["var(--orange)", s ? fmtQty(s.meals_rescued) : "–", "meals rescued"],
          ["var(--mint)", s ? `${fmtQty(s.co2e_avoided_kg)} kg` : "–", "CO₂e avoided"],
          ["var(--pink)", s ? inr(s.value_recovered_inr) : "–", "recovered for sellers"]].map(([col, n, u]) => (
          <div className="stat" key={u}><div className="bar" style={{ background: col }} /><div className="n">{n}</div><div className="u">{u}</div></div>
        ))}
      </div>

      <div className="row between no-print" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 28 }}>CSR impact certificate</h2>
        <div className="row">
          <Field label="For">
            <select className="select" value={orgId || ""} onChange={(e) => setOrgId(Number(e.target.value))}>
              {donors.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </Field>
          <button className="btn btn-dark" style={{ alignSelf: "end" }} onClick={() => window.print()} disabled={!c}>Print / save PDF</button>
        </div>
      </div>

      {c && (
        <div className="cert">
          <div className="row between" style={{ alignItems: "start", position: "relative", zIndex: 1 }}>
            <div>
              <p className="eyebrow">Certificate of impact · {c.certificate_no}</p>
              <h2 style={{ marginTop: 10 }}>{c.org}</h2>
              <p className="muted" style={{ marginTop: 6 }}>kept these resources in use through Waste2Worth.</p>
            </div>
            <div className="cert-seal">W2W<br />verified</div>
          </div>
          <div className="grid grid-4" style={{ marginTop: 28, position: "relative", zIndex: 1 }}>
            {[["Meals donated", fmtQty(c.meals_rescued)], ["Kept out of landfill", `${fmtQty(c.kg_diverted)} kg`],
              ["CO₂e avoided", `${fmtQty(c.co2e_avoided_kg)} kg`], ["Value recovered", inr(c.value_recovered_inr)]].map(([k, v]) => (
              <div key={k} className="card-soft"><div className="tiny muted">{k}</div><div style={{ fontFamily: "var(--display)", fontWeight: 800, fontSize: 28 }}>{v}</div></div>
            ))}
          </div>
          <div style={{ marginTop: 24, position: "relative", zIndex: 1 }}>
            <p><b>Received by:</b> {c.recipients.length ? c.recipients.join(", ") : "No claims yet"}</p>
            <p className="small muted" style={{ marginTop: 10 }}>{c.method}</p>
          </div>
        </div>
      )}

      <LiveIntegrations />
    </div>
  );
}
