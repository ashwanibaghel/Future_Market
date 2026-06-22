"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import { Lightbulb, Flame, AlertTriangle, MessageSquare, Filter } from "lucide-react";
import { formatIST, formatISTDate } from "@/lib/timeUtils";

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const CONFIDENCE_STYLE: Record<string, string> = {
  HIGH:   "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  MEDIUM: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  LOW:    "text-slate-400 bg-slate-800/40 border-slate-700/30",
};

const CATEGORY_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  BUILDUP: {
    icon: <Flame className="w-4 h-4" />,
    label: "Build-Up",
    color: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  },
  VOLATILITY: {
    icon: <AlertTriangle className="w-4 h-4" />,
    label: "Volatility",
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
};

import { useMarketData } from "@/context/MarketDataContext";

export default function InsightsPage() {
  const {
    symbol,
    setSymbol,
    insightsData: insights,
    insightsLoading: loading,
    insightsError: error,
    isRefreshing,
    lastSync,
    connected,
    refreshAll,
  } = useMarketData();

  const [filterCategory, setFilterCategory] = useState<string>("ALL");
  const [filterConfidence, setFilterConfidence] = useState<string>("ALL");

  const filtered = insights.filter((ins) => {
    const catMatch = filterCategory === "ALL" || ins.category === filterCategory;
    const confMatch = filterConfidence === "ALL" || ins.confidence_level === filterConfidence;
    return catMatch && confMatch;
  });

  const categoryCounts: Record<string, number> = {};
  const confidenceCounts: Record<string, number> = {};
  insights.forEach((ins) => {
    categoryCounts[ins.category] = (categoryCounts[ins.category] ?? 0) + 1;
    confidenceCounts[ins.confidence_level] = (confidenceCounts[ins.confidence_level] ?? 0) + 1;
  });

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
          title="Insights"
          subtitle="Generated signals & market interpretations"
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

          {!loading && !error && (
            <div className="flex flex-col gap-5 max-w-4xl">

              {/* Summary strip */}
              <div className="flex flex-wrap gap-3">
                {[
                  { label: "Total", val: insights.length, color: "text-slate-300" },
                  { label: "High Confidence", val: confidenceCounts["HIGH"] ?? 0, color: "text-emerald-400" },
                  { label: "Medium Confidence", val: confidenceCounts["MEDIUM"] ?? 0, color: "text-amber-400" },
                  { label: "Build-Up", val: categoryCounts["BUILDUP"] ?? 0, color: "text-orange-400" },
                  { label: "Volatility", val: categoryCounts["VOLATILITY"] ?? 0, color: "text-rose-400" },
                ].map((s) => (
                  <div key={s.label} className="flex items-center gap-2 px-3 py-2 bg-[#0d1117] border border-[#1e2433] rounded-xl text-xs">
                    <span className={`text-lg font-black font-mono ${s.color}`}>{s.val}</span>
                    <span className="text-slate-500 font-medium">{s.label}</span>
                  </div>
                ))}
              </div>

              {/* Filters */}
              <div className="flex items-center gap-3 flex-wrap">
                <Filter className="w-3.5 h-3.5 text-slate-600" />
                <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">Category:</span>
                {["ALL", "BUILDUP", "VOLATILITY"].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setFilterCategory(cat)}
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-all ${
                      filterCategory === cat
                        ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/30"
                        : "bg-[#0d1117] text-slate-500 border-[#1e2433] hover:border-[#2a3347]"
                    }`}
                  >
                    {cat === "ALL" ? "All" : cat === "BUILDUP" ? "Build-Up" : "Volatility"}
                  </button>
                ))}
                <div className="w-px h-4 bg-[#1e2433]" />
                <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">Confidence:</span>
                {["ALL", "HIGH", "MEDIUM", "LOW"].map((conf) => (
                  <button
                    key={conf}
                    onClick={() => setFilterConfidence(conf)}
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-all ${
                      filterConfidence === conf
                        ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/30"
                        : "bg-[#0d1117] text-slate-500 border-[#1e2433] hover:border-[#2a3347]"
                    }`}
                  >
                    {conf}
                  </button>
                ))}
              </div>

              {/* Insights list */}
              {filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
                  <Lightbulb className="w-10 h-10 text-slate-700" />
                  <p className="text-slate-500 font-semibold">
                    {insights.length === 0
                      ? "No insights generated yet. Data appears after market open."
                      : "No insights match your current filters."}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-2.5">
                  {filtered.map((ins: any) => {
                    const catConf = CATEGORY_CONFIG[ins.category] ?? {
                      icon: <MessageSquare className="w-4 h-4" />,
                      label: ins.category,
                      color: "text-slate-400 bg-slate-800/40 border-slate-700/30",
                    };
                    return (
                      <div
                        key={ins.id}
                        className="flex items-start gap-4 p-4 bg-[#0d1117] border border-[#1e2433] rounded-xl hover:border-[#2a3347] hover:bg-[#131920] transition-all group"
                      >
                        {/* Category icon */}
                        <div className={`shrink-0 p-2 rounded-lg border ${catConf.color}`}>
                          {catConf.icon}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-slate-200 font-semibold leading-relaxed group-hover:text-slate-100">
                            {ins.insight_text}
                          </p>
                          <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                            <span>{catConf.label}</span>
                            <span className="w-1 h-1 bg-slate-700 rounded-full" />
                            <span className="font-mono normal-case font-medium">
                              {formatISTDate(ins.timestamp)}
                              {" "}
                              {formatIST(ins.timestamp)}
                            </span>
                          </div>
                        </div>

                        {/* Confidence badge */}
                        <span className={`shrink-0 px-2.5 py-1 rounded-lg border text-[10px] font-black uppercase tracking-wider ${CONFIDENCE_STYLE[ins.confidence_level] ?? CONFIDENCE_STYLE.LOW}`}>
                          {ins.confidence_level}
                        </span>
                      </div>
                    );
                  })}
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
