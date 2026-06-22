"use client";

import React, { useState } from "react";
import { Activity, Clock } from "lucide-react";

interface TimelineItem {
  timestamp: string;
  spot_price: number;
  market_state: string;
  strength: string;
  pcr: number;
  insights?: string[];
}

interface MarketStateTimelineProps {
  timeline?: TimelineItem[];
}

const STATE_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  "LONG BUILD-UP": { bg: "bg-emerald-500 hover:bg-emerald-400", text: "text-emerald-400", border: "border-emerald-500/30", label: "Long Build-Up" },
  "SHORT BUILD-UP": { bg: "bg-rose-500 hover:bg-rose-400", text: "text-rose-400", border: "border-rose-500/30", label: "Short Build-Up" },
  "SHORT COVERING": { bg: "bg-indigo-500 hover:bg-indigo-400", text: "text-indigo-400", border: "border-indigo-500/30", label: "Short Covering" },
  "LONG UNWINDING": { bg: "bg-amber-500 hover:bg-amber-400", text: "text-amber-400", border: "border-amber-500/30", label: "Long Unwinding" },
  "NEUTRAL": { bg: "bg-slate-600 hover:bg-slate-500", text: "text-slate-400", border: "border-slate-600/30", label: "Neutral" },
};

export default function MarketStateTimeline({ timeline = [] }: MarketStateTimelineProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!timeline || timeline.length === 0) {
    return (
      <div className="w-full bg-[#0d1117]/80 border border-[#1e2433] rounded-2xl p-4 text-center text-slate-500 text-xs">
        No state timeline data available.
      </div>
    );
  }

  // Ensure we display exactly up to 15 items
  const items = timeline.slice(-15);

  // Backend stores UTC timestamps without 'Z' suffix — append it so browser parses correctly as UTC
  const toUTC = (isoString?: string) => {
    if (!isoString) return null;
    // If already has timezone info, use as-is; otherwise treat as UTC
    const s = isoString.trim();
    if (s.endsWith("Z") || s.includes("+") || s.match(/\d{2}:\d{2}:\d{2}-/)) return new Date(s);
    return new Date(s + "Z");
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "—";
    try {
      const d = toUTC(isoString);
      if (!d) return "—";
      return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
    } catch (e) {
      return isoString;
    }
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "—";
    try {
      const d = toUTC(isoString);
      if (!d) return "—";
      return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", timeZone: "Asia/Kolkata" });
    } catch (e) {
      return isoString;
    }
  };

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-2xl relative flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-400" />
          Market State Timeline (Last {items.length} Snapshots)
        </h3>
        <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
          <Clock className="w-3.5 h-3.5" />
          Sequence Flow
        </div>
      </div>

      {/* Timeline Bar Track */}
      <div className="relative">
        <div className="flex w-full items-center gap-1.5 h-6">
          {items.map((item, idx) => {
            const conf = STATE_COLORS[item.market_state] || STATE_COLORS["NEUTRAL"];
            const isHovered = hoveredIndex === idx;

            return (
              <div
                key={idx}
                className={`flex-1 h-full rounded-md cursor-pointer transition-all duration-200 relative ${conf.bg} ${
                  isHovered ? "scale-y-110 shadow-lg shadow-white/5 ring-1 ring-white/20" : "opacity-90 hover:opacity-100"
                }`}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
              />
            );
          })}
        </div>

        {/* Start / End Timestamp indicators */}
        <div className="flex justify-between mt-2 px-0.5 text-[9px] text-slate-500 font-mono font-bold uppercase tracking-wider">
          <span>{formatTime(items[0]?.timestamp)} ({formatDate(items[0]?.timestamp)})</span>
          <span>{formatTime(items[items.length - 1]?.timestamp)} (Live)</span>
        </div>

        {/* Hover Tooltip Container */}
        {hoveredIndex !== null && items[hoveredIndex] && (() => {
          const hoveredPct = ((hoveredIndex + 0.5) / items.length) * 100;
          let tooltipStyle: React.CSSProperties = {
            left: `${hoveredPct}%`,
            transform: "translateX(-50%)",
            top: "34px",
          };
          let arrowStyle: React.CSSProperties = {
            left: "50%",
            transform: "translateX(-50%) rotate(45deg)",
          };

          if (hoveredIndex < 3) {
            tooltipStyle = {
              left: "0px",
              top: "34px",
            };
            arrowStyle = {
              left: `${hoveredPct}%`,
              transform: "translateX(-50%) rotate(45deg)",
            };
          } else if (hoveredIndex > items.length - 4) {
            tooltipStyle = {
              right: "0px",
              left: "auto",
              top: "34px",
            };
            arrowStyle = {
              right: `${100 - hoveredPct}%`,
              left: "auto",
              transform: "translateX(50%) rotate(45deg)",
            };
          }

          return (
            <div 
              className="absolute z-30 w-[240px] bg-[#090d16] border border-slate-700/80 rounded-xl p-4 shadow-2xl backdrop-blur-lg animate-fadeIn"
              style={tooltipStyle}
            >
              {/* Small arrow pointing up */}
              <div 
                className="absolute -top-1.5 w-3 h-3 bg-[#090d16] border-l border-t border-slate-700/80" 
                style={arrowStyle}
              />

              <div className="flex flex-col gap-2">
                {/* Header */}
                <div className="flex justify-between items-center border-b border-slate-800 pb-1.5">
                  <span className="text-[10px] text-slate-400 font-mono font-semibold">
                    {formatTime(items[hoveredIndex].timestamp)} ({formatDate(items[hoveredIndex].timestamp)})
                  </span>
                  <span className={`text-[8px] font-black uppercase tracking-wider px-2 py-0.5 rounded border ${
                    items[hoveredIndex].strength === "HIGH" ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/10" :
                    items[hoveredIndex].strength === "MEDIUM" ? "text-amber-400 border-amber-500/20 bg-amber-500/10" :
                    "text-slate-400 border-slate-700/20 bg-slate-800/40"
                  }`}>
                    {items[hoveredIndex].strength}
                  </span>
                </div>

                {/* State */}
                <div>
                  <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest block">
                    State
                  </span>
                  <span className={`text-xs font-black uppercase ${STATE_COLORS[items[hoveredIndex].market_state]?.text || "text-slate-300"}`}>
                    {items[hoveredIndex].market_state}
                  </span>
                </div>

                {/* Spot & PCR Grid */}
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div>
                    <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest block">
                      Spot Price
                    </span>
                    <span className="text-xs font-bold font-mono text-slate-200">
                      ₹{items[hoveredIndex].spot_price.toLocaleString("en-IN", { minimumFractionDigits: 1 })}
                    </span>
                  </div>
                  <div>
                    <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest block">
                      PCR
                    </span>
                    <span className="text-xs font-bold font-mono text-slate-200">
                      {items[hoveredIndex].pcr.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-2 border-t border-slate-800/50">
        {Object.entries(STATE_COLORS).map(([stateKey, config]) => (
          <div key={stateKey} className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${config.bg.split(" ")[0]}`} />
            <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">{config.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
