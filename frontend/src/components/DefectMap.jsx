import { useState } from "react";
import { imgUrl } from "../api";

export const SEVERITY = {
  high: { color: "#D1495B", soft: "rgba(209,73,91,.18)", label: "Needs attention" },
  medium: { color: "#D68A10", soft: "rgba(214,138,16,.18)", label: "Cosmetic damage" },
  low: { color: "#8A7B1F", soft: "rgba(180,160,40,.16)", label: "Minor wear" },
  ok: { color: "#23875C", soft: "rgba(35,135,92,.16)", label: "Sound" },
};

/** The photo with the AI's findings drawn on it: red where it matters, green where it's fine. */
export default function DefectMap({ image, map, height }) {
  const [active, setActive] = useState(null);
  const regions = map?.regions || [];
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="defect-frame" style={height ? { height } : undefined}>
        <img src={imgUrl(image.url)} alt="" />
        {regions.map((r, i) => {
          const s = SEVERITY[r.severity] || SEVERITY.medium;
          const on = active === i;
          return (
            <button key={i} type="button" className={`defect-box ${on ? "on" : ""}`}
              style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%`,
                       borderColor: s.color, background: on ? s.soft : "transparent" }}
              onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)} onBlur={() => setActive(null)}
              aria-label={`${r.label}: ${s.label}`}>
              <span className="defect-tag" style={{ background: s.color }}>{r.label}</span>
            </button>
          );
        })}
      </div>

      {map?.summary && <p className="small">{map.summary}</p>}
      {regions.length > 0 && (
        <ul className="defect-list">
          {regions.map((r, i) => {
            const s = SEVERITY[r.severity] || SEVERITY.medium;
            return (
              <li key={i} className={active === i ? "on" : ""} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}>
                <span className="dot-sev" style={{ background: s.color }} />
                <b>{r.label}</b>
                <span className="small muted">{r.note || s.label}</span>
              </li>
            );
          })}
        </ul>
      )}
      {map?.warnings?.length > 0 && <div className="alert alert-warn small">{map.warnings[0]}</div>}
    </div>
  );
}

export function DefectSummary({ map }) {
  const counts = (map?.regions || []).reduce((acc, r) => ({ ...acc, [r.severity]: (acc[r.severity] || 0) + 1 }), {});
  const order = ["high", "medium", "low", "ok"].filter((k) => counts[k]);
  if (!order.length) return null;
  return (
    <div className="row" style={{ gap: 6 }}>
      {order.map((k) => (
        <span key={k} className="chip" style={{ background: SEVERITY[k].soft, color: SEVERITY[k].color, borderColor: SEVERITY[k].color }}>
          {counts[k]} {SEVERITY[k].label.toLowerCase()}
        </span>
      ))}
    </div>
  );
}
