import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import {
  DETECTION_COLOR,
  RISK_CATEGORIES,
  VERIFICATION_LABEL,
  escapeHtml,
  formatDateTime,
  riskMeta
} from "../../data/outbreak";
import { classLabel } from "../../data/classes";

const DEFAULT_CENTER = [15, 20];
const DEFAULT_ZOOM = 2;

// Detections: circles. Predicted risk: rounded squares with a text glyph.
// Confirmed = solid fill; unverified = hollow ring, so status never relies on colour alone.
function detectionIcon(obs) {
  const confirmed = obs.verification_status === "confirmed";
  const rejected = obs.verification_status === "rejected";
  const healthy = obs.disease === "healthy";
  const color = healthy ? "#2e9f7a" : DETECTION_COLOR;
  const fill = confirmed ? color : "rgba(13,20,17,0.85)";
  const style = `width:18px;height:18px;border-radius:50%;border:3px ${rejected ? "dotted" : confirmed ? "solid" : "dashed"} ${color};background:${fill};box-shadow:0 0 0 2px rgba(0,0,0,.45)`;
  return L.divIcon({ className: "outbreak-marker", html: `<div style="${style}"></div>`, iconSize: [18, 18], iconAnchor: [9, 9] });
}

function plantationIcon(plantation, selected) {
  const meta = riskMeta(plantation.risk?.overall?.category ?? "insufficient_data");
  const ring = selected ? "box-shadow:0 0 0 3px #ffffff,0 0 0 5px rgba(0,0,0,.6)" : "box-shadow:0 0 0 2px rgba(0,0,0,.5)";
  const style = `width:26px;height:26px;border-radius:7px;background:${meta.color};color:${meta.text};display:grid;place-items:center;font:700 11px/1 system-ui,sans-serif;border:2px solid rgba(0,0,0,.55);${ring}`;
  return L.divIcon({
    className: "outbreak-marker",
    html: `<div style="${style}">${escapeHtml(meta.short)}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13]
  });
}

function clusterIcon(kind) {
  return (cluster) => {
    const children = cluster.getAllChildMarkers();
    const count = children.length;
    if (kind === "plantation") {
      const order = RISK_CATEGORIES.map((c) => c.id); // most severe first
      const worst = children.reduce((best, m) => Math.min(best, order.indexOf(m.options.priority ?? "insufficient_data")), order.length - 1);
      const meta = riskMeta(order[worst]);
      return L.divIcon({
        className: "outbreak-marker",
        html: `<div style="min-width:34px;height:34px;padding:0 6px;border-radius:9px;background:${meta.color};color:${meta.text};display:grid;place-items:center;font:700 12px system-ui,sans-serif;border:2px solid rgba(0,0,0,.55)" title="${count} plantations, highest priority: ${escapeHtml(meta.label)}">${count} ${escapeHtml(meta.short)}</div>`,
        iconSize: [38, 34]
      });
    }
    return L.divIcon({
      className: "outbreak-marker",
      html: `<div style="width:34px;height:34px;border-radius:50%;background:rgba(229,72,77,.25);border:3px solid ${DETECTION_COLOR};color:#fff;display:grid;place-items:center;font:700 12px system-ui,sans-serif" title="${count} observations">${count}</div>`,
      iconSize: [34, 34]
    });
  };
}

function observationPopup(obs) {
  const rows = [
    ["Disease", classLabel(obs.disease)],
    ["Observed", formatDateTime(obs.observed_at)],
    ["Model confidence", obs.confidence == null ? "Not recorded" : `${(obs.confidence * 100).toFixed(1)}%`],
    ["Status", VERIFICATION_LABEL[obs.verification_status] ?? obs.verification_status],
    ["Source", obs.detection_source === "manual_report" ? "Manual report" : "Model detection"],
    ["Crop", obs.crop_type.replace(/_/g, " ")]
  ];
  if (obs.plantation_alias) rows.push(["Plantation", obs.plantation_alias]);
  if (obs.notes) rows.push(["Notes", obs.notes]);
  if (!obs.coordinates_precise) rows.push(["Location", "Approximate (rounded for privacy)"]);
  const heading = obs.disease === "healthy" ? "Healthy classification" : "Reported disease detection";
  const note =
    obs.verification_status === "confirmed"
      ? ""
      : `<p class="op-note">Unverified: a model output, not a confirmed infection.</p>`;
  return `<div class="op"><strong>${escapeHtml(heading)}</strong><dl>${rows
    .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`)
    .join("")}</dl>${note}</div>`;
}

function plantationPopup(p) {
  const overall = p.risk?.overall;
  const meta = riskMeta(overall?.category ?? "insufficient_data");
  const lines = [
    `<dt>Crop</dt><dd>${escapeHtml(p.crop_type.replace(/_/g, " "))}</dd>`,
    `<dt>Inspection priority</dt><dd>${escapeHtml(overall ? meta.label : "Not assessed")}</dd>`
  ];
  if (overall?.score != null) lines.push(`<dt>Priority index</dt><dd>${overall.score.toFixed(0)} / 100 (${escapeHtml(overall.disease_label)})</dd>`);
  if (p.name) lines.push(`<dt>Name</dt><dd>${escapeHtml(p.name)}</dd>`);
  return `<div class="op"><strong>${escapeHtml(p.alias)}</strong><dl>${lines.join("")}</dl><p class="op-note">Predicted risk, not verified infection. Select for details.</p></div>`;
}

const OutbreakMap = forwardRef(function OutbreakMap(
  { observations, plantations, selectedPlantationId, onSelectPlantation, searchArea, userLocation, pickMode, onPick },
  ref
) {
  const containerRef = useRef(null);
  const state = useRef({});
  const callbacks = useRef({});
  callbacks.current = { onSelectPlantation, onPick, pickMode };

  // Create the map once
  useEffect(() => {
    const map = L.map(containerRef.current, { center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM, worldCopyJump: true, minZoom: 2 });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const detections = L.markerClusterGroup({ maxClusterRadius: 45, iconCreateFunction: clusterIcon("detection"), showCoverageOnHover: false });
    const plants = L.markerClusterGroup({ maxClusterRadius: 30, iconCreateFunction: clusterIcon("plantation"), showCoverageOnHover: false });
    const overlays = L.layerGroup();
    map.addLayer(plants).addLayer(detections).addLayer(overlays);

    map.on("click", (e) => {
      if (callbacks.current.pickMode) callbacks.current.onPick?.({ lat: e.latlng.lat, lon: e.latlng.lng });
    });

    state.current = { map, detections, plants, overlays, fitted: false };
    // Tile layout needs a size recalculation after the container settles
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      map.remove();
      state.current = {};
    };
  }, []);

  // Detections
  useEffect(() => {
    const { detections } = state.current;
    if (!detections) return;
    detections.clearLayers();
    observations.forEach((obs) => {
      const label = `${classLabel(obs.disease)}, ${VERIFICATION_LABEL[obs.verification_status] ?? obs.verification_status}`;
      const marker = L.marker([obs.latitude, obs.longitude], { icon: detectionIcon(obs), title: label, alt: label, keyboard: true });
      marker.bindPopup(observationPopup(obs));
      detections.addLayer(marker);
    });
  }, [observations]);

  // Plantations
  useEffect(() => {
    const { plants } = state.current;
    if (!plants) return;
    plants.clearLayers();
    plantations.forEach((p) => {
      const meta = riskMeta(p.risk?.overall?.category ?? "insufficient_data");
      const label = `Plantation ${p.alias}: ${meta.label}`;
      const marker = L.marker([p.latitude, p.longitude], {
        icon: plantationIcon(p, p.id === selectedPlantationId),
        title: label,
        alt: label,
        keyboard: true,
        priority: p.risk?.overall?.category ?? "insufficient_data"
      });
      marker.bindPopup(plantationPopup(p));
      marker.on("click", () => callbacks.current.onSelectPlantation?.(p.id));
      plants.addLayer(marker);
    });
  }, [plantations, selectedPlantationId]);

  // Fit the view to the data the first time any arrives
  useEffect(() => {
    const s = state.current;
    if (!s.map || s.fitted) return;
    const points = [...observations, ...plantations].map((x) => [x.latitude, x.longitude]);
    if (points.length === 0) return;
    s.map.fitBounds(L.latLngBounds(points).pad(0.2), { maxZoom: 13 });
    s.fitted = true;
  }, [observations, plantations]);

  // Proximity-search circle + user location
  useEffect(() => {
    const { overlays } = state.current;
    if (!overlays) return;
    overlays.clearLayers();
    if (searchArea) {
      L.circle([searchArea.lat, searchArea.lon], {
        radius: searchArea.radiusKm * 1000,
        color: "#2bb3b1",
        weight: 2,
        dashArray: "6 6",
        fillColor: "#2bb3b1",
        fillOpacity: 0.07,
        interactive: false
      })
        .bindTooltip("Proximity-search area (not a model of disease spread)", { sticky: true })
        .addTo(overlays);
    }
    if (userLocation) {
      L.circleMarker([userLocation.lat, userLocation.lon], { radius: 7, color: "#ffffff", weight: 2, fillColor: "#2b7fff", fillOpacity: 1 })
        .bindTooltip("Your location")
        .addTo(overlays);
    }
  }, [searchArea, userLocation]);

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.style.cursor = pickMode ? "crosshair" : "";
  }, [pickMode]);

  useImperativeHandle(ref, () => ({
    resetView() {
      const { map } = state.current;
      if (!map) return;
      const points = [...observations, ...plantations].map((x) => [x.latitude, x.longitude]);
      if (points.length) map.fitBounds(L.latLngBounds(points).pad(0.2), { maxZoom: 13 });
      else map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    },
    flyTo(lat, lon, zoom = 12) {
      state.current.map?.flyTo([lat, lon], zoom);
    }
  }));

  return (
    <div
      ref={containerRef}
      className="outbreak-map h-[460px] w-full rounded-xl border border-line md:h-[560px]"
      role="region"
      aria-label="Interactive outbreak map. Markers are keyboard focusable; use the tables and lists beside the map for a text view."
      data-testid="outbreak-map"
    />
  );
});

export default OutbreakMap;
