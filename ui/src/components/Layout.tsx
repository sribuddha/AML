import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
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
  const [apiKeyRequired, setApiKeyRequired] = useState<boolean | null>(null);
  const [opsExpanded, setOpsExpanded] = useState(true);
  const location = useLocation();

  useEffect(() => {
    api.get<PaginatedResponse<unknown>>("/api/sar", { status: "pending_review", per_page: 1 })
      .then((data) => {
        setPendingCount(data.total);
        setApiKeyRequired(false);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) {
          setApiKeyRequired(true);
        } else {
          setApiKeyRequired(false);
        }
      });
  }, [location.pathname]);

  const isLocked = apiKeyRequired === true;
  const inSettings = location.pathname === "/settings";

  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">
        <div className="px-6 py-5 border-b border-slate-200">
          <Link to="/" className="text-lg font-bold text-slate-800 hover:text-blue-600 transition-colors">
            AML Monitor
          </Link>
        </div>

        {!isLocked ? (
          <>
            <nav className="flex-1 px-3 py-4 space-y-1">
              <NavItem to="/compliance" label="Compliance" icon="🛡️" badge={pendingCount} />

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

              <NavItem to="/customers" label="Customers" icon="👥" />
              <NavItem to="/transactions" label="Transactions" icon="📋" />

              <hr className="border-slate-100 my-2" />
              <NavItem to="/test" label="Test Data Generator" icon="🧪" />
            </nav>

            <div className="px-3 py-4 border-t border-slate-200">
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-blue-50 text-blue-700 border-l-4 border-blue-600 -ml-3 pl-[11px]"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
                  }`
                }
              >
                <span className="text-lg">⚙️</span>
                <span>Settings</span>
              </NavLink>
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
          </>
        ) : (
          <>
            <nav className="flex-1 px-3 py-4">
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-blue-50 text-blue-700 border-l-4 border-blue-600 -ml-3 pl-[11px]"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
                  }`
                }
              >
                <span className="text-lg">⚙️</span>
                <span>Settings</span>
              </NavLink>
              <a
                href="/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors mt-1"
              >
                <span className="text-lg">📄</span>
                <span>API Docs</span>
              </a>
            </nav>
          </>
        )}
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="px-8 py-6">
          {isLocked && !inSettings ? (
            <div className="flex items-center justify-center h-full min-h-[60vh]">
              <div className="text-center max-w-md">
                <div className="text-5xl mb-4">🔒</div>
                <h2 className="text-xl font-bold text-slate-800 mb-2">API Key Required</h2>
                <p className="text-sm text-slate-500 mb-6">
                  The server requires an API key. Go to Settings to enter your key.
                </p>
                <Link
                  to="/settings"
                  className="inline-flex px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Go to Settings
                </Link>
              </div>
            </div>
          ) : (
            <Outlet />
          )}
        </div>
        <Toaster />
      </main>
    </div>
  );
}
