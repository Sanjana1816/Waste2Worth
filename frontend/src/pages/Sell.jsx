import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, errorText, imgUrl, inr, pretty } from "../api";
import { usePersona, useToast } from "../app-state";
import Illo, { CATEGORY_ILLO } from "../components/Illo";
import { ErrorBox, Field, RouteChip, SpeakButton, Spinner } from "../components/ui";
import { DefectSummary } from "../components/DefectMap";

const STEPS = [["snap", "Snap"], ["details", "Details"], ["photos", "Proof photos"], ["review", "Publish"]];
const SELLER_ROLES = ["business", "brand", "individual"];
const PROVENANCE = [
  ["brand", "Brand / manufacturer"], ["product_name", "Product name as sold"], ["model_sku", "Model / SKU / design code"],
  ["manufacturer_color", "Colour name exactly as the company describes it"], ["purchased_from", "Where it was bought"],
  ["purchase_year", "Year of purchase"],
];

const EMPTY = {
  category: "", title: "", quantity: "", unit: "", condition: "good", source_type: "business_surplus", route: "",
  reason_code: "", reason_detail: "", brand: "", product_name: "", model_sku: "", manufacturer_color: "",
  purchased_from: "", purchase_year: "", has_invoice: false, asking_price_per_unit: "", new_price_per_unit: "", attributes: {},
};

function Stepper({ step }) {
  const idx = STEPS.findIndex(([k]) => k === step);
  return (
    <div className="stepper" aria-label="Progress">
      {STEPS.map(([k, label], i) => (
        <div key={k} className={i === idx ? "on" : i < idx ? "done" : ""} aria-current={i === idx ? "step" : undefined}>
          <b>{i < idx ? "✓" : i + 1}</b>{label}
        </div>
      ))}
    </div>
  );
}

/* ---------- step 1: snap + AI ---------- */
function SnapStep({ categories, onDone }) {
  const [files, setFiles] = useState([]);
  const [hint, setHint] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);

  const add = (list) => setFiles((xs) => [...xs, ...Array.from(list).filter((f) => f.type.startsWith("image/"))].slice(0, 2));
  const analyze = async () => {
    setBusy(true); setErr(null);
    try { setResult(await api.analyze(files, hint)); } catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  };
  const a = result?.analysis;

  return (
    <div className="grid grid-2" style={{ alignItems: "start" }}>
      <div className="stack">
        <div className={`dropzone ${drag ? "drag" : ""}`} onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}>
          <Illo name="tiles" className="" />
          <p style={{ fontWeight: 700, marginTop: 8 }}>Drop 1 or 2 photos of your item</p>
          <p className="small muted">Or take them now. Daylight works best.</p>
          <span className="btn btn-dark upload-btn" style={{ marginTop: 14 }}>
            Choose photos
            <input type="file" accept="image/*" multiple capture="environment" onChange={(e) => add(e.target.files)} aria-label="Choose photos" />
          </span>
          {previews.length > 0 && <div className="previews">{previews.map((p) => <img key={p} src={p} alt="" />)}</div>}
        </div>
        <Field label="What is it, roughly? (optional)">
          <select className="select" value={hint} onChange={(e) => setHint(e.target.value)}>
            <option value="">Let the AI decide</option>
            {categories.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
        </Field>
        <div className="row">
          <button className="btn btn-primary" onClick={analyze} disabled={!files.length || busy}>{busy ? <><Spinner /> Identifying…</> : "Identify with AI"}</button>
          <button className="linkish" onClick={() => onDone(null)}>Skip and fill in myself</button>
        </div>
        {err && <div className="alert alert-bad">{err}</div>}
      </div>

      <div className="card card-pad">
        {!a ? (
          <div className="stack muted small">
            <p className="eyebrow">What the AI does</p>
            <p>It identifies the material, condition and colour, spots defects and suggests reuse ideas. It never sets the price: that comes from clear, fixed rules.</p>
            <p>You check and confirm everything on the next step.</p>
          </div>
        ) : (
          <div className="stack">
            <div className="row between"><p className="eyebrow">AI result · {a.provider}</p>{a.confidence > 0 && <span className="chip chip-neutral num">{Math.round(a.confidence * 100)}% sure</span>}</div>
            <h3 style={{ fontSize: 26 }}>{categories.find((c) => c.key === a.category)?.label || "Not sure what this is"}</h3>
            {a.description && <p>{a.description}</p>}
            <dl className="kv">
              {a.condition && <><dt>Condition</dt><dd>{pretty(a.condition)}</dd></>}
              {a.material && <><dt>Material</dt><dd>{a.material}</dd></>}
              {a.visible_color_name && <><dt>Colour seen</dt><dd>{a.visible_color_name}</dd></>}
              {a.defects_seen?.length > 0 && <><dt>Defects</dt><dd>{a.defects_seen.join(", ")}</dd></>}
            </dl>
            {a.safety_flags?.length > 0 && <div className="alert alert-bad">Safety check: {a.safety_flags.join(", ")}</div>}
            {a.warnings?.map((w) => <div key={w} className="alert alert-warn">{w}</div>)}
            {a.reuse_ideas?.length > 0 && (
              <div className="stack" style={{ gap: 8 }}>
                <div className="row between"><b>Reuse ideas</b><SpeakButton text={a.reuse_ideas.map((i) => i.title + (i.steps?.length ? ": " + i.steps.join(". ") : "")).join(". ")} /></div>
                {a.reuse_ideas.map((i) => <div key={i.title} className="idea small"><span>{i.title}</span><span className="chip chip-neutral">{i.difficulty}</span></div>)}
              </div>
            )}
            <button className="btn btn-primary" onClick={() => onDone(result)}>Use this and continue</button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- step 2: details (form built from the category spec) ---------- */
function AttrInput({ attr, value, onChange }) {
  if (attr.type === "enum") {
    return (
      <select className="select" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose…</option>
        {attr.options.map((o) => <option key={o} value={o}>{pretty(o)}</option>)}
      </select>
    );
  }
  if (attr.type === "bool") {
    return (
      <div className="toggle" role="group">
        <button type="button" aria-pressed={value === true} onClick={() => onChange(true)}>Yes</button>
        <button type="button" aria-pressed={value === false} onClick={() => onChange(false)}>No</button>
      </div>
    );
  }
  if (attr.type === "datetime") {
    const local = value ? toLocalInput(value) : "";
    return <input className="input" type="datetime-local" value={local} onChange={(e) => onChange(e.target.value ? new Date(e.target.value).toISOString() : "")} />;
  }
  const numeric = attr.type === "int" || attr.type === "number";
  return <input className="input" type={numeric ? "number" : "text"} step={attr.type === "number" ? "any" : undefined} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
}

function toLocalInput(iso) {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function DetailsStep({ categories, spec, form, setForm, errors, onCategory, onSubmit, busy, isBrand }) {
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setAttr = (k, v) => setForm((f) => ({ ...f, attributes: { ...f.attributes, [k]: v } }));
  const brandSecond = form.source_type === "brand_second";
  const required = new Set([...(spec?.provenance_required || []).map((p) => p.key), ...(brandSecond ? spec?.brand_second_extras?.requires || [] : [])]);
  const attrs = [...(spec?.attributes || []), ...(brandSecond ? spec?.brand_second_extras?.attributes || [] : [])];
  const e = (k) => errors[k];
  const detailLen = form.reason_detail.trim().length;
  const need = form.reason_code === "other" ? 25 : 15;

  return (
    <form className="form" onSubmit={(ev) => { ev.preventDefault(); onSubmit(); }} noValidate>
      <div className="fieldset">
        <h3>What are you listing?</h3><p>Pick the category. The rest of the form adapts to it.</p>
        <div className="form-grid">
          <Field label="Category" required error={e("category")}>
            <select className="select" value={form.category} onChange={(ev) => onCategory(ev.target.value)}>
              <option value="">Choose…</option>
              {categories.map((c) => <option key={c.key} value={c.key}>{c.label} · {c.group}</option>)}
            </select>
          </Field>
          <Field label="Title" required error={e("title")} hint="What a buyer would search for">
            <input className="input" value={form.title} onChange={(ev) => set("title", ev.target.value)} placeholder="e.g. Matte white floor tiles, 600×600" />
          </Field>
          {spec && (
            <>
              <Field label="Quantity" required error={e("quantity")}>
                <div className="row" style={{ flexWrap: "nowrap" }}>
                  <input className="input" type="number" min="0" step="any" value={form.quantity} onChange={(ev) => set("quantity", ev.target.value)} />
                  <select className="select" style={{ maxWidth: 130 }} value={form.unit} onChange={(ev) => set("unit", ev.target.value)} aria-label="Unit">
                    {spec.units.map((u) => <option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
              </Field>
              <Field label="Condition" required error={e("condition")}>
                <select className="select" value={form.condition} onChange={(ev) => set("condition", ev.target.value)}>
                  {["new", "like_new", "good", "fair", "poor"].map((c) => <option key={c} value={c}>{pretty(c)}</option>)}
                </select>
              </Field>
              <Field label="Route" hint="Leave it to us and we'll pick the route that wastes least" error={e("route")}>
                <select className="select" value={form.route} onChange={(ev) => set("route", ev.target.value)}>
                  <option value="">Recommend for me</option>
                  {spec.routes.map((r) => <option key={r} value={r}>{pretty(r)}</option>)}
                </select>
              </Field>
              {isBrand && !spec.perishable && (
                <Field label="Listing type" group>
                  <div className="toggle" role="group">
                    <button type="button" aria-pressed={!brandSecond} onClick={() => set("source_type", "business_surplus")}>Surplus</button>
                    <button type="button" aria-pressed={brandSecond} onClick={() => set("source_type", "brand_second")}>Brand second</button>
                  </div>
                </Field>
              )}
            </>
          )}
        </div>
      </div>

      {spec && (
        <>
          <div className="fieldset">
            <h3>Why is this being given away or sold?</h3><p>Buyers trust listings more when they know the story. Be specific.</p>
            <div className="form-grid">
              <Field label="Reason" required error={e("reason_code")}>
                <select className="select" value={form.reason_code} onChange={(ev) => set("reason_code", ev.target.value)}>
                  <option value="">Choose…</option>
                  {spec.reasons.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
                </select>
              </Field>
              <Field label="In your words" required error={e("reason_detail")} hint={`${detailLen}/${need}+ characters`} className="span-2">
                <textarea className="textarea" value={form.reason_detail} onChange={(ev) => set("reason_detail", ev.target.value)}
                  placeholder="e.g. Client switched to wooden flooring after we'd bought the tiles. Still in sealed boxes." />
              </Field>
            </div>
          </div>

          {!spec.perishable && (
            <div className="fieldset">
              <h3>Where it came from</h3>
              <p>Photos can look different under different lighting, so the manufacturer's colour name and design code are what we match on.</p>
              <div className="form-grid">
                {PROVENANCE.map(([k, label]) => (
                  <Field key={k} label={label} required={required.has(k)} error={e(k)}>
                    <input className="input" type={k === "purchase_year" ? "number" : "text"} value={form[k]} onChange={(ev) => set(k, ev.target.value)}
                      placeholder={{ manufacturer_color: "e.g. Arctic Matte White", model_sku: "e.g. TR-6060-MW" }[k] || ""} />
                  </Field>
                ))}
                <Field label="Invoice available" group>
                  <div className="toggle" role="group">
                    <button type="button" aria-pressed={form.has_invoice} onClick={() => set("has_invoice", true)}>Yes</button>
                    <button type="button" aria-pressed={!form.has_invoice} onClick={() => set("has_invoice", false)}>No</button>
                  </div>
                </Field>
              </div>
            </div>
          )}

          <div className="fieldset">
            <h3>{spec.label} details</h3><p>These help buyers and the matching engine.</p>
            <div className="form-grid">
              {attrs.map((a) => (
                <Field key={a.key} label={a.label + (a.unit ? ` (${a.unit})` : "")} required={a.required} hint={a.help} error={e(`attributes.${a.key}`)}
                  group={a.type === "bool"}
                  className={a.type === "text" && /description/.test(a.key) ? "span-2" : ""}>
                  <AttrInput attr={a} value={form.attributes[a.key]} onChange={(v) => setAttr(a.key, v)} />
                </Field>
              ))}
            </div>
          </div>

          {!spec.perishable && form.route !== "donate" && (
            <div className="fieldset">
              <h3>Price</h3><p>Second-hand must be cheaper than new. We'll tell you the maximum for this condition.</p>
              <div className="form-grid">
                <Field label={`Your price per ${form.unit || "unit"} (₹)`} error={e("asking_price_per_unit")} hint="Leave empty to donate or decide later">
                  <input className="input" type="number" min="0" value={form.asking_price_per_unit} onChange={(ev) => set("asking_price_per_unit", ev.target.value)} />
                </Field>
                <Field label={`Price when new, per ${form.unit || "unit"} (₹)`} required={brandSecond} error={e("new_price_per_unit")} hint="MRP / invoice price. Otherwise we use a reference price">
                  <input className="input" type="number" min="0" value={form.new_price_per_unit} onChange={(ev) => set("new_price_per_unit", ev.target.value)} />
                </Field>
              </div>
            </div>
          )}
        </>
      )}
      {Object.keys(errors).length > 0 && <div className="alert alert-bad">Fix the highlighted fields and try again.</div>}
      <div className="row"><button className="btn btn-primary" type="submit" disabled={!spec || busy}>{busy ? <Spinner /> : "Save and add photos"}</button></div>
    </form>
  );
}

/* ---------- step 3: required proof photos ---------- */
function ShotSlot({ shot, required, upload, onUpload, onScan }) {
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [err, setErr] = useState(null);
  const state = upload ? (upload.quality_ok ? "ok" : "bad") : "";
  const pick = async (file) => {
    if (!file) return;
    setBusy(true); setErr(null);
    try { await onUpload(shot.key, file); } catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  };
  return (
    <div className={`shot ${state}`}>
      <h4><span>{shot.label}</span>{required ? <span className="chip chip-neutral">Required</span> : <span className="chip chip-neutral">Optional</span>}</h4>
      <div className="shot-preview">{upload?.preview ? <img src={upload.preview} alt={shot.label} /> : <span>{shot.help}</span>}</div>
      {upload && (upload.quality_ok
        ? <div className="row small" style={{ color: "var(--ok)", fontWeight: 700 }}>✓ Looks good
            {upload.white_balanced && <span className="row" style={{ gap: 6, color: "var(--ink-2)", fontWeight: 500 }}>· true colour <span className="swatch" style={{ background: upload.color_hex }} /></span>}
          </div>
        : <div className="alert alert-bad small"><b>Please retake</b><ul>{(upload.problems || []).map((p) => <li key={p}>{p}</li>)}</ul></div>)}
      {upload?.preview && <p>{shot.help}</p>}
      {err && <div className="error-text">{err}</div>}
      <div className="row" style={{ gap: 8 }}>
        <span className={`btn btn-sm ${upload?.quality_ok ? "" : "btn-dark"} upload-btn`}>
          {busy ? <Spinner /> : upload ? "Retake" : "Add photo"}
          <input type="file" accept="image/*" capture="environment" onChange={(e) => pick(e.target.files?.[0])} disabled={busy} aria-label={`Upload ${shot.label}`} />
        </span>
        {upload?.quality_ok && upload.id && (
          <button type="button" className="btn btn-sm" disabled={scanning}
            onClick={async () => { setScanning(true); setErr(null);
              try { await onScan(upload.id); } catch (e) { setErr(errorText(e)); } finally { setScanning(false); } }}>
            {scanning ? <><Spinner /> Scanning…</> : upload.defect_map ? "Rescan damage" : "Scan for damage"}
          </button>
        )}
      </div>
      {upload?.defect_map && (
        <div className="stack" style={{ gap: 8 }}>
          <DefectSummary map={upload.defect_map} />
          {upload.defect_map.summary && <p className="small">{upload.defect_map.summary}</p>}
          {upload.defect_map.warnings?.[0] && <p className="small muted">{upload.defect_map.warnings[0]}</p>}
        </div>
      )}
    </div>
  );
}

function PhotosStep({ spec, listing, readiness, setReadiness, uploads, setUploads, onNext }) {
  const scan = async (shotKey, imageId) => {
    const map = await api.inspectImage(listing.id, imageId);
    setUploads((u) => ({ ...u, [shotKey]: { ...u[shotKey], defect_map: map } }));
  };
  const brandSecond = listing.source_type === "brand_second";
  const shots = [...spec.shots, ...(brandSecond ? spec.brand_second_extras?.shots || [] : [])];
  const requiredKeys = new Set([...readiness.missing_shots, ...readiness.retake_shots].map((s) => s.shot));
  shots.forEach((s) => { if (s.required) requiredKeys.add(s.key); });

  const onUpload = async (shotKey, file) => {
    const r = await api.uploadImage(listing.id, shotKey, file);
    setUploads((u) => ({ ...u, [shotKey]: { ...r.image, preview: URL.createObjectURL(file) } }));
    setReadiness(r.readiness);
  };
  const pct = Math.min(100, (readiness.image_count / readiness.min_images) * 100);
  const outstanding = readiness.missing_shots.length + readiness.retake_shots.length;

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="card card-pad stack">
        <div className="row between">
          <b>{readiness.image_count} of at least {readiness.min_images} good photos</b>
          <span className="small muted">{outstanding ? `${outstanding} required ${outstanding === 1 ? "shot" : "shots"} to go` : "All required shots done"}</span>
        </div>
        <div className="progress"><div style={{ width: `${pct}%` }} /></div>
        {spec.color_critical && <p className="small muted">Colour matters for {spec.label.toLowerCase()}. For the colour reference, put the item in the middle of a plain white A4 sheet. We use the paper to cancel out your lighting.</p>}
      </div>
      <div className="shots">
        {shots.map((s) => (
          <ShotSlot key={s.key} shot={s} required={requiredKeys.has(s.key)} upload={uploads[s.key]}
                    onUpload={onUpload} onScan={(imageId) => scan(s.key, imageId)} />
        ))}
      </div>
      <div className="row"><button className="btn btn-primary" onClick={onNext} disabled={outstanding > 0 || readiness.image_count < readiness.min_images}>Review and publish</button>
        {outstanding > 0 && <span className="small muted">Add the required photos to continue.</span>}</div>
    </div>
  );
}

/* ---------- step 4: review ---------- */
function ReviewStep({ spec, listing, readiness, onEdit, onPublish, busy }) {
  const s = listing.route_suggestion;
  return (
    <div className="grid grid-2" style={{ alignItems: "start" }}>
      <div className="card card-pad stack">
        <div className="row"><RouteChip route={listing.route} /><span className="chip chip-neutral">{spec.label}</span></div>
        <h2 style={{ fontSize: 30 }}>{listing.title}</h2>
        <dl className="kv">
          <dt>Quantity</dt><dd>{listing.quantity} {listing.unit}</dd>
          <dt>Your price</dt><dd>{listing.route === "donate" ? "Free" : listing.asking_price_per_unit ? `${inr(listing.asking_price_per_unit)} per ${listing.unit.replace(/s$/, "")}` : "Not set"}</dd>
          {listing.price_cap_per_unit && <><dt>Maximum allowed</dt><dd>{inr(listing.price_cap_per_unit)} per {listing.unit.replace(/s$/, "")}</dd></>}
          <dt>Lot value (est.)</dt><dd>{listing.est_value_high ? `${inr(listing.est_value_low)} – ${inr(listing.est_value_high)}` : "–"}</dd>
          <dt>CO₂e saved (est.)</dt><dd>{listing.co2_saved_kg} kg</dd>
        </dl>
        <button className="linkish" onClick={onEdit} style={{ alignSelf: "start" }}>Edit details</button>
      </div>
      <div className="stack">
        {s && (
          <div className="card card-pad stack">
            <p className="eyebrow">Why this route</p>
            {s.why.map((w) => <p key={w}>{w}</p>)}
          </div>
        )}
        {readiness.field_errors.length > 0 && <div className="alert alert-bad"><b>Still to fix</b><ul>{readiness.field_errors.map((f) => <li key={f.field}>{f.message}</li>)}</ul></div>}
        <button className={`btn ${listing.route === "donate" ? "btn-orange" : "btn-primary"} btn-block`} onClick={onPublish} disabled={busy || !readiness.ready}>
          {busy ? <Spinner /> : listing.route === "donate" && spec.perishable ? "Publish and alert NGOs" : "Publish listing"}
        </button>
      </div>
    </div>
  );
}

/* ---------- page ---------- */
export default function Sell() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { persona } = usePersona();
  const [categories, setCategories] = useState([]);
  const [step, setStep] = useState(id ? "photos" : "snap");
  const [spec, setSpec] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [listing, setListing] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [uploads, setUploads] = useState({});
  const [busy, setBusy] = useState(false);
  const [loadErr, setLoadErr] = useState(null);

  useEffect(() => { api.categories().then(setCategories).catch(setLoadErr); }, []);

  const loadSpec = async (key) => {
    const s = key ? await api.category(key) : null;
    setSpec(s);
    return s;
  };

  // Resume a draft (e.g. from the food voice flow)
  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const li = await api.listing(id);
        if (li.status !== "draft") { nav(`/listing/${li.id}`, { replace: true }); return; }
        await loadSpec(li.category);
        setListing(li);
        setForm(fromListing(li));
        setReadiness(li.readiness);
        const ups = {};
        li.images.forEach((img) => { ups[img.shot_type] = { ...img, preview: imgUrl(img.url), problems: img.quality_ok ? [] : ["This photo didn't pass. Retake it."] }; });
        setUploads(ups);
        setStep("photos");
      } catch (e) { setLoadErr(e); }
    })();
  }, [id]);

  const onCategory = async (key) => {
    const s = await loadSpec(key).catch(() => null);
    setForm((f) => ({ ...f, category: key, unit: s?.units[0] || "", reason_code: "", attributes: {}, route: s?.perishable ? "donate" : f.route }));
  };

  const fromSnap = async (result) => {
    const pre = result?.form_prefill;
    if (pre?.category) {
      const s = await loadSpec(pre.category).catch(() => null);
      setForm((f) => ({ ...f, category: pre.category, unit: s?.units[0] || "", condition: pre.condition || f.condition, attributes: { ...pre.attributes } }));
    }
    setStep("details");
  };

  const submit = async () => {
    if (!persona) return;
    setBusy(true); setErrors({});
    const body = toBody(form);
    try {
      let r;
      if (listing && listing.category === form.category) {
        const { category: _c, ...patch } = body;
        r = await api.updateListing(listing.id, patch);
      } else {
        r = await api.createListing({ ...body, seller_id: persona.id });
      }
      setListing(r.listing);
      setReadiness(r.readiness);
      setStep("photos");
      window.scrollTo(0, 0);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) setErrors(e.fields);
      else toast(errorText(e), "bad");
    } finally { setBusy(false); }
  };

  const publish = async () => {
    setBusy(true);
    try {
      const r = await api.publish(listing.id);
      toast(r.dispatch ? `Published. Alerted ${r.dispatch.filter((d) => d.channel === "voice_call").length} NGOs.` : "Published! Your listing is live.");
      nav(`/listing/${listing.id}`);
    } catch (e) {
      if (e.detail?.readiness) setReadiness(e.detail.readiness);
      toast(errorText(e), "bad");
    } finally { setBusy(false); }
  };

  const goReview = async () => {
    const [li, rd] = await Promise.all([api.listing(listing.id), api.readiness(listing.id)]);
    setListing(li); setReadiness(rd); setStep("review");
  };

  const wrongRole = persona && !SELLER_ROLES.includes(persona.role);

  return (
    <div className="container">
      <div className="page-head">
        <div><p className="eyebrow">List waste</p><h1>Give it a second life.</h1><p>Photos, a few honest details, and we'll handle the value, the route and the matching.</p></div>
        {spec && <Illo name={CATEGORY_ILLO[spec.key]} className="" />}
      </div>
      <Stepper step={step} />
      {loadErr && <ErrorBox error={errorText(loadErr)} />}
      {wrongRole && <div className="alert alert-warn" style={{ marginBottom: 20 }}>You're acting as a {persona.role}. Switch to a business, brand or individual account (top right) to list items.</div>}

      {step === "snap" && <SnapStep categories={categories} onDone={fromSnap} />}
      {step === "details" && (
        <DetailsStep categories={categories} spec={spec} form={form} setForm={setForm} errors={errors} onCategory={onCategory}
          onSubmit={submit} busy={busy || wrongRole} isBrand={persona?.role === "brand"} />
      )}
      {step === "photos" && listing && spec && readiness && (
        <PhotosStep spec={spec} listing={listing} readiness={readiness} setReadiness={setReadiness} uploads={uploads} setUploads={setUploads} onNext={goReview} />
      )}
      {step === "review" && listing && (
        <ReviewStep spec={spec} listing={listing} readiness={readiness} onEdit={() => setStep("details")} onPublish={publish} busy={busy} />
      )}
      {step !== "snap" && step !== "review" && (
        <p className="small muted" style={{ marginTop: 24 }}>Drafts are saved. <Link to="/explore" className="linkish">Browse listings</Link></p>
      )}
    </div>
  );
}

function toBody(form) {
  const num = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
  const str = (v) => (v === "" ? null : v);
  const attributes = {};
  Object.entries(form.attributes).forEach(([k, v]) => { if (v !== "" && v !== null && v !== undefined) attributes[k] = v; });
  return {
    category: form.category, title: form.title, quantity: num(form.quantity), unit: form.unit, condition: form.condition,
    source_type: form.source_type, route: str(form.route), reason_code: form.reason_code, reason_detail: form.reason_detail,
    brand: str(form.brand), product_name: str(form.product_name), model_sku: str(form.model_sku),
    manufacturer_color: str(form.manufacturer_color), purchased_from: str(form.purchased_from), purchase_year: num(form.purchase_year),
    has_invoice: form.has_invoice, asking_price_per_unit: num(form.asking_price_per_unit), new_price_per_unit: num(form.new_price_per_unit),
    attributes,
  };
}

function fromListing(li) {
  const f = { ...EMPTY };
  Object.keys(EMPTY).forEach((k) => { if (li[k] !== null && li[k] !== undefined) f[k] = li[k]; });
  f.attributes = { ...(li.attributes || {}) };
  return f;
}
