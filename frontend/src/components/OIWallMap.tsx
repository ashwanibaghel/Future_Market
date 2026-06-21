"use client";

import React, { useMemo } from "react";
import { Layers, ArrowUpDown } from "lucide-react";

interface StrikeItem {
  strike: number;
  call_oi: number;
  call_change_oi: number;
  put_oi: number;
  put_change_oi: number;
}

interface AnalyticsData {
  support?: number | null;
  secondary_support?: number | null;
  resistance?: number | null;
  secondary_resistance?: number | null;
}

interface ChainData {
  spot_price: number;
  expiry_date?: string;
  analytics?: AnalyticsData;
  strikes?: StrikeItem[];
}

interface OIWallMapProps {
  chainData: ChainData | null;
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

export default function OIWallMap({ chainData }: OIWallMapProps) {
  const nodes = useMemo(() => {
    if (!chainData) return [];

    const spotPrice = chainData.spot_price;
    const s1 = chainData.analytics?.support ?? null;
    const s2 = chainData.analytics?.secondary_support ?? null;
    const r1 = chainData.analytics?.resistance ?? null;
    const r2 = chainData.analytics?.secondary_resistance ?? null;
    const strikes = chainData.strikes ?? [];

    const getStrikeDetails = (strikeVal: number | null) => {
      if (strikeVal === null) return null;
      return strikes.find((s) => s.strike === strikeVal) || null;
    };

    const s2Details = getStrikeDetails(s2);
    const s1Details = getStrikeDetails(s1);
    const r1Details = getStrikeDetails(r1);
    const r2Details = getStrikeDetails(r2);

    const list = [];

    // Add nodes only if they are available
    if (r2 !== null) {
      list.push({
        type: "r2",
        strike: r2,
        name: "Secondary Resistance (R2 Ceiling)",
        isSupport: false,
        isSpot: false,
        oi: r2Details?.call_oi ?? 0,
        change: r2Details?.call_change_oi ?? 0,
      });
    }

    if (r1 !== null) {
      list.push({
        type: "r1",
        strike: r1,
        name: "Primary Resistance (R1 Ceiling)",
        isSupport: false,
        isSpot: false,
        oi: r1Details?.call_oi ?? 0,
        change: r1Details?.call_change_oi ?? 0,
      });
    }

    // Spot Price node
    list.push({
      type: "spot",
      strike: spotPrice,
      name: "Spot Price (Current Index Level)",
      isSupport: false,
      isSpot: true,
      oi: 0,
      change: 0,
    });

    if (s1 !== null) {
      list.push({
        type: "s1",
        strike: s1,
        name: "Primary Support (S1 Floor)",
        isSupport: true,
        isSpot: false,
        oi: s1Details?.put_oi ?? 0,
        change: s1Details?.put_change_oi ?? 0,
      });
    }

    if (s2 !== null) {
      list.push({
        type: "s2",
        strike: s2,
        name: "Secondary Support (S2 Floor)",
        isSupport: true,
        isSpot: false,
        oi: s2Details?.put_oi ?? 0,
        change: s2Details?.put_change_oi ?? 0,
      });
    }

    // Sort descending by strike price (highest strike price at the top)
    return list.sort((a, b) => b.strike - a.strike);
  }, [chainData]);

  if (!chainData || nodes.length === 0) {
    return (
      <div className="w-full bg-[#0d1117]/80 border border-[#1e2433] rounded-2xl p-4 text-center text-slate-500 text-xs">
        No S/R wall map data available.
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-2xl flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/40">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
          <Layers className="w-4.5 h-4.5 text-indigo-400" />
          OI Wall Map (Visual Barriers)
        </h3>
        <div className="flex items-center gap-1 text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
          <ArrowUpDown className="w-3.5 h-3.5" />
          Relative View
        </div>
      </div>

      {/* Vertical Map Timeline Track */}
      <div className="relative pl-6 flex flex-col gap-6">
        {/* Continuous vertical line track */}
        <div className="absolute left-[33px] top-4 bottom-4 w-0.5 bg-gradient-to-b from-rose-500/30 via-yellow-500/30 to-emerald-500/30 border-dashed border-l border-slate-700/60 z-0" />

        {nodes.map((node, index) => {
          let cardStyle = "";
          let dotStyle = "";
          let badgeStyle = "";
          
          if (node.isSpot) {
            cardStyle = "bg-yellow-500/5 border-yellow-500/20";
            dotStyle = "bg-yellow-400 ring-4 ring-yellow-500/20 shadow shadow-yellow-400";
            badgeStyle = "text-yellow-400 bg-yellow-500/10 border-yellow-500/20";
          } else if (node.isSupport) {
            cardStyle = "bg-emerald-500/4 border-emerald-500/15 hover:border-emerald-500/25";
            dotStyle = "bg-emerald-500 ring-4 ring-emerald-500/10";
            badgeStyle = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
          } else {
            cardStyle = "bg-rose-500/4 border-rose-500/15 hover:border-rose-500/25";
            dotStyle = "bg-rose-500 ring-4 ring-rose-500/10";
            badgeStyle = "text-rose-400 bg-rose-500/10 border-rose-500/20";
          }

          return (
            <div key={`${node.type}-${index}`} className="flex items-center gap-4 relative z-10">
              {/* Left indicator marker */}
              <div className="flex items-center justify-center w-4 h-4 shrink-0">
                <div className={`w-2.5 h-2.5 rounded-full transition-transform ${dotStyle} ${node.isSpot ? 'animate-pulse' : ''}`} />
              </div>

              {/* Node Card Details */}
              <div className={`flex-1 p-3.5 border rounded-xl backdrop-blur-sm transition-all duration-300 ${cardStyle}`}>
                <div className="flex justify-between items-start gap-2 mb-1.5">
                  <div>
                    <span className="block text-[8px] font-bold text-slate-500 uppercase tracking-widest leading-none mb-1">
                      {node.isSpot ? "Spot Price Indicator" : node.isSupport ? "Support Barrier" : "Resistance Barrier"}
                    </span>
                    <h4 className="text-xs font-bold text-slate-200">
                      {node.name}
                    </h4>
                  </div>
                  <span className="text-[10px] font-black font-mono text-slate-100">
                    ₹{node.strike.toLocaleString("en-IN", { minimumFractionDigits: node.isSpot ? 2 : 0, maximumFractionDigits: node.isSpot ? 2 : 0 })}
                  </span>
                </div>

                {!node.isSpot && (
                  <div className="flex items-center justify-between pt-1.5 border-t border-slate-800/40 text-[10px]">
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <span className="font-semibold">{node.isSupport ? "Put OI" : "Call OI"}:</span>
                      <span className="font-mono text-slate-200 font-bold">{formatNumber(node.oi)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-slate-500">Change:</span>
                      <span className={`font-mono font-bold ${node.change >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {node.change >= 0 ? "+" : ""}{formatNumber(node.change)}
                      </span>
                    </div>
                  </div>
                )}

                {node.isSpot && (
                  <div className="text-[9px] text-slate-500 font-bold uppercase tracking-wider pt-1 flex items-center justify-between">
                    <span>Active Expiry: {chainData.expiry_date || "—"}</span>
                    <span className="animate-pulse text-yellow-500 font-extrabold text-[8px]">Live Tracking</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
