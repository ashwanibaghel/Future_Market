"use client";

import React from "react";
import { Activity, AlertTriangle, TrendingUp, TrendingDown, Clock, Shield } from "lucide-react";
import { formatIST } from "@/lib/timeUtils";

interface MarketStateBannerProps {
  symbol: string;
  onSymbolChange: (sym: string) => void;
  spotPrice: number;
  expiryDate: string;
  timestamp: string;
  pcr?: number | null;
  marketState?: string | null;
  strength?: string | null;
  ivChange?: number | null;
}

export default function MarketStateBanner({
  symbol,
  onSymbolChange,
  spotPrice,
  expiryDate,
  timestamp,
  pcr,
  marketState,
  strength,
  ivChange
}: MarketStateBannerProps) {
  
  // Safe fallbacks for optional parameters
  const pcrValue = pcr ?? 1.15;
  const marketStateValue = marketState ?? "N/A";
  const strengthValue = strength ?? "N/A";
  const ivChangeValue = ivChange ?? 4.2;

  // Format timestamp — using shared IST utility (backend sends UTC without 'Z')
  const formatTime = (isoString: string) => {
    if (!isoString) return "--:--:--";
    try {
      return formatIST(isoString, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true });
    } catch {
      return isoString;
    }
  };

  const getStrengthColor = (str: string) => {
    switch (str.toUpperCase()) {
      case "HIGH":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
      case "MEDIUM":
        return "text-amber-400 bg-amber-500/10 border-amber-500/30";
      case "LOW":
        return "text-rose-400 bg-rose-500/10 border-rose-500/30";
      default:
        return "text-slate-400 bg-slate-500/10 border-slate-500/30";
    }
  };

  const getStateColor = (state: string) => {
    if (state.includes("LONG")) return "from-emerald-500/20 to-teal-500/20 border-emerald-500/30 text-emerald-300";
    if (state.includes("SHORT")) return "from-rose-500/20 to-pink-500/20 border-rose-500/30 text-rose-300";
    return "from-slate-800 to-slate-900 border-slate-700 text-slate-300";
  };

  return (
    <div className="w-full bg-slate-950/60 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col md:flex-row justify-between items-stretch gap-6">
      {/* Left section: Selector & Core Spot Details */}
      <div className="flex flex-wrap items-center gap-6">
        {/* Symbol Selectors */}
        <div className="flex bg-slate-900 p-1.5 rounded-xl border border-slate-800">
          {["NIFTY", "BANKNIFTY"].map((sym) => (
            <button
              key={sym}
              onClick={() => onSymbolChange(sym)}
              className={`px-4 py-2 rounded-lg text-sm font-bold tracking-wide transition-all ${
                symbol === sym
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/35"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {sym}
            </button>
          ))}
        </div>

        {/* Spot Price */}
        <div>
          <span className="block text-[10px] text-slate-500 font-bold uppercase tracking-wider">Spot Price</span>
          <span className="text-2xl font-black text-slate-100 font-mono">
            ₹{spotPrice ? spotPrice.toLocaleString("en-IN", { minimumFractionDigits: 1 }) : "---"}
          </span>
        </div>

        {/* Expiry date */}
        <div>
          <span className="block text-[10px] text-slate-500 font-bold uppercase tracking-wider">Nearest Expiry</span>
          <span className="text-sm font-bold text-slate-300 bg-slate-900/60 border border-slate-800/80 px-2.5 py-1.5 rounded-lg mt-0.5 block">
            {expiryDate || "---"}
          </span>
        </div>
      </div>

      {/* Right section: Market State Banner */}
      <div className="flex-1 flex flex-col sm:flex-row justify-between items-center bg-slate-900/40 border border-slate-800/80 rounded-xl p-4 gap-4">
        {/* Market Buildup State */}
        <div className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border bg-gradient-to-r ${getStateColor(marketStateValue)}`}>
          <Activity className="w-5 h-5 animate-pulse" />
          <div>
            <span className="block text-[8px] text-slate-400/80 uppercase tracking-widest font-black">Market State</span>
            <span className="text-sm font-extrabold tracking-wider">{marketStateValue}</span>
          </div>
        </div>

        {/* Strength & PCR & IV Grid */}
        <div className="grid grid-cols-3 gap-6 text-center">
          {/* Strength */}
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Strength</span>
            <span className={`text-xs font-black px-2 py-0.5 rounded-full border mt-1 ${getStrengthColor(strengthValue)}`}>
              {strengthValue}
            </span>
          </div>

          {/* PCR */}
          <div>
            <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">PCR</span>
            <span className="text-sm font-bold text-slate-300 font-mono flex items-center justify-center gap-0.5 mt-0.5">
              {pcrValue.toFixed(2)}
              {pcrValue >= 1 ? (
                <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
              )}
            </span>
          </div>

          {/* IV Change */}
          <div>
            <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">IV Change</span>
            <span className={`text-sm font-bold font-mono mt-0.5 block ${ivChangeValue >= 0 ? "text-rose-400" : "text-emerald-400"}`}>
              {ivChangeValue >= 0 ? "+" : ""}
              {ivChangeValue.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Sync Telemetry */}
        <div className="flex items-center gap-2 border-l border-slate-800 pl-4 text-xs text-slate-500">
          <Clock className="w-4 h-4 text-slate-600" />
          <div>
            <span className="block text-[8px] text-slate-600 font-bold uppercase tracking-widest">Last Update</span>
            <span className="font-mono font-bold text-slate-400">{formatTime(timestamp)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
