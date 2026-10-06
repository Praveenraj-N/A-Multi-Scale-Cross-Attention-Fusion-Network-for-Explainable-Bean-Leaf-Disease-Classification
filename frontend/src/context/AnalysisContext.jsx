import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// Holds the latest analysis (shared by Disease Prediction and Explainable AI)
// and a short history of recent analyses for the dashboard. Only the history
// summary (with a small thumbnail) is kept in localStorage; full results and
// Grad-CAM images stay in memory.

const HISTORY_KEY = "mscaf.recentAnalyses";
const HISTORY_LIMIT = 6;

const AnalysisContext = createContext(null);

function readHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeHistory(history) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    // Storage full or blocked: history just won't persist
  }
}

export async function makeThumbnail(src, size = 96) {
  try {
    const image = new Image();
    image.src = src;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const scale = Math.max(size / image.naturalWidth, size / image.naturalHeight);
    const w = image.naturalWidth * scale;
    const h = image.naturalHeight * scale;
    canvas.getContext("2d").drawImage(image, (size - w) / 2, (size - h) / 2, w, h);
    return canvas.toDataURL("image/jpeg", 0.7);
  } catch {
    return null;
  }
}

export function AnalysisProvider({ children }) {
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState(readHistory);

  useEffect(() => writeHistory(history), [history]);

  // Release the previous object URL when the analysis is replaced
  useEffect(() => {
    const url = current?.imageUrl;
    return () => {
      if (url?.startsWith("blob:")) URL.revokeObjectURL(url);
    };
  }, [current?.imageUrl]);

  const recordAnalysis = useCallback(async ({ result, imageUrl, fileName }) => {
    const analyzedAt = new Date().toISOString();
    const id = `${analyzedAt}-${Math.random().toString(36).slice(2, 7)}`;

    setCurrent({ id, result, imageUrl, fileName, analyzedAt });

    const thumb = await makeThumbnail(imageUrl);

    setHistory((prev) =>
      [
        {
          id,
          fileName,
          analyzedAt,
          predictedClass: result.predicted_class,
          confidence: result.confidence,
          isMock: Boolean(result.isMock),
          thumb
        },
        ...prev
      ].slice(0, HISTORY_LIMIT)
    );
  }, []);

  const clearHistory = useCallback(() => setHistory([]), []);

  const value = useMemo(
    () => ({ current, history, recordAnalysis, clearHistory, clearCurrent: () => setCurrent(null) }),
    [current, history, recordAnalysis, clearHistory]
  );

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (!context) throw new Error("useAnalysis must be used inside AnalysisProvider");
  return context;
}
