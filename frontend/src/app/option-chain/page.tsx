"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import { Trophy, ArrowUp, ArrowDown } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(0) + "K";
  return n.toString();
}

function OIBar({ value, max, color }: { value: number; max: number; color: "indigo" | "emerald" }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="relative flex items-center justify-end gap-2 w-full">
      <span className="relative z-10 font-mono text-xs">{fmt(value)}</span>
      <div className="absolute inset-y-1 right-0 left-0 rounded overflow-hidden opacity-25 pointer-events-none">
        <div
          className={`h-full ${color === "indigo" ? "bg-indigo-500" : "bg-emerald-500"}`}
          style={{ width: `${pct}%`, float: "right" }}
        />
      </div>
    </div>
  );
}

import { useMarketData } from "@/context/MarketDataContext";

export default function OptionChainPage() {
  const {
    symbol,
    setSymbol,
    chainData: data,
    chainLoading: loading,
    chainError: error,
    isRefreshing,
    lastSync,
    connected,
    refreshAll,
  } = useMarketData();

  const [filterATM, setFilterATM] = useState(true);
  const atmRef = useRef<HTMLTableRowElement>(null);

  // Scroll ATM row into view after data loads
  useEffect(() => {
    if (data && atmRef.current) {
      setTimeout(() => atmRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 200);
    }
  }, [data]);

  const strikes = data?.strikes ?? [];
  const spotPrice = data?.spot_price ?? 0;

  const atmStrike = strikes.reduce((prev: any, curr: any) =>
    Math.abs(curr.strike - spotPrice) < Math.abs(prev.strike - spotPrice) ? curr : prev,
    strikes[0]
  );

  const maxCallOI  = Math.max(...strikes.map((s: any) => s.call_oi), 1);
  const maxPutOI   = Math.max(...strikes.map((s: any) => s.put_oi), 1);
  const maxCallVol = Math.max(...strikes.map((s: any) => s.call_volume), 1);
  const maxPutVol  = Math.max(...strikes.map((s: any) => s.put_volume), 1);

  const maxCallOIStrike = strikes.find((s: any) => s.call_oi === maxCallOI);
  const maxPutOIStrike  = strikes.find((s: any) => s.put_oi  === maxPutOI);

  const displayStrikes = filterATM
    ? (() => {
        const idx = strikes.findIndex((s: any) => s.strike === atmStrike?.strike);
        return strikes.slice(Math.max(0, idx - 8), Math.min(strikes.length, idx + 9));
      })()
    : strikes;

  return (
    <div className="flex h-screen overflow-hidden bg-[#060810]">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar
          symbol={symbol}
          onSymbolChange={setSymbol}
          onRefresh={refreshAll}
          isRefreshing={isRefreshing}
          lastSyncTime={lastSync}
          providerConnected={connected}
          title="Option Chain"
          subtitle="Full derivatives table"
        />

        <main className="flex-1 overflow-y-auto pb-24 md:pb-0">
          {loading && (
            <div className="flex items-center justify-center py-40 gap-4">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-slate-500 text-sm">Fetching strike data...</p>
            </div>
          )}

          {!loading && error && (
            <div className="max-w-md mx-auto mt-16 p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl text-center">
              <p className="text-rose-400 font-bold mb-2">{error}</p>
              <button onClick={refreshAll} className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-semibold hover:bg-rose-500">Retry</button>
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Toolbar */}
              <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-3 border-b border-[#1e2433] bg-[#060810]/90 backdrop-blur-md">
                {/* Max OI Badges */}
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1.5 rounded-lg">
                    <Trophy className="w-3.5 h-3.5 text-indigo-400" />
                    Max Call OI: <span className="font-mono">{maxCallOIStrike?.strike}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 rounded-lg">
                    <Trophy className="w-3.5 h-3.5 text-emerald-400" />
                    Max Put OI: <span className="font-mono">{maxPutOIStrike?.strike}</span>
                  </div>
                  <div className="text-[11px] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 rounded-lg font-mono">
                    ATM: ₹{atmStrike?.strike}
                  </div>
                </div>

                <button
                  id="btn-filter-atm"
                  onClick={() => setFilterATM(!filterATM)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                    filterATM
                      ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/30"
                      : "bg-[#0d1117] text-slate-400 border-[#1e2433] hover:border-[#2a3347]"
                  }`}
                >
                  {filterATM ? "ATM ± 8 Strikes" : "All Strikes"}
                </button>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[760px]">
                  <thead>
                    <tr className="border-b border-[#1e2433] text-[9px] font-black text-slate-500 uppercase tracking-widest bg-[#0d1117]">
                      <th className="px-3 py-3 text-center" colSpan={4}>
                        <span className="text-indigo-400">CALLS</span>
                        <span className="text-slate-700 ml-2">Bearish / Writing</span>
                      </th>
                      <th className="px-4 py-3 text-center bg-[#131920] border-x border-[#1e2433] text-slate-300 text-[10px]">
                        STRIKE
                      </th>
                      <th className="px-3 py-3 text-center" colSpan={4}>
                        <span className="text-emerald-400">PUTS</span>
                        <span className="text-slate-700 ml-2">Bullish / Support</span>
                      </th>
                    </tr>
                    <tr className="border-b border-[#1e2433] text-[9px] font-bold text-slate-600 uppercase tracking-widest bg-[#060810]">
                      <th className="px-3 py-2 text-right">OI</th>
                      <th className="px-3 py-2 text-right">Chg OI</th>
                      <th className="px-3 py-2 text-right">Volume</th>
                      <th className="px-3 py-2 text-right border-r border-[#1e2433] text-indigo-400/70">LTP</th>
                      <th className="px-4 py-2 text-center bg-[#131920] border-x border-[#1e2433] text-slate-400 text-[10px]">Strike Price</th>
                      <th className="px-3 py-2 text-left border-l border-[#1e2433] text-emerald-400/70">LTP</th>
                      <th className="px-3 py-2 text-left">Volume</th>
                      <th className="px-3 py-2 text-left">Chg OI</th>
                      <th className="px-3 py-2 text-left">OI</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1e2433]/50">
                    {displayStrikes.map((s: any) => {
                      const isATM = s.strike === atmStrike?.strike;
                      const isMaxCallOI = s.call_oi === maxCallOI;
                      const isMaxPutOI  = s.put_oi  === maxPutOI;

                      return (
                        <tr
                          key={s.strike}
                          ref={isATM ? atmRef : undefined}
                          className={`transition-colors text-xs ${
                            isATM
                              ? "bg-yellow-500/5 border-y border-yellow-500/15"
                              : "hover:bg-[#0d1117]/60"
                          }`}
                        >
                          {/* Call OI */}
                          <td className={`px-3 py-2.5 text-right ${isMaxCallOI ? "text-indigo-300 font-bold" : "text-slate-400"}`}>
                            <div className="flex items-center justify-end gap-1">
                              {isMaxCallOI && <Trophy className="w-3 h-3 text-indigo-400" />}
                              <OIBar value={s.call_oi} max={maxCallOI} color="indigo" />
                            </div>
                          </td>
                          {/* Call Chg OI */}
                          <td className={`px-3 py-2.5 text-right font-mono font-medium ${s.call_change_oi > 0 ? "text-rose-400" : s.call_change_oi < 0 ? "text-emerald-400" : "text-slate-600"}`}>
                            <span className="flex items-center justify-end gap-0.5">
                              {s.call_change_oi > 0 ? <ArrowUp className="w-2.5 h-2.5" /> : s.call_change_oi < 0 ? <ArrowDown className="w-2.5 h-2.5" /> : null}
                              {fmt(Math.abs(s.call_change_oi))}
                            </span>
                          </td>
                          {/* Call Vol */}
                          <td className={`px-3 py-2.5 text-right font-mono ${s.call_volume === maxCallVol ? "text-amber-400 font-bold" : "text-slate-500"}`}>
                            {fmt(s.call_volume)}
                          </td>
                          {/* Call LTP */}
                          <td className="px-3 py-2.5 text-right font-mono text-indigo-200 border-r border-[#1e2433]">
                            ₹{s.call_ltp.toFixed(1)}
                          </td>

                          {/* Strike */}
                          <td className={`px-4 py-2.5 text-center font-black text-sm bg-[#131920] border-x border-[#1e2433] ${isATM ? "text-yellow-400" : "text-slate-200"}`}>
                            <span>{s.strike}</span>
                            {isATM && (
                              <span className="block text-[8px] text-yellow-400/70 font-bold uppercase tracking-widest leading-none mt-0.5">
                                ATM
                              </span>
                            )}
                          </td>

                          {/* Put LTP */}
                          <td className="px-3 py-2.5 text-left font-mono text-emerald-200 border-l border-[#1e2433]">
                            ₹{s.put_ltp.toFixed(1)}
                          </td>
                          {/* Put Vol */}
                          <td className={`px-3 py-2.5 text-left font-mono ${s.put_volume === maxPutVol ? "text-amber-400 font-bold" : "text-slate-500"}`}>
                            {fmt(s.put_volume)}
                          </td>
                          {/* Put Chg OI */}
                          <td className={`px-3 py-2.5 text-left font-mono font-medium ${s.put_change_oi > 0 ? "text-emerald-400" : s.put_change_oi < 0 ? "text-rose-400" : "text-slate-600"}`}>
                            <span className="flex items-center gap-0.5">
                              {s.put_change_oi > 0 ? <ArrowUp className="w-2.5 h-2.5" /> : s.put_change_oi < 0 ? <ArrowDown className="w-2.5 h-2.5" /> : null}
                              {fmt(Math.abs(s.put_change_oi))}
                            </span>
                          </td>
                          {/* Put OI */}
                          <td className={`px-3 py-2.5 text-left ${isMaxPutOI ? "text-emerald-300 font-bold" : "text-slate-400"}`}>
                            <div className="flex items-center gap-1">
                              {isMaxPutOI && <Trophy className="w-3 h-3 text-emerald-400" />}
                              <OIBar value={s.put_oi} max={maxPutOI} color="emerald" />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-4 px-5 py-3 border-t border-[#1e2433] text-[10px] text-slate-600 font-medium">
                <span className="flex items-center gap-1.5"><Trophy className="w-3 h-3 text-indigo-400" /> Max Call / Put OI strike</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-amber-400/30 rounded border border-amber-500/30" /> Highest volume strike</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-yellow-400/20 rounded border border-yellow-500/20" /> ATM strike</span>
              </div>
            </>
          )}
        </main>
      </div>

      <BottomNav />
    </div>
  );
}
