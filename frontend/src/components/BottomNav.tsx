"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, TableProperties, BarChart3, Lightbulb, FlaskConical, Database } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/option-chain", label: "Chain", icon: TableProperties },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/insights", label: "Insights", icon: Lightbulb },
  { href: "/edge-lab", label: "Edge Lab", icon: FlaskConical },
  { href: "/research", label: "Research", icon: Database },
];


export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 bg-[#0d1117]/95 backdrop-blur-md border-t border-[#1e2433] safe-area-bottom">
      <div className="flex items-center justify-around px-2 py-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all ${
                active ? "text-indigo-400" : "text-slate-600 hover:text-slate-400"
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className={`text-[9px] font-bold tracking-wide ${active ? "text-indigo-400" : ""}`}>
                {item.label}
              </span>
              {active && (
                <span className="w-1 h-1 bg-indigo-400 rounded-full" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
