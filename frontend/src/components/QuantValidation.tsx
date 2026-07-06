import React, { useState, useEffect } from "react";
import { 
  FileText, CheckCircle2, AlertTriangle, RefreshCw, 
  Sliders, UserCheck, TrendingUp, BarChart2, Shield 
} from "lucide-react";

interface ReportSummary {
  id: number;
  date: string;
  summary: {
    total_snapshots: number;
    success_rate_pct: number;
    total_signals: number;
    system_win_rate_pct: number;
    system_wins: number;
    system_losses: number;
    correct_avoidances: number;
    missed_opportunities: number;
  };
}

interface ReportDetail {
  id: number;
  date: string;
  summary: {
    summary: {
      total_snapshots: number;
      success_snapshots: number;
      success_rate_pct: number;
      total_signals: number;
      buy_call_count: number;
      buy_put_count: number;
      no_trade_count: number;
      system_trades: number;
      system_win_rate_pct: number;
      system_wins: number;
      system_losses: number;
      system_flats: number;
      correct_avoidances: number;
      missed_opportunities: number;
    };
    confusion_matrix: {
      BUY_CALL: { actual_bullish: number; actual_bearish: number; actual_range: number };
      BUY_PUT: { actual_bullish: number; actual_bearish: number; actual_range: number };
      NO_TRADE: { actual_bullish: number; actual_bearish: number; actual_range: number };
    };
    patterns: Record<string, {
      total: number;
      wins: number;
      losses: number;
      avoidances: number;
      missed: number;
      avg_move: number;
      win_rate_pct: number;
    }>;
    phases: Record<string, {
      total: number;
      wins: number;
      losses: number;
      avoidances: number;
      missed: number;
      win_rate_pct: number;
    }>;
    rules: {
      contributions: Record<string, {
        winning_avg: number;
        losing_avg: number;
        win_count: number;
        loss_count: number;
      }>;
      correlations: Record<string, Record<string, number>>;
    };
    manual_vs_system: {
      manual_decisions_count: number;
      agreement_rate_pct: number;
      manual_win_rate_pct: number;
      manual_wins: number;
      manual_losses: number;
    };
    data_quality: {
      missing_greeks_snapshots: number;
      missing_iv_snapshots: number;
      outliers_detected: number;
      collection_gaps: number;
    };
  };
  markdown: string;
}

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export default function QuantValidation() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async () => {
    try {
      setLoadingList(true);
      const res = await fetch(`${BACKEND_URL}/api/analytics/reports`);
      if (!res.ok) throw new Error("Failed to fetch reports list");
      const data = await res.json();
      setReports(data);
      if (data.length > 0 && !selectedDate) {
        setSelectedDate(data[0].date);
      }
    } catch (e: any) {
      setError(e.message || "An error occurred");
    } finally {
      setLoadingList(false);
    }
  };

  const fetchDetail = async (date: string) => {
    try {
      setLoadingDetail(true);
      const res = await fetch(`${BACKEND_URL}/api/analytics/reports/${date}`);
      if (!res.ok) throw new Error("Failed to fetch report details");
      const data = await res.json();
      setDetail(data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoadingDetail(false);
    }
  };

  const triggerTodayReport = async () => {
    try {
      setTriggering(true);
      const res = await fetch(`${BACKEND_URL}/api/analytics/reports/trigger`, {
        method: "POST"
      });
      if (!res.ok) throw new Error("Failed to trigger validation");
      await fetchReports();
      if (reports.length > 0) {
        setSelectedDate(reports[0].date);
      }
    } catch (e: any) {
      alert(`Trigger failed: ${e.message}`);
    } finally {
      setTriggering(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  useEffect(() => {
    if (selectedDate) {
      fetchDetail(selectedDate);
    }
  }, [selectedDate]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
      {/* Left Sidebar: Reports List */}
      <div className="lg:col-span-1 bg-[#0b0e14]/90 border border-[#1e2433] rounded-2xl p-4 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-black uppercase tracking-wider text-slate-400">Reports Index</h3>
          <button
            onClick={triggerTodayReport}
            disabled={triggering}
            className="p-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 disabled:opacity-50 transition-colors"
            title="Generate Today's Report"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
          </button>
        </div>

        {loadingList ? (
          <div className="py-8 text-center text-xs text-slate-500">Loading reports index...</div>
        ) : reports.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-600">
            No reports generated yet. Click refresh to trigger today's validation.
          </div>
        ) : (
          <div className="flex flex-col gap-2 overflow-y-auto max-h-[480px] pr-1">
            {reports.map((r) => (
              <button
                key={r.date}
                onClick={() => setSelectedDate(r.date)}
                className={`w-full text-left p-3 rounded-xl border transition-all text-xs flex flex-col gap-1.5 ${
                  selectedDate === r.date
                    ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-300"
                    : "bg-[#0d1117]/40 border-white/5 text-slate-400 hover:border-slate-800 hover:bg-[#0d1117]/80"
                }`}
              >
                <div className="flex items-center justify-between font-black font-mono">
                  <span>{r.date}</span>
                  <span className="text-[10px] bg-white/5 px-1.5 py-0.5 rounded">
                    {r.summary.total_signals || 0} sigs
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-500 font-medium">
                  <span>Win Rate: {r.summary.system_win_rate_pct || 0}%</span>
                  <span>Uptime: {r.summary.success_rate_pct || 0}%</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right Content: Report Details */}
      <div className="lg:col-span-3 flex flex-col gap-6">
        {loadingDetail ? (
          <div className="bg-[#0b0e14]/90 border border-[#1e2433] rounded-2xl p-12 text-center flex flex-col items-center justify-center min-h-[300px]">
            <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin mb-3" />
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Compiling quantitative validation report...</p>
          </div>
        ) : !detail ? (
          <div className="bg-[#0b0e14]/90 border border-[#1e2433] rounded-2xl p-12 text-center text-slate-500 text-xs">
            Select a validation report from the index.
          </div>
        ) : (
          <>
            {/* 1. Quick Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-4 rounded-xl">
                <span className="block text-[8px] font-black text-slate-500 uppercase tracking-widest">System Win Rate</span>
                <span className="text-xl font-black font-mono text-emerald-400 mt-0.5 block">
                  {detail.summary.summary.system_win_rate_pct}%
                </span>
                <span className="text-[9px] text-slate-500">
                  {detail.summary.summary.system_wins}W - {detail.summary.summary.system_losses}L
                </span>
              </div>
              <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-4 rounded-xl">
                <span className="block text-[8px] font-black text-slate-500 uppercase tracking-widest">Trader Alignment</span>
                <span className="text-xl font-black font-mono text-indigo-400 mt-0.5 block">
                  {detail.summary.manual_vs_system.agreement_rate_pct}%
                </span>
                <span className="text-[9px] text-slate-500">
                  Uncle Ji matched system
                </span>
              </div>
              <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-4 rounded-xl">
                <span className="block text-[8px] font-black text-slate-500 uppercase tracking-widest">Gaps & Outliers</span>
                <span className="text-xl font-black font-mono text-rose-400 mt-0.5 block">
                  {detail.summary.data_quality.collection_gaps + detail.summary.data_quality.outliers_detected}
                </span>
                <span className="text-[9px] text-slate-500">
                  {detail.summary.data_quality.collection_gaps} gaps | {detail.summary.data_quality.outliers_detected} outlier
                </span>
              </div>
              <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-4 rounded-xl">
                <span className="block text-[8px] font-black text-slate-500 uppercase tracking-widest">Correct Avoidances</span>
                <span className="text-xl font-black font-mono text-slate-300 mt-0.5 block">
                  {detail.summary.summary.correct_avoidances}
                </span>
                <span className="text-[9px] text-slate-500">
                  Avoided range moves
                </span>
              </div>
            </div>

            {/* 2. Confusion Matrix Panel */}
            <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-5 rounded-2xl flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-indigo-400" />
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-300">Confusion Matrix (60m Excursion)</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-center border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[#1e2433] text-[9px] font-black text-slate-500 uppercase tracking-wider">
                      <th className="pb-3 text-left pl-2">Predicted \ Actual</th>
                      <th className="pb-3 text-emerald-400">Bullish Move</th>
                      <th className="pb-3 text-rose-400">Bearish Move</th>
                      <th className="pb-3 text-slate-400">Rangebound</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    <tr className="border-b border-white/5">
                      <td className="py-3 text-left pl-2 font-sans font-bold text-slate-400">BUY_CALL</td>
                      <td className="py-3 bg-emerald-500/10 text-emerald-400 font-bold">{detail.summary.confusion_matrix.BUY_CALL.actual_bullish}</td>
                      <td className="py-3 bg-rose-500/5 text-rose-400/60">{detail.summary.confusion_matrix.BUY_CALL.actual_bearish}</td>
                      <td className="py-3 bg-slate-900/40 text-slate-500">{detail.summary.confusion_matrix.BUY_CALL.actual_range}</td>
                    </tr>
                    <tr className="border-b border-white/5">
                      <td className="py-3 text-left pl-2 font-sans font-bold text-slate-400">BUY_PUT</td>
                      <td className="py-3 bg-emerald-500/5 text-emerald-400/60">{detail.summary.confusion_matrix.BUY_PUT.actual_bullish}</td>
                      <td className="py-3 bg-rose-500/10 text-rose-400 font-bold">{detail.summary.confusion_matrix.BUY_PUT.actual_bearish}</td>
                      <td className="py-3 bg-slate-900/40 text-slate-500">{detail.summary.confusion_matrix.BUY_PUT.actual_range}</td>
                    </tr>
                    <tr>
                      <td className="py-3 text-left pl-2 font-sans font-bold text-slate-400">NO_TRADE</td>
                      <td className="py-3 bg-orange-500/10 text-orange-400" title="Missed Opportunity">{detail.summary.confusion_matrix.NO_TRADE.actual_bullish}</td>
                      <td className="py-3 bg-orange-500/10 text-orange-400" title="Missed Opportunity">{detail.summary.confusion_matrix.NO_TRADE.actual_bearish}</td>
                      <td className="py-3 bg-emerald-500/10 text-emerald-400 font-bold" title="Correct Avoidance">{detail.summary.confusion_matrix.NO_TRADE.actual_range}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. Pattern Accuracy Table */}
            <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-5 rounded-2xl flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-300">Pattern-wise Win Rates</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[#1e2433] text-[9px] font-black text-slate-500 uppercase tracking-wider">
                      <th className="pb-3 pl-2">Pattern ID</th>
                      <th className="pb-3">Count</th>
                      <th className="pb-3">Win Rate</th>
                      <th className="pb-3">Avg Move (pts)</th>
                      <th className="pb-3">Avoided</th>
                      <th className="pb-3">Missed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(detail.summary.patterns || {}).map(([p_id, p_d]: any) => (
                      <tr key={p_id} className="border-b border-white/5 hover:bg-white/5 transition-colors font-mono">
                        <td className="py-3 pl-2 text-slate-300 font-sans font-bold">{p_id}</td>
                        <td className="py-3 text-slate-400">{p_d.total}</td>
                        <td className={`py-3 font-bold ${p_d.win_rate_pct >= 60 ? "text-emerald-400" : "text-slate-400"}`}>
                          {p_d.win_rate_pct}%
                        </td>
                        <td className={`py-3 ${p_d.avg_move >= 0 ? "text-emerald-400/80" : "text-rose-400/80"}`}>
                          {p_d.avg_move}
                        </td>
                        <td className="py-3 text-slate-500">{p_d.avoidances}</td>
                        <td className="py-3 text-orange-400/80">{p_d.missed}</td>
                      </tr>
                    ))}
                    {Object.keys(detail.summary.patterns || {}).length === 0 && (
                      <tr>
                        <td colSpan={6} className="py-4 text-center text-slate-600 font-sans text-xs">
                          No signal patterns logged for this report session.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 4. Rule Correlation Heatmap */}
            <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-5 rounded-2xl flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-indigo-400" />
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-300">Rule Multi-Collinearity Correlation Matrix</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-center border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[#1e2433] text-[9px] font-black text-slate-500 uppercase tracking-wider">
                      <th className="pb-3 text-left pl-2">Rule</th>
                      {Object.keys(detail.summary.rules.correlations || {}).map((r) => (
                        <th key={r} className="pb-3 truncate max-w-[80px]" title={r}>{r}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {Object.entries(detail.summary.rules.correlations || {}).map(([r1, row]: any) => (
                      <tr key={r1} className="border-b border-white/5">
                        <td className="py-3 text-left pl-2 font-sans font-bold text-slate-400 max-w-[120px] truncate" title={r1}>{r1}</td>
                        {Object.entries(row).map(([r2, val]: any) => {
                          const isHigh = Math.abs(val) >= 0.7 && r1 !== r2;
                          return (
                            <td 
                              key={r2} 
                              className={`py-3 font-bold ${
                                isHigh ? "bg-rose-500/10 text-rose-400" : "text-slate-500"
                              }`}
                              title={`${r1} vs ${r2}: ${val}`}
                            >
                              {val === 1.0 ? "1.00" : val.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 5. Pre-rendered Markdown Text Report */}
            <div className="bg-[#0b0e14]/90 border border-[#1e2433] p-5 rounded-2xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-white/5 pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-400" />
                  <h4 className="text-xs font-black uppercase tracking-wider text-slate-300">Raw Validation Log</h4>
                </div>
              </div>
              <pre className="text-slate-400 text-xs font-mono whitespace-pre-wrap max-h-[300px] overflow-y-auto bg-slate-950/50 p-4 border border-white/5 rounded-xl">
                {detail.markdown}
              </pre>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
