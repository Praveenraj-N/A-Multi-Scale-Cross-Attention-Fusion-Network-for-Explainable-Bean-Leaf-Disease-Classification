import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import {
  BookOpen,
  ChartColumn,
  Database,
  LayoutDashboard,
  Menu,
  Network,
  ScanEye,
  ScanLine,
  TriangleAlert,
  X
} from "lucide-react";
import StatusBadge from "../components/StatusBadge";
import { useHealth } from "../hooks/useHealth";
import { USE_MOCK } from "../services/api";

export const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/predict", label: "Disease Prediction", icon: ScanLine },
  { to: "/explainability", label: "Explainable AI", icon: ScanEye },
  { to: "/architecture", label: "Model Architecture", icon: Network },
  { to: "/results", label: "Research Results", icon: ChartColumn },
  { to: "/failure-analysis", label: "Failure Analysis", icon: TriangleAlert },
  { to: "/dataset", label: "Dataset", icon: Database },
  { to: "/about", label: "About Project", icon: BookOpen }
];

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <img src="/favicon.svg" alt="" className="size-9 rounded-lg" />
      <div className="leading-tight">
        <p className="font-display text-lg font-semibold tracking-tight text-ink">MSCAF-Net</p>
        <p className="text-xs text-ink-3">Bean leaf disease AI</p>
      </div>
    </div>
  );
}

function NavList({ onNavigate }) {
  return (
    <nav aria-label="Main">
      <ul className="space-y-0.5">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  isActive ? "bg-raised font-medium text-ink" : "text-ink-2 hover:bg-raised/60 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`size-4 ${isActive ? "text-leaf" : "text-ink-3 group-hover:text-ink-2"}`} aria-hidden />
                  {label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default function AppLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const health = useHealth();
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const sidebarFooter = (
    <div className="space-y-3 border-t border-line pt-4">
      <StatusBadge health={health} compact />
      <p className="text-xs leading-relaxed text-ink-3">
        Research prototype. Predictions support, but do not replace, expert diagnosis in the field.
      </p>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-raised focus:px-4 focus:py-2">
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <div className="hidden border-r border-line bg-panel/60 lg:block">
      <aside className="sticky top-0 flex h-screen flex-col justify-between px-4 py-6">
        <div className="space-y-8">
          <div className="px-2">
            <Brand />
          </div>
          <NavList />
        </div>
        {sidebarFooter}
      </aside>
      </div>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-ground/90 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <div className="flex items-center gap-2">
          <StatusBadge health={health} compact />
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="rounded-lg border border-line p-2 text-ink-2 hover:text-ink"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
          >
            <Menu className="size-5" />
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button type="button" className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} aria-label="Close navigation" />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col justify-between overflow-y-auto border-r border-line bg-panel px-4 py-5">
            <div className="space-y-6">
              <div className="flex items-center justify-between px-2">
                <Brand />
                <button type="button" onClick={() => setDrawerOpen(false)} className="rounded-lg p-2 text-ink-3 hover:text-ink" aria-label="Close navigation">
                  <X className="size-5" />
                </button>
              </div>
              <NavList onNavigate={() => setDrawerOpen(false)} />
            </div>
            {sidebarFooter}
          </div>
        </div>
      )}

      <main id="main" className="min-w-0">
        {USE_MOCK && (
          <div className="border-b border-amber/40 bg-amber-dim/40 px-4 py-2 text-center text-sm text-amber">
            Mock mode is on (VITE_USE_MOCK=true). Predictions shown are replayed sample data, not model output.
          </div>
        )}
        <div key={location.pathname} className="page-enter mx-auto max-w-[1240px] px-4 py-8 sm:px-6 lg:px-10 lg:py-12">
          <Outlet context={{ health }} />
        </div>
      </main>
    </div>
  );
}
