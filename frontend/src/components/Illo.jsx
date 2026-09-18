/* Hand-drawn sticker illustrations, in the softened palette. */
const K = "#17171C";
const s = { stroke: K, strokeWidth: 4, strokeLinejoin: "round", strokeLinecap: "round" };

const ART = {
  tiles: (
    <g {...s}>
      <path d="M14 78 L60 100 L106 78 L60 56 Z" fill="#8EA3F4" />
      <path d="M14 78 v10 L60 110 v-10 Z" fill="#6F86DD" /><path d="M106 78 v10 L60 110 v-10 Z" fill="#5A70C4" />
      <path d="M14 56 L60 78 L106 56 L60 34 Z" fill="#FFFFFF" />
      <path d="M14 56 v10 L60 88 v-10 Z" fill="#E4E2EC" /><path d="M106 56 v10 L60 88 v-10 Z" fill="#CFCCDA" />
      <path d="M14 34 L60 56 L106 34 L60 12 Z" fill="#F29AC2" />
      <path d="M14 34 v10 L60 66 v-10 Z" fill="#DE7FAB" /><path d="M106 34 v10 L60 66 v-10 Z" fill="#C96C97" />
    </g>
  ),
  bowl: (
    <g {...s}>
      <path d="M44 22 q-6 8 0 14 q6 6 0 14 M60 16 q-6 8 0 14 q6 6 0 14 M76 22 q-6 8 0 14 q6 6 0 14" fill="none" />
      <ellipse cx="60" cy="62" rx="44" ry="12" fill="#FFDC7A" />
      <circle cx="46" cy="58" r="4" fill="#FFAE73" /><circle cx="66" cy="56" r="4" fill="#86DBBF" /><circle cx="78" cy="62" r="3.5" fill="#F29AC2" />
      <path d="M16 62 q4 42 44 42 q40 0 44 -42 q-4 12 -44 12 q-40 0 -44 -12 z" fill="#FFAE73" />
    </g>
  ),
  hoodie: (
    <g {...s}>
      <path d="M42 18 q18 -10 36 0 l22 12 l14 34 l-16 6 l-6 -14 v50 h-64 v-50 l-6 14 l-16 -6 l14 -34 z" fill="#BBA8F5" />
      <path d="M44 18 q16 24 32 0" fill="#A28DEB" />
      <path d="M52 34 v12 M68 34 v12" fill="none" strokeWidth="3" />
      <rect x="40" y="72" width="40" height="16" rx="4" fill="#C6E77A" />
    </g>
  ),
  laptop: (
    <g {...s}>
      <rect x="22" y="24" width="76" height="52" rx="6" fill={K} />
      <rect x="28" y="30" width="64" height="40" rx="3" fill="#86DBBF" />
      <path d="M40 46 l10 8 l-10 8 M56 62 h14" fill="none" strokeWidth="3.5" />
      <path d="M10 82 h100 l-8 12 h-84 z" fill="#FFDC7A" />
    </g>
  ),
  chair: (
    <g {...s}>
      <rect x="34" y="14" width="52" height="46" rx="10" fill="#FFAE73" />
      <rect x="26" y="58" width="68" height="16" rx="6" fill="#C6E77A" />
      <path d="M34 74 l-6 34 M86 74 l6 34 M44 74 l-2 26 M76 74 l2 26" fill="none" />
    </g>
  ),
  recycle: (
    <g {...s}>
      <path d="M60 14 l20 34 h-14 l-6 -10 l-14 24 l-12 -7 z" fill="#86DBBF" />
      <path d="M104 88 l-40 0 l7 -12 h12 l-14 -24 l12 -7 z" fill="#FFDC7A" />
      <path d="M20 90 l20 -34 l7 12 l-6 10 h28 v14 z" fill="#F29AC2" />
    </g>
  ),
  box: (
    <g {...s}>
      <path d="M16 40 L60 22 L104 40 L60 58 Z" fill="#F2D7A8" />
      <path d="M16 40 v46 L60 104 V58 Z" fill="#E4BF83" /><path d="M104 40 v46 L60 104 V58 Z" fill="#D2A86A" />
      <path d="M38 31 L82 49 v14" fill="none" strokeWidth="3" />
    </g>
  ),
  plank: (
    <g {...s}>
      <rect x="14" y="30" width="92" height="20" rx="4" fill="#E4BF83" />
      <rect x="20" y="56" width="86" height="20" rx="4" fill="#D2A86A" />
      <rect x="10" y="82" width="92" height="20" rx="4" fill="#F2D7A8" />
      <path d="M30 40 h20 M60 66 h24 M24 92 h14" fill="none" strokeWidth="2.5" />
    </g>
  ),
  mic: (
    <g {...s}>
      <rect x="44" y="12" width="32" height="56" rx="16" fill="#F29AC2" />
      <path d="M32 54 q0 28 28 28 q28 0 28 -28 M60 82 v20 M44 104 h32" fill="none" />
    </g>
  ),
  phone: (
    <g {...s}>
      <rect x="34" y="10" width="52" height="100" rx="12" fill="#BBA8F5" />
      <path d="M50 24 q10 -6 20 0 M44 50 q16 -14 32 0 M38 76 q22 -20 44 0" fill="none" strokeWidth="3.5" />
    </g>
  ),
  leaf: (
    <g {...s}>
      <path d="M20 100 C20 40 60 16 104 16 C104 64 78 100 20 100 Z" fill="#C6E77A" />
      <path d="M20 100 C44 72 64 54 90 32" fill="none" />
    </g>
  ),
  certificate: (
    <g {...s}>
      <rect x="18" y="14" width="84" height="92" rx="10" fill="#FFFFFF" />
      <path d="M34 38 h52 M34 54 h52 M34 70 h30" fill="none" strokeWidth="3.5" />
      <circle cx="84" cy="88" r="14" fill="#C6E77A" />
    </g>
  ),
};

export const CATEGORY_ILLO = {
  tiles: "tiles", wood: "plank", metal: "recycle", fabric: "hoodie", clothing: "hoodie",
  electronics: "laptop", furniture: "chair", packaging: "box", food_cooked: "bowl",
};

export const CATEGORY_TINT = {
  tiles: "var(--blue-soft)", wood: "var(--sun-soft)", metal: "var(--mint-soft)", fabric: "var(--violet-soft)",
  clothing: "var(--violet-soft)", electronics: "var(--mint-soft)", furniture: "var(--orange-soft)",
  packaging: "var(--sun-soft)", food_cooked: "var(--orange-soft)",
};

export default function Illo({ name, className, title }) {
  return (
    <svg viewBox="0 0 120 120" className={className} role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      {ART[name] || ART.recycle}
    </svg>
  );
}

export function Arrow() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
