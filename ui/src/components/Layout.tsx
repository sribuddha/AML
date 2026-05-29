import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import Toaster from "./Toaster";
import type { PaginatedResponse } from "../types";

function isOpsActive(pathname: string) {
  return pathname === "/operations" || pathname.startsWith("/operations/");
}

function NavItem({ to, label, icon, badge }: { to: string; label: string; icon: string; badge?: number }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? "bg-blue-50 text-blue-700 border-l-4 border-blue-600 -ml-3 pl-[11px]"
            : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
        }`
      }
    >
      <span className="text-lg">{icon}</span>
      <span>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="ml-auto bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </NavLink>
  );
}

export default function Layout() {
  const [pendingCount, setPendingCount] = useState(0);
  const [opsExpanded, setOpsExpanded] = useState(true);
  const location = useLocation();

  useEffect(() => {
    const load = () => {
      api.get<PaginatedResponse<unknown>>("/api/sar", { status: "pending_review", per_page: 1 })
        .then((data) => setPendingCount(data.total))
        .catch(() => {});
    };
    load();
    const handler = () => load();
    window.addEventListener("sar-reviewed", handler);
    return () => window.removeEventListener("sar-reviewed", handler);
  }, [location.pathname]);

  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">
        <div className="px-6 py-5 border-b border-slate-200">
          <Link to="/" className="text-lg font-bold text-slate-800 hover:text-blue-600 transition-colors">AML Monitor</Link>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {/* 1. Compliance */}
          <NavItem to="/compliance" label="Compliance" icon="🛡️" badge={pendingCount} />

          {/* 2. Operations — collapsible */}
          <div>
            <button
              onClick={() => setOpsExpanded(v => !v)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left ${
                isOpsActive(location.pathname)
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
              }`}
            >
              <span className="text-lg">📤</span>
              <span className="flex-1">Operations</span>
              <span className="text-xs text-slate-400">{opsExpanded ? "▼" : "▶"}</span>
            </button>
            {opsExpanded && (
              <div className="ml-4 mt-0.5 space-y-0.5">
                <NavLink
                  to="/operations"
                  end
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700 border-l-4 border-blue-600 -ml-3 pl-[9px]"
                        : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                    }`
                  }
                >
                  <span className="text-xs w-4 text-center">↑</span>
                  <span>Upload</span>
                </NavLink>
                <NavLink
                  to="/operations/rules"
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700 border-l-4 border-blue-600 -ml-3 pl-[9px]"
                        : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
                    }`
                  }
                >
                  <span className="text-xs w-4 text-center">⚙</span>
                  <span>Rules</span>
                </NavLink>
              </div>
            )}
          </div>

          {/* 3. Customers */}
          <NavItem to="/customers" label="Customers" icon="👥" />

          {/* 4. Transactions */}
          <NavItem to="/transactions" label="Transactions" icon="📋" />

          {/* Separator + Test Data Generator */}
          <hr className="border-slate-100 my-2" />
          <NavItem to="/test" label="Test Data Generator" icon="🧪" />
        </nav>
        <div className="px-3 py-4 border-t border-slate-200">
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <span className="text-lg">📄</span>
            <span>API Docs</span>
          </a>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="px-8 py-6">
          <Outlet />
        </div>
        <Toaster />
      </main>
    </div>
  );
}
