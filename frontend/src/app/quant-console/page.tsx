"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import {
  TrendingUp, TrendingDown, Clock, HelpCircle,
  BarChart3, AlertCircle, RefreshCw, ShieldAlert,
  Play, Pause, SkipForward, SkipBack, X, Calendar,
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

const STATE_STYLE: Record<string, string> = {
  "LONG BUILD-UP":  "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  "SHORT BUILD-UP": "text-rose-400 bg-rose-500/10 border-rose-500/20",
  "SHORT COVERING": "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  "LONG UNWINDING": "text-amber-400 bg-amber-500/10 border-amber-500/20",
  "NEUTRAL":        "text-slate-400 bg-slate-500/10 border-slate-500/20",
};

const STATE_DOT: Record<string, string> = {
  "LONG BUILD-UP":  "border-emerald-500",
  "SHORT BUILD-UP": "border-rose-500",
  "SHORT COVERING": "border-indigo-500",
  "LONG UNWINDING": "border-amber-500",
  "NEUTRAL":        "border-slate-700",
};

const STATE_BG_COLOR: Record<string, string> = {
  "LONG BUILD-UP":  "bg-emerald-500",
  "SHORT BUILD-UP": "bg-rose-500",
  "SHORT COVERING": "bg-indigo-500",
  "LONG UNWINDING": "bg-amber-500",
  "NEUTRAL":        "bg-slate-500",
};

function calc_diff_pct(curr: number, prev: number) {
  if (!prev || prev === 0) return 0;
  return ((curr - prev) / prev) * 100;
}

function renderPct(val: number) {
  if (val === 0) return <span className="text-slate-500 font-mono">0.00%</span>;
  const pos = val > 0;
  return (
    <span className={`inline-flex items-center gap-1 font-mono font-semibold ${pos ? "text-emerald-400" : "text-rose-400"}`}>
      {pos ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {pos ? "+" : ""}{val.toFixed(2)}%
    </span>
  );
}

function fmtNum(n: number) {
  return new Intl.NumberFormat("en-IN").format(n);
}

import { useMarketData } from "@/context/MarketDataContext";

export default function QuantConsolePage() {
  const {
    symbol,
    setSymbol,
    quantData: liveQuantData,
    quantLoading: loading,
    quantError: error,
    isRefreshing,
    lastSync,
    refreshAll,
  } = useMarketData();

  // Replay Console States
  const [replayMode, setReplayMode] = useState(false);
  const [replayBuffer, setReplayBuffer] = useState<any[]>([]);
  const [replayIndex, setReplayIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1000); // 1s per step by default

  const [replayDate, setReplayDate] = useState("2026-06-19");
  const [replayStart, setReplayStart] = useState("09:15");
  const [replayEnd, setReplayEnd] = useState("15:30");
  const [replayLoading, setReplayLoading] = useState(false);

  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "info") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 5000);
  };

  // Load replay data from API
  const handleLoadReplay = async () => {
    setReplayLoading(true);
    try {
      const startIso = `${replayDate}T${replayStart}:00`;
      const endIso = `${replayDate}T${replayEnd}:00`;
      const res = await fetch(`${BACKEND_URL}/api/replay?symbol=${symbol}&start=${startIso}&end=${endIso}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to load replay data");
      }
      const d = await res.json();
      if (d.data && d.data.length > 0) {
        setReplayBuffer(d.data);
        setReplayIndex(0);
        setReplayMode(true);
        setIsPlaying(false);
        showToast("Historical simulation loaded successfully!", "success");
      } else {
        showToast("No historical snapshots found in the selected range.", "error");
      }
    } catch (err: any) {
      showToast("Replay Error: " + err.message, "error");
    } finally {
      setReplayLoading(false);
    }
  };

  // Auto-play interval
  useEffect(() => {
    let intervalId: any = null;
    if (isPlaying && replayMode && replayBuffer.length > 0) {
      intervalId = setInterval(() => {
        setReplayIndex((prev) => {
          if (prev >= replayBuffer.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, playSpeed);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isPlaying, replayMode, replayBuffer, playSpeed]);

  // Compute active local quantData (overrides liveQuantData)
  const quantData = React.useMemo(() => {
    if (replayMode && replayBuffer.length > 0 && replayIndex < replayBuffer.length) {
      const curr = replayBuffer[replayIndex];
      const prev = replayIndex > 0 ? replayBuffer[replayIndex - 1] : null;

      const spot_diff_pct = prev ? ((curr.spot_price - prev.spot_price) / prev.spot_price) * 100 : 0.0;
      const pcr_diff_pct = prev ? ((curr.pcr - prev.pcr) / prev.pcr) * 100 : 0.0;

      // Slice timeline for the latest 15 steps
      const rawTimeline = [];
      const startIdx = Math.max(0, replayIndex - 14);
      for (let j = startIdx; j <= replayIndex; j++) {
        rawTimeline.push(replayBuffer[j]);
      }
      rawTimeline.reverse();

      return {
        ...liveQuantData,
        current: {
          spot_price: curr.spot_price,
          pcr: curr.pcr,
          average_iv: curr.average_iv ?? 12.0,
          market_state: curr.market_state,
          strength: curr.strength,
          total_oi: curr.total_oi ?? 1000000,
          total_volume: curr.total_volume ?? 5000000
        },
        previous: prev ? {
          spot_price: prev.spot_price,
          pcr: prev.pcr,
          average_iv: prev.average_iv ?? 12.0,
          market_state: prev.market_state,
          strength: prev.strength,
          total_oi: prev.total_oi ?? 1000000,
          total_volume: prev.total_volume ?? 5000000
        } : null,
        difference: {
          spot_diff_pct,
          pcr_diff_pct,
          iv_diff_pct: 0.0,
          oi_diff_pct: 0.0,
          volume_diff_pct: 0.0
        },
        rule_explanation: {
          spot_change_pct: spot_diff_pct,
          oi_change_pct: 0.0,
          vol_change_pct: 0.0,
          reason: `Replay Mode: classified as '${curr.market_state}' (${curr.strength} Strength) at ${new Date(curr.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}.`
        },
        timeline: rawTimeline.map(t => ({
          timestamp: t.timestamp,
          spot_price: t.spot_price,
          market_state: t.market_state,
          strength: t.strength,
          pcr: t.pcr,
          insights: t.insights
        }))
      };
    }
    return liveQuantData;
  }, [replayMode, replayBuffer, replayIndex, liveQuantData]);

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
          providerConnected={!error}
          title="Quant Console"
          subtitle="Internal rule validation — Developer only"
        />

        <main className="flex-1 overflow-y-auto p-5 md:p-7 pb-24 md:pb-8">
          {/* Dev-mode banner */}
          <div className="mb-5 flex items-center justify-between gap-2 px-4 py-2.5 bg-violet-500/5 border border-violet-500/15 rounded-xl text-[11px] font-semibold text-violet-400">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-3.5 h-3.5" />
              Internal Quant Validation Console — Not for end-users
            </div>
            {!loading && !error && quantData?.is_mock_data && (
              <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-bold text-[9px] uppercase tracking-wider animate-pulse">
                Mock Data Active
              </span>
            )}
          </div>

          {/* Replay Console Panel */}
          <div className="mb-6 bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4 relative overflow-hidden">
            {/* Glowing accent border */}
            <div className={`absolute top-0 left-0 w-full h-[2px] ${replayMode ? "bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-500 animate-pulse" : "bg-transparent"}`} />

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="text-xs font-black text-slate-300 uppercase tracking-widest flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${replayMode ? "bg-indigo-400 animate-ping" : "bg-slate-600"}`} />
                  Replay Console Sandbox
                </h3>
                <p className="text-[10px] text-slate-500 mt-1">
                  {replayMode 
                    ? "Historical replay simulation active. Live feed paused." 
                    : "Simulate historical index options market state transitions."}
                </p>
              </div>

              {replayMode && (
                <button
                  onClick={() => {
                    setReplayMode(false);
                    setIsPlaying(false);
                    setReplayBuffer([]);
                  }}
                  className="px-3 py-1.5 bg-rose-950/40 border border-rose-500/20 hover:border-rose-500/40 text-rose-300 rounded-xl text-[10px] font-black uppercase tracking-wider flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                  Exit Replay
                </button>
              )}
            </div>

            {/* Controls Row */}
            {!replayMode ? (
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3.5 items-end bg-[#131920]/45 border border-[#1e2433]/40 p-4 rounded-xl">
                <div>
                  <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Date</label>
                  <input
                    type="date"
                    value={replayDate}
                    onChange={(e) => setReplayDate(e.target.value)}
                    className="w-full bg-[#060810] border border-[#1e2433] rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-bold outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Start Time</label>
                  <input
                    type="time"
                    value={replayStart}
                    onChange={(e) => setReplayStart(e.target.value)}
                    className="w-full bg-[#060810] border border-[#1e2433] rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-bold outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">End Time</label>
                  <input
                    type="time"
                    value={replayEnd}
                    onChange={(e) => setReplayEnd(e.target.value)}
                    className="w-full bg-[#060810] border border-[#1e2433] rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-bold outline-none focus:border-indigo-500"
                  />
                </div>
                <button
                  onClick={handleLoadReplay}
                  disabled={replayLoading}
                  className="w-full px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-black uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  {replayLoading ? (
                    <div className="w-3.5 h-3.5 border border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <Calendar className="w-3.5 h-3.5" />
                      Load Simulation
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-4 bg-[#131920]/45 border border-[#1e2433]/40 p-4 rounded-xl">
                {/* Playback Controls Panel */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  {/* Player Buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setReplayIndex(prev => Math.max(0, prev - 1))}
                      disabled={replayIndex === 0}
                      className="p-2 bg-[#060810] border border-[#1e2433] hover:border-indigo-500/40 disabled:opacity-30 rounded-lg text-slate-400 hover:text-slate-200 cursor-pointer"
                      title="Step Backward"
                    >
                      <SkipBack className="w-4 h-4" />
                    </button>
                    
                    <button
                      onClick={() => setIsPlaying(!isPlaying)}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer"
                    >
                      {isPlaying ? (
                        <>
                          <Pause className="w-3.5 h-3.5" /> Pause
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5" /> Play
                        </>
                      )}
                    </button>

                    <button
                      onClick={() => setReplayIndex(prev => Math.min(replayBuffer.length - 1, prev + 1))}
                      disabled={replayIndex === replayBuffer.length - 1}
                      className="p-2 bg-[#060810] border border-[#1e2433] hover:border-indigo-500/40 disabled:opacity-30 rounded-lg text-slate-400 hover:text-slate-200 cursor-pointer"
                      title="Step Forward"
                    >
                      <SkipForward className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Playhead Progress Info */}
                  <div className="flex flex-col gap-1 items-start sm:items-end">
                    <div className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                      <span className="text-[10px] text-slate-500">PLAYHEAD:</span>
                      <span>
                        {new Date(replayBuffer[replayIndex].timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit"
                        })}
                      </span>
                      <span className="text-slate-600">|</span>
                      <span className="text-indigo-400">Step {replayIndex + 1}/{replayBuffer.length}</span>
                    </div>
                    <span className="text-[9px] text-slate-500 font-bold font-mono">
                      SPOT: ₹{fmtNum(replayBuffer[replayIndex].spot_price)} | PCR: {replayBuffer[replayIndex].pcr.toFixed(2)}
                    </span>
                  </div>

                  {/* Speed Selector */}
                  <div className="flex items-center gap-2 bg-[#060810] border border-[#1e2433] p-1 rounded-lg">
                    {[
                      { label: "1s", speed: 1000 },
                      { label: "2s", speed: 2000 },
                      { label: "5s", speed: 5000 },
                    ].map((sp) => (
                      <button
                        key={sp.label}
                        onClick={() => setPlaySpeed(sp.speed)}
                        className={`px-2 py-1 rounded text-[9px] font-black tracking-wider uppercase transition-all cursor-pointer ${
                          playSpeed === sp.speed
                            ? "bg-indigo-600 text-white"
                            : "text-slate-500 hover:text-slate-300"
                        }`}
                      >
                        {sp.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Progress bar slider */}
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max={replayBuffer.length - 1}
                    value={replayIndex}
                    onChange={(e) => {
                      setReplayIndex(parseInt(e.target.value));
                      setIsPlaying(false);
                    }}
                    className="flex-1 accent-indigo-500 h-1 bg-[#060810] rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>

          {loading && (
            <div className="flex items-center justify-center py-32">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && error && (
            <div className="max-w-md mx-auto mt-16 p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl text-center">
              <AlertCircle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
              <p className="text-rose-400 font-bold mb-2">Console Error</p>
              <p className="text-slate-500 text-xs mb-4">{error}</p>
              <button onClick={refreshAll} className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-semibold hover:bg-rose-500">Retry</button>
            </div>
          )}

          {!loading && !error && quantData && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-7xl">

              {/* Left column */}
              <div className="lg:col-span-2 flex flex-col gap-6">

                {/* Section 1 + 2 */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

                  {/* Section 1: Current Snapshot */}
                  <div className="md:col-span-1 bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                    <div>
                      <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 1</span>
                      <h2 className="text-sm font-bold text-slate-300 mt-0.5">Current Snapshot</h2>
                    </div>
                    <div className="flex flex-col gap-3.5">
                      <div>
                        <p className="text-[10px] text-slate-500 font-bold tracking-wide uppercase">Spot Price</p>
                        <p className="text-xl font-black font-mono text-slate-100">₹{fmtNum(quantData.current.spot_price)}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase">PCR</p>
                          <p className="text-base font-bold font-mono text-slate-200">{quantData.current.pcr.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase">Avg IV</p>
                          <p className="text-base font-bold font-mono text-slate-200">{quantData.current.average_iv.toFixed(2)}%</p>
                        </div>
                      </div>
                      <div className="border-t border-[#1e2433] pt-3">
                        <p className="text-[10px] text-slate-500 font-bold uppercase mb-1.5">Market State</p>
                        <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-black border ${STATE_STYLE[quantData.current.market_state] ?? STATE_STYLE["NEUTRAL"]}`}>
                          {quantData.current.market_state}
                        </span>
                        <span className="text-[10px] text-slate-400 font-bold ml-2">{quantData.current.strength}</span>
                      </div>
                    </div>
                  </div>

                  {/* Section 2: Comparison Matrix */}
                  <div className="md:col-span-2 bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-3">
                    <div>
                      <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 2</span>
                      <h2 className="text-sm font-bold text-slate-300 mt-0.5">Comparison Matrix</h2>
                    </div>
                    {quantData.previous ? (
                      <div className="overflow-x-auto mt-1">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-[#1e2433] text-slate-500 font-bold text-[10px] uppercase tracking-wider">
                              <th className="pb-2">Metric</th>
                              <th className="pb-2 text-right">Previous</th>
                              <th className="pb-2 text-right">Current</th>
                              <th className="pb-2 text-right">Change</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#1e2433]/50">
                            {[
                              { label: "Spot", prev: `₹${fmtNum(quantData.previous.spot_price)}`, curr: `₹${fmtNum(quantData.current.spot_price)}`, diff: quantData.difference.spot_diff_pct },
                              { label: "PCR",  prev: quantData.previous.pcr.toFixed(2), curr: quantData.current.pcr.toFixed(2), diff: quantData.difference.pcr_diff_pct },
                              { label: "Avg IV", prev: `${quantData.previous.average_iv.toFixed(2)}%`, curr: `${quantData.current.average_iv.toFixed(2)}%`, diff: quantData.difference.iv_diff_pct },
                              { label: "Total OI", prev: fmtNum(quantData.previous.total_oi), curr: fmtNum(quantData.current.total_oi), diff: quantData.difference.oi_diff_pct },
                              { label: "Volume", prev: fmtNum(quantData.previous.total_volume), curr: fmtNum(quantData.current.total_volume), diff: quantData.difference.volume_diff_pct },
                            ].map((row) => (
                              <tr key={row.label}>
                                <td className="py-2.5 text-slate-400 font-medium">{row.label}</td>
                                <td className="py-2.5 text-right font-mono text-slate-500">{row.prev}</td>
                                <td className="py-2.5 text-right font-mono text-slate-200">{row.curr}</td>
                                <td className="py-2.5 text-right">{renderPct(row.diff)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="flex-1 flex items-center justify-center text-slate-600 text-xs italic py-10">
                        Previous snapshot not yet available.
                      </div>
                    )}
                  </div>
                </div>

                {/* Section 3: Rule Explanation */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6 flex flex-col gap-4">
                  <div>
                    <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 3</span>
                    <h2 className="text-sm font-bold text-slate-300 mt-0.5">Rule Parameters Breakdown</h2>
                  </div>
                  <div className="grid grid-cols-3 gap-4 border-b border-[#1e2433] pb-5">
                    {[
                      { label: "Spot Change", val: quantData.rule_explanation.spot_change_pct, decimals: 3 },
                      { label: "OI Change", val: quantData.rule_explanation.oi_change_pct, decimals: 2 },
                      { label: "Volume Change", val: quantData.rule_explanation.vol_change_pct, decimals: 2 },
                    ].map((metric) => (
                      <div key={metric.label} className="bg-[#131920] border border-[#1e2433] p-3.5 rounded-xl text-center">
                        <p className="text-[10px] text-slate-500 font-black tracking-wider uppercase mb-1">{metric.label}</p>
                        <p className={`text-lg font-black font-mono ${metric.val >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {metric.val >= 0 ? "+" : ""}{metric.val.toFixed(metric.decimals)}%
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-start gap-3 bg-indigo-500/5 border border-indigo-500/10 p-4 rounded-xl">
                    <HelpCircle className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-xs font-bold text-slate-300 mb-1">Classification Logic</h3>
                      <p className="text-xs text-slate-400 leading-relaxed">{quantData.rule_explanation.reason}</p>
                    </div>
                  </div>
                </div>

                {/* Section 5: Historical Directional Alignment */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 5</span>
                      <h2 className="text-sm font-bold text-slate-300 mt-0.5">Historical Directional Alignment</h2>
                    </div>
                    <span className="text-[10px] text-slate-500 font-bold bg-[#131920] px-2.5 py-1 rounded-lg border border-[#1e2433]">
                      Total Completed Outcomes: {quantData.evidence_engine.total_samples}
                    </span>
                  </div>

                  {quantData.evidence_engine.insufficient_data ? (
                    <div className="flex flex-col items-center justify-center p-8 bg-amber-500/5 border border-amber-500/15 rounded-xl text-center">
                      <ShieldAlert className="w-8 h-8 text-amber-500 mb-2 animate-pulse" />
                      <h3 className="text-xs font-bold text-slate-300">Insufficient Historical Data</h3>
                      <p className="text-[10px] text-slate-500 mt-1 max-w-xs leading-relaxed">
                        Minimum {quantData.evidence_engine.min_sample_size} completed outcomes required to generate reliable historical alignments. (Current: {quantData.evidence_engine.total_samples})
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Bullish Buildups */}
                      <div className="bg-[#131920]/40 border border-[#1e2433]/60 rounded-xl p-4 flex flex-col gap-4">
                        <h3 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 border-b border-[#1e2433] pb-2">
                          <TrendingUp className="w-3.5 h-3.5" />
                          Bullish Buildups (Long Build-up / Short Covering)
                        </h3>
                        <div className="flex flex-col gap-3">
                          {["5m", "15m", "30m", "60m"].map((h) => {
                            const val = quantData.evidence_engine.bullish[h];
                            const rate = val?.rate ?? 0;
                            const success = val?.success ?? 0;
                            const total = quantData.evidence_engine.bullish.total;
                            return (
                              <div key={h} className="flex flex-col gap-1">
                                <div className="flex justify-between text-[11px] font-bold">
                                  <span className="text-slate-400 font-mono">Horizon {h}</span>
                                  <span className="text-slate-500">
                                    <span className="text-emerald-400 font-mono">{rate.toFixed(1)}%</span> Alignment ({success}/{total} cases)
                                  </span>
                                </div>
                                <div className="h-2 w-full bg-[#1c2331] rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                                    style={{ width: `${rate}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Bearish Buildups */}
                      <div className="bg-[#131920]/40 border border-[#1e2433]/60 rounded-xl p-4 flex flex-col gap-4">
                        <h3 className="text-xs font-bold text-rose-400 flex items-center gap-1.5 border-b border-[#1e2433] pb-2">
                          <TrendingDown className="w-3.5 h-3.5" />
                          Bearish Buildups (Short Build-up / Long Unwinding)
                        </h3>
                        <div className="flex flex-col gap-3">
                          {["5m", "15m", "30m", "60m"].map((h) => {
                            const val = quantData.evidence_engine.bearish[h];
                            const rate = val?.rate ?? 0;
                            const success = val?.success ?? 0;
                            const total = quantData.evidence_engine.bearish.total;
                            return (
                              <div key={h} className="flex flex-col gap-1">
                                <div className="flex justify-between text-[11px] font-bold">
                                  <span className="text-slate-400 font-mono">Horizon {h}</span>
                                  <span className="text-slate-500">
                                    <span className="text-rose-400 font-mono">{rate.toFixed(1)}%</span> Alignment ({success}/{total} cases)
                                  </span>
                                </div>
                                <div className="h-2 w-full bg-[#1c2331] rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-rose-500 rounded-full transition-all duration-500"
                                    style={{ width: `${rate}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Section 7: Observed Outcome Effect Size */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                  <div>
                    <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 7</span>
                    <h2 className="text-sm font-bold text-slate-300 mt-0.5">Observed Outcome Effect Size (Avg Index Move)</h2>
                  </div>

                  {quantData.evidence_engine.insufficient_data ? (
                    <div className="flex flex-col items-center justify-center p-8 bg-amber-500/5 border border-amber-500/15 rounded-xl text-center">
                      <ShieldAlert className="w-8 h-8 text-amber-500 mb-2 animate-pulse" />
                      <h3 className="text-xs font-bold text-slate-300">Insufficient Historical Data</h3>
                      <p className="text-[10px] text-slate-500 mt-1 max-w-xs leading-relaxed">
                        Minimum {quantData.evidence_engine.min_sample_size} completed outcomes required to generate reliable effect sizes. (Current: {quantData.evidence_engine.total_samples})
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs min-w-[600px]">
                        <thead>
                          <tr className="border-b border-[#1e2433] text-slate-500 font-bold text-[10px] uppercase tracking-wider">
                            <th className="pb-3 pl-2">Buildup State</th>
                            <th className="pb-3 text-right">5m Horizon</th>
                            <th className="pb-3 text-right">15m Horizon</th>
                            <th className="pb-3 text-right">30m Horizon</th>
                            <th className="pb-3 text-right pr-2">60m Horizon</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1e2433]/50">
                          {Object.entries(quantData.effect_size).map(([state, horizons]: [string, any]) => (
                            <tr key={state} className="hover:bg-[#131920]/20 transition-colors">
                              <td className="py-3 pl-2 font-medium">
                                <span className={`inline-block px-2.5 py-0.5 rounded text-[10px] font-black border ${STATE_STYLE[state] ?? STATE_STYLE["NEUTRAL"]}`}>
                                  {state}
                                </span>
                              </td>
                              {["5m", "15m", "30m", "60m"].map((h) => {
                                const pts = horizons[h]?.avg_points ?? 0;
                                const pct = horizons[h]?.avg_pct ?? 0;
                                const samples = horizons[h]?.samples ?? 0;
                                const color = pts > 0 ? "text-emerald-400" : pts < 0 ? "text-rose-400" : "text-slate-500";
                                const prefix = pts > 0 ? "+" : "";

                                return (
                                  <td key={h} className="py-3 text-right font-mono">
                                    <div className={`font-bold ${color}`}>
                                      {prefix}{pts.toFixed(1)} pts
                                    </div>
                                    <div className="text-[10px] text-slate-500">
                                      ({prefix}{pct.toFixed(2)}%) <span className="text-[9px] text-slate-600">n={samples}</span>
                                    </div>
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Section 8: Maximum Excursion Analysis */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 8</span>
                      <h2 className="text-sm font-bold text-slate-300 mt-0.5">Maximum Excursion Analysis (MFE / MAE)</h2>
                    </div>
                  </div>

                  {quantData.evidence_engine.insufficient_data ? (
                    <div className="flex flex-col items-center justify-center p-8 bg-amber-500/5 border border-amber-500/15 rounded-xl text-center">
                      <ShieldAlert className="w-8 h-8 text-amber-500 mb-2 animate-pulse" />
                      <h3 className="text-xs font-bold text-slate-300">Insufficient Historical Data</h3>
                      <p className="text-[10px] text-slate-500 mt-1 max-w-xs leading-relaxed">
                        Minimum {quantData.evidence_engine.min_sample_size} completed outcomes required to generate excursion analysis. (Current: {quantData.evidence_engine.total_samples})
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs min-w-[600px]">
                        <thead>
                          <tr className="border-b border-[#1e2433] text-slate-500 font-bold text-[10px] uppercase tracking-wider">
                            <th className="pb-3 pl-2">Buildup State</th>
                            <th className="pb-3 text-center">Completed Samples</th>
                            <th className="pb-3 text-right">Net Expectancy</th>
                            <th className="pb-3 text-right">Max Favorable (MFE)</th>
                            <th className="pb-3 text-right pr-2">Max Adverse (MAE)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1e2433]/50">
                          {Object.entries(quantData.excursion_analysis).map(([state, data]: [string, any]) => {
                            const expPoints = data.expectancy_points ?? 0.0;
                            const expPct = data.expectancy_pct ?? 0.0;
                            const expColor = expPoints > 0 ? "text-emerald-400" : expPoints < 0 ? "text-rose-400" : "text-slate-500";

                            const mfeAvgPts = data.avg_mfe_points ?? 0.0;
                            const mfeMedPts = data.median_mfe_points ?? 0.0;
                            const mfeBestPts = data.best_mfe_points ?? 0.0;
                            const mfeTime = data.avg_time_to_mfe ?? 0.0;

                            const maeAvgPts = data.avg_mae_points ?? 0.0;
                            const maeMedPts = data.median_mae_points ?? 0.0;
                            const maeWorstPts = data.worst_mae_points ?? 0.0;
                            const maeTime = data.avg_time_to_mae ?? 0.0;

                            return (
                              <tr key={state} className="hover:bg-[#131920]/20 transition-colors">
                                <td className="py-3 pl-2 font-medium">
                                  <span className={`inline-block px-2.5 py-0.5 rounded text-[10px] font-black border ${STATE_STYLE[state] ?? STATE_STYLE["NEUTRAL"]}`}>
                                    {state}
                                  </span>
                                </td>
                                <td className="py-3 text-center font-mono font-bold text-slate-400">
                                  {data.total_samples}
                                </td>
                                <td className="py-3 text-right font-mono">
                                  <div className={`font-bold ${expColor}`}>
                                    {expPoints >= 0 ? "+" : ""}{expPoints.toFixed(1)} pts
                                  </div>
                                  <div className="text-[10px] text-slate-500">
                                    ({expPoints >= 0 ? "+" : ""}{expPct.toFixed(2)}%)
                                  </div>
                                </td>
                                <td className="py-3 text-right font-mono">
                                  <div className="font-bold text-emerald-400">
                                    Avg: +{mfeAvgPts.toFixed(1)} pts
                                  </div>
                                  <div className="text-[10px] text-slate-400">
                                    Med: +{mfeMedPts.toFixed(1)} pts <span className="text-slate-600">| Max: +{mfeBestPts.toFixed(1)}</span>
                                  </div>
                                  <div className="text-[9px] text-slate-500 mt-0.5 flex items-center justify-end gap-1">
                                    <Clock className="w-2.5 h-2.5" />
                                    Avg time: {mfeTime.toFixed(1)}m
                                  </div>
                                </td>
                                <td className="py-3 text-right font-mono pr-2">
                                  <div className="font-bold text-rose-400">
                                    Avg: {maeAvgPts.toFixed(1)} pts
                                  </div>
                                  <div className="text-[10px] text-slate-400">
                                    Med: {maeMedPts.toFixed(1)} pts <span className="text-slate-600">| Min: {maeWorstPts.toFixed(1)}</span>
                                  </div>
                                  <div className="text-[9px] text-slate-500 mt-0.5 flex items-center justify-end gap-1">
                                    <Clock className="w-2.5 h-2.5" />
                                    Avg time: {maeTime.toFixed(1)}m
                                  </div>
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

              {/* Right column */}
              <div className="lg:col-span-1 flex flex-col gap-6">

                {/* Section 4: Timeline */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                  <div>
                    <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 4</span>
                    <h2 className="text-sm font-bold text-slate-300 mt-0.5">Insight & State Timeline</h2>
                  </div>
                  <div className="flex-1 overflow-y-auto max-h-[380px] flex flex-col gap-5 pl-4 border-l border-[#1e2433] ml-2 pr-1">
                    {quantData.timeline.map((step: any, i: number) => (
                      <div key={i} className="relative flex flex-col gap-1.5">
                        <span className={`absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full border-2 bg-[#060810] ${STATE_DOT[step.market_state] ?? STATE_DOT["NEUTRAL"]}`} />
                        <div className="flex justify-between items-center text-[10px] font-bold text-slate-500">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-slate-700" />
                            {new Date(step.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                          </span>
                          <span className="font-mono">PCR: {step.pcr.toFixed(2)}</span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${STATE_STYLE[step.market_state] ?? STATE_STYLE["NEUTRAL"]}`}>
                            {step.market_state}
                          </span>
                          <span className="text-[11px] font-bold font-mono text-slate-400">₹{fmtNum(step.spot_price)}</span>
                        </div>
                        {step.insights?.length > 0 && (
                          <ul className="pl-2 border-l border-[#1e2433] flex flex-col gap-0.5">
                            {step.insights.map((txt: string, j: number) => (
                              <li key={j} className="text-[10px] text-slate-500 leading-relaxed">• {txt}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Section 6: State Occurrence Distribution */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                  <div>
                    <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 6</span>
                    <h2 className="text-sm font-bold text-slate-300 mt-0.5">Buildup State Distribution</h2>
                  </div>
                  <div className="flex flex-col gap-3.5">
                    {Object.entries(quantData.state_distribution).map(([state, d]: [string, any]) => {
                      const percentage = d.percentage;
                      const count = d.count;
                      return (
                        <div key={state} className="flex flex-col gap-1.5">
                          <div className="flex justify-between items-center text-[10px] font-bold">
                            <span className={`px-2 py-0.5 rounded text-[9px] font-black border ${STATE_STYLE[state] ?? STATE_STYLE["NEUTRAL"]}`}>
                              {state}
                            </span>
                            <span className="text-slate-400 font-mono">
                              {percentage.toFixed(1)}% <span className="text-slate-600 font-normal">({count} counts)</span>
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-[#1c2331] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${STATE_BG_COLOR[state] ?? "bg-slate-500"}`}
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Section 6.5: State vs Observed Outcome Matrix */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4">
                  <div>
                    <span className="text-[9px] font-black text-indigo-400 tracking-widest uppercase">Section 6.5</span>
                    <h2 className="text-sm font-bold text-slate-300 mt-0.5">State vs Observed Outcome Matrix (60m)</h2>
                  </div>
                  {quantData.evidence_engine.insufficient_data ? (
                    <div className="flex flex-col items-center justify-center p-6 bg-amber-500/5 border border-amber-500/15 rounded-xl text-center">
                      <ShieldAlert className="w-7 h-7 text-amber-500 mb-1.5 animate-pulse" />
                      <h3 className="text-xs font-bold text-slate-300">Insufficient Data</h3>
                      <p className="text-[9px] text-slate-500 mt-1 max-w-xs">
                        Matrix requires {quantData.evidence_engine.min_sample_size} outcomes.
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#1e2433] text-slate-500 font-black text-[9px] uppercase tracking-wider">
                            <th className="pb-2">State</th>
                            <th className="pb-2 text-center text-emerald-400 font-bold">UP</th>
                            <th className="pb-2 text-center text-indigo-400 font-bold">FLAT</th>
                            <th className="pb-2 text-center text-rose-400 font-bold">DOWN</th>
                            <th className="pb-2 text-right">Samples</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1e2433]/50 text-[10px] font-bold">
                          {Object.entries(quantData.state_outcome_matrix).map(([state, d]: [string, any]) => (
                            <tr key={state}>
                              <td className="py-2.5 text-slate-400 font-medium truncate max-w-[85px]">{state.replace(" BUILD-UP", "")}</td>
                              <td className="py-2.5 text-center font-mono text-emerald-400">{(d.up_pct).toFixed(0)}%</td>
                              <td className="py-2.5 text-center font-mono text-indigo-400">{(d.flat_pct).toFixed(0)}%</td>
                              <td className="py-2.5 text-center font-mono text-rose-400">{(d.down_pct).toFixed(0)}%</td>
                              <td className="py-2.5 text-right font-mono text-slate-500">{d.total_samples}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

              </div>

            </div>
          )}
        </main>
      </div>

      <BottomNav />

      {/* Toast Notification */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-2xl transition-all duration-300 ${
          toast.type === "success" ? "bg-emerald-950/90 border-emerald-500/30 text-emerald-300" :
          toast.type === "error" ? "bg-rose-950/90 border-rose-500/30 text-rose-300" :
          "bg-indigo-950/90 border-indigo-500/30 text-indigo-300"
        }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${
            toast.type === "success" ? "bg-emerald-400" :
            toast.type === "error" ? "bg-rose-400" :
            "bg-indigo-400"
          }`} />
          <span className="text-xs font-bold font-mono">{toast.message}</span>
          <button onClick={() => setToast(null)} className="ml-2 text-slate-500 hover:text-slate-300 cursor-pointer">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
