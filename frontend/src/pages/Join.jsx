import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, errorText } from "../api";
import { usePersona, useToast } from "../app-state";
import Illo from "../components/Illo";
import { Field, Spinner } from "../components/ui";

const ROLES = [
  { key: "business", illo: "tiles", title: "Business", text: "Builders, restaurants, offices, shops: list surplus and leftovers." },
  { key: "brand", illo: "hoodie", title: "Brand", text: "Sell factory seconds with cosmetic flaws, below MRP." },
  { key: "individual", illo: "chair", title: "Individual", text: "Give away or sell things from home." },
  { key: "buyer", illo: "box", title: "Buyer", text: "Buy second-hand stock and pooled lots for less than new." },
  { key: "ngo", illo: "bowl", title: "NGO", text: "Claim free food and clothes. We verify NGOs before they can claim." },
  { key: "recycler", illo: "recycle", title: "Recycler", text: "Get scrap and e-waste routed to you. Certified recyclers get e-waste." },
];

const AREAS = [
  ["Koramangala", 12.9352, 77.6245], ["Indiranagar", 12.9784, 77.6408], ["HSR Layout", 12.9116, 77.6474],
  ["Whitefield", 12.9698, 77.75], ["Marathahalli", 12.9569, 77.7011], ["Jayanagar", 12.925, 77.5938],
  ["Malleshwaram", 13.0035, 77.571], ["Hebbal", 13.0358, 77.597], ["Electronic City", 12.8452, 77.6602],
  ["Peenya", 13.028, 77.519],
];

const CATEGORY_PROMPT = {
  business: "What do you use or buy? (optional)", buyer: "What are you looking for? (optional)",
  ngo: "What can you accept?", recycler: "What do you recycle?",
};

export default function Join() {
  const nav = useNavigate();
  const toast = useToast();
  const { reload, choose } = usePersona();
  const [cats, setCats] = useState([]);
  const [role, setRole] = useState("business");
  const [form, setForm] = useState({ name: "", phone: "", area: "Koramangala", lat: null, lng: null, accepts: [] });
  const [locating, setLocating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => { api.categories().then(setCats).catch(() => {}); }, []);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const locate = () => {
    if (!navigator.geolocation) { toast("Your browser can't share location. Pick an area instead.", "bad"); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setForm((f) => ({ ...f, lat: +p.coords.latitude.toFixed(5), lng: +p.coords.longitude.toFixed(5), area: "" })); setLocating(false); },
      () => { toast("Location was blocked. Pick your area from the list instead.", "bad"); setLocating(false); },
      { timeout: 10000 },
    );
  };

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (form.name.trim().length < 2) errs.name = "Enter your business or your own name";
    if (form.phone && !/^\+?[0-9 ]{8,16}$/.test(form.phone)) errs.phone = "Use digits only, e.g. +91 98765 43210";
    if (role === "ngo" && !form.accepts.length) errs.accepts = "Pick at least one thing you can accept";
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const area = AREAS.find((a) => a[0] === form.area);
    setBusy(true);
    try {
      const org = await api.createOrg({
        name: form.name.trim(), role, phone: form.phone.trim() || null, city: "Bengaluru",
        lat: form.lat ?? area[1], lng: form.lng ?? area[2], accepts_categories: form.accepts,
      });
      await reload();
      choose(org.id);
      toast(`Welcome, ${org.name}! You're now using your new account.`);
      nav(["business", "brand", "individual"].includes(role) ? "/dashboard" : role === "ngo" ? "/food" : "/explore");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setErrors({ name: "That name is taken. Try adding your area." });
      else toast(errorText(err), "bad");
    } finally { setBusy(false); }
  };

  const toggleCat = (k) => set("accepts", form.accepts.includes(k) ? form.accepts.filter((x) => x !== k) : [...form.accepts, k]);

  return (
    <div className="container">
      <div className="page-head">
        <div><p className="eyebrow">Create an account</p><h1>Join Waste2Worth.</h1>
          <p>Takes a minute. Tell us who you are and roughly where, and we'll match you with people nearby.</p></div>
      </div>

      <form className="form" onSubmit={submit} noValidate>
        <div className="fieldset">
          <h3>I am a…</h3><p>This decides what you can do. You can make more than one account.</p>
          <div className="role-grid" role="radiogroup" aria-label="Account type">
            {ROLES.map((r) => (
              <button type="button" key={r.key} role="radio" aria-checked={role === r.key}
                className={`role-card ${role === r.key ? "on" : ""}`} onClick={() => { setRole(r.key); set("accepts", []); }}>
                <span className="ico"><Illo name={r.illo} /></span>
                <b>{r.title}</b>
                <span className="small muted">{r.text}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="fieldset">
          <h3>Your details</h3>
          <p>{role === "ngo" || role === "recycler"
            ? "New NGOs and recyclers start unverified. You can browse straight away; claiming unlocks once we verify you."
            : "Buyers see your name on your listings."}</p>
          <div className="form-grid">
            <Field label={role === "individual" || role === "buyer" ? "Your name" : "Business / organisation name"} required error={errors.name}>
              <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={80}
                placeholder={role === "ngo" ? "e.g. Hope Kitchen Collective" : role === "individual" ? "e.g. Meera S." : "e.g. Green Leaf Cafe"} />
            </Field>
            <Field label="Phone" error={errors.phone} hint={role === "ngo" ? "We ring this number when food is ready near you" : "Optional"}>
              <input className="input" type="tel" value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+91 98765 43210" />
            </Field>
            <Field label="Where are you?" required hint={form.lat ? `Using your location (${form.lat}, ${form.lng})` : "Your pickups and matches are based on this"}>
              <div className="row" style={{ flexWrap: "nowrap" }}>
                <select className="select" value={form.area} onChange={(e) => setForm((f) => ({ ...f, area: e.target.value, lat: null, lng: null }))}>
                  {form.lat && <option value="">My current location</option>}
                  {AREAS.map(([a]) => <option key={a} value={a}>{a}, Bengaluru</option>)}
                </select>
                <button type="button" className="btn btn-sm" onClick={locate} disabled={locating}>{locating ? <Spinner /> : "Use my location"}</button>
              </div>
            </Field>
          </div>
        </div>

        {CATEGORY_PROMPT[role] && (
          <div className="fieldset">
            <h3>{CATEGORY_PROMPT[role]}</h3><p>We use this to send you the right items first.</p>
            <div className="row" style={{ gap: 8 }}>
              {cats.filter((c) => role !== "ngo" || ["food_cooked", "clothing", "fabric", "furniture", "electronics"].includes(c.key))
                .map((c) => (
                  <button type="button" key={c.key} className="filter-chip" aria-pressed={form.accepts.includes(c.key)} onClick={() => toggleCat(c.key)}>{c.label}</button>
                ))}
            </div>
            {errors.accepts && <p className="error-text" style={{ marginTop: 8 }}>{errors.accepts}</p>}
          </div>
        )}

        <div className="row"><button className="btn btn-primary" type="submit" disabled={busy}>{busy ? <Spinner /> : "Create account"}</button>
          <span className="small muted">No password needed for this demo. Real sign-in comes later.</span></div>
      </form>
    </div>
  );
}
