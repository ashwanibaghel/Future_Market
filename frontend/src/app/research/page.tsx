"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import TopBar from "@/components/TopBar";
import { 
  Database, CheckCircle2, Clock, ShieldCheck, 
  BarChart2, FileDown, Calendar, RefreshCw, AlertCircle
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

interface DatasetStatus {
  total_samples: number;
  completed_labels: number;
  pending_labels: number;
  label_quality_breakdown: {
    FULL: number;
    PARTIAL: number;
    INCOMPLETE: number;
  };
  timeframe_breakdown: {
    "1m": number;
    "5m": number;
    "15m": number;
  };
  expiry_breakdown: {
    WEEKLY: number;
    MONTHLY: number;
  };
  data_quality_metrics: {
    avg_quality_score: number;
    missing_iv_pct: number;
    missing_pcr_pct: number;
  };
  class_balance: {
    "15m": { UP: number; DOWN: number; SIDEWAYS: number };
    "30m": { UP: number; DOWN: number; SIDEWAYS: number };
    "60m": { UP: number; DOWN: number; SIDEWAYS: number };
  };
}

export default function ResearchPage() {
  const [data, setData] = useState<DatasetStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastSync, setLastSync] = useState<Date | null>(new Date());

  // Export filters
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [exportTimeframe, setExportTimeframe] = useState("");
  const [exportSymbol, setExportSymbol] = useState("");
  const [exporting, setExporting] = useState(false);

  const fetchStatus = async () => {
    try {
      setError(null);
      const res = await fetch(`${BACKEND_URL}/api/ml-dataset-status`);
      if (!res.ok) {
        throw new Error("Failed to fetch ML Feature Store status.");
      }
      const json = await res.json();
      setData(json);
      setLastSync(new Date());
    } catch (err: any) {
      setError(err.message || "An error occurred.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchStatus();
  };

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    setExporting(true);
    try {
      let query = "";
      if (startDate) query += `&start_date=${startDate}`;
      if (endDate) query += `&end_date=${endDate}`;
      if (exportTimeframe) query += `&timeframe=${exportTimeframe}`;
      if (exportSymbol) query += `&symbol=${exportSymbol}`;
      
      // Clean query string
      if (query.startsWith("&")) {
        query = "?" + query.substring(1);
      } else if (query) {
        query = "?" + query;
      }

      window.open(`${BACKEND_URL}/api/ml-dataset-export${query}`);
    } catch (err) {
      console.error("Export failed", err);
    } finally {
      setExporting(false);
    }
  };

  const renderHorizontalPercentageBar = (up: number, sideways: number, down: number) => {
    const total = up + sideways + down;
    if (total === 0) {
      return (
        <div className="h-6 w-full bg-[#1a2230] rounded-xl flex items-center justify-center text-[10px] font-bold text-slate-500">
          No Outcomes Recorded
        </div>
      );
    }
    const upPct = (up / total) * 100;
    const sidewaysPct = (sideways / total) * 100;
    const downPct = (down / total) * 100;

    return (
      <div className="flex flex-col gap-1.5 w-full">
        <div className="h-6 w-full rounded-xl overflow-hidden flex font-mono text-[9px] font-black text-slate-900">
          {upPct > 0 && (
            <div 
              style={{ width: `${upPct}%` }} 
              className="bg-emerald-500 flex items-center justify-center transition-all hover:brightness-110"
              title={`UP: ${up} (${upPct.toFixed(1)}%)`}
            >
              {upPct > 12 && `${upPct.toFixed(0)}% UP`}
            </div>
          )}
          {sidewaysPct > 0 && (
            <div 
              style={{ width: `${sidewaysPct}%` }} 
              className="bg-slate-400 flex items-center justify-center transition-all hover:brightness-110"
              title={`SIDEWAYS: ${sideways} (${sidewaysPct.toFixed(1)}%)`}
            >
              {sidewaysPct > 12 && `${sidewaysPct.toFixed(0)}% SIDE`}
            </div>
          )}
          {downPct > 0 && (
            <div 
              style={{ width: `${downPct}%` }} 
              className="bg-rose-500 flex items-center justify-center transition-all hover:brightness-110"
              title={`DOWN: ${down} (${downPct.toFixed(1)}%)`}
            >
              {downPct > 12 && `${downPct.toFixed(0)}% DOWN`}
            </div>
          )}
        </div>
        <div className="flex justify-between text-[10px] font-bold text-slate-500 px-1">
          <span>UP: {up}</span>
          <span>SIDEWAYS: {sideways}</span>
          <span>DOWN: {down}</span>
        </div>
      </div>
    );
  };

  const renderProgressBar = (value: number, total: number, colorClass: string) => {
    const pct = total > 0 ? (value / total) * 100 : 0;
    return (
      <div className="flex flex-col gap-1.5 w-full">
        <div className="flex justify-between text-[11px] font-bold text-slate-400">
          <span>Count: {value}</span>
          <span>{pct.toFixed(1)}%</span>
        </div>
        <div className="h-2 w-full bg-[#18202d] rounded-full overflow-hidden">
          <div 
            style={{ width: `${pct}%` }} 
            className={`h-full rounded-full transition-all ${colorClass}`}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#060810]">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar
          symbol="NIFTY"
          onSymbolChange={() => {}}
          onRefresh={handleRefresh}
          isRefreshing={refreshing}
          lastSyncTime={lastSync}
          providerConnected={true}
          title="ML Research Console"
          subtitle="Feature Store analysis, retrospective labels, and dataset health"
        />

        <main className="flex-1 overflow-y-auto p-5 md:p-7 pb-24 md:pb-8">
          {loading && (
            <div className="flex items-center justify-center py-40">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && error && (
            <div className="max-w-md mx-auto mt-16 p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl text-center">
              <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-3" />
              <p className="text-rose-400 font-bold mb-4">{error}</p>
              <button 
                onClick={fetchStatus} 
                className="px-5 py-2 bg-rose-600 text-white rounded-xl text-xs font-bold hover:bg-rose-500 transition-colors"
              >
                Retry Connection
              </button>
            </div>
          )}

          {!loading && !error && data && (
            <div className="flex flex-col gap-6 max-w-6xl mx-auto">
              
              {/* ─── Metric Cards (Dataset Growth) ─── */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 hover:border-[#2a3347] transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Total Samples</span>
                    <Database className="w-4 h-4 text-indigo-400" />
                  </div>
                  <span className="text-2xl font-black font-mono text-slate-100">{data.total_samples.toLocaleString()}</span>
                  <span className="block text-[11px] text-slate-500 mt-1">1m/5m/15m snapshots</span>
                </div>

                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 hover:border-[#2a3347] transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Completed Labels</span>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  </div>
                  <span className="text-2xl font-black font-mono text-emerald-400">{data.completed_labels.toLocaleString()}</span>
                  <span className="block text-[11px] text-slate-500 mt-1">
                    {data.total_samples > 0 
                      ? `${((data.completed_labels / data.total_samples) * 100).toFixed(1)}% complete` 
                      : "0% complete"}
                  </span>
                </div>

                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 hover:border-[#2a3347] transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Pending Labels</span>
                    <Clock className="w-4 h-4 text-amber-400" />
                  </div>
                  <span className="text-2xl font-black font-mono text-amber-400">{data.pending_labels.toLocaleString()}</span>
                  <span className="block text-[11px] text-slate-500 mt-1">Waiting for 60m outcomes</span>
                </div>

                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 hover:border-[#2a3347] transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Data Quality Score</span>
                    <ShieldCheck className="w-4 h-4 text-indigo-400" />
                  </div>
                  <span className="text-2xl font-black font-mono text-indigo-400">{data.data_quality_metrics.avg_quality_score}/100</span>
                  <span className="block text-[11px] text-slate-500 mt-1">Average snapshot integrity</span>
                </div>
              </div>

              {/* ─── Coverage & Health Row ─── */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                
                {/* Timeframe Coverage */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5">
                  <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">Timeframe Coverage</span>
                  <div className="flex flex-col gap-4">
                    <div>
                      <span className="block text-xs font-bold text-slate-400 mb-1">1-Minute Candles (1m)</span>
                      {renderProgressBar(data.timeframe_breakdown["1m"], data.total_samples, "bg-indigo-500")}
                    </div>
                    <div>
                      <span className="block text-xs font-bold text-slate-400 mb-1">5-Minute Rollups (5m)</span>
                      {renderProgressBar(data.timeframe_breakdown["5m"], data.total_samples, "bg-indigo-400")}
                    </div>
                    <div>
                      <span className="block text-xs font-bold text-slate-400 mb-1">15-Minute Rollups (15m)</span>
                      {renderProgressBar(data.timeframe_breakdown["15m"], data.total_samples, "bg-violet-500")}
                    </div>
                  </div>
                </div>

                {/* Expiry & Label Quality */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5">
                  <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">Expiry & Label Quality</span>
                  <div className="flex flex-col gap-4">
                    <div>
                      <span className="block text-xs font-bold text-slate-400 mb-1">Weekly Expiries</span>
                      {renderProgressBar(data.expiry_breakdown.WEEKLY, data.total_samples, "bg-emerald-500")}
                    </div>
                    <div>
                      <span className="block text-xs font-bold text-slate-400 mb-1">Monthly Expiries</span>
                      {renderProgressBar(data.expiry_breakdown.MONTHLY, data.total_samples, "bg-teal-500")}
                    </div>
                    <div className="border-t border-[#1e2433] pt-3 mt-1">
                      <div className="flex justify-between text-[11px] font-bold text-slate-500">
                        <span>Label Status:</span>
                        <span>Full: {data.label_quality_breakdown.FULL} | Part: {data.label_quality_breakdown.PARTIAL}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Data Integrity / Issue Monitor */}
                <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5">
                  <span className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">Data Integrity Issues</span>
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between p-3.5 bg-[#141a24] rounded-xl border border-[#1e2433]">
                      <div>
                        <span className="block text-xs font-bold text-slate-300">Missing IV Rate</span>
                        <span className="text-[10px] text-slate-500">Strikes with zero Implied Volatility</span>
                      </div>
                      <span className={`text-sm font-black font-mono ${data.data_quality_metrics.missing_iv_pct > 15 ? "text-rose-400" : "text-slate-300"}`}>
                        {data.data_quality_metrics.missing_iv_pct}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-[#141a24] rounded-xl border border-[#1e2433]">
                      <div>
                        <span className="block text-xs font-bold text-slate-300">Missing PCR Rate</span>
                        <span className="text-[10px] text-slate-500">Snapshots without Put-Call ratios</span>
                      </div>
                      <span className={`text-sm font-black font-mono ${data.data_quality_metrics.missing_pcr_pct > 10 ? "text-rose-400" : "text-slate-300"}`}>
                        {data.data_quality_metrics.missing_pcr_pct}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-[#141a24] rounded-xl border border-[#1e2433]">
                      <div>
                        <span className="block text-xs font-bold text-slate-300">Label Completeness</span>
                        <span className="text-[10px] text-slate-500">Snapshots with full target labels</span>
                      </div>
                      <span className="text-sm font-black font-mono text-emerald-400">
                        {data.total_samples > 0 
                          ? `${((data.label_quality_breakdown.FULL / data.total_samples) * 100).toFixed(1)}%` 
                          : "100%"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* ─── Class Balance Breakdown ─── */}
              <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-6">
                  <BarChart2 className="w-4 h-4 text-indigo-400" />
                  <span className="text-sm font-bold text-slate-300">Target Labels Class Balance (UP / SIDEWAYS / DOWN)</span>
                </div>
                <div className="flex flex-col gap-6">
                  <div>
                    <span className="block text-xs font-black text-slate-400 uppercase mb-2">15-Minute Horizon (direction_15m)</span>
                    {renderHorizontalPercentageBar(data.class_balance["15m"].UP, data.class_balance["15m"].SIDEWAYS, data.class_balance["15m"].DOWN)}
                  </div>
                  <div className="border-t border-[#1a2230] pt-4">
                    <span className="block text-xs font-black text-slate-400 uppercase mb-2">30-Minute Horizon (direction_30m)</span>
                    {renderHorizontalPercentageBar(data.class_balance["30m"].UP, data.class_balance["30m"].SIDEWAYS, data.class_balance["30m"].DOWN)}
                  </div>
                  <div className="border-t border-[#1a2230] pt-4">
                    <span className="block text-xs font-black text-slate-400 uppercase mb-2">60-Minute Horizon (direction_60m)</span>
                    {renderHorizontalPercentageBar(data.class_balance["60m"].UP, data.class_balance["60m"].SIDEWAYS, data.class_balance["60m"].DOWN)}
                  </div>
                </div>
              </div>

              {/* ─── Export Dataset Panel ─── */}
              <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Calendar className="w-4 h-4 text-indigo-400" />
                  <span className="text-sm font-bold text-slate-300">Export Labeled Dataset</span>
                </div>
                <p className="text-xs text-slate-500 mb-6">
                  Filters options features and retrospective labels. Export format is CSV with complete columns.
                </p>
                <form onSubmit={handleExport} className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                  <div>
                    <label className="block text-[9px] font-black text-slate-500 uppercase mb-2">Start Date</label>
                    <input 
                      type="date" 
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full bg-[#141a24] border border-[#1e2433] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] font-black text-slate-500 uppercase mb-2">End Date</label>
                    <input 
                      type="date" 
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full bg-[#141a24] border border-[#1e2433] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[9px] font-black text-slate-500 uppercase mb-2">Timeframe</label>
                    <select
                      value={exportTimeframe}
                      onChange={(e) => setExportTimeframe(e.target.value)}
                      className="w-full bg-[#141a24] border border-[#1e2433] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="">All Timeframes</option>
                      <option value="1m">1-Minute (1m)</option>
                      <option value="5m">5-Minute (5m)</option>
                      <option value="15m">15-Minute (15m)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[9px] font-black text-slate-500 uppercase mb-2">Symbol</label>
                    <select
                      value={exportSymbol}
                      onChange={(e) => setExportSymbol(e.target.value)}
                      className="w-full bg-[#141a24] border border-[#1e2433] rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="">All Symbols</option>
                      <option value="NIFTY">NIFTY</option>
                      <option value="BANKNIFTY">BANKNIFTY</option>
                    </select>
                  </div>
                  <div>
                    <button 
                      type="submit" 
                      disabled={exporting}
                      className="w-full flex items-center justify-center gap-2 bg-indigo-600 text-white rounded-xl py-2 px-4 text-xs font-bold hover:bg-indigo-500 transition-colors disabled:opacity-50"
                    >
                      {exporting ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileDown className="w-3.5 h-3.5" />
                      )}
                      <span>{exporting ? "Preparing..." : "Export CSV"}</span>
                    </button>
                  </div>
                </form>
              </div>

            </div>
          )}
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
