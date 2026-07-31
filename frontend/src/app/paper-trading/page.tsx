"use client";

import React, { useState, useEffect } from "react";

interface ModelOpinion {
  name: string;
  opinion: string;
  status: string;
}

interface TradeItem {
  time: string;
  decision: string;
  entry: number;
  exit: number;
  pnl: number;
  reason: string;
  status: string;
}

interface DashboardData {
  mode: "PLAYBACK" | "LIVE";
  virtual_capital: number;
  starting_capital: number;
  todays_pnl: number;
  todays_roi_pct: number;
  current_market: string;
  market_status: string;
  current_candle_time: string;
  status: string;
  current_ai_decision: {
    decision: string;
    confidence: number;
    reason: string;
    sentiment: string;
    risk_level: string;
  };
  model_opinions: Record<string, ModelOpinion>;
  decision_fusion: {
    synthesis_summary: string;
    dominant_weights: string[];
    consensus_pct: number;
  };
  mod13_review: {
    role: string;
    why_trade_taken: string;
    confidence_justified: string;
    should_trade_delay: string;
    exit_evaluation: string;
    lessons: string;
    counterfactual: string;
  };
  total_signals: number;
  executed_trades: number;
  no_trade_count: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  avg_profit: number;
  avg_loss: number;
  max_drawdown_pct: number;
  trade_history: TradeItem[];
}

export default function PaperTradingControlRoom() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [stepping, setStepping] = useState<boolean>(false);
  const [market, setMarket] = useState<string>("NIFTY");

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/paper-trading/dashboard`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleModeSwitch = async (newMode: "PLAYBACK" | "LIVE") => {
    try {
      const res = await fetch(`${backendUrl}/api/paper-trading/mode?mode=${newMode}`, {
        method: "POST",
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error("Failed to set mode:", err);
    }
  };

  const handleStep = async () => {
    setStepping(true);
    try {
      const res = await fetch(`${backendUrl}/api/paper-trading/playback/step?symbol=${market}`, {
        method: "POST",
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error("Failed to step playback:", err);
    } finally {
      setStepping(false);
    }
  };

  const handleRun10 = async () => {
    setStepping(true);
    try {
      const res = await fetch(`${backendUrl}/api/paper-trading/playback/run?steps=10&symbol=${market}`, {
        method: "POST",
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error("Failed to run playback:", err);
    } finally {
      setStepping(false);
    }
  };

  const handleReset = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/paper-trading/reset?capital=100000`, {
        method: "POST",
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.error("Failed to reset account:", err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6 font-mono">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-400 text-sm">Connecting to AI Trader Control Room Engine...</p>
        </div>
      </div>
    );
  }

  const dec = data?.current_ai_decision;
  const isIdle = data?.total_signals === 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-4 md:p-8 space-y-6">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* 1. TOP SECTION */}
        <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-slate-950 border border-slate-800 rounded-2xl p-5 md:p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className={`w-3 h-3 rounded-full ${data?.mode === "LIVE" ? "bg-emerald-500 animate-ping" : "bg-amber-500"}`}></span>
              <h1 className="text-xl md:text-2xl font-black text-white tracking-tight">
                AI TRADER CONTROL ROOM
              </h1>
              <span className="px-2.5 py-0.5 text-xs font-bold bg-slate-800 text-slate-300 rounded-full border border-slate-700">
                Mode: {data?.mode}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-400 font-mono pt-1">
              <span>Market Status: <strong className={data?.market_status === "OPEN" ? "text-emerald-400" : "text-amber-400"}>{data?.market_status}</strong></span>
              <span>Candle Time: <strong className="text-white">{data?.current_candle_time}</strong></span>
              <span>System Status: <strong className="text-emerald-400">{data?.status}</strong></span>
            </div>
          </div>

          {/* MARKET SELECTOR & MODE SWITCH */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex bg-slate-950/80 p-1 rounded-xl border border-slate-800">
              {["NIFTY", "BANKNIFTY", "SENSEX"].map((m) => (
                <button
                  key={m}
                  onClick={() => setMarket(m)}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    market === m ? "bg-emerald-600 text-white shadow-md" : "text-slate-400 hover:text-white"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>

            <div className="flex bg-slate-950/80 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => handleModeSwitch("PLAYBACK")}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  data?.mode === "PLAYBACK" ? "bg-amber-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                Playback Mode
              </button>
              <button
                onClick={() => handleModeSwitch("LIVE")}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  data?.mode === "LIVE" ? "bg-emerald-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                Live Mode
              </button>
            </div>
          </div>
        </div>

        {/* 2. CURRENT AI DECISION CARD & VIRTUAL ACCOUNT */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* CURRENT AI DECISION CARD (2 COLS) */}
          <div className="lg:col-span-2 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
              <div>
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Current AI Decision
                </span>
                <p className="text-xs text-slate-500 mt-0.5">Synthesized by Decision Fusion Engine</p>
              </div>

              {/* DECISION BADGE */}
              <div className={`px-5 py-2.5 text-lg font-black rounded-xl border ${
                isIdle
                  ? "bg-slate-800 text-slate-400 border-slate-700"
                  : dec?.decision.includes("BUY")
                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
                  : dec?.decision.includes("SELL")
                  ? "bg-rose-500/20 text-rose-400 border-rose-500/40"
                  : "bg-blue-950/40 text-blue-300 border-blue-800/50"
              }`}>
                {isIdle ? "Waiting for first decision..." : dec?.decision}
              </div>
            </div>

            {/* CONFIDENCE BAR & METRICS */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
              <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Confidence</span>
                <span className="text-emerald-400 text-lg font-bold">{isIdle ? "0.0%" : `${dec?.confidence}%`}</span>
              </div>

              <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Market Sentiment</span>
                <span className="text-white text-base font-bold">{isIdle ? "Neutral" : dec?.sentiment}</span>
              </div>

              <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Risk Level</span>
                <span className={`text-base font-bold ${dec?.risk_level === "HIGH" ? "text-rose-400" : "text-emerald-400"}`}>
                  {isIdle ? "LOW" : dec?.risk_level}
                </span>
              </div>
            </div>

            {/* DECISION REASON */}
            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800/80">
              <span className="text-xs font-semibold text-slate-400 block mb-1">Decision Reason</span>
              <p className="text-sm font-medium text-slate-200">
                {isIdle ? "System idle. Click Step 1 Minute Forward or wait for market open." : dec?.reason}
              </p>
            </div>
          </div>

          {/* VIRTUAL ACCOUNT CARD (1 COL) */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5 flex flex-col justify-between">
            <div>
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                Virtual Account
              </div>

              <div className="space-y-1">
                <span className="text-xs text-slate-400">Current Capital</span>
                <div className="text-3xl font-black text-white font-mono">
                  ₹{data?.virtual_capital?.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-4 font-mono text-xs">
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Today&apos;s P/L</span>
                  <span className={`text-sm font-bold ${data?.todays_pnl && data.todays_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    ₹{data?.todays_pnl?.toFixed(2)}
                  </span>
                </div>

                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Today&apos;s ROI</span>
                  <span className="text-sm font-bold text-white">
                    {data?.todays_roi_pct?.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>

            {/* PLAYBACK / RESET CONTROLS */}
            <div className="space-y-2 pt-2 border-t border-slate-800/80">
              {data?.mode === "PLAYBACK" && (
                <>
                  <button
                    onClick={handleStep}
                    disabled={stepping}
                    className="w-full py-2.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition-all shadow-md disabled:opacity-50"
                  >
                    {stepping ? "Stepping..." : "Step 1 Minute Forward ▶"}
                  </button>

                  <button
                    onClick={handleRun10}
                    disabled={stepping}
                    className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-xl transition-all border border-slate-700 disabled:opacity-50"
                  >
                    Fast Forward 10 Steps ⏩
                  </button>
                </>
              )}

              <button
                onClick={handleReset}
                className="w-full py-2 px-3 bg-rose-950/30 hover:bg-rose-900/40 text-rose-300 font-semibold text-[11px] rounded-xl transition-all border border-rose-900/40"
              >
                Reset Account (₹1,00,000.00)
              </button>
            </div>
          </div>
        </div>

        {/* 3. STATISTICS BAR */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 font-mono text-xs">
          {[
            { label: "Total Signals", val: data?.total_signals },
            { label: "Executed Trades", val: data?.executed_trades },
            { label: "No Trade", val: data?.no_trade_count },
            { label: "Wins", val: data?.wins, color: "text-emerald-400" },
            { label: "Losses", val: data?.losses, color: "text-rose-400" },
            { label: "Win Rate", val: `${data?.win_rate_pct}%`, color: "text-emerald-400" },
            { label: "Avg Profit", val: `₹${data?.avg_profit}` },
            { label: "Max Drawdown", val: `${data?.max_drawdown_pct}%` },
          ].map((s, idx) => (
            <div key={idx} className="bg-slate-900 border border-slate-800 rounded-xl p-3 text-center">
              <span className="text-slate-400 block text-[10px] uppercase">{s.label}</span>
              <span className={`text-base font-bold mt-1 block ${s.color || "text-white"}`}>{s.val}</span>
            </div>
          ))}
        </div>

        {/* 4. MODEL STATUS GRID (SPECIALIZED MODELS EXPOSED SEPARATELY) */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-base font-bold text-white">Specialized Model Opinions</h3>
              <p className="text-xs text-slate-400">Every model exposes its own independent opinion</p>
            </div>
            <span className="text-xs font-mono text-emerald-400">10 Active Cognitive Models</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 font-mono text-xs">
            {data?.model_opinions && Object.entries(data.model_opinions).map(([key, m]) => (
              <div key={key} className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 block font-semibold truncate">{m.name}</span>
                <span className="text-xs font-bold text-white block">{isIdle ? "Waiting..." : m.opinion}</span>
                <span className="inline-block px-1.5 py-0.5 text-[9px] font-bold rounded bg-slate-800 text-slate-300">
                  {isIdle ? "NEUTRAL" : m.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 5. DECISION FUSION & MOD_13 REVIEWER */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* DECISION FUSION BREAKDOWN */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-3">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">Decision Fusion Engine</h3>
              <span className="text-xs text-slate-400 font-mono">Synthesizer Layer</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {isIdle ? "Waiting for model output synthesis..." : data?.decision_fusion?.synthesis_summary}
            </p>
            <div className="pt-2 text-[11px] font-mono text-slate-400">
              Dominant Consensus: <strong className="text-emerald-400">{data?.decision_fusion?.consensus_pct}%</strong>
            </div>
          </div>

          {/* MOD_13 REVIEWER CARD (NOT THE TRADER!) */}
          <div className="bg-gradient-to-br from-slate-900 to-purple-950/30 border border-purple-900/40 rounded-2xl p-6 shadow-xl space-y-3">
            <div className="flex justify-between items-center border-b border-purple-900/40 pb-3">
              <h3 className="text-base font-bold text-purple-300">MOD_13 Meta-Cognition Reviewer</h3>
              <span className="px-2 py-0.5 text-[10px] font-bold bg-purple-900/40 text-purple-300 rounded border border-purple-800/50">
                Reviewer ONLY
              </span>
            </div>

            <div className="space-y-2 text-xs font-sans text-slate-300">
              <div>
                <strong className="text-purple-400 block text-[11px]">Why Trade Was Taken:</strong>
                <span>{isIdle ? "Waiting for first trade execution..." : data?.mod13_review?.why_trade_taken}</span>
              </div>

              <div>
                <strong className="text-purple-400 block text-[11px]">Confidence Justification & Lessons:</strong>
                <span>{isIdle ? "Pending review..." : data?.mod13_review?.lessons}</span>
              </div>
            </div>
          </div>
        </div>

        {/* 6. TRADE HISTORY TABLE */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <h3 className="text-base font-bold text-white">Trade History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="uppercase bg-slate-950 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3">Decision</th>
                  <th className="py-2.5 px-3">Entry</th>
                  <th className="py-2.5 px-3">Exit</th>
                  <th className="py-2.5 px-3">PnL</th>
                  <th className="py-2.5 px-3">Reason</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data?.trade_history && data.trade_history.length > 0 ? (
                  data.trade_history.slice().reverse().map((t, i) => (
                    <tr key={i} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 text-slate-300">{t.time}</td>
                      <td className="py-2.5 px-3 font-bold text-emerald-400">{t.decision}</td>
                      <td className="py-2.5 px-3 text-white">₹{t.entry}</td>
                      <td className="py-2.5 px-3 text-white">₹{t.exit}</td>
                      <td className="py-2.5 px-3 text-slate-400">₹{t.pnl.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-slate-300 font-sans">{t.reason}</td>
                      <td className="py-2.5 px-3 font-bold text-amber-400">{t.status}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-slate-500 font-sans">
                      Waiting for first decision...
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
