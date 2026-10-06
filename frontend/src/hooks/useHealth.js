import { useCallback, useEffect, useState } from "react";
import { getHealth, USE_MOCK } from "../services/api";

// Live backend status. Polls every 30 s so the status reflects reality.
export function useHealth(intervalMs = 30000) {
  const [state, setState] = useState({ status: "checking", data: null, error: null, checkedAt: null });

  const check = useCallback(async () => {
    if (USE_MOCK) {
      setState({ status: "mock", data: null, error: null, checkedAt: new Date() });
      return;
    }

    try {
      const data = await getHealth();
      setState({ status: data.model_loaded ? "ready" : "loading", data, error: null, checkedAt: new Date() });
    } catch (error) {
      setState({ status: "offline", data: null, error: error.message, checkedAt: new Date() });
    }
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [check, intervalMs]);

  return { ...state, refresh: check };
}
