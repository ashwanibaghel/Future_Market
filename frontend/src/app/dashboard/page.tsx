"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import StatCard from "@/components/StatCard";
import SupportResistance from "@/components/SupportResistance";
import HistoricalCharts from "@/components/HistoricalCharts";
import MarketStateTimeline from "@/components/MarketStateTimeline";
import SupportResistanceHeatmap from "@/components/SupportResistanceHeatmap";
import OIWallMap from "@/components/OIWallMap";
import {
  Activity, TrendingUp, TrendingDown, Minus,
  BarChart2, Layers, Zap, Clock, Lightbulb,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

const BACKEND_URL = "http://127.0.0.1:8000";

const STATE_CONFIG: Record<string, { gradient: string; border: string; text: string; dot: string }> = {
  "LONG BUILD-UP":   { gradient: "from-emerald-500/15 to-teal-500/5",    border: "border-emerald-500/25", text: "text-emerald-300", dot: "bg-emerald-400" },
  "SHORT BUILD-UP":  { gradient: "from-rose-500/15 to-pink-500/5",        border: "border-rose-500/25",    text: "text-rose-300",    dot: "bg-rose-400" },
  "SHORT COVERING":  { gradient: "from-indigo-500/15 to-violet-500/5",    border: "border-indigo-500/25",  text: "text-indigo-300",  dot: "bg-indigo-400" },
  "LONG UNWINDING":  { gradient: "from-amber-500/15 to-orange-500/5",     border: "border-amber-500/25",   text: "text-amber-300",   dot: "bg-amber-400" },
  "NEUTRAL":         { gradient: "from-slate-800/60 to-slate-900/30",     border: "border-slate-700/40",   text: "text-slate-300",   dot: "bg-slate-500" },
};

const STRENGTH_STYLE: Record<string, string> = {
  HIGH:   "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  MEDIUM: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  LOW:    "text-slate-400 bg-slate-800/40 border-slate-700/30",
};

function formatBigNumber(n: number) {
  if (n >= 1_00_00_000) return (n / 1_00_00_000).toFixed(2) + " Cr";
  if (n >= 1_00_000)    return (n / 1_00_000).toFixed(2) + " L";
  if (n >= 1_000)       return (n / 1_000).toFixed(1) + "K";
  return n.toString();
}

import { useMarketData } from "@/context/MarketDataContext";

export default function DashboardPage() {
  const {
    symbol,
    setSymbol,
    chainData: data,
    chainLoading: loading,
    chainError: error,
    insightsData,
    trendsData,
    trendsLoading,
    trendsError,
    isRefreshing,
    lastSync,
    connected,
    refreshAll,
    quantData,
  } = useMarketData();

  const [activeTab, setActiveTab] = useState<"overview" | "trends">("overview");

  const insights = insightsData.slice(0, 5);

  const state = data?.analytics?.market_state ?? "NEUTRAL";
  const strength = data?.analytics?.strength ?? "LOW";
  const stateConf = STATE_CONFIG[state] ?? STATE_CONFIG["NEUTRAL"];
  const spotPrice = data?.spot_price ?? 0;
  const pcr = data?.analytics?.pcr ?? 0;
  const ivChange = data?.analytics?.iv_change ?? 0;

  const totalCallOI = data?.strikes?.reduce((s: number, r: any) => s + r.call_oi, 0) ?? 0;
  const totalPutOI  = data?.strikes?.reduce((s: number, r: any) => s + r.put_oi,  0) ?? 0;
  const totalVol    = data?.strikes?.reduce((s: number, r: any) => s + r.call_volume + r.put_volume, 0) ?? 0;

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
          title="Dashboard"
          subtitle="Live market overview"
        />

        <main className="flex-1 overflow-y-auto p-5 md:p-7 pb-24 md:pb-8">
          {/* Background glows */}
          <div className="pointer-events-none fixed top-0 left-64 w-[500px] h-[400px] bg-indigo-600/4 rounded-full blur-[120px]" />

          {loading && (
            <div className="flex flex-col items-center justify-center py-40 gap-4">
              <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-slate-500 text-sm font-medium">Fetching live data from NSE...</p>
            </div>
          )}

          {!loading && error && (
            <div className="max-w-md mx-auto mt-16 p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl text-center">
              <p className="text-rose-400 font-bold mb-2">Connection Error</p>
              <p className="text-slate-500 text-xs mb-4">{error}</p>
              <button
                onClick={refreshAll}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && data && (
            <div className="flex flex-col gap-6 max-w-6xl">

              {/* ─── Hero: Market State + Spot + Key Metrics ─── */}
              <div className={`relative bg-gradient-to-br ${stateConf.gradient} border ${stateConf.border} rounded-2xl p-6 overflow-hidden`}>
                {/* Decorative blur */}
                <div className={`absolute -top-10 -right-10 w-48 h-48 ${stateConf.dot} opacity-10 rounded-full blur-[60px] pointer-events-none`} />

                <div className="flex flex-col md:flex-row md:items-center gap-6">
                  {/* Market State — PRIMARY (left) */}
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl bg-[#060810]/50 border ${stateConf.border} flex items-center justify-center`}>
                      <Activity className={`w-6 h-6 ${stateConf.text}`} />
                    </div>
                    <div>
                      <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest">
                        Market State
                      </span>
                      <span className={`text-xl font-black tracking-tight ${stateConf.text}`}>
                        {state}
                      </span>
                      <span className={`mt-1 inline-block px-2 py-0.5 rounded-lg border text-[10px] font-black uppercase tracking-wider ${STRENGTH_STYLE[strength] ?? STRENGTH_STYLE.LOW}`}>
                        {strength} Strength
                      </span>
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="hidden md:block w-px h-12 bg-white/10" />

                  {/* Spot Price — secondary */}
                  <div>
                    <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest">
                      Spot Price
                    </span>
                    <span className="text-3xl font-black font-mono text-slate-100">
                      ₹{spotPrice.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                    </span>
                    <span className="block text-[10px] text-slate-500 font-medium mt-0.5">
                      {data.expiry_date || "—"}
                    </span>
                  </div>

                  {/* Divider */}
                  <div className="hidden md:block w-px h-12 bg-white/10" />

                  {/* PCR + IV */}
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest">PCR</span>
                      <span className="flex items-center gap-1 text-lg font-black font-mono text-slate-200 mt-0.5">
                        {pcr.toFixed(2)}
                        {pcr >= 1 ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : <TrendingDown className="w-4 h-4 text-rose-400" />}
                      </span>
                      <span className="text-[10px] text-slate-500">{pcr >= 1.2 ? "Put Heavy" : pcr <= 0.8 ? "Call Heavy" : "Balanced"}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest">IV Change</span>
                      <span className={`text-lg font-black font-mono mt-0.5 block ${ivChange >= 0 ? "text-rose-400" : "text-emerald-400"}`}>
                        {ivChange >= 0 ? "+" : ""}{ivChange.toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-slate-500">{ivChange >= 0 ? "Expanding" : "Compressing"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Market State Timeline */}
              <MarketStateTimeline timeline={quantData?.timeline} />

              {/* Tab Switcher */}
              <div className="flex border-b border-[#1e2433] gap-6 mt-2 mb-1">
                <button
                  onClick={() => setActiveTab("overview")}
                  className={`pb-2.5 text-xs font-black uppercase tracking-wider transition-all border-b-2 cursor-pointer ${
                    activeTab === "overview"
                      ? "border-indigo-500 text-indigo-400"
                      : "border-transparent text-slate-500 hover:text-slate-300"
                  }`}
                >
                  Intraday Overview
                </button>
                <button
                  onClick={() => setActiveTab("trends")}
                  className={`pb-2.5 text-xs font-black uppercase tracking-wider transition-all border-b-2 cursor-pointer ${
                    activeTab === "trends"
                      ? "border-indigo-500 text-indigo-400"
                      : "border-transparent text-slate-500 hover:text-slate-300"
                  }`}
                >
                  Historical Trends
                </button>
              </div>

              {activeTab === "overview" ? (
                <>
                  {/* ─── Stat Cards Row ─── */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard
                      label="Total Call OI"
                      value={formatBigNumber(totalCallOI)}
                      accent="indigo"
                      icon={<Layers className="w-4 h-4" />}
                      mono
                    />
                    <StatCard
                      label="Total Put OI"
                      value={formatBigNumber(totalPutOI)}
                      accent="emerald"
                      icon={<Layers className="w-4 h-4" />}
                      mono
                    />
                    <StatCard
                      label="Total Volume"
                      value={formatBigNumber(totalVol)}
                      accent="amber"
                      icon={<BarChart2 className="w-4 h-4" />}
                      mono
                    />
                    <StatCard
                      label="Expiry"
                      value={data.expiry_date || "—"}
                      accent="slate"
                      icon={<Clock className="w-4 h-4" />}
                    />
                  </div>

                  {/* ─── S/R Visual + Insights ─── */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* S/R Bar */}
                    <div className="lg:col-span-2">
                      <SupportResistance
                        spotPrice={spotPrice}
                        primarySupport={data.analytics?.support}
                        secondarySupport={data.analytics?.secondary_support}
                        primaryResistance={data.analytics?.resistance}
                        secondaryResistance={data.analytics?.secondary_resistance}
                      />
                    </div>

                    {/* Recent Insights (compact) */}
                    <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Lightbulb className="w-4 h-4 text-amber-400" />
                          <span className="text-xs font-bold text-slate-300">Recent Insights</span>
                        </div>
                        <Link
                          href="/insights"
                          className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                        >
                          View All <ArrowRight className="w-3 h-3" />
                        </Link>
                      </div>

                      {insights.length === 0 ? (
                        <div className="flex-1 flex items-center justify-center py-8 text-slate-600 text-xs text-center">
                          No insights generated yet.<br />Data will appear after first market session.
                        </div>
                      ) : (
                        <div className="flex flex-col gap-2">
                          {insights.map((ins: any, i: number) => (
                            <div
                              key={i}
                              className="flex items-start gap-2.5 p-3 bg-[#131920] border border-[#1e2433] rounded-xl hover:border-[#2a3347] transition-colors"
                            >
                              <span className={`mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full ${
                                ins.confidence_level === "HIGH" ? "bg-emerald-400" :
                                ins.confidence_level === "MEDIUM" ? "bg-amber-400" : "bg-slate-500"
                              }`} />
                              <p className="text-[11px] text-slate-400 leading-relaxed font-medium">
                                {ins.insight_text}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ─── S/R Heatmap + OI Wall Map ─── */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2">
                      <SupportResistanceHeatmap strikes={data?.strikes} spotPrice={spotPrice} />
                    </div>
                    <div className="lg:col-span-1">
                      <OIWallMap chainData={data} />
                    </div>
                  </div>

                  {/* ─── Quick nav footer ─── */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { href: "/option-chain", label: "Option Chain Table", sub: "Full strike data" },
                      { href: "/analytics", label: "Deep Analytics", sub: "PCR trend & IV" },
                      { href: "/insights", label: "All Insights", sub: "Signals feed" },
                      { href: "/quant-console", label: "Quant Console", sub: "Rule validation" },
                    ].map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="flex items-center justify-between p-4 bg-[#0d1117] border border-[#1e2433] rounded-xl hover:border-[#2a3347] hover:bg-[#131920] transition-all group"
                      >
                        <div>
                          <p className="text-xs font-bold text-slate-300 group-hover:text-slate-100">{item.label}</p>
                          <p className="text-[10px] text-slate-600">{item.sub}</p>
                        </div>
                        <ArrowRight className="w-4 h-4 text-slate-700 group-hover:text-indigo-400 transition-colors" />
                      </Link>
                    ))}
                  </div>
                </>
              ) : (
                <HistoricalCharts
                  trends={trendsData || []}
                  loading={trendsLoading}
                  error={trendsError}
                />
              )}

            </div>
          )}
        </main>
      </div>

      <BottomNav />
    </div>
  );
}
