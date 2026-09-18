import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText, pretty } from "../api";
import { usePersona, useToast } from "../app-state";
import Illo from "../components/Illo";
import { Empty, Field, ListingCard, Spinner } from "../components/ui";

const SAMPLE = "Chalis plates veg biryani bache hain, cooked at 7 pm, packed in containers";

function Recorder({ onAudio, disabled }) {
  const [rec, setRec] = useState(null);
  const chunks = useRef([]);
  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => chunks.current.push(e.data);
      mr.onstop = () => { stream.getTracks().forEach((t) => t.stop()); onAudio(new Blob(chunks.current, { type: mr.mimeType || "audio/webm" })); };
      mr.start();
      setRec(mr);
    } catch {
      onAudio(null, "Microphone blocked. Allow mic access or type the listing instead.");
    }
  };
  const stop = () => { rec?.stop(); setRec(null); };
  return (
    <button className={`mic ${rec ? "rec" : ""}`} onClick={rec ? stop : start} disabled={disabled} aria-label={rec ? "Stop recording" : "Start recording"}>
      {rec ? <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="#fff" /></svg> : <Illo name="mic" />}
    </button>
  );
}

export default function Food() {
  const nav = useNavigate();
  const toast = useToast();
  const { persona } = usePersona();
  const [text, setText] = useState("");
  const [draft, setDraft] = useState(null);
  const [transcript, setTranscript] = useState("");
  const [reason, setReason] = useState({ code: "end_of_day", detail: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [live, setLive] = useState(null);

  const loadLive = () => api.listings({ category: "food_cooked", route: "donate" }).then(setLive).catch(() => setLive([]));
  useEffect(() => { loadLive(); }, []);

  const handle = async (p) => {
    setBusy(true); setErr(null);
    try { const r = await p; setTranscript(r.transcript); setDraft(r.draft); } catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  };
  const onAudio = (blob, problem) => {
    if (problem) { setErr(problem); return; }
    handle(api.voiceDraft(persona.id, blob));
  };
  const setA = (k, v) => setDraft((d) => ({ ...d, attributes: { ...d.attributes, [k]: v } }));

  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.createListing({
        seller_id: persona.id, category: "food_cooked", route: "donate", title: draft.title || draft.attributes.dish_name,
        quantity: Number(draft.quantity), unit: draft.unit, condition: "new",
        reason_code: reason.code, reason_detail: reason.detail || `Surplus ${draft.attributes.dish_name} from today's service, still fresh.`,
        attributes: Object.fromEntries(Object.entries(draft.attributes).filter(([, v]) => v !== null && v !== "")),
      });
      toast("Draft saved. Add two quick photos to publish.");
      nav(`/sell/${r.listing.id}`);
    } catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  };

  const isKitchen = persona && ["business", "individual"].includes(persona.role);
  const localCooked = draft?.attributes.cooked_at ? toLocal(draft.attributes.cooked_at) : "";

  return (
    <div className="container">
      <div className="page-head">
        <div><p className="eyebrow">Food rescue · free, always</p><h1>Cooked too much? Say it.</h1>
          <p>Speak or type what's left. We alert the nearest verified NGOs by phone within minutes, and the listing expires automatically when the food stops being safe.</p></div>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="card card-pad stack" style={{ gap: 18, background: "linear-gradient(180deg, var(--orange-soft), var(--surface) 55%)" }}>
          {!isKitchen && <div className="alert alert-warn small">Switch to a kitchen account, e.g. Spice Route Kitchen, to post food.</div>}
          <div className="row" style={{ gap: 18, flexWrap: "nowrap" }}>
            <Recorder onAudio={onAudio} disabled={busy || !isKitchen} />
            <div><b style={{ fontFamily: "var(--display)", fontSize: 22 }}>Tap and speak</b>
              <p className="small muted">Hindi, English or Hinglish. E.g. “{SAMPLE}”</p></div>
          </div>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="…or type it here" aria-label="Describe the food" />
            <button className="btn btn-dark" onClick={() => handle(api.textDraft(text || SAMPLE))} disabled={busy || !isKitchen}>{busy ? <Spinner /> : "Parse"}</button>
          </div>
          {err && <div className="alert alert-bad">{err}</div>}

          {draft && (
            <div className="stack" style={{ gap: 14 }}>
              <div className="divider" />
              <p className="small muted">Heard: “{transcript}”. Check each field.</p>
              <div className="form-grid">
                <Field label="Dish" required><input className="input" value={draft.attributes.dish_name || ""} onChange={(e) => setA("dish_name", e.target.value)} /></Field>
                <Field label="Quantity" required>
                  <div className="row" style={{ flexWrap: "nowrap" }}>
                    <input className="input" type="number" value={draft.quantity ?? ""} onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))} />
                    <select className="select" style={{ maxWidth: 110 }} value={draft.unit} onChange={(e) => setDraft((d) => ({ ...d, unit: e.target.value }))}><option>plates</option><option>kg</option></select>
                  </div>
                </Field>
                <Field label="Type" required error={!draft.attributes.diet ? "Please confirm veg / non-veg" : null}>
                  <select className="select" value={draft.attributes.diet || ""} onChange={(e) => setA("diet", e.target.value)}>
                    <option value="">Choose…</option>{["veg", "non_veg", "egg", "vegan", "jain"].map((d) => <option key={d} value={d}>{pretty(d)}</option>)}
                  </select>
                </Field>
                <Field label="Cooked at" required><input className="input" type="datetime-local" value={localCooked} onChange={(e) => setA("cooked_at", new Date(e.target.value).toISOString())} /></Field>
                <Field label="Kept" required>
                  <select className="select" value={draft.attributes.storage} onChange={(e) => setA("storage", e.target.value)}>
                    {["hot_holding", "room_temp", "refrigerated"].map((d) => <option key={d} value={d}>{pretty(d)}</option>)}
                  </select>
                </Field>
                <Field label="Packed in" required>
                  <select className="select" value={draft.attributes.packaging} onChange={(e) => setA("packaging", e.target.value)}>
                    {["sealed_containers", "covered_trays", "bulk_vessel"].map((d) => <option key={d} value={d}>{pretty(d)}</option>)}
                  </select>
                </Field>
                <Field label="Allergens"><input className="input" value={draft.attributes.allergens || ""} onChange={(e) => setA("allergens", e.target.value)} placeholder="nuts, dairy, gluten…" /></Field>
                <Field label="Why is it surplus?" required>
                  <select className="select" value={reason.code} onChange={(e) => setReason((r) => ({ ...r, code: e.target.value }))}>
                    <option value="end_of_day">End-of-day surplus</option><option value="event_leftover">Event / wedding leftover</option>
                    <option value="overproduction">Cooked too much</option><option value="cancelled_order">Cancelled bulk order</option>
                  </select>
                </Field>
                <Field label="Details" className="span-2" hint="Optional. We'll write a default if you leave it empty">
                  <input className="input" value={reason.detail} onChange={(e) => setReason((r) => ({ ...r, detail: e.target.value }))} placeholder="e.g. A corporate lunch order was cancelled" />
                </Field>
              </div>
              <button className="btn btn-orange" onClick={create} disabled={busy || !draft.attributes.diet || !(draft.quantity > 0)}>Continue to photos</button>
            </div>
          )}
        </div>

        <div className="stack">
          <div className="row between"><h2 style={{ fontSize: 26 }}>Live rescues</h2><button className="btn btn-sm" onClick={loadLive}>Refresh</button></div>
          {live === null ? <div className="skeleton" style={{ height: 300 }} />
            : live.length === 0 ? <Empty illo="bowl" title="No food waiting right now.">When a kitchen posts, it shows up here with a countdown.</Empty>
              : <div className="grid grid-2">{live.map((li) => <ListingCard key={li.id} listing={li} />)}</div>}
          <p className="small muted">Verified NGOs can open any card to claim it. Unverified groups can see listings but can't claim them.</p>
        </div>
      </div>
    </div>
  );
}

function toLocal(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
