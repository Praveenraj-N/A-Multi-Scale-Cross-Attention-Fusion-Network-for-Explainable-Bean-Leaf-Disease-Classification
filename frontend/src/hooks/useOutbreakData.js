import { useCallback, useEffect, useRef, useState } from "react";
import { filtersToParams } from "../data/outbreak";
import { getAccess, getHistory, getMapData } from "../services/outbreakApi";

// Loads the map data and history for the current filters. Each load cancels the
// previous in-flight request, and failures keep the last good data visible.
export function useOutbreakData(filters, accessKey) {
  const [state, setState] = useState({ status: "loading", data: null, history: null, historyError: null, error: null });
  const [tick, setTick] = useState(0);
  const controller = useRef(null);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  const filterKey = JSON.stringify(filters);

  useEffect(() => {
    controller.current?.abort();
    const ctl = new AbortController();
    controller.current = ctl;
    setState((s) => ({ ...s, status: "loading", error: null }));

    // Selecting no disease or no verification status matches nothing: skip the request
    if (filters.diseases.length === 0 || filters.verification.length === 0) {
      setState((s) => ({
        ...s,
        status: "ready",
        data: { observations: [], plantations: [], truncated: {}, summary: {}, weather: { status: "not_requested" } },
        history: null
      }));
      return () => ctl.abort();
    }

    (async () => {
      const mapParams = filtersToParams(filters);
      const histParams = filtersToParams(filters, { includeRisk: false });
      histParams.delete("risk_category");
      histParams.delete("radius_km");
      histParams.delete("verification_status"); // history reports confirmed vs unverified itself

      const [map, hist] = await Promise.allSettled([
        getMapData(mapParams, { signal: ctl.signal }),
        getHistory(histParams, { signal: ctl.signal })
      ]);
      if (ctl.signal.aborted) return;

      setState((prev) => ({
        status: map.status === "fulfilled" ? "ready" : "error",
        data: map.status === "fulfilled" ? map.value : prev.data,
        error: map.status === "rejected" ? map.reason : null,
        history: hist.status === "fulfilled" ? hist.value : prev.history,
        historyError: hist.status === "rejected" ? hist.reason : null
      }));
    })();

    return () => ctl.abort();
    // filterKey stands in for the filters object; accessKey/tick re-trigger on key change and manual refresh
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey, accessKey, tick]);

  return { ...state, refresh };
}

export function useAccess(accessKey) {
  const [state, setState] = useState({ status: "loading", access: null, error: null });

  useEffect(() => {
    const ctl = new AbortController();
    setState((s) => ({ ...s, status: "loading" }));
    getAccess({ signal: ctl.signal })
      .then((access) => setState({ status: "ready", access, error: null }))
      .catch((error) => {
        if (error.name !== "AbortError") setState({ status: "error", access: null, error });
      });
    return () => ctl.abort();
  }, [accessKey]);

  return state;
}
