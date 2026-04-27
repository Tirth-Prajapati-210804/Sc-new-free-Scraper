import {
  History,
  LayoutDashboard,
  LogOut,
  Plane,
  Table,
  Users,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { cn } from "../../utils/cn";

const BASE_NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/explorer", icon: Table, label: "Data Explorer" },
  { to: "/logs", icon: History, label: "Collection Logs" },
];

export function Sidebar() {
  const { user, logout } = useAuth();

  const navItems = [
    ...BASE_NAV,
    ...(user?.role === "admin"
      ? [
        {
          to: "/users",
          icon: Users,
          label: "User Management",
        },
      ]
      : []),
  ];

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[220px] shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col">
      {/* Brand */}
      <div className="border-b border-slate-200 px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-600 to-violet-600 shadow-[0_10px_26px_-14px_rgba(79,70,229,0.75)]">
            <Plane className="h-4.5 w-4.5 text-white" />
          </div>

          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">
              AntiGravity
            </p>

            <p className="truncate text-[15px] font-bold leading-tight text-slate-900">
              Flight Tracker
            </p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">
          Navigation
        </p>

        <nav
          aria-label="Main navigation"
          className="mt-2.5 space-y-1"
        >
          {navItems.map(
            ({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-all",
                    isActive
                      ? "bg-indigo-50 text-brand-700"
                      : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <div
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition",
                        isActive
                          ? "bg-white text-brand-700 ring-1 ring-brand-100"
                          : "bg-slate-100 text-slate-400 group-hover:bg-white group-hover:text-slate-700 group-hover:ring-1 group-hover:ring-slate-200"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>

                    <span className="truncate">
                      {label}
                    </span>
                  </>
                )}
              </NavLink>
            )
          )}
        </nav>
      </div>

      {/* Footer */}
      <div className="border-t border-slate-200 p-4">
        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-3">
          <p className="truncate text-sm font-semibold text-slate-900">
            {user?.full_name}
          </p>

          <p className="mt-0.5 truncate text-xs text-slate-400">
            {user?.email}
          </p>

          <button
            onClick={logout}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-500 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </div>
    </aside>
  );
}
