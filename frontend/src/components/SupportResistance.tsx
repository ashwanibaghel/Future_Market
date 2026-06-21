"use client";

import React from "react";
import { Shield, ShieldAlert, Award } from "lucide-react";

interface SupportResistanceProps {
  spotPrice: number;
  primarySupport?: number | null;
  secondarySupport?: number | null;
  primaryResistance?: number | null;
  secondaryResistance?: number | null;
}

export default function SupportResistance({
  spotPrice,
  primarySupport,
  secondarySupport,
  primaryResistance,
  secondaryResistance
}: SupportResistanceProps) {
  
  // Safe fallbacks for optional parameters
  const s1 = primarySupport ?? 23900;
  const s2 = secondarySupport ?? 23800;
  const r1 = primaryResistance ?? 24100;
  const r2 = secondaryResistance ?? 24200;

  // Calculate spot position percentage on the scale
  // Let the scale go from (Secondary Support - 100) to (Secondary Resistance + 100)
  const minRange = s2 - 100;
  const maxRange = r2 + 100;
  const range = maxRange - minRange;
  
  const getPercentage = (val: number) => {
    const pct = ((val - minRange) / range) * 100;
    return Math.min(Math.max(pct, 0), 100);
  };

  const spotPct = getPercentage(spotPrice);

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-6 shadow-2xl flex flex-col gap-6">
      <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
        <Award className="w-4.5 h-4.5 text-indigo-400" />
        Support & Resistance Levels
      </h3>

      {/* Numerical Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Secondary Support */}
        <div className="bg-slate-950/40 border border-slate-850 p-3 rounded-lg flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-rose-500/80" />
          <div>
            <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">S2 (Secondary Support)</span>
            <span className="text-sm font-bold text-rose-300 font-mono">₹{s2}</span>
          </div>
        </div>

        {/* Primary Support */}
        <div className="bg-slate-950/40 border border-slate-850 p-3 rounded-lg flex items-center gap-3">
          <Shield className="w-5 h-5 text-rose-400" />
          <div>
            <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">S1 (Primary Support)</span>
            <span className="text-sm font-bold text-rose-400 font-mono">₹{s1}</span>
          </div>
        </div>

        {/* Primary Resistance */}
        <div className="bg-slate-950/40 border border-slate-850 p-3 rounded-lg flex items-center gap-3">
          <Shield className="w-5 h-5 text-indigo-400" />
          <div>
            <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">R1 (Primary Resistance)</span>
            <span className="text-sm font-bold text-indigo-400 font-mono">₹{r1}</span>
          </div>
        </div>

        {/* Secondary Resistance */}
        <div className="bg-slate-950/40 border border-slate-850 p-3 rounded-lg flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-indigo-500/80" />
          <div>
            <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">R2 (Secondary Resistance)</span>
            <span className="text-sm font-bold text-indigo-300 font-mono">₹{r2}</span>
          </div>
        </div>
      </div>

      {/* Visual Progress Scale Bar */}
      <div className="relative w-full pt-6 pb-2">
        {/* Background track */}
        <div className="h-3 w-full bg-slate-950 rounded-full border border-slate-800 relative overflow-hidden">
          {/* Support Zone (Rose glow) */}
          <div
            className="absolute h-full left-0 bg-gradient-to-r from-rose-900/40 to-rose-500/20"
            style={{ width: `${getPercentage(s1)}%` }}
          ></div>
          
          {/* Neutral corridor */}
          <div
            className="absolute h-full bg-indigo-500/10"
            style={{
              left: `${getPercentage(s1)}%`,
              width: `${getPercentage(r1) - getPercentage(s1)}%`
            }}
          ></div>

          {/* Resistance Zone (Indigo glow) */}
          <div
            className="absolute h-full right-0 bg-gradient-to-r from-indigo-500/20 to-indigo-900/40"
            style={{ left: `${getPercentage(r1)}%` }}
          ></div>
        </div>

        {/* Pin pointers */}
        {/* Support S1 Pin */}
        <div
          className="absolute -top-1.5 flex flex-col items-center"
          style={{ left: `${getPercentage(s1)}%`, transform: "translateX(-50%)" }}
        >
          <span className="w-1.5 h-6 bg-rose-500 rounded-full"></span>
          <span className="text-[8px] font-bold text-rose-500 mt-1">S1</span>
        </div>

        {/* Resistance R1 Pin */}
        <div
          className="absolute -top-1.5 flex flex-col items-center"
          style={{ left: `${getPercentage(r1)}%`, transform: "translateX(-50%)" }}
        >
          <span className="w-1.5 h-6 bg-indigo-500 rounded-full"></span>
          <span className="text-[8px] font-bold text-indigo-500 mt-1">R1</span>
        </div>

        {/* Spot Price Glow Marker */}
        <div
          className="absolute -top-3.5 flex flex-col items-center z-10 transition-all duration-500"
          style={{ left: `${spotPct}%`, transform: "translateX(-50%)" }}
        >
          <div className="bg-yellow-500 text-slate-950 text-[9px] font-black px-2 py-0.5 rounded shadow-lg shadow-yellow-500/40 tracking-wider">
            ₹{spotPrice ? spotPrice.toFixed(0) : "---"}
          </div>
          <span className="w-2.5 h-2.5 bg-yellow-400 border border-slate-950 rounded-full shadow shadow-yellow-400 animate-ping absolute top-4"></span>
          <span className="w-2 h-2 bg-yellow-400 border border-slate-950 rounded-full absolute top-4"></span>
        </div>
      </div>
    </div>
  );
}
