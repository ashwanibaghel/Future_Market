"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import { useMarketData } from "@/context/MarketDataContext";
import EdgePerformanceChart from "@/components/EdgePerformanceChart";
import SignalDecayChart from "@/components/SignalDecayChart";
import { 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  Gauge, 
  Layers, 
  Compass, 
  ShieldCheck, 
  Zap, 
  Clock, 
  LineChart 
} from "lucide-react";

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

interface EdgeMetric {
  market_state: string;
  samples: number;
  success_15m?: number;
  success_30m?: number;
  success_60m?: number;
  avg_mfe?: number;
  median_mfe?: number;
  avg_mae?: number;
  median_mae?: number;
  edge_score?: number;
  confidence?: string;
  edge_decay?: number;
  movement_std_dev?: number;
  consistency_score?: number;
  edge_quality?: string;
  status: string;
}

export default function EdgeLabPage() {
  const {
    symbol,
    setSymbol,
    isRefreshing,
    lastSync,
    connected,
    refreshAll
  } = useMarketData();

  const [timeframe, setTimeframe] = useState<string>("5m");
  const [metrics, setMetrics] = useState<EdgeMetric[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/edge-lab?symbol=${symbol}&timeframe=${timeframe}`);
      if (!res.ok) {
        throw new Error("Failed to fetch Edge Lab statistics.");
      }
      const data = await res.json();
      setMetrics(data);
    } catch (err: any) {
      setError(err.message || "An error occurred.");
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // Separate states into Valid (having data) and Insufficient
  const validMetrics = metrics.filter(m => m.status === "SUCCESS");
  const insufficientMetrics = metrics.filter(m => m.status === "INSUFFICIENT_DATA");

  // Sort valid metrics: Top Edge (High Edge Score) vs Weak Edge (Low Edge Score)
  const topEdge = [...validMetrics].sort((a, b) => (b.edge_score || 0) - (a.edge_score || 0));
  const weakEdge = [...validMetrics].sort((a, b) => (a.edge_score || 0) - (b.edge_score || 0));

  const timeframeLabels: Record<string, string> = {
    "1m": "1 Minute",
    "5m": "5 Minute",
    "15m": "15 Minute"
  };

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
          title="Edge Lab"
          subtitle="Signal alignment, excursions, decay and consistency metrics"
        />

        <main className="flex-1 overflow-y-auto p-5 md:p-7 pb-24 md:pb-8">
          
          {/* Timeframe Selectors */}
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1e2433]">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-400" />
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Analysis Horizon</span>
            </div>
            
            <div className="flex bg-[#0d1117] p-1 rounded-xl border border-[#1e2433]">
              {["1m", "5m", "15m"].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                    timeframe === tf
                      ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/25"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {timeframeLabels[tf]}
                </button>
              ))}
            </div>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-40">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && error && (
            <div className="max-w-md mx-auto mt-12 p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl text-center">
              <p className="text-rose-400 font-bold mb-3">{error}</p>
              <button
                onClick={fetchMetrics}
                className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-semibold hover:bg-rose-500 transition-colors"
              >
                Retry Request
              </button>
            </div>
          )}

          {!loading && !error && (
            <div className="flex flex-col gap-8 max-w-6xl">
              
              {/* 100% Real Data Notice */}
              <div className="bg-[#0b101d] border border-indigo-500/20 rounded-2xl p-4 flex items-center gap-3">
                <ShieldCheck className="w-5 h-5 text-indigo-400 shrink-0" />
                <p className="text-xs text-slate-300 font-medium">
                  <strong>Quant Validation Guarantee:</strong> This analysis is calculated on 100% real historical snapshots. Mock/seeded outcomes are completely excluded to protect mathematical integrity.
                </p>
              </div>

              {/* ─── Visual Analysis Dashboard: Performance & Decay ─── */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <EdgePerformanceChart metrics={metrics} />
                <SignalDecayChart metrics={metrics} />
              </div>

              {/* Ranks Layout */}
              {validMetrics.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  
                  {/* Left Column: Top Edge (High Performers) */}
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center gap-2 px-1">
                      <TrendingUp className="w-4.5 h-4.5 text-emerald-400" />
                      <h2 className="text-sm font-extrabold text-slate-200 uppercase tracking-wider">Top Performing Edge</h2>
                    </div>

                    <div className="flex flex-col gap-4">
                      {topEdge.map((metric) => (
                        <SignalCard key={metric.market_state} metric={metric} />
                      ))}
                    </div>
                  </div>

                  {/* Right Column: Weak Edge (Low Performers/Noise) */}
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center gap-2 px-1">
                      <TrendingDown className="w-4.5 h-4.5 text-rose-400" />
                      <h2 className="text-sm font-extrabold text-slate-200 uppercase tracking-wider">High Noise / Weak Signals</h2>
                    </div>

                    <div className="flex flex-col gap-4">
                      {weakEdge.map((metric) => (
                        <SignalCard key={metric.market_state} metric={metric} />
                      ))}
                    </div>
                  </div>

                </div>
              ) : (
                insufficientMetrics.length === 0 && (
                  <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-12 text-center text-slate-500">
                    No historical snapshots or outcomes loaded for {symbol} on {timeframeLabels[timeframe]} timeframe.
                  </div>
                )
              )}

              {/* Insufficient Data Cards Section */}
              {insufficientMetrics.length > 0 && (
                <div className="flex flex-col gap-4 mt-4">
                  <div className="flex items-center gap-2 px-1">
                    <AlertTriangle className="w-4.5 h-4.5 text-slate-500" />
                    <h2 className="text-sm font-extrabold text-slate-400 uppercase tracking-wider">Insufficient Historical Data</h2>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {insufficientMetrics.map((metric) => (
                      <div 
                        key={metric.market_state} 
                        className="bg-[#0a0d14]/60 border border-[#1b202e] rounded-2xl p-5 flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-bold text-slate-400">{metric.market_state}</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 bg-slate-800 text-slate-400 rounded-lg">
                              Samples: {metric.samples}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 font-medium">
                            Need at least 20 completed outcomes to compute Edge stats. Execute more trading days to build history.
                          </p>
                        </div>
                        <div className="mt-4 pt-3 border-t border-[#161a26] flex items-center gap-2 text-[10px] font-bold text-slate-600 uppercase tracking-wider">
                          <Gauge className="w-3.5 h-3.5" />
                          Quality: Insufficient Data
                        </div>
                      </div>
                    ))}
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

function SignalCard({ metric }: { metric: EdgeMetric }) {
  const isBullish = metric.market_state.includes("LONG") || metric.market_state.includes("COVERING");
  
  // Decide Quality Colors
  const qualityStyles: Record<string, { bg: string, text: string, border: string, glow: string }> = {
    "HIGH QUALITY": {
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/25",
      glow: "shadow-emerald-500/10"
    },
    "MEDIUM QUALITY": {
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/25",
      glow: "shadow-amber-500/10"
    },
    "LOW QUALITY": {
      bg: "bg-rose-500/10",
      text: "text-rose-400",
      border: "border-rose-500/25",
      glow: "shadow-rose-500/10"
    }
  };
  
  const qStyle = qualityStyles[metric.edge_quality || ""] || {
    bg: "bg-slate-800/40",
    text: "text-slate-400",
    border: "border-slate-700/30",
    glow: ""
  };

  return (
    <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6 hover:border-[#2a3347] transition-all relative overflow-hidden group">
      
      {/* Top Banner Row */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className={`text-base font-black tracking-tight ${isBullish ? "text-slate-100" : "text-slate-200"}`}>
            {metric.market_state}
          </h3>
          <span className="block text-[10px] text-slate-500 font-semibold mt-0.5 uppercase tracking-wider">
            Buildup State Signal
          </span>
        </div>
        
        <span className={`text-[10px] font-black tracking-widest px-2.5 py-1 rounded-xl border uppercase shadow-sm ${qStyle.bg} ${qStyle.text} ${qStyle.border} ${qStyle.glow}`}>
          {metric.edge_quality}
        </span>
      </div>

      {/* Main Stats Row */}
      <div className="grid grid-cols-3 gap-4 py-3 border-y border-[#181f2f] mb-4">
        <div>
          <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">Edge Score</span>
          <span className="text-xl font-black font-mono text-indigo-400">{metric.edge_score}</span>
        </div>
        
        <div>
          <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">Consistency</span>
          <span className="text-xl font-black font-mono text-slate-200">{metric.consistency_score}%</span>
        </div>

        <div>
          <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">Confidence</span>
          <span className={`text-xl font-black tracking-tight ${
            metric.confidence === "HIGH" ? "text-emerald-400" : 
            metric.confidence === "MEDIUM" ? "text-amber-400" : "text-rose-400"
          }`}>
            {metric.confidence}
          </span>
        </div>
      </div>

      {/* Excursions & Alignment Details Grid */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 mb-4">
        
        {/* Alignment rates */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1">
            <Compass className="w-3 h-3 text-indigo-400" />
            Alignment (Success)
          </span>
          <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-400">
            <span>15m:</span>
            <span>{metric.success_15m}%</span>
          </div>
          <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-400">
            <span>30m:</span>
            <span>{metric.success_30m}%</span>
          </div>
          <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-300">
            <span>60m:</span>
            <span className="text-indigo-300">{metric.success_60m}%</span>
          </div>
        </div>

        {/* Excursions */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1">
            <LineChart className="w-3 h-3 text-rose-400" />
            Excursion (60m Window)
          </span>
          <div className="flex items-center justify-between text-xs font-bold">
            <span className="text-slate-500 font-normal">Avg MFE:</span>
            <span className="text-emerald-400 font-mono">+{metric.avg_mfe} pts</span>
          </div>
          <div className="flex items-center justify-between text-xs font-bold">
            <span className="text-slate-500 font-normal">Med MFE:</span>
            <span className="text-emerald-400 font-mono">+{metric.median_mfe} pts</span>
          </div>
          <div className="flex items-center justify-between text-xs font-bold">
            <span className="text-slate-500 font-normal">Avg MAE:</span>
            <span className="text-rose-400 font-mono">{metric.avg_mae} pts</span>
          </div>
          <div className="flex items-center justify-between text-xs font-bold">
            <span className="text-slate-500 font-normal">Med MAE:</span>
            <span className="text-rose-400 font-mono">{metric.median_mae} pts</span>
          </div>
        </div>

      </div>

      {/* Stability Metrics Footer */}
      <div className="flex flex-wrap items-center justify-between pt-3 border-t border-[#181f2f] text-[10px] font-bold text-slate-500">
        <div className="flex items-center gap-1">
          <Zap className="w-3.5 h-3.5 text-indigo-400" />
          <span>Std Dev: <span className="font-mono text-slate-300">{metric.movement_std_dev} pts</span></span>
        </div>

        <div className="flex items-center gap-1">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span>Samples Evaluated: <span className="font-mono text-slate-300">{metric.samples}</span></span>
        </div>

        <div className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-indigo-400" />
          <span>Edge Decay: 
            <span className={`font-mono ml-1 ${
              (metric.edge_decay || 0) < 0 ? "text-rose-400" : "text-emerald-400"
            }`}>
              {(metric.edge_decay || 0) >= 0 ? "+" : ""}{metric.edge_decay}%
            </span>
          </span>
        </div>
      </div>

    </div>
  );
}
