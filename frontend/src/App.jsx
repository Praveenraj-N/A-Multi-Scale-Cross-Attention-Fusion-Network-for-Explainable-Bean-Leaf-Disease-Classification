import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";
import AppLayout from "./layouts/AppLayout";

// Each page is its own chunk, so chart code only loads on pages that use it
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Predict = lazy(() => import("./pages/Predict"));
const Explainability = lazy(() => import("./pages/Explainability"));
const Architecture = lazy(() => import("./pages/Architecture"));
const Results = lazy(() => import("./pages/Results"));
const FailureAnalysis = lazy(() => import("./pages/FailureAnalysis"));
const Dataset = lazy(() => import("./pages/Dataset"));
const OutbreakMonitoring = lazy(() => import("./pages/OutbreakMonitoring"));
const About = lazy(() => import("./pages/About"));
const NotFound = lazy(() => import("./pages/NotFound"));

function page(Component) {
  return (
    <Suspense fallback={<div className="py-24 text-center text-sm text-ink-3" role="status">Loading page</div>}>
      <Component />
    </Suspense>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={page(Dashboard)} />
        <Route path="predict" element={page(Predict)} />
        <Route path="explainability" element={page(Explainability)} />
        <Route path="architecture" element={page(Architecture)} />
        <Route path="results" element={page(Results)} />
        <Route path="failure-analysis" element={page(FailureAnalysis)} />
        <Route path="dataset" element={page(Dataset)} />
        <Route path="outbreak" element={page(OutbreakMonitoring)} />
        <Route path="about" element={page(About)} />
        <Route path="*" element={page(NotFound)} />
      </Route>
    </Routes>
  );
}
