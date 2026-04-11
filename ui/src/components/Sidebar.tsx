import { NavLink } from "react-router-dom";
import { useHealth } from "../hooks/useHealth";

const navItems = [
  { to: "/", label: "Dashboard", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" },
  { to: "/opportunities", label: "Opportunities", icon: "M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
  { to: "/companies", label: "Companies", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
  { to: "/compare", label: "A/B Compare", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
];

export function Sidebar() {
  const { data: health } = useHealth();

  const healthColor =
    health?.status === "healthy"
      ? "bg-success"
      : health?.status === "degraded"
        ? "bg-warning"
        : "bg-error";

  return (
    <aside className="w-[var(--sidebar-width)] bg-bg-panel border-r border-border-subtle flex flex-col shrink-0 h-screen">
      {/* Logo */}
      <div className="px-5 py-5 flex items-center gap-2">
        <span className="text-h3 text-text-primary tracking-tight">terrAIn</span>
        <span className={`w-2 h-2 rounded-full ${healthColor} shrink-0`} />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 flex flex-col gap-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-caption-lg transition-colors ${
                isActive
                  ? "text-text-primary bg-surface-05 border-l-2 border-accent"
                  : "text-text-muted hover:text-text-secondary hover:bg-surface-02"
              }`
            }
          >
            <svg
              className="w-4 h-4 shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
            </svg>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border-subtle">
        <p className="text-micro text-text-subtle">
          {health ? `${health.environment}` : "connecting..."}
        </p>
      </div>
    </aside>
  );
}
