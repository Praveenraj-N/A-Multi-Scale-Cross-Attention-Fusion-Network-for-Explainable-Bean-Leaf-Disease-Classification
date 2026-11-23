import { createRef } from "react";
import { MemoryRouter } from "react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MapFilters from "../components/outbreak/MapFilters";
import MapLegend from "../components/outbreak/MapLegend";
import ObservationForm from "../components/outbreak/ObservationForm";
import OutbreakMap from "../components/outbreak/OutbreakMap";
import SummaryCards from "../components/outbreak/SummaryCards";
import OutbreakMonitoring from "../pages/OutbreakMonitoring";
import { DEFAULT_FILTERS, RISK_CATEGORIES, escapeHtml, filtersToParams, parseCoordinate } from "../data/outbreak";

vi.mock("../services/outbreakApi", async (importOriginal) => ({
  ...(await importOriginal()),
  createObservation: vi.fn(),
  getAccess: vi.fn(),
  getMapData: vi.fn(),
  getHistory: vi.fn(),
  getNearbyPlantations: vi.fn(),
  getRisk: vi.fn()
}));

import * as api from "../services/outbreakApi";

const obs = (over = {}) => ({
  id: "o1", disease: "bean_rust", confidence: 0.93, observed_at: "2026-05-31T12:00:00Z", crop_type: "common_bean",
  verification_status: "unverified", detection_source: "model_detection", plantation_alias: null, latitude: 12.9, longitude: 77.6,
  coordinates_precise: true, notes: null, ...over
});
const plantation = (over = {}) => ({
  id: "p1", alias: "PL-ABC123", crop_type: "common_bean", latitude: 12.95, longitude: 77.65, name: null,
  risk: { overall: { category: "high", category_label: "High", score: 61, disease_label: "Bean rust" } }, ...over
});

describe("helpers", () => {
  it("validates coordinates", () => {
    expect(parseCoordinate("12.5", "lat")).toEqual({ value: 12.5 });
    expect(parseCoordinate("91", "lat").error).toMatch(/between -90 and 90/);
    expect(parseCoordinate("-181", "lon").error).toMatch(/between -180 and 180/);
    expect(parseCoordinate("abc", "lat").error).toMatch(/number/);
    expect(parseCoordinate("", "lon").error).toMatch(/required/);
  });

  it("escapes HTML so notes cannot inject markup into popups", () => {
    expect(escapeHtml(`<img src=x onerror="alert(1)">&'`)).toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;");
  });

  it("turns filters into API query parameters", () => {
    const p = filtersToParams({ ...DEFAULT_FILTERS, diseases: ["bean_rust"], risk: ["high"], crop: " common_bean ", dateFrom: "2026-05-01", radiusKm: 12 });
    expect(p.getAll("disease")).toEqual(["bean_rust"]);
    expect(p.getAll("verification_status")).toEqual(["confirmed", "unverified"]);
    expect(p.getAll("risk_category")).toEqual(["high"]);
    expect(p.get("crop_type")).toBe("common_bean");
    expect(p.get("radius_km")).toBe("12");
    expect(p.get("date_from")).toBe(new Date("2026-05-01T00:00:00").toISOString()); // start of the local day
    expect(filtersToParams(DEFAULT_FILTERS).has("disease")).toBe(false); // all diseases = no filter
  });
});

describe("MapLegend", () => {
  it("lists every risk category with a text label and glyph, and distinguishes detections from predicted risk", () => {
    render(<MapLegend />);
    RISK_CATEGORIES.forEach((c) => expect(screen.getByText(c.label)).toBeInTheDocument());
    expect(screen.getByText(/Confirmed disease detection/)).toBeInTheDocument();
    expect(screen.getByText(/Unverified model detection/)).toBeInTheDocument();
    expect(screen.getByText(/not verified infections/)).toBeInTheDocument();
    expect(screen.getByText(/not a model of how disease spreads/)).toBeInTheDocument();
  });
});

describe("MapFilters", () => {
  it("emits changes for disease, verification, risk, crop, dates and radius", async () => {
    const onChange = vi.fn();
    render(<MapFilters filters={DEFAULT_FILTERS} onChange={onChange} onReset={vi.fn()} />);

    await userEvent.click(screen.getByRole("checkbox", { name: "Bean rust" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, diseases: ["angular_leaf_spot", "healthy"] });

    await userEvent.click(screen.getByRole("checkbox", { name: "High priority" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, risk: ["high"] });

    await userEvent.click(screen.getByRole("checkbox", { name: "Confirmed" }));
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, verification: ["unverified"] });

    await userEvent.type(screen.getByLabelText("Crop type"), "m");
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_FILTERS, crop: "m" });

    screen.getByLabelText("From").focus();
    await userEvent.type(screen.getByLabelText("From"), "2026-05-01");
    expect(onChange).toHaveBeenCalled();
  });

  it("warns on an inverted date range and disables reset at defaults", () => {
    const { rerender } = render(<MapFilters filters={DEFAULT_FILTERS} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeDisabled();
    rerender(<MapFilters filters={{ ...DEFAULT_FILTERS, dateFrom: "2026-06-02", dateTo: "2026-06-01" }} onChange={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/start date is after the end date/);
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeEnabled();
  });
});

describe("SummaryCards", () => {
  it("shows real numbers and an explicit unavailable state instead of inventing metrics", () => {
    render(<SummaryCards summary={{ reported_detections: 7, plantations_registered: 3, plantations_requiring_inspection: null, high_priority_locations: null, recent_detections_7d: 2 }} />);
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getAllByText(/Not available/)).toHaveLength(2);
  });
});

describe("OutbreakMap", () => {
  beforeEach(() => {
    // jsdom has no layout: give elements a size so Leaflet computes a viewport and draws markers
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(500);
  });

  it("renders a marker per observation and plantation with accessible labels", () => {
    // Co-located items may be grouped into clusters; either form must carry text
    const { container } = render(
      <OutbreakMap
        observations={[obs(), obs({ id: "o2", verification_status: "confirmed", latitude: 12.9, longitude: 77.6 })]}
        plantations={[plantation({ latitude: 12.9, longitude: 77.6 })]}
      />
    );
    expect(screen.getByTestId("outbreak-map")).toBeInTheDocument();
    const icons = Array.from(container.querySelectorAll(".leaflet-marker-icon"));
    expect(icons.length).toBeGreaterThan(0);
    const text = icons.map((el) => `${el.getAttribute("title") ?? ""} ${el.textContent}`).join("|");
    // Clusters carry counts and a priority letter; unclustered markers carry full status text
    expect(text).toMatch(/Bean rust|High priority|observations|plantations|H/);
  });

  it("renders an empty map without markers and exposes imperative controls", () => {
    const ref = createRef();
    const { container } = render(<OutbreakMap ref={ref} observations={[]} plantations={[]} />);
    expect(container.querySelectorAll(".leaflet-marker-icon")).toHaveLength(0);
    expect(() => ref.current.resetView()).not.toThrow();
  });

  it("uses a responsive height contract for mobile and desktop", () => {
    render(<OutbreakMap observations={[]} plantations={[]} />);
    const el = screen.getByTestId("outbreak-map");
    expect(el.className).toMatch(/h-\[460px\]/);
    expect(el.className).toMatch(/md:h-\[560px\]/);
    expect(el.className).toMatch(/w-full/);
  });
});

describe("ObservationForm", () => {
  beforeEach(() => vi.clearAllMocks());

  it("asks for an access key when the user cannot write", () => {
    render(<ObservationForm plantations={[]} canWrite={false} />);
    expect(screen.getByText(/Access key needed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save observation" })).not.toBeInTheDocument();
  });

  it("blocks submission with invalid coordinates and never calls the API", async () => {
    render(<ObservationForm plantations={[]} canWrite prefill={{ disease: "bean_rust", confidence: 0.9 }} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "95");
    await userEvent.type(screen.getByLabelText("Longitude"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Save observation" }));
    expect(await screen.findByText(/Latitude must be between -90 and 90/)).toBeInTheDocument();
    expect(api.createObservation).not.toHaveBeenCalled();
  });

  it("submits a pre-filled model detection as unverified with an idempotency key", async () => {
    api.createObservation.mockResolvedValue({ id: "new" });
    const onCreated = vi.fn();
    render(<ObservationForm plantations={[]} canWrite prefill={{ disease: "bean_rust", confidence: 0.934 }} onCreated={onCreated} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "12.9");
    await userEvent.type(screen.getByLabelText("Longitude"), "77.6");
    await userEvent.click(screen.getByRole("button", { name: "Save observation" }));
    await waitFor(() => expect(api.createObservation).toHaveBeenCalledTimes(1));
    const body = api.createObservation.mock.calls[0][0];
    expect(body).toMatchObject({ disease: "bean_rust", detection_source: "model_detection", verification_status: "unverified", latitude: 12.9, longitude: 77.6, location_source: "manual_entry" });
    expect(body.confidence).toBeCloseTo(0.934);
    expect(body.client_id).toBeTruthy();
    expect(await screen.findByText("Observation saved.")).toBeInTheDocument();
    expect(onCreated).toHaveBeenCalled();
  });

  it("shows API failures such as duplicates", async () => {
    api.createObservation.mockRejectedValue(new Error("That looks like a duplicate of an existing observation."));
    render(<ObservationForm plantations={[]} canWrite prefill={{ disease: "bean_rust", confidence: 0.9 }} />);
    await userEvent.type(screen.getByLabelText("Latitude"), "1");
    await userEvent.type(screen.getByLabelText("Longitude"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Save observation" }));
    expect(await screen.findByText(/duplicate/)).toBeInTheDocument();
  });

  it("uses a registered plantation without requiring typed coordinates", async () => {
    api.createObservation.mockResolvedValue({ id: "n" });
    render(<ObservationForm plantations={[plantation()]} canWrite />);
    await userEvent.click(screen.getByText("Registered plantation"));
    await userEvent.selectOptions(screen.getByLabelText("Plantation"), "p1");
    await userEvent.type(screen.getByLabelText(/Model confidence/), "88");
    await userEvent.click(screen.getByRole("button", { name: "Save observation" }));
    await waitFor(() => expect(api.createObservation).toHaveBeenCalled());
    const body = api.createObservation.mock.calls[0][0];
    expect(body.plantation_id).toBe("p1");
    expect(body.latitude).toBeUndefined();
  });
});

describe("OutbreakMonitoring page", () => {
  beforeEach(() => vi.clearAllMocks());

  async function renderPage() {
    return render(<MemoryRouter><OutbreakMonitoring /></MemoryRouter>);
  }

  const emptyMap = {
    observations: [], plantations: [], truncated: {}, weather: { status: "not_requested" },
    summary: { reported_detections: 0, plantations_registered: 0, plantations_requiring_inspection: null, high_priority_locations: null, recent_detections_7d: 0 }
  };
  const emptyHistory = { total: 0, by_disease: {}, by_verification: {}, series: [], bucket: "day", priority_series: [], priority_note: "Priority history exists only for days on which an assessment snapshot was stored.", interpretation_note: "Counts are reports." };
  const access = { role: "public", writes_enabled: true };

  it("shows empty states, the legend, and no invented data", async () => {
    api.getAccess.mockResolvedValue(access);
    api.getMapData.mockResolvedValue(emptyMap);
    api.getHistory.mockResolvedValue(emptyHistory);
    await renderPage();
    expect(await screen.findByText(/Nothing to show for these filters/)).toBeInTheDocument();
    expect(screen.getByText("Map legend")).toBeInTheDocument();
    expect(screen.getByText(/No observations in this date range/)).toBeInTheDocument();
    expect(screen.getByText(/No plantation selected/)).toBeInTheDocument();
    expect(screen.getByText(/Priority history exists only/)).toBeInTheDocument();
    expect(screen.getByText(/Public view/)).toBeInTheDocument();
    expect(screen.getByText(/Access key needed/)).toBeInTheDocument();
  });

  it("explains an offline API", async () => {
    const offline = Object.assign(new Error("Can't reach the MSCAF-Net API at http://127.0.0.1:8000. Start the backend and try again."), { offline: true });
    api.getAccess.mockRejectedValue(offline);
    api.getMapData.mockRejectedValue(offline);
    api.getHistory.mockRejectedValue(offline);
    await renderPage();
    expect(await screen.findByText("The API is offline")).toBeInTheDocument();
    expect(screen.getAllByText(/Can't reach the MSCAF-Net API/).length).toBeGreaterThan(0);
  });

  it("warns that the environmental assessment is incomplete when weather failed", async () => {
    api.getAccess.mockResolvedValue(access);
    api.getMapData.mockResolvedValue({ ...emptyMap, weather: { status: "unavailable" } });
    api.getHistory.mockResolvedValue(emptyHistory);
    await renderPage();
    expect(await screen.findByText("Environmental assessment incomplete")).toBeInTheDocument();
  });

  it("refetches with the new filter when a disease is unchecked", async () => {
    api.getAccess.mockResolvedValue(access);
    api.getMapData.mockResolvedValue(emptyMap);
    api.getHistory.mockResolvedValue(emptyHistory);
    await renderPage();
    await screen.findByText(/Nothing to show/);
    await userEvent.click(within(screen.getByRole("form", { name: "Map filters" })).getByRole("checkbox", { name: "Healthy" }));
    await waitFor(() => {
      const last = api.getMapData.mock.calls.at(-1)[0];
      expect(last.getAll("disease")).toEqual(["angular_leaf_spot", "bean_rust"]);
    });
  });

  it("uses a responsive grid for filters and map", async () => {
    api.getAccess.mockResolvedValue(access);
    api.getMapData.mockResolvedValue(emptyMap);
    api.getHistory.mockResolvedValue(emptyHistory);
    const { container } = await renderPage();
    await screen.findByText(/Nothing to show/);
    expect(container.innerHTML).toMatch(/lg:grid-cols-\[280px_minmax\(0,1fr\)\]/);
    expect(container.innerHTML).toMatch(/grid-cols-2 gap-3 lg:grid-cols-5/);
  });
});
