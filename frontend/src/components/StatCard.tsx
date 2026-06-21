"use client";

import React from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  badge?: { text: string; color: "indigo" | "emerald" | "rose" | "amber" | "slate" };
  accent?: "indigo" | "emerald" | "rose" | "amber" | "slate";
  mono?: boolean;
  icon?: React.ReactNode;
  size?: "sm" | "md" | "lg";
}

const BADGE_STYLES = {
  indigo: "bg-indigo-500/10 border-indigo-500/20 text-indigo-300",
  emerald: "bg-emerald-500/10 border-emerald-500/20 text-emerald-300",
  rose: "bg-rose-500/10 border-rose-500/20 text-rose-300",
  amber: "bg-amber-500/10 border-amber-500/20 text-amber-300",
  slate: "bg-slate-800/60 border-slate-700/40 text-slate-400",
};

const VALUE_SIZES = {
  sm: "text-xl font-bold",
  md: "text-2xl font-extrabold",
  lg: "text-3xl font-black",
};

export default function StatCard({
  label,
  value,
  subValue,
  badge,
  accent = "indigo",
  mono = false,
  icon,
  size = "md",
}: StatCardProps) {
  return (
    <div className="relative bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-3 overflow-hidden hover:border-[#2a3347] transition-colors group">
      {/* Subtle glow in corner */}
      <div
        className={`absolute top-0 right-0 w-20 h-20 rounded-full blur-[40px] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none ${
          accent === "indigo" ? "bg-indigo-500/10" :
          accent === "emerald" ? "bg-emerald-500/10" :
          accent === "rose" ? "bg-rose-500/10" :
          accent === "amber" ? "bg-amber-500/10" :
          "bg-slate-500/5"
        }`}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.15em]">
          {label}
        </span>
        {icon && (
          <span className={`text-slate-600 group-hover:${accent === "indigo" ? "text-indigo-500" : "text-slate-400"} transition-colors`}>
            {icon}
          </span>
        )}
      </div>

      {/* Value */}
      <div className="flex items-end gap-2">
        <span
          className={`${VALUE_SIZES[size]} text-slate-100 leading-none ${
            mono ? "font-mono" : ""
          }`}
        >
          {value}
        </span>
        {subValue && (
          <span className="text-xs font-medium text-slate-500 mb-0.5 pb-0.5">{subValue}</span>
        )}
      </div>

      {/* Badge */}
      {badge && (
        <div
          className={`inline-flex self-start items-center px-2 py-0.5 rounded-md border text-[10px] font-black uppercase tracking-wider ${
            BADGE_STYLES[badge.color]
          }`}
        >
          {badge.text}
        </div>
      )}
    </div>
  );
}
