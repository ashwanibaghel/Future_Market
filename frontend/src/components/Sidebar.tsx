"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  TableProperties,
  BarChart3,
  Lightbulb,
  FlaskConical,
  ChevronLeft,
  ChevronRight,
  Activity,
  Zap,
  Database,
} from "lucide-react";

const NAV_ITEMS = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    description: "Live market overview",
  },
  {
    href: "/option-chain",
    label: "Option Chain",
    icon: TableProperties,
    description: "Full derivatives table",
  },
  {
    href: "/analytics",
    label: "Analytics",
    icon: BarChart3,
    description: "PCR, S/R, IV trends",
  },
  {
    href: "/insights",
    label: "Insights",
    icon: Lightbulb,
    description: "Generated signals feed",
  },
  {
    href: "/edge-lab",
    label: "Edge Lab",
    icon: FlaskConical,
    description: "Signal statistics & Edge",
  },
  {
    href: "/research",
    label: "ML Research",
    icon: Database,
    description: "ML dataset & labels store",
  },
];


const DEV_ITEMS = [
  {
    href: "/quant-console",
    label: "Quant Console",
    icon: FlaskConical,
    description: "Developer validation tool",
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <aside
      className={`hidden md:flex flex-col shrink-0 h-screen sticky top-0 border-r border-[#1e2433] bg-[#0d1117] transition-all duration-300 ${
        collapsed ? "w-[64px]" : "w-[220px]"
      }`}
    >
      {/* Logo */}
      <div
        className={`flex items-center gap-3 px-4 py-5 border-b border-[#1e2433] ${
          collapsed ? "justify-center" : ""
        }`}
      >
        <div className="shrink-0 w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-600/30 animate-glow">
          <Zap className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div>
            <span className="text-sm font-black tracking-tight text-slate-100">OI Lens</span>
            <span className="block text-[9px] font-bold text-indigo-400 tracking-widest uppercase">
              Intelligence
            </span>
          </div>
        )}
      </div>

      {/* Nav Items */}
      <nav className="flex-1 flex flex-col gap-1 p-2 pt-4 overflow-y-auto">
        {/* Label */}
        {!collapsed && (
          <span className="text-[9px] font-black text-slate-600 uppercase tracking-[0.15em] px-2 mb-1">
            Markets
          </span>
        )}

        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all relative ${
                active
                  ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/20"
                  : "text-slate-500 hover:text-slate-200 hover:bg-[#131920] border border-transparent"
              } ${collapsed ? "justify-center" : ""}`}
            >
              {/* Active indicator bar */}
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-indigo-400 rounded-r-full" />
              )}
              <Icon
                className={`shrink-0 w-4.5 h-4.5 transition-transform group-hover:scale-110 ${
                  active ? "text-indigo-400" : ""
                }`}
              />
              {!collapsed && (
                <span className="font-semibold tracking-tight">{item.label}</span>
              )}
            </Link>
          );
        })}

        {/* Divider */}
        <div className="my-3 border-t border-[#1e2433]" />

        {/* Dev section */}
        {!collapsed && (
          <span className="text-[9px] font-black text-slate-600 uppercase tracking-[0.15em] px-2 mb-1">
            Developer
          </span>
        )}
        {DEV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all relative ${
                active
                  ? "bg-violet-600/10 text-violet-300 border border-violet-500/20"
                  : "text-slate-600 hover:text-slate-400 hover:bg-[#131920] border border-transparent"
              } ${collapsed ? "justify-center" : ""}`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-violet-400 rounded-r-full" />
              )}
              <Icon
                className={`shrink-0 w-4.5 h-4.5 transition-transform group-hover:scale-110 ${
                  active ? "text-violet-400" : ""
                }`}
              />
              {!collapsed && (
                <span className="font-semibold tracking-tight">{item.label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="p-3 border-t border-[#1e2433]">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-slate-600 hover:text-slate-300 hover:bg-[#131920] transition-all text-xs font-medium ${
            collapsed ? "justify-center" : ""
          }`}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
