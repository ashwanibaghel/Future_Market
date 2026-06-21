"use client";

import React, { useState, useEffect } from "react";
import { RefreshCw, Wifi, WifiOff, Clock } from "lucide-react";
import { useMarketData } from "@/context/MarketDataContext";

interface TopBarProps {
  symbol: string;
  onSymbolChange: (sym: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  lastSyncTime: Date | null;
  providerConnected: boolean;
  title: string;
  subtitle?: string;
}

export default function TopBar({
  symbol,
  onSymbolChange,
  onRefresh,
  isRefreshing,
  lastSyncTime,
  providerConnected,
  title,
  subtitle,
}: TopBarProps) {
  const [relativeTime, setRelativeTime] = useState<string>("--");
  const { 
    selectedExpiry, 
    setSelectedExpiry, 
    expiryList,
    selectedDate,
    setSelectedDate,
    marketDatesList
  } = useMarketData();

  // Update relative time every second
  useEffect(() => {
    const update = () => {
      if (!lastSyncTime) {
        setRelativeTime("--");
        return;
      }
      const diffSec = Math.floor((Date.now() - lastSyncTime.getTime()) / 1000);
      if (diffSec < 5) setRelativeTime("just now");
      else if (diffSec < 60) setRelativeTime(`${diffSec}s ago`);
      else if (diffSec < 3600) setRelativeTime(`${Math.floor(diffSec / 60)}m ago`);
      else setRelativeTime(`${Math.floor(diffSec / 3600)}h ago`);
    };
    update();
    const t = setInterval(update, 1000);
    return () => clearInterval(t);
  }, [lastSyncTime]);

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-6 py-3.5 border-b border-[#1e2433] bg-[#060810]/80 backdrop-blur-md">
      {/* Left — Page title */}
      <div>
        <h1 className="text-sm font-bold text-slate-200 tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-[10px] text-slate-500 font-medium tracking-wider uppercase mt-0.5">
            {subtitle}
          </p>
        )}
      </div>

      {/* Right — Controls */}
      <div className="flex items-center gap-3">
        {/* Provider status */}
        <div
          className={`hidden sm:flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-lg border ${
            providerConnected
              ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/5"
              : "text-rose-400 border-rose-500/20 bg-rose-500/5"
          }`}
        >
          {providerConnected ? (
            <Wifi className="w-3.5 h-3.5" />
          ) : (
            <WifiOff className="w-3.5 h-3.5" />
          )}
          <span>{providerConnected ? "NSE Connected" : "NSE Offline"}</span>
        </div>

        {/* Last sync */}
        <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-medium text-slate-500 px-2.5 py-1.5 rounded-lg border border-[#1e2433] bg-[#0d1117]">
          <Clock className="w-3 h-3" />
          <span>Synced {relativeTime}</span>
        </div>

        {/* Symbol selector */}
        <div className="flex bg-[#0d1117] border border-[#1e2433] rounded-xl p-1 gap-1">
          {["NIFTY", "BANKNIFTY"].map((sym) => (
            <button
              key={sym}
              id={`symbol-${sym.toLowerCase()}`}
              onClick={() => onSymbolChange(sym)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide transition-all ${
                symbol === sym
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/25"
                  : "text-slate-500 hover:text-slate-200"
              }`}
            >
              {sym}
            </button>
          ))}
        </div>

        {/* Date Selector */}
        {marketDatesList.length > 0 ? (
          <div className="flex items-center bg-[#0d1117] border border-[#1e2433] rounded-xl px-3 py-1.5">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mr-2 hidden md:inline">Date:</span>
            <select
              id="date-select"
              value={selectedDate || ""}
              onChange={(e) => setSelectedDate(e.target.value || null)}
              className="bg-transparent text-xs font-bold text-slate-300 outline-none border-none cursor-pointer focus:ring-0"
            >
              {marketDatesList.map((dt) => (
                <option key={dt} value={dt} className="bg-[#0d1117] text-slate-300">
                  {dt}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="flex items-center bg-[#0d1117] border border-[#1e2433] rounded-xl px-3 py-1.5 text-xs text-slate-500 font-medium">
            No dates
          </div>
        )}

        {/* Expiry Selector */}
        {expiryList.length > 0 ? (
          <div className="flex items-center bg-[#0d1117] border border-[#1e2433] rounded-xl px-3 py-1.5">
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mr-2 hidden md:inline">Expiry:</span>
            <select
              id="expiry-select"
              value={selectedExpiry || ""}
              onChange={(e) => setSelectedExpiry(e.target.value || null)}
              className="bg-transparent text-xs font-bold text-slate-300 outline-none border-none cursor-pointer focus:ring-0"
            >
              {expiryList.map((expiry) => (
                <option key={expiry} value={expiry} className="bg-[#0d1117] text-slate-300">
                  {expiry}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="flex items-center bg-[#0d1117] border border-[#1e2433] rounded-xl px-3 py-1.5 text-xs text-slate-500 font-medium">
            No expiries
          </div>
        )}

        {/* Refresh button */}
        <button
          id="btn-refresh"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-[#1e2433] bg-[#0d1117] hover:bg-[#131920] text-slate-400 hover:text-slate-200 text-xs font-semibold disabled:opacity-50 transition-all"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-indigo-400" : ""}`}
          />
          <span className="hidden sm:inline">{isRefreshing ? "Syncing..." : "Sync"}</span>
        </button>
      </div>
    </header>
  );
}
