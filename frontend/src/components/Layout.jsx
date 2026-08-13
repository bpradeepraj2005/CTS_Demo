import { useEffect, useState } from "react";
import {
  Bell,
  ChevronDown,
  CircleDot,
  LogOut,
  Menu,
  PauseCircle,
  ShieldCheck,
  X,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Layout({ portal, nav }) {
  const { user, logout, refresh } = useAuth();
  const navigate = useNavigate();

  const [busy, setBusy] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const isPayer = portal === "payer";

  const accent = isPayer ? "payer" : "provider";

  const mark = isPayer ? "bg-payer" : "bg-provider";

  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  const toggleAvailability = async () => {
    if (!user) return;

    setBusy(true);

    try {
      await api.patch("/api/auth/availability", {
        is_available: !user.is_available,
        unavailable_reason: user.is_available
          ? "On another case"
          : null,
      });

      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-40 border-b border-rule bg-white/90 backdrop-blur-xl">
        <div className="flex h-16 items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              className="grid h-10 w-10 place-items-center rounded-lg border border-rule bg-white text-ink-2 lg:hidden"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={18} />
            </button>

            <div className="flex items-center gap-3">
              <div
                className={`grid h-10 w-10 place-items-center rounded-xl text-white shadow-lg ${
                  isPayer
                    ? "bg-payer shadow-payer/20"
                    : "bg-provider shadow-provider/20"
                }`}
              >
                <ShieldCheck size={20} />
              </div>

              <div className="hidden sm:block">
                <div className="text-sm font-bold tracking-tight">
                  PriorAuth AI
                </div>

                <div className="text-[10px] font-medium uppercase tracking-[.12em] text-ink-3">
                  {isPayer
                    ? "Payer intelligence"
                    : "Hospital management"}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isPayer && user && (
              <button
                onClick={toggleAvailability}
                disabled={busy}
                className={`hidden items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition sm:flex ${
                  user.is_available
                    ? "border-approve-line bg-approve-soft text-approve"
                    : "border-rule bg-slate-50 text-ink-2"
                }`}
              >
                {user.is_available ? (
                  <CircleDot size={14} />
                ) : (
                  <PauseCircle size={14} />
                )}

                {user.is_available
                  ? "Available"
                  : "Unavailable"}
              </button>
            )}

            <button className="grid h-10 w-10 place-items-center rounded-lg border border-rule bg-white text-ink-2 hover:bg-slate-50">
              <Bell size={17} />
            </button>

            {user && (
              <div className="hidden items-center gap-2 pl-2 sm:flex">
                <div
                  className={`grid h-9 w-9 place-items-center rounded-full text-xs font-bold text-white ${mark}`}
                >
                  {user.full_name?.charAt(0)?.toUpperCase() ||
                    "U"}
                </div>

                <div className="max-w-[150px]">
                  <div className="truncate text-xs font-semibold">
                    {user.full_name}
                  </div>

                  <div className="truncate text-[10px] text-ink-3">
                    {user.organization_name}
                  </div>
                </div>

                <ChevronDown size={14} className="text-ink-3" />
              </div>
            )}

            <button
              onClick={() => {
                logout();
                navigate("/");
              }}
              className="grid h-10 w-10 place-items-center rounded-lg border border-rule bg-white text-ink-3 hover:bg-red-50 hover:text-deny"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <div className="flex">
        <aside className="sidebar-gradient sticky top-16 hidden h-[calc(100vh-64px)] w-64 shrink-0 border-r border-rule lg:block">
          <Sidebar
            nav={nav}
            portal={portal}
            user={user}
          />
        </aside>

        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div
              className="absolute inset-0 bg-slate-950/30 backdrop-blur-sm"
              onClick={() => setMobileOpen(false)}
            />

            <aside className="relative h-full w-80 bg-white shadow-elevated">
              <div className="flex h-16 items-center justify-between border-b border-rule px-5">
                <div className="font-bold">
                  Navigation
                </div>

                <button
                  onClick={() => setMobileOpen(false)}
                  className="grid h-9 w-9 place-items-center rounded-lg border border-rule"
                >
                  <X size={17} />
                </button>
              </div>

              <Sidebar
                nav={nav}
                portal={portal}
                user={user}
                onNavigate={() => setMobileOpen(false)}
              />
            </aside>
          </div>
        )}

        <main className="min-w-0 flex-1">
          <div className="mx-auto max-w-[1500px] px-4 py-6 lg:px-8 lg:py-8">
            <div className="page-enter">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function Sidebar({
  nav,
  portal,
  user,
  onNavigate,
}) {
  const isPayer = portal === "payer";

  return (
    <div className="flex h-full flex-col px-3 py-5">
      <div className="mb-5 rounded-xl bg-slate-50 p-4">
        <div className="text-[10px] font-semibold uppercase tracking-[.13em] text-ink-3">
          Workspace
        </div>

        <div className="mt-2 text-sm font-bold">
          {isPayer
            ? "Payer operations"
            : "Hospital operations"}
        </div>

        <div className="mt-1 text-xs text-ink-3">
          {user?.organization_name || "Organization"}
        </div>
      </div>

      <nav className="space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-semibold transition ${
                  isActive
                    ? isPayer
                      ? "bg-payer-soft text-payer"
                      : "bg-provider-soft text-provider"
                    : "text-ink-2 hover:bg-slate-100 hover:text-ink"
                }`
              }
            >
              <Icon size={17} strokeWidth={1.9} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto rounded-xl border border-rule bg-white p-4">
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${
              isPayer
                ? "bg-payer"
                : "bg-provider"
            }`}
          />

          <span className="text-xs font-semibold">
            AI decision engine
          </span>
        </div>

        <p className="mt-2 text-[10px] leading-4 text-ink-3">
          Document extraction, medical necessity,
          ML scoring and audit logging enabled.
        </p>
      </div>
    </div>
  );
}