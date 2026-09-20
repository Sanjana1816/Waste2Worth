import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const INK = "#17171C";
const COLLECTED = "#23875C";
const PENDING = "#F29AC2";
const BUYER = "#8EA3F4";

/** A numbered pin drawn in the app's sticker style, so no external marker images are needed. */
function pin(label, fill, done) {
  const html = `<span style="
      display:grid;place-items:center;width:30px;height:30px;border-radius:50% 50% 50% 4px;
      transform:rotate(-45deg);background:${fill};border:2.5px solid ${INK};
      box-shadow:2px 2px 0 ${INK};font:700 13px/1 Figtree,system-ui,sans-serif;color:${INK}">
      <span style="transform:rotate(45deg)">${done ? "✓" : label}</span></span>`;
  return L.divIcon({ html, className: "", iconSize: [30, 30], iconAnchor: [15, 30], popupAnchor: [0, -28] });
}

export default function TrackMap({ tracking, height = 380, onSelect }) {
  const box = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);

  useEffect(() => {
    if (!box.current || map.current) return;
    map.current = L.map(box.current, { scrollWheelZoom: false, attributionControl: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { map.current?.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    if (!map.current || !layer.current || !tracking) return;
    layer.current.clearLayers();
    const stops = tracking.stops || [];
    const points = [];

    stops.forEach((s) => {
      points.push([s.lat, s.lng]);
      L.marker([s.lat, s.lng], { icon: pin(s.stop_no, s.collected ? COLLECTED : PENDING, s.collected) })
        .addTo(layer.current)
        .bindPopup(`<b>Stop ${s.stop_no} · ${s.seller}</b><br>${s.quantity} ${s.unit} · ${s.distance_km} km from you` +
          `<br>${s.collected ? "✓ Collected" : "Waiting for pickup"}`)
        .on("click", () => onSelect?.(s));
    });

    const b = tracking.buyer;
    if (b) {
      points.push([b.lat, b.lng]);
      L.marker([b.lat, b.lng], { icon: pin("★", BUYER, false) }).addTo(layer.current)
        .bindPopup(`<b>${b.name}</b><br>Delivery point`);
    }

    if (points.length > 1) {
      L.polyline(points, { color: INK, weight: 3, opacity: .55, dashArray: "8 8" }).addTo(layer.current);
      const done = stops.filter((s) => s.collected).map((s) => [s.lat, s.lng]);
      if (done.length > 1) L.polyline(done, { color: COLLECTED, weight: 4 }).addTo(layer.current);
    }
    if (points.length) map.current.fitBounds(L.latLngBounds(points).pad(0.25));
  }, [tracking, onSelect]);

  return <div ref={box} style={{ height, width: "100%", borderRadius: 18, overflow: "hidden", border: "1px solid var(--line)" }} />;
}
