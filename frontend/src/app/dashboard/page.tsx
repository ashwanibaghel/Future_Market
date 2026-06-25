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

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

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
import { formatIST, formatISTDate } from "@/lib/timeUtils";

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
    latestSignal,
    signalsStats,
    signalsHistory,
    signalsLoading,
    signalsError,
    executeSignal,
  } = useMarketData();

  const [activeTab, setActiveTab] = useState<"overview" | "trends" | "signals">("overview");

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
                <button
                  onClick={() => setActiveTab("signals")}
                  className={`pb-2.5 text-xs font-black uppercase tracking-wider transition-all border-b-2 cursor-pointer ${
                    activeTab === "signals"
                      ? "border-indigo-500 text-indigo-400"
                      : "border-transparent text-slate-500 hover:text-slate-300"
                  }`}
                >
                  Signal Advisor
                </button>
              </div>

              {activeTab === "overview" && (
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
              )}

              {activeTab === "trends" && (
                <HistoricalCharts
                  trends={trendsData || []}
                  loading={trendsLoading}
                  error={trendsError}
                />
              )}

              {activeTab === "signals" && (
                <div className="flex flex-col gap-6">
                  {/* Decision + Performance Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Decision Panel Card (2/3 columns) */}
                        <div className="lg:col-span-2 flex flex-col gap-6">
                          {(() => {
                            if (!latestSignal) {
                              return (
                                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-8 text-center flex flex-col items-center justify-center min-h-[250px]">
                                  <p className="text-slate-500 text-xs font-semibold">No signals generated yet for {symbol}.</p>
                                </div>
                              );
                            }

                            const sigType = latestSignal.signal_type || "NO_TRADE";
                            const isBuyCall = sigType === "BUY_CALL";
                            const isBuyPut = sigType === "BUY_PUT";
                            const isNoTrade = sigType === "NO_TRADE";

                            // Styling configurations
                            const cardStyles = isBuyCall
                              ? "from-emerald-950/20 to-emerald-900/5 border-emerald-500/30"
                              : isBuyPut
                              ? "from-rose-950/20 to-rose-900/5 border-rose-500/30"
                              : "from-slate-800/40 to-slate-900/10 border-[#1e2433]";

                            const badgeStyles = isBuyCall
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                              : isBuyPut
                              ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                              : "bg-slate-800/60 text-slate-400 border-[#1e2433]";

                            const isV2 = latestSignal.signal_version === "v2";
                            const confidencePct = isV2
                              ? Math.round(latestSignal.confidence_ratio || 0)
                              : (latestSignal.total_conditions > 0
                                ? Math.round((latestSignal.matched_conditions / latestSignal.total_conditions) * 100)
                                : 0);

                            // Parse reasons object
                            let reasonsObj: Record<string, any> = {};
                            try {
                              reasonsObj = typeof latestSignal.reasons === "string"
                                ? JSON.parse(latestSignal.reasons)
                                : latestSignal.reasons || {};
                            } catch (e) {}

                            // Parse inputs object
                            let inputsObj: Record<string, any> = {};
                            try {
                              inputsObj = typeof latestSignal.signal_inputs === "string"
                                ? JSON.parse(latestSignal.signal_inputs)
                                : latestSignal.signal_inputs || {};
                            } catch (e) {}

                            return (
                              <div className={`relative bg-gradient-to-br ${cardStyles} border rounded-2xl p-6 overflow-hidden`}>
                                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                                  {/* Left: Recommended Trade Type */}
                                  <div>
                                    <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest">
                                      Decision Output
                                    </span>
                                    <div className="flex items-center gap-3 mt-1.5">
                                      <div className={`px-3 py-1 rounded-xl text-lg font-black border tracking-wider ${badgeStyles}`}>
                                        {sigType.replace("_", " ")}
                                      </div>
                                      {latestSignal.suggested_strike && (
                                        <div className="text-xl font-mono font-black text-slate-200">
                                          {latestSignal.suggested_strike}
                                        </div>
                                      )}
                                    </div>
                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mt-3">
                                      Generated At: {formatIST(latestSignal.timestamp, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })} ({symbol} Spot: ₹{latestSignal.spot_price})
                                    </div>
                                  </div>

                                  {/* Right: Confidence Gauge */}
                                  <div className="flex items-center gap-4 bg-[#060810]/50 border border-white/5 rounded-2xl p-4">
                                    <div className="relative w-16 h-16 flex items-center justify-center">
                                      {/* Circle background */}
                                      <svg className="w-16 h-16 -rotate-90">
                                        <circle cx="32" cy="32" r="28" className="stroke-slate-800 fill-none" strokeWidth="6" />
                                        <circle
                                          cx="32"
                                          cy="32"
                                          r="28"
                                          className={`fill-none ${isBuyCall ? "stroke-emerald-400" : isBuyPut ? "stroke-rose-400" : "stroke-indigo-400"}`}
                                          strokeWidth="6"
                                          strokeDasharray={`${2 * Math.PI * 28}`}
                                          strokeDashoffset={`${2 * Math.PI * 28 * (1 - confidencePct / 100)}`}
                                          strokeLinecap="round"
                                        />
                                      </svg>
                                      <span className="absolute text-xs font-black font-mono text-slate-200">
                                        {confidencePct}%
                                      </span>
                                    </div>
                                    <div>
                                      <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest">
                                        {isV2 ? "Confidence Ratio" : "Rule Match"}
                                      </span>
                                      <span className="text-xs font-bold text-slate-300">
                                        {isV2
                                          ? `${confidencePct}% Bias (Margin: ${latestSignal.decision_margin || 0} pts)`
                                          : `${latestSignal.matched_conditions} of ${latestSignal.total_conditions} rules`}
                                      </span>
                                    </div>
                                  </div>
                                </div>

                                {/* Divider */}
                                <div className="w-full h-px bg-white/5 my-5" />

                                {/* Reasons list */}
                                <h4 className="text-xs font-bold text-slate-300 mb-3 uppercase tracking-wider">
                                  {isV2 ? `Rule Checklist (Dynamic Threshold: ${latestSignal.dynamic_threshold || 70} pts)` : "Rule Checklist"}
                                </h4>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                                  {isV2 ? (
                                    Object.entries(reasonsObj).map(([ruleName, data]) => {
                                      const ruleData = data as {
                                        contribution?: number;
                                        weight?: number;
                                        raw?: string | number;
                                        normalized?: number;
                                      };
                                      const contribution = ruleData.contribution ?? 0;
                                      const maxVal = ruleData.weight ?? 15;
                                      const isPassed = contribution > 0;
                                      const rawVal = ruleData.raw ?? "";
                                      return (
                                        <div
                                          key={ruleName}
                                          className="flex items-center justify-between p-2.5 bg-[#060810]/40 border border-white/5 rounded-xl hover:border-[#1e2433] transition-colors"
                                        >
                                          <div className="flex items-center gap-2.5">
                                            <div className={`w-4 h-4 rounded-full flex items-center justify-center border text-[9px] font-black ${
                                              isPassed
                                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                                : "bg-[#0d1117] text-slate-600 border-[#1e2433]"
                                            }`}>
                                              {isPassed ? "✓" : "✗"}
                                            </div>
                                            <div>
                                              <span className={`text-[10px] font-bold block ${isPassed ? "text-slate-300" : "text-slate-500 font-medium"}`}>
                                                {ruleName}
                                              </span>
                                              {rawVal && (
                                                <span className="text-[8px] font-mono text-slate-500 block leading-tight mt-0.5 max-w-[180px] truncate" title={String(rawVal)}>
                                                  {String(rawVal)}
                                                </span>
                                              )}
                                            </div>
                                          </div>
                                          <span className="text-[10px] font-mono font-bold text-slate-400 bg-white/5 px-2 py-0.5 rounded whitespace-nowrap">
                                            {contribution} / {maxVal} pts
                                          </span>
                                        </div>
                                      );
                                    })
                                  ) : (
                                    [
                                      { key: "market_state_bullish", label: "Market State is Bullish (Long Buildup/Short Covering)", active: isBuyCall },
                                      { key: "market_state_bearish", label: "Market State is Bearish (Short Buildup/Long Unwinding)", active: isBuyPut },
                                      { key: "above_vwap", label: "Spot Above Daily Options VWAP", active: isBuyCall },
                                      { key: "below_vwap", label: "Spot Below Daily Options VWAP", active: isBuyPut },
                                      { key: "above_ema20", label: "Spot Above EMA20", active: isBuyCall },
                                      { key: "below_ema20", label: "Spot Below EMA20", active: isBuyPut },
                                      { key: "price_up", label: "Price Increasing (Current vs Previous Spot)", active: isBuyCall },
                                      { key: "price_down", label: "Price Decreasing (Current vs Previous Spot)", active: isBuyPut },
                                      { key: "pcr_up", label: "PCR Improving (Increasing PCR)", active: isBuyCall },
                                      { key: "pcr_down", label: "PCR Declining (Decreasing PCR)", active: isBuyPut },
                                      { key: "strength_high_medium", label: "Buildup Strength is HIGH or MEDIUM", active: true }
                                    ].filter((item) => item.active || isNoTrade).map((item) => {
                                      const val = reasonsObj[item.key] ?? false;
                                      return (
                                        <div
                                          key={item.key}
                                          className="flex items-center gap-2.5 p-2 bg-[#060810]/40 border border-white/5 rounded-xl hover:border-[#1e2433] transition-colors"
                                        >
                                          <div className={`w-4 h-4 rounded-full flex items-center justify-center border text-[9px] font-black ${
                                            val
                                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                              : "bg-[#0d1117] text-slate-600 border-[#1e2433]"
                                          }`}>
                                            {val ? "✓" : "✗"}
                                          </div>
                                          <span className={`text-[10px] font-bold ${val ? "text-slate-300" : "text-slate-500 font-medium"}`}>
                                            {item.label}
                                          </span>
                                        </div>
                                      );
                                    })
                                  )}
                                </div>

                                {/* Auditing Input Values */}
                                {Object.keys(inputsObj).length > 0 && (
                                  <>
                                    <div className="w-full h-px bg-white/5 my-5" />
                                    <h4 className="text-xs font-bold text-slate-300 mb-3 uppercase tracking-wider">Rule Input Snapshots (Debugging/ML Audit)</h4>
                                    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
                                      {Object.entries(inputsObj).map(([key, val]) => (
                                        <div key={key} className="bg-[#060810]/50 border border-white/5 rounded-xl p-2.5 text-center">
                                          <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">{key}</span>
                                          <span className="text-[11px] font-mono font-bold text-slate-300 mt-1 block">
                                            {typeof val === "number" ? val.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(val)}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </>
                                )}

                                {/* Execution Action */}
                                {!isNoTrade && (
                                  <>
                                    <div className="w-full h-px bg-white/5 my-5" />
                                    <div className="flex items-center justify-between gap-4">
                                      <span className="text-[10px] text-slate-500 font-bold leading-relaxed max-w-sm">
                                        Track whether you took this trade. Recording executions helps compare system accuracy vs actual user trading accuracy.
                                      </span>
                                      {latestSignal.was_executed ? (
                                        <button
                                          disabled
                                          className="px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold whitespace-nowrap"
                                        >
                                          Trade Executed ✓
                                        </button>
                                      ) : (
                                        <button
                                          onClick={() => executeSignal(latestSignal.id)}
                                          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold whitespace-nowrap shadow-lg shadow-indigo-600/25 transition-all"
                                        >
                                          Mark Executed
                                        </button>
                                      )}
                                    </div>
                                  </>
                                )}
                              </div>
                            );
                          })()}
                        </div>

                        {/* Performance Scorecard Grid (1/3 column) */}
                        <div className="flex flex-col gap-6">
                          <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                            <span className="text-xs font-black text-slate-300 uppercase tracking-wider block">Performance Scorecard</span>
                            
                            <div className="grid grid-cols-2 gap-3">
                              <div className="bg-[#060810]/50 border border-white/5 rounded-xl p-3.5 text-center">
                                <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">Win Rate</span>
                                <span className="text-2xl font-black font-mono text-emerald-400 mt-1 block">
                                  {signalsStats?.overall_accuracy_pct ?? "0.0"}%
                                </span>
                              </div>
                              <div className="bg-[#060810]/50 border border-white/5 rounded-xl p-3.5 text-center">
                                <span className="block text-[9px] text-slate-500 font-bold uppercase tracking-wider">Total Trades</span>
                                <span className="text-2xl font-black font-mono text-slate-300 mt-1 block">
                                  {signalsStats?.total_signals ?? "0"}
                                </span>
                              </div>
                            </div>

                            {/* W/L/F breakdown */}
                            <div className="flex items-center justify-between border-b border-[#1e2433] pb-3 text-xs">
                              <span className="text-slate-500 font-semibold">Wins</span>
                              <span className="font-bold text-emerald-400 font-mono">{signalsStats?.wins ?? 0}</span>
                            </div>
                            <div className="flex items-center justify-between border-b border-[#1e2433] pb-3 text-xs">
                              <span className="text-slate-500 font-semibold">Losses</span>
                              <span className="font-bold text-rose-400 font-mono">{signalsStats?.losses ?? 0}</span>
                            </div>
                            <div className="flex items-center justify-between pb-1 text-xs">
                              <span className="text-slate-500 font-semibold">Flats</span>
                              <span className="font-bold text-slate-400 font-mono">{signalsStats?.flats ?? 0}</span>
                            </div>
                            
                            <div className="w-full h-px bg-white/5 my-2" />
                            
                            {/* Timeframe Accuracy Matrix */}
                            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mt-2">Accuracy Matrix (Timeframe)</span>
                            <div className="flex flex-col gap-2.5 mt-2">
                              {["15m", "30m", "60m"].map((tf) => {
                                const tfData = signalsStats?.timeframe_accuracy?.[tf] || {};
                                const pct = tfData.accuracy_pct ?? 0.0;
                                return (
                                  <div key={tf} className="flex items-center justify-between bg-[#060810]/50 border border-white/5 rounded-xl p-2.5 text-xs">
                                    <span className="text-slate-400 font-black font-mono">{tf} horizon</span>
                                    <div className="flex items-center gap-2">
                                      <span className="text-slate-500 font-medium">({tfData.wins ?? 0}/{tfData.total ?? 0} W)</span>
                                      <span className={`font-black font-mono ${pct >= 70 ? "text-emerald-400" : pct >= 50 ? "text-amber-400" : "text-slate-400"}`}>
                                        {pct}%
                                      </span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Active Signal History Table */}
                      <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5">
                        <span className="text-xs font-black text-slate-300 uppercase tracking-wider block mb-4">Signal History Log</span>
                        
                        {signalsHistory.length === 0 ? (
                          <div className="py-12 text-center text-slate-600 text-xs font-semibold">
                            No active signal history found.
                          </div>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                              <thead>
                                <tr className="border-b border-[#1e2433] text-[9px] font-black text-slate-500 uppercase tracking-wider">
                                  <th className="pb-3 pl-2">Time</th>
                                  <th className="pb-3">Action</th>
                                  <th className="pb-3 font-mono">Strike</th>
                                  <th className="pb-3">15m</th>
                                  <th className="pb-3">30m</th>
                                  <th className="pb-3">60m</th>
                                  <th className="pb-3">Move (60m)</th>
                                  <th className="pb-3">Executed?</th>
                                </tr>
                              </thead>
                              <tbody>
                                {signalsHistory.map((sig) => {
                                  const isBuyCall = sig.signal_type === "BUY_CALL";
                                  const isExecuted = sig.was_executed;
                                  
                                  const badgeColor = isBuyCall
                                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                                    : "text-rose-400 bg-rose-500/10 border-rose-500/20";
                                    
                                  const outcomeBadge = (val: string) => {
                                    if (val === "WIN") return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
                                    if (val === "LOSS") return "text-rose-400 bg-rose-500/10 border-rose-500/20";
                                    if (val === "FLAT") return "text-slate-400 bg-slate-800/40 border-slate-700/30";
                                    return "text-indigo-400 bg-indigo-500/10 border-indigo-500/20 animate-pulse";
                                  };

                                  return (
                                    <tr key={sig.id} className="border-b border-white/5 hover:bg-[#131920]/40 text-xs text-slate-300 transition-colors">
                                      <td className="py-3 pl-2 text-slate-500 font-medium font-mono whitespace-nowrap">
                                        {formatISTDate(sig.timestamp)}, {formatIST(sig.timestamp, { hour: '2-digit', minute: '2-digit', hour12: true })}
                                      </td>
                                      <td className="py-3">
                                        <span className={`px-2 py-0.5 rounded-lg border text-[9px] font-black uppercase tracking-wider ${badgeColor}`}>
                                          {sig.signal_type.replace("_", " ")}
                                        </span>
                                      </td>
                                      <td className="py-3 font-mono font-bold text-slate-200">
                                        {sig.suggested_strike || "—"}
                                      </td>
                                      <td className="py-3">
                                        <span className={`px-1.5 py-0.5 rounded-md border text-[9px] font-black uppercase tracking-wider ${outcomeBadge(sig.outcome_15m)}`}>
                                          {sig.outcome_15m}
                                        </span>
                                      </td>
                                      <td className="py-3">
                                        <span className={`px-1.5 py-0.5 rounded-md border text-[9px] font-black uppercase tracking-wider ${outcomeBadge(sig.outcome_30m)}`}>
                                          {sig.outcome_30m}
                                        </span>
                                      </td>
                                      <td className="py-3">
                                        <span className={`px-1.5 py-0.5 rounded-md border text-[9px] font-black uppercase tracking-wider ${outcomeBadge(sig.outcome_60m)}`}>
                                          {sig.outcome_60m}
                                        </span>
                                      </td>
                                      <td className="py-3 font-mono font-medium">
                                        <span className={sig.move_60m_points > 0 ? "text-emerald-400" : sig.move_60m_points < 0 ? "text-rose-400" : "text-slate-500"}>
                                          {sig.move_60m_points > 0 ? "+" : ""}{sig.move_60m_points?.toFixed(1) ?? "—"} pts ({sig.move_60m_pct?.toFixed(2) ?? "—"}%)
                                        </span>
                                      </td>
                                      <td className="py-3 pl-2">
                                        {isExecuted ? (
                                          <span className="text-emerald-400 font-bold">Yes ✓</span>
                                        ) : (
                                          <button
                                            onClick={() => executeSignal(sig.id)}
                                            className="px-2 py-0.5 rounded border border-[#1e2433] bg-[#0d1117] hover:bg-indigo-600 hover:text-white text-[10px] font-bold text-slate-400 transition-all"
                                          >
                                            Mark Execute
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
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
