"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import { Shield, ShieldAlert, TrendingUp, TrendingDown, Activity, BarChart3 } from "lucide-react";
import { formatIST } from "@/lib/timeUtils";

import { useMarketData } from "@/context/MarketDataContext";

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const STATE_DOT: Record<string, string> = {
  "LONG BUILD-UP":  "bg-emerald-400",
  "SHORT BUILD-UP": "bg-rose-400",
  "SHORT COVERING": "bg-indigo-400",
  "LONG UNWINDING": "bg-amber-400",
  "NEUTRAL":        "bg-slate-600",
};

const STATE_TEXT: Record<string, string> = {
  "LONG BUILD-UP":  "text-emerald-400",
  "SHORT BUILD-UP": "text-rose-400",
  "SHORT COVERING": "text-indigo-400",
  "LONG UNWINDING": "text-amber-400",
  "NEUTRAL":        "text-slate-400",
};

export default function AnalyticsPage() {
  const {
    symbol,
    setSymbol,
    chainData,
    chainLoading,
    chainError,
    quantData,
    quantLoading,
    quantError,
    isRefreshing,
    lastSync,
    connected,
    refreshAll,
  } = useMarketData();

  const loading = chainLoading || quantLoading;
  const error = chainError || quantError;

  const analytics = chainData?.analytics;
  const timeline = quantData?.timeline ?? [];

  // Last 1 hour = up to 60 snapshots at 1m interval
  const oneHourTimeline = [...timeline].reverse().slice(0, 60).reverse();

  // PCR chart range
  const pcrValues = oneHourTimeline.map((t: any) => t.pcr ?? 0).filter((v: number) => v > 0);
  const pcrMin = pcrValues.length ? Math.min(...pcrValues) * 0.97 : 0.5;
  const pcrMax = pcrValues.length ? Math.max(...pcrValues) * 1.03 : 2;
  const pcrRange = pcrMax - pcrMin;

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
          title="Analytics"
          subtitle="PCR trends, S/R levels, IV analysis"
        />

        <main className="flex-1 overflow-y-auto p-5 md:p-7 pb-24 md:pb-8">
          {loading && (
            <div className="flex items-center justify-center py-40">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && error && (
            <div className="max-w-md mx-auto mt-16 p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl text-center">
              <p className="text-rose-400 font-bold mb-2">{error}</p>
              <button onClick={refreshAll} className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-semibold hover:bg-rose-500">Retry</button>
            </div>
          )}

          {!loading && !error && chainData && (
            <div className="flex flex-col gap-6 max-w-6xl">

              {/* ─── PCR + IV Row ─── */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  {
                    label: "Put-Call Ratio",
                    value: analytics?.pcr?.toFixed(3) ?? "—",
                    sub: analytics?.pcr >= 1.2 ? "Put Heavy (Bullish)" : analytics?.pcr <= 0.8 ? "Call Heavy (Bearish)" : "Balanced",
                    color: analytics?.pcr >= 1 ? "text-emerald-400" : "text-rose-400",
                  },
                  {
                    label: "IV Change",
                    value: analytics?.iv_change != null ? `${analytics.iv_change >= 0 ? "+" : ""}${analytics.iv_change.toFixed(2)}%` : "—",
                    sub: analytics?.iv_change >= 0 ? "Expanding — Fear up" : "Compressing — Calm",
                    color: analytics?.iv_change >= 0 ? "text-rose-400" : "text-emerald-400",
                  },
                  {
                    label: "Market State",
                    value: analytics?.market_state ?? "NEUTRAL",
                    sub: `${analytics?.strength ?? "LOW"} Strength`,
                    color: STATE_TEXT[analytics?.market_state] ?? "text-slate-400",
                  },
                  {
                    label: "Spot Price",
                    value: `₹${chainData.spot_price?.toLocaleString("en-IN", { minimumFractionDigits: 1 }) ?? "—"}`,
                    sub: chainData.expiry_date ?? "—",
                    color: "text-slate-200",
                  },
                ].map((item, i) => (
                  <div key={i} className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 hover:border-[#2a3347] transition-colors">
                    <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">{item.label}</span>
                    <span className={`text-xl font-black font-mono ${item.color}`}>{item.value}</span>
                    <span className="block text-[11px] text-slate-500 font-medium mt-1">{item.sub}</span>
                  </div>
                ))}
              </div>

              {/* ─── PCR Timeline Chart (Last 1 Hour) ─── */}
              <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm font-bold text-slate-300">PCR Trend — Last 1 Hour</span>
                  </div>
                  <div className="flex items-center gap-4 text-[10px] font-semibold">
                    <span className="text-slate-500">Min: <span className="text-rose-400 font-mono">{pcrMin > 0 ? pcrMin.toFixed(2) : "—"}</span></span>
                    <span className="text-slate-500">Max: <span className="text-emerald-400 font-mono">{pcrMax > 0 ? pcrMax.toFixed(2) : "—"}</span></span>
                  </div>
                </div>

                {oneHourTimeline.length < 2 ? (
                  <div className="flex items-center justify-center h-32 text-slate-600 text-sm">
                    Collecting data... Chart will appear after a few minutes.
                  </div>
                ) : (
                  <div className="relative h-40">
                    {/* Y-axis labels */}
                    <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between text-right pr-2">
                      <span className="text-[9px] font-mono text-slate-600">{pcrMax.toFixed(2)}</span>
                      <span className="text-[9px] font-mono text-slate-600">{((pcrMax + pcrMin) / 2).toFixed(2)}</span>
                      <span className="text-[9px] font-mono text-slate-600">{pcrMin.toFixed(2)}</span>
                    </div>

                    {/* Chart area */}
                    <div className="absolute left-12 right-0 top-0 bottom-0">
                      {/* Grid lines */}
                      {[0, 50, 100].map((pct) => (
                        <div key={pct} className="absolute w-full border-t border-[#1e2433]" style={{ top: `${pct}%` }} />
                      ))}

                      {/* Bars */}
                      <div className="absolute inset-0 flex items-end gap-px">
                        {oneHourTimeline.map((snap: any, i: number) => {
                          const pcr = snap.pcr ?? 0;
                          const heightPct = pcrRange > 0 ? ((pcr - pcrMin) / pcrRange) * 100 : 50;
                          const state = snap.market_state ?? "NEUTRAL";
                          const color =
                            state === "LONG BUILD-UP"   ? "bg-emerald-500/70" :
                            state === "SHORT BUILD-UP"  ? "bg-rose-500/70" :
                            state === "SHORT COVERING"  ? "bg-indigo-500/70" :
                            state === "LONG UNWINDING"  ? "bg-amber-500/70" :
                                                          "bg-slate-600/60";
                          return (
                            <div
                              key={i}
                              className="flex-1 flex flex-col justify-end group relative"
                              title={`${formatIST(snap.timestamp)} | PCR: ${pcr.toFixed(2)} | ${state}`}
                            >
                              <div className={`w-full rounded-t-sm ${color} hover:brightness-125 transition-all`} style={{ height: `${Math.max(heightPct, 2)}%` }} />
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {/* Time labels */}
                {oneHourTimeline.length >= 2 && (
                  <div className="flex justify-between ml-12 mt-2 text-[9px] font-mono text-slate-600">
                    <span>{formatIST(oneHourTimeline[0]?.timestamp)}</span>
                    <span>← 1 Hour →</span>
                    <span>{formatIST(oneHourTimeline[oneHourTimeline.length - 1]?.timestamp)}</span>
                  </div>
                )}

                {/* Legend */}
                <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-[#1e2433]">
                  {[
                    { color: "bg-emerald-500/70", label: "Long Build-Up" },
                    { color: "bg-rose-500/70",    label: "Short Build-Up" },
                    { color: "bg-indigo-500/70",  label: "Short Covering" },
                    { color: "bg-amber-500/70",   label: "Long Unwinding" },
                    { color: "bg-slate-600/60",   label: "Neutral" },
                  ].map((l) => (
                    <span key={l.label} className="flex items-center gap-1.5 text-[10px] text-slate-500 font-medium">
                      <span className={`w-2.5 h-2.5 rounded-sm ${l.color}`} /> {l.label}
                    </span>
                  ))}
                </div>
              </div>

              {/* ─── Support / Resistance Deep ─── */}
              <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-5">
                  <Shield className="w-4 h-4 text-indigo-400" />
                  <span className="text-sm font-bold text-slate-300">Support & Resistance Analysis</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {/* Support */}
                  <div className="flex flex-col gap-3">
                    <span className="text-[10px] font-black text-rose-400/80 uppercase tracking-widest">Support Levels</span>
                    {[
                      { label: "S1 — Primary Support", val: analytics?.support, strength: analytics?.support_strength, dist: analytics?.distance_to_support },
                      { label: "S2 — Secondary Support", val: analytics?.secondary_support, strength: null, dist: null },
                    ].map((s, i) => (
                      <div key={i} className="flex items-center justify-between p-4 bg-rose-500/5 border border-rose-500/15 rounded-xl">
                        <div className="flex items-center gap-3">
                          {i === 0 ? <Shield className="w-5 h-5 text-rose-400" /> : <ShieldAlert className="w-5 h-5 text-rose-400/60" />}
                          <div>
                            <p className="text-[10px] text-slate-500 font-semibold">{s.label}</p>
                            <p className="text-lg font-black font-mono text-rose-300">₹{s.val?.toFixed(0) ?? "—"}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          {s.strength && (
                            <span className={`text-[10px] font-black px-2 py-0.5 rounded-lg border ${
                              s.strength === "HIGH" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" :
                              s.strength === "MEDIUM" ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
                              "text-slate-500 bg-slate-800/40 border-slate-700/30"
                            }`}>{s.strength}</span>
                          )}
                          {s.dist != null && (
                            <p className="text-[10px] text-slate-500 mt-1 font-mono">
                              {s.dist.toFixed(1)} pts away
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Resistance */}
                  <div className="flex flex-col gap-3">
                    <span className="text-[10px] font-black text-indigo-400/80 uppercase tracking-widest">Resistance Levels</span>
                    {[
                      { label: "R1 — Primary Resistance", val: analytics?.resistance, strength: analytics?.resistance_strength, dist: analytics?.distance_to_resistance },
                      { label: "R2 — Secondary Resistance", val: analytics?.secondary_resistance, strength: null, dist: null },
                    ].map((r, i) => (
                      <div key={i} className="flex items-center justify-between p-4 bg-indigo-500/5 border border-indigo-500/15 rounded-xl">
                        <div className="flex items-center gap-3">
                          {i === 0 ? <Shield className="w-5 h-5 text-indigo-400" /> : <ShieldAlert className="w-5 h-5 text-indigo-400/60" />}
                          <div>
                            <p className="text-[10px] text-slate-500 font-semibold">{r.label}</p>
                            <p className="text-lg font-black font-mono text-indigo-300">₹{r.val?.toFixed(0) ?? "—"}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          {r.strength && (
                            <span className={`text-[10px] font-black px-2 py-0.5 rounded-lg border ${
                              r.strength === "HIGH" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" :
                              r.strength === "MEDIUM" ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
                              "text-slate-500 bg-slate-800/40 border-slate-700/30"
                            }`}>{r.strength}</span>
                          )}
                          {r.dist != null && (
                            <p className="text-[10px] text-slate-500 mt-1 font-mono">
                              {r.dist.toFixed(1)} pts away
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* ─── State Timeline (scrollable) ─── */}
              {oneHourTimeline.length > 0 && (
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Activity className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm font-bold text-slate-300">Market State History — Last 1 Hour</span>
                  </div>
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {oneHourTimeline.map((snap: any, i: number) => {
                      const state = snap.market_state ?? "NEUTRAL";
                      const dot = STATE_DOT[state] ?? "bg-slate-600";
                      const txt = STATE_TEXT[state] ?? "text-slate-400";
                      return (
                        <div key={i} className="shrink-0 flex flex-col items-center gap-1 group">
                          <span className={`w-2 h-2 rounded-full ${dot}`} />
                          <span className={`text-[8px] font-bold ${txt} whitespace-nowrap`}>
                            {state.split(" ").map((w: string) => w[0]).join("")}
                          </span>
                          <span className="text-[8px] text-slate-600 font-mono">
                            {formatIST(snap.timestamp)}
                          </span>
                          <span className="text-[8px] text-slate-600 font-mono">
                            {snap.pcr?.toFixed(2) ?? ""}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  {/* State abbreviation legend */}
                  <div className="flex flex-wrap gap-3 mt-3 pt-3 border-t border-[#1e2433] text-[9px] text-slate-600">
                    <span>LBU = Long Build-Up</span>
                    <span>SBU = Short Build-Up</span>
                    <span>SC = Short Covering</span>
                    <span>LU = Long Unwinding</span>
                    <span>N = Neutral</span>
                  </div>
                </div>
              )}

            </div>
          )}
        </main>
      </div>

      <BottomNav />
    </div>
  );
}
