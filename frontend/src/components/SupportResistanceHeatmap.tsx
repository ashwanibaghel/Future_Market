"use client";

import React, { useMemo } from "react";
import { Flame } from "lucide-react";

interface StrikeItem {
  strike: number;
  call_oi: number;
  call_change_oi: number;
  put_oi: number;
  put_change_oi: number;
}

interface SupportResistanceHeatmapProps {
  strikes?: StrikeItem[];
  spotPrice?: number;
}

const formatNumber = (val: number) => {
  const absVal = Math.abs(val);
  let formatted = "";
  if (absVal >= 1_00_00_000) formatted = (absVal / 1_00_00_000).toFixed(2) + " Cr";
  else if (absVal >= 1_00_000) formatted = (absVal / 1_00_000).toFixed(1) + " L";
  else if (absVal >= 1_000) formatted = (absVal / 1_000).toFixed(0) + "K";
  else formatted = absVal.toString();
  
  return val < 0 ? `-${formatted}` : formatted;
};

export default function SupportResistanceHeatmap({
  strikes = [],
  spotPrice = 0,
}: SupportResistanceHeatmapProps) {
  
  // Calculate 10 closest strikes to spot, sorted descending (highest at top)
  const heatmapStrikes = useMemo(() => {
    if (!strikes || strikes.length === 0 || !spotPrice) return [];
    
    // Sort by proximity
    const sortedByProximity = [...strikes].sort(
      (a, b) => Math.abs(a.strike - spotPrice) - Math.abs(b.strike - spotPrice)
    );
    
    // Take top 10 and sort descending by strike price
    return sortedByProximity.slice(0, 10).sort((a, b) => b.strike - a.strike);
  }, [strikes, spotPrice]);

  // Find max OI in these 10 strikes to scale bars
  const maxOI = useMemo(() => {
    if (heatmapStrikes.length === 0) return 1;
    return Math.max(
      ...heatmapStrikes.map((s) => Math.max(s.call_oi, s.put_oi)),
      1
    );
  }, [heatmapStrikes]);

  if (heatmapStrikes.length === 0) {
    return (
      <div className="w-full bg-[#0d1117]/80 border border-[#1e2433] rounded-2xl p-4 text-center text-slate-500 text-xs">
        No option chain strikes data available to render S/R heatmap.
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-2xl flex flex-col gap-4">
      {/* Title */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/40">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
          <Flame className="w-4.5 h-4.5 text-amber-500 animate-pulse" />
          S/R Depth Heatmap (Change OI Overlay)
        </h3>
        <div className="flex items-center gap-3 text-[10px] font-bold uppercase tracking-wider">
          <span className="text-emerald-400">Put Support</span>
          <span className="text-slate-600">|</span>
          <span className="text-rose-400">Call Resistance</span>
        </div>
      </div>

      {/* Column Headers */}
      <div className="flex w-full text-[9px] font-black text-slate-500 uppercase tracking-wider px-1">
        <div className="w-[42%] text-right pr-4">Put OI / Change</div>
        <div className="w-[16%] text-center">Strike</div>
        <div className="w-[42%] text-left pl-4">Call OI / Change</div>
      </div>

      {/* Heatmap List */}
      <div className="flex flex-col gap-1">
        {heatmapStrikes.map((strikeItem) => {
          // Check if this is closest strike above/below spot
          const isClosest =
            Math.abs(strikeItem.strike - spotPrice) ===
            Math.min(...heatmapStrikes.map((s) => Math.abs(s.strike - spotPrice)));
            
          const putPct = (strikeItem.put_oi / maxOI) * 100;
          const callPct = (strikeItem.call_oi / maxOI) * 100;

          // Format Change OI text with signs
          const putChangeText = strikeItem.put_change_oi >= 0 
            ? `+${formatNumber(strikeItem.put_change_oi)}` 
            : formatNumber(strikeItem.put_change_oi);
            
          const callChangeText = strikeItem.call_change_oi >= 0 
            ? `+${formatNumber(strikeItem.call_change_oi)}` 
            : formatNumber(strikeItem.call_change_oi);

          return (
            <div
              key={strikeItem.strike}
              className={`flex w-full items-center py-2.5 rounded-lg border transition-all ${
                isClosest 
                  ? "bg-slate-950/70 border-slate-700/60 shadow-inner" 
                  : "bg-slate-950/25 border-transparent hover:bg-slate-950/40"
              }`}
            >
              {/* Put Side (Left) */}
              <div className="w-[42%] pr-4 text-right flex items-center justify-end gap-2 relative overflow-hidden h-6">
                {/* Put OI heat bar growing right-to-left */}
                <div
                  className="absolute right-0 top-0 bottom-0 bg-gradient-to-l from-emerald-500/12 to-emerald-500/2 border-r-2 border-emerald-500/30 rounded-l"
                  style={{ width: `${putPct}%` }}
                />
                <span className="text-[10px] font-semibold text-slate-500 z-10">
                  {putChangeText}
                </span>
                <span className="text-xs font-mono font-black text-emerald-400 z-10">
                  {formatNumber(strikeItem.put_oi)}
                </span>
              </div>

              {/* Center Strike Price */}
              <div className="w-[16%] text-center z-10 flex flex-col items-center justify-center">
                <span className={`px-2 py-0.5 rounded font-mono text-xs font-bold leading-none ${
                  isClosest 
                    ? "bg-yellow-500/10 border border-yellow-500/30 text-yellow-400" 
                    : "text-slate-300 border border-transparent"
                }`}>
                  {strikeItem.strike}
                </span>
                {isClosest && (
                  <span className="text-[7px] font-black text-yellow-500 uppercase tracking-widest mt-0.5">
                    ATM
                  </span>
                )}
              </div>

              {/* Call Side (Right) */}
              <div className="w-[42%] pl-4 text-left flex items-center justify-start gap-2 relative overflow-hidden h-6">
                {/* Call OI heat bar growing left-to-right */}
                <div
                  className="absolute left-0 top-0 bottom-0 bg-gradient-to-r from-rose-500/12 to-rose-500/2 border-l-2 border-rose-500/30 rounded-r"
                  style={{ width: `${callPct}%` }}
                />
                <span className="text-xs font-mono font-black text-rose-400 z-10">
                  {formatNumber(strikeItem.call_oi)}
                </span>
                <span className="text-[10px] font-semibold text-slate-500 z-10">
                  {callChangeText}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
