"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleX,
  Clock3,
  Database,
  Download,
  Gauge,
  GitBranch,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldCheck,
} from "lucide-react";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import { useMarketData } from "@/context/MarketDataContext";

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type ResearchTab = "health" | "replay" | "exports";
type HealthStatus = "READY" | "DEGRADED" | "BLOCKED";

interface HealthCheck {
  key: string;
  label: string;
  passed: boolean;
  value: number;
  target: number;
}

interface DatasetStatus {
  total_samples: number;
  completed_labels: number;
  pending_labels: number;
  label_quality_breakdown: { FULL: number; PARTIAL: number; INCOMPLETE: number };
  timeframe_breakdown: { "1m": number; "5m": number; "15m": number };
  expiry_breakdown: { WEEKLY: number; MONTHLY: number };
  data_quality_metrics: {
    avg_quality_score: number;
    missing_iv_pct: number;
    missing_pcr_pct: number;
    missing_greeks_pct: number;
    missing_oi_pct: number;
    duplicate_records: number;
  };
  research_coverage: {
    pattern_observations: number;
    feature_lineage_records: number;
    metadata_records: number;
    pattern_coverage_pct: number;
    metadata_coverage_pct: number;
    unique_patterns: number;
  };
  collection_health: {
    collection_gaps: number;
    largest_gap_minutes: number;
    crawl_success_pct: number;
    average_latency_ms: number;
    p95_latency_ms: number;
    maximum_latency_ms: number;
  };
  health_summary: {
    score: number;
    status: HealthStatus;
    components: Record<string, number>;
    checks: HealthCheck[];
  };
  class_balance: {
    "15m": { UP: number; DOWN: number; SIDEWAYS: number };
    "30m": { UP: number; DOWN: number; SIDEWAYS: number };
    "60m": { UP: number; DOWN: number; SIDEWAYS: number };
  };
}

interface PatternLibraryItem {
  id: number;
  pattern_id: string;
  pattern_version: string;
  observed_count: number;
  average_confidence: number;
  maximum_age_snapshots: number;
}

interface ReplayPoint {
  timestamp: string;
  spot_price: number;
  pcr: number;
  iv_change: number;
  support: number;
  resistance: number;
  market_state: string;
  strength: string;
  insights: string[];
  pattern: {
    pattern_id: string;
    pattern_version: string;
    confidence: number;
    age_snapshots: number;
    trend_state: string;
    oi_state: string;
    pcr_state: string;
  };
  feature_lineage: Record<string, { sources: string[]; value: string | number }>;
}

interface ReplaySession {
  symbol: string;
  market_date: string;
  timezone: string;
  count: number;
  data: ReplayPoint[];
}

function statusColor(status: HealthStatus) {
  if (status === "READY") return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
  if (status === "DEGRADED") return "text-amber-400 border-amber-500/30 bg-amber-500/10";
  return "text-rose-400 border-rose-500/30 bg-rose-500/10";
}

function formatNumber(value: number, digits = 0) {
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function formatReplayTime(timestamp: string) {
  const utcValue = timestamp.endsWith("Z") ? timestamp : `${timestamp}Z`;
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(utcValue));
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "text-slate-100",
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: string;
}) {
  return (
    <div className="min-w-0 border border-[#202838] bg-[#0d1117] rounded-lg p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[10px] font-bold uppercase text-slate-500">{label}</span>
        <Icon className="h-4 w-4 shrink-0 text-slate-500" />
      </div>
      <div className={`mt-3 truncate font-mono text-2xl font-bold ${tone}`}>{value}</div>
      <div className="mt-1 truncate text-[11px] text-slate-500">{detail}</div>
    </div>
  );
}

function ProgressRow({ label, value, color = "bg-cyan-500" }: { label: string; value: number; color?: string }) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-[11px]">
        <span className="font-medium text-slate-400">{label}</span>
        <span className="font-mono text-slate-300">{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[#1a2230]">
        <div className={`h-full ${color}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function BalanceBar({ values }: { values: { UP: number; DOWN: number; SIDEWAYS: number } }) {
  const total = values.UP + values.DOWN + values.SIDEWAYS;
  const up = total ? (values.UP / total) * 100 : 0;
  const side = total ? (values.SIDEWAYS / total) * 100 : 0;
  const down = total ? (values.DOWN / total) * 100 : 0;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-[#1a2230]">
        <span className="bg-emerald-500" style={{ width: `${up}%` }} />
        <span className="bg-slate-400" style={{ width: `${side}%` }} />
        <span className="bg-rose-500" style={{ width: `${down}%` }} />
      </div>
      <div className="mt-2 flex justify-between font-mono text-[10px] text-slate-500">
        <span className="text-emerald-400">UP {values.UP}</span>
        <span>SIDE {values.SIDEWAYS}</span>
        <span className="text-rose-400">DOWN {values.DOWN}</span>
      </div>
    </div>
  );
}

export default function ResearchPage() {
  const { symbol, setSymbol, selectedDate } = useMarketData();
  const [tab, setTab] = useState<ResearchTab>("health");
  const [data, setData] = useState<DatasetStatus | null>(null);
  const [patterns, setPatterns] = useState<PatternLibraryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [lastSync, setLastSync] = useState<Date | null>(null);

  const [replayDate, setReplayDate] = useState("");
  const [replay, setReplay] = useState<ReplaySession | null>(null);
  const [replayIndex, setReplayIndex] = useState(0);
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [exportTimeframe, setExportTimeframe] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (symbol) params.set("symbol", symbol);
    if (selectedDate) params.set("date", selectedDate);
    const healthUrl = `${BACKEND_URL}/api/ml-dataset-status?${params.toString()}`;
    const patternUrl = `${BACKEND_URL}/api/patterns/library?symbol=${encodeURIComponent(symbol)}&limit=6`;

    Promise.all([
      fetch(healthUrl, { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error("Dataset health request failed");
        return response.json() as Promise<DatasetStatus>;
      }),
      fetch(patternUrl, { signal: controller.signal }).then((response) => {
        if (!response.ok) throw new Error("Pattern library request failed");
        return response.json() as Promise<{ data: PatternLibraryItem[] }>;
      }),
    ])
      .then(([health, patternResponse]) => {
        setData(health);
        setPatterns(patternResponse.data);
        setError(null);
        setLastSync(new Date());
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setError(requestError instanceof Error ? requestError.message : "Dataset health request failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      });

    return () => controller.abort();
  }, [symbol, selectedDate, refreshNonce]);

  useEffect(() => {
    if (!playing || !replay || replay.data.length < 2) return;
    const interval = window.setInterval(() => {
      setReplayIndex((current) => Math.min(replay.data.length - 1, current + 1));
    }, Math.max(80, 1000 / speed));
    return () => window.clearInterval(interval);
  }, [playing, replay, speed]);

  const currentReplay = replay?.data[replayIndex] || null;
  const replayProgress = replay && replay.data.length > 1
    ? (replayIndex / (replay.data.length - 1)) * 100
    : 0;
  const passedChecks = data?.health_summary.checks.filter((check) => check.passed).length || 0;
  const replayMarketDate = replayDate || selectedDate || "";

  const maxPatternCount = useMemo(
    () => Math.max(1, ...patterns.map((pattern) => pattern.observed_count)),
    [patterns],
  );

  const refresh = () => {
    setRefreshing(true);
    setRefreshNonce((value) => value + 1);
  };

  const loadReplay = async () => {
    if (!replayMarketDate) {
      setReplayError("Select a market date first");
      return;
    }
    setReplayLoading(true);
    setReplayError(null);
    setPlaying(false);
    try {
      const url = `${BACKEND_URL}/api/replay/session?symbol=${encodeURIComponent(symbol)}&market_date=${replayMarketDate}`;
      const response = await fetch(url);
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail || "Replay request failed");
      }
      const session = (await response.json()) as ReplaySession;
      setReplay(session);
      setReplayIndex(0);
    } catch (requestError: unknown) {
      setReplayError(requestError instanceof Error ? requestError.message : "Replay request failed");
    } finally {
      setReplayLoading(false);
    }
  };

  const exportDataset = () => {
    const params = new URLSearchParams();
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    if (exportTimeframe) params.set("timeframe", exportTimeframe);
    if (symbol) params.set("symbol", symbol);
    window.open(`${BACKEND_URL}/api/ml-dataset-export?${params.toString()}`);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#060810]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar
          symbol={symbol}
          onSymbolChange={setSymbol}
          onRefresh={refresh}
          isRefreshing={refreshing}
          lastSyncTime={lastSync}
          providerConnected={!error}
          title="Dataset Research"
          subtitle="Health, lineage, patterns, and market replay"
        />

        <main className="flex-1 overflow-y-auto pb-24 md:pb-8">
          <div className="sticky top-0 z-10 border-b border-[#1e2433] bg-[#080b12]/95 px-4 py-3 backdrop-blur md:px-6">
            <div className="flex max-w-7xl items-center gap-1">
              {([
                ["health", ShieldCheck, "Dataset Health"],
                ["replay", Activity, "Market Replay"],
                ["exports", Download, "Exports"],
              ] as const).map(([value, Icon, label]) => (
                <button
                  key={value}
                  onClick={() => setTab(value)}
                  className={`flex h-9 items-center gap-2 rounded-md px-3 text-xs font-semibold transition-colors ${
                    tab === value
                      ? "bg-cyan-500/15 text-cyan-300"
                      : "text-slate-500 hover:bg-[#131923] hover:text-slate-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="mx-auto max-w-7xl p-4 md:p-6">
            {loading && (
              <div className="flex h-64 items-center justify-center">
                <RefreshCw className="h-6 w-6 animate-spin text-cyan-400" />
              </div>
            )}

            {!loading && error && (
              <div className="flex items-center justify-between gap-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-4">
                <div className="flex items-center gap-3">
                  <CircleX className="h-5 w-5 text-rose-400" />
                  <span className="text-sm font-medium text-rose-300">{error}</span>
                </div>
                <button onClick={refresh} className="rounded-md border border-rose-500/30 p-2 text-rose-300" title="Retry">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            )}

            {!loading && !error && data && tab === "health" && (
              <div className="space-y-5">
                <section className="grid gap-4 border-b border-[#1e2433] pb-5 lg:grid-cols-[220px_1fr]">
                  <div className={`rounded-lg border p-5 ${statusColor(data.health_summary.status)}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase">Release Gate</span>
                      <Gauge className="h-4 w-4" />
                    </div>
                    <div className="mt-4 flex items-end gap-2">
                      <span className="font-mono text-5xl font-bold">{data.health_summary.score}</span>
                      <span className="mb-1 text-sm font-bold">/ 100</span>
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t border-current/20 pt-3">
                      <span className="text-sm font-bold">{data.health_summary.status}</span>
                      <span className="font-mono text-xs">{passedChecks}/{data.health_summary.checks.length} checks</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                    <MetricCard label="Samples" value={formatNumber(data.total_samples)} detail="Feature snapshots" icon={Database} />
                    <MetricCard label="Patterns" value={formatNumber(data.research_coverage.pattern_observations)} detail={`${data.research_coverage.unique_patterns} signatures`} icon={GitBranch} tone="text-cyan-300" />
                    <MetricCard label="Lineage" value={formatNumber(data.research_coverage.feature_lineage_records)} detail={`${data.research_coverage.pattern_coverage_pct}% covered`} icon={Activity} tone="text-emerald-300" />
                    <MetricCard label="Full Labels" value={formatNumber(data.label_quality_breakdown.FULL)} detail={`${data.completed_labels} completed`} icon={CheckCircle2} tone="text-emerald-300" />
                    <MetricCard label="Gaps" value={formatNumber(data.collection_health.collection_gaps)} detail={`${data.collection_health.largest_gap_minutes}m largest`} icon={Clock3} tone={data.collection_health.collection_gaps ? "text-amber-300" : "text-emerald-300"} />
                    <MetricCard label="Duplicates" value={formatNumber(data.data_quality_metrics.duplicate_records)} detail="Version-aware" icon={Server} tone={data.data_quality_metrics.duplicate_records ? "text-rose-300" : "text-emerald-300"} />
                  </div>
                </section>

                <section className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
                  <div className="rounded-lg border border-[#202838] bg-[#0d1117]">
                    <div className="flex items-center justify-between border-b border-[#202838] px-4 py-3">
                      <div>
                        <h2 className="text-sm font-bold text-slate-200">Validation Checks</h2>
                        <p className="mt-0.5 text-[10px] uppercase text-slate-600">Sprint release criteria</p>
                      </div>
                      <ShieldCheck className="h-4 w-4 text-cyan-400" />
                    </div>
                    <div className="divide-y divide-[#1a2230]">
                      {data.health_summary.checks.map((check) => (
                        <div key={check.key} className="grid grid-cols-[24px_1fr_90px_90px] items-center gap-2 px-4 py-2.5 text-xs">
                          {check.passed
                            ? <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                            : <AlertTriangle className="h-4 w-4 text-amber-400" />}
                          <span className="font-medium text-slate-300">{check.label}</span>
                          <span className="text-right font-mono text-slate-400">{formatNumber(check.value, 2)}</span>
                          <span className="text-right font-mono text-[10px] text-slate-600">target {check.target}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                    <div className="mb-5 flex items-center justify-between">
                      <div>
                        <h2 className="text-sm font-bold text-slate-200">Coverage Components</h2>
                        <p className="mt-0.5 text-[10px] uppercase text-slate-600">Weighted health inputs</p>
                      </div>
                      <BarChart3 className="h-4 w-4 text-cyan-400" />
                    </div>
                    <div className="space-y-4">
                      <ProgressRow label="Feature quality" value={data.health_summary.components.feature_quality} color="bg-amber-500" />
                      <ProgressRow label="Full label coverage" value={data.health_summary.components.full_label_coverage} color="bg-emerald-500" />
                      <ProgressRow label="Pattern coverage" value={data.health_summary.components.pattern_coverage} />
                      <ProgressRow label="Metadata coverage" value={data.health_summary.components.metadata_coverage} color="bg-blue-500" />
                      <ProgressRow label="Collection continuity" value={data.health_summary.components.continuity} color="bg-violet-500" />
                      <ProgressRow label="Duplicate integrity" value={data.health_summary.components.duplicate_integrity} color="bg-teal-500" />
                    </div>
                  </div>
                </section>

                <section className="grid gap-5 lg:grid-cols-3">
                  <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                    <h2 className="text-sm font-bold text-slate-200">Missing Fields</h2>
                    <div className="mt-4 space-y-4">
                      <ProgressRow label="IV missing" value={data.data_quality_metrics.missing_iv_pct} color="bg-rose-500" />
                      <ProgressRow label="Greeks missing" value={data.data_quality_metrics.missing_greeks_pct} color="bg-rose-500" />
                      <ProgressRow label="PCR missing" value={data.data_quality_metrics.missing_pcr_pct} color="bg-amber-500" />
                      <ProgressRow label="OI missing" value={data.data_quality_metrics.missing_oi_pct} color="bg-amber-500" />
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                    <h2 className="text-sm font-bold text-slate-200">Provider Collection</h2>
                    <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-4">
                      {[
                        ["Success", `${data.collection_health.crawl_success_pct}%`],
                        ["Average", `${formatNumber(data.collection_health.average_latency_ms)} ms`],
                        ["P95", `${formatNumber(data.collection_health.p95_latency_ms)} ms`],
                        ["Maximum", `${formatNumber(data.collection_health.maximum_latency_ms)} ms`],
                      ].map(([label, value]) => (
                        <div key={label} className="border-b border-[#1a2230] pb-3">
                          <div className="text-[10px] uppercase text-slate-600">{label}</div>
                          <div className="mt-1 font-mono text-sm font-bold text-slate-300">{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                    <h2 className="text-sm font-bold text-slate-200">Timeframe Mix</h2>
                    <div className="mt-4 space-y-4">
                      {(["1m", "5m", "15m"] as const).map((timeframe, index) => {
                        const count = data.timeframe_breakdown[timeframe];
                        const pct = data.total_samples ? (count / data.total_samples) * 100 : 0;
                        return <ProgressRow key={timeframe} label={`${timeframe}  ${count}`} value={pct} color={["bg-cyan-500", "bg-blue-500", "bg-violet-500"][index]} />;
                      })}
                    </div>
                  </div>
                </section>

                <section className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
                  <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                    <h2 className="text-sm font-bold text-slate-200">Label Balance</h2>
                    <div className="mt-4 space-y-5">
                      {(["15m", "30m", "60m"] as const).map((horizon) => (
                        <div key={horizon}>
                          <div className="mb-2 text-[10px] font-bold uppercase text-slate-500">{horizon} outcome</div>
                          <BalanceBar values={data.class_balance[horizon]} />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-sm font-bold text-slate-200">Pattern Frequency</h2>
                      <span className="font-mono text-[10px] text-slate-600">pattern-v1.0</span>
                    </div>
                    <div className="mt-4 space-y-3">
                      {patterns.length === 0 && <div className="py-8 text-center text-xs text-slate-600">No pattern observations</div>}
                      {patterns.map((pattern) => (
                        <div key={pattern.id}>
                          <div className="mb-1.5 flex items-center justify-between gap-3 text-[11px]">
                            <span className="min-w-0 truncate font-mono text-slate-300" title={pattern.pattern_id}>{pattern.pattern_id}</span>
                            <span className="shrink-0 font-mono text-cyan-300">{pattern.observed_count}</span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-[#1a2230]">
                            <div className="h-full bg-cyan-500" style={{ width: `${(pattern.observed_count / maxPatternCount) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              </div>
            )}

            {!loading && tab === "replay" && (
              <div className="space-y-5">
                <section className="flex flex-col gap-3 border-b border-[#1e2433] pb-5 md:flex-row md:items-end md:justify-between">
                  <div className="flex flex-wrap items-end gap-3">
                    <label className="block">
                      <span className="mb-1.5 block text-[10px] font-bold uppercase text-slate-600">Market date</span>
                      <input
                        type="date"
                        value={replayMarketDate}
                        onChange={(event) => setReplayDate(event.target.value)}
                        className="h-9 rounded-md border border-[#263044] bg-[#0d1117] px-3 text-xs text-slate-300 outline-none focus:border-cyan-500"
                      />
                    </label>
                    <button
                      onClick={loadReplay}
                      disabled={replayLoading || !replayMarketDate}
                      className="flex h-9 items-center gap-2 rounded-md bg-cyan-600 px-4 text-xs font-bold text-white hover:bg-cyan-500 disabled:opacity-50"
                    >
                      <RefreshCw className={`h-4 w-4 ${replayLoading ? "animate-spin" : ""}`} />
                      Load session
                    </button>
                  </div>
                  {replay && <div className="font-mono text-xs text-slate-500">{replay.count} snapshots · {replay.timezone}</div>}
                </section>

                {replayError && (
                  <div className="flex items-center gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
                    <CircleX className="h-4 w-4" /> {replayError}
                  </div>
                )}

                {!replay && !replayError && (
                  <div className="flex h-72 flex-col items-center justify-center border border-dashed border-[#263044] text-slate-600">
                    <Activity className="mb-3 h-7 w-7" />
                    <span className="text-sm font-medium">No replay session loaded</span>
                  </div>
                )}

                {replay && replay.data.length === 0 && (
                  <div className="flex h-72 items-center justify-center border border-dashed border-[#263044] text-sm text-slate-600">No snapshots for this session</div>
                )}

                {replay && currentReplay && (
                  <>
                    <section className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                      <div className="flex flex-col gap-4 md:flex-row md:items-center">
                        <div className="flex items-center gap-1">
                          <button onClick={() => { setPlaying(false); setReplayIndex(0); }} className="replay-icon" title="Restart replay"><RotateCcw className="h-4 w-4" /></button>
                          <button onClick={() => setReplayIndex((value) => Math.max(0, value - 1))} className="replay-icon" title="Previous snapshot"><ChevronLeft className="h-4 w-4" /></button>
                          <button onClick={() => setPlaying((value) => !value)} className="flex h-9 w-9 items-center justify-center rounded-md bg-cyan-600 text-white hover:bg-cyan-500" title={playing ? "Pause replay" : "Play replay"}>
                            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                          </button>
                          <button onClick={() => setReplayIndex((value) => Math.min(replay.data.length - 1, value + 1))} className="replay-icon" title="Next snapshot"><ChevronRight className="h-4 w-4" /></button>
                        </div>

                        <div className="min-w-0 flex-1">
                          <input
                            type="range"
                            min={0}
                            max={Math.max(0, replay.data.length - 1)}
                            value={replayIndex}
                            onChange={(event) => { setPlaying(false); setReplayIndex(Number(event.target.value)); }}
                            className="w-full accent-cyan-500"
                            aria-label="Replay timeline"
                          />
                          <div className="mt-1 flex justify-between font-mono text-[10px] text-slate-600">
                            <span>{replay.data[0] ? formatReplayTime(replay.data[0].timestamp) : "--"}</span>
                            <span>{replayIndex + 1} / {replay.data.length} · {replayProgress.toFixed(0)}%</span>
                            <span>{replay.data.at(-1) ? formatReplayTime(replay.data.at(-1)!.timestamp) : "--"}</span>
                          </div>
                        </div>

                        <div className="flex rounded-md border border-[#263044] bg-[#080b12] p-0.5">
                          {[1, 5, 10, 30].map((value) => (
                            <button key={value} onClick={() => setSpeed(value)} className={`h-7 min-w-10 rounded px-2 font-mono text-[10px] ${speed === value ? "bg-cyan-500/20 text-cyan-300" : "text-slate-600 hover:text-slate-300"}`}>{value}x</button>
                          ))}
                        </div>
                      </div>
                    </section>

                    <section className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
                      <MetricCard label="IST Time" value={formatReplayTime(currentReplay.timestamp)} detail={`Step ${replayIndex + 1}`} icon={Clock3} tone="text-cyan-300" />
                      <MetricCard label="Spot" value={formatNumber(currentReplay.spot_price, 2)} detail={symbol} icon={Activity} />
                      <MetricCard label="PCR" value={formatNumber(currentReplay.pcr, 3)} detail={`${currentReplay.pattern.pcr_state}`} icon={BarChart3} />
                      <MetricCard label="Pattern" value={`${currentReplay.pattern.confidence}%`} detail={`${currentReplay.pattern.age_snapshots} snapshots`} icon={GitBranch} tone="text-cyan-300" />
                      <MetricCard label="Support" value={formatNumber(currentReplay.support, 2)} detail="OI support" icon={ChevronRight} tone="text-emerald-300" />
                      <MetricCard label="Resistance" value={formatNumber(currentReplay.resistance, 2)} detail="OI resistance" icon={ChevronLeft} tone="text-rose-300" />
                      <MetricCard label="State" value={currentReplay.strength} detail={currentReplay.market_state} icon={Gauge} />
                      <MetricCard label="IV Change" value={`${formatNumber(currentReplay.iv_change, 2)}%`} detail="Replay delta" icon={Activity} />
                    </section>

                    <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117]">
                        <div className="border-b border-[#202838] px-4 py-3">
                          <h2 className="text-sm font-bold text-slate-200">Pattern State</h2>
                        </div>
                        <div className="grid gap-4 p-4 md:grid-cols-2">
                          <div>
                            <div className="font-mono text-sm font-bold text-cyan-300 break-all">{currentReplay.pattern.pattern_id}</div>
                            <div className="mt-1 text-[10px] uppercase text-slate-600">{currentReplay.pattern.pattern_version}</div>
                          </div>
                          <div className="grid grid-cols-3 gap-2">
                            {[currentReplay.pattern.trend_state, currentReplay.pattern.oi_state, currentReplay.pattern.pcr_state].map((state) => (
                              <div key={state} className="rounded-md border border-[#263044] bg-[#111722] px-2 py-2 text-center font-mono text-[10px] text-slate-300">{state}</div>
                            ))}
                          </div>
                        </div>
                        <div className="border-t border-[#202838] p-4">
                          <div className="mb-3 text-[10px] font-bold uppercase text-slate-600">Feature lineage</div>
                          <div className="space-y-2">
                            {Object.entries(currentReplay.feature_lineage).map(([name, lineage]) => (
                              <div key={name} className="grid gap-1 border-b border-[#1a2230] pb-2 text-[11px] md:grid-cols-[130px_1fr_110px]">
                                <span className="font-mono text-cyan-300">{name}</span>
                                <span className="truncate text-slate-500" title={lineage.sources.join(" ← ")}>{lineage.sources.join(" ← ")}</span>
                                <span className="text-right font-mono text-slate-300">{String(lineage.value)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                        <h2 className="text-sm font-bold text-slate-200">Replay Insights</h2>
                        <div className="mt-4 space-y-2">
                          {currentReplay.insights.length === 0 && <div className="text-xs text-slate-600">No insights at this step</div>}
                          {currentReplay.insights.map((insight, index) => (
                            <div key={`${index}-${insight}`} className="border-l-2 border-cyan-500/50 bg-[#111722] px-3 py-2 text-xs leading-5 text-slate-400">{insight}</div>
                          ))}
                        </div>
                      </div>
                    </section>
                  </>
                )}
              </div>
            )}

            {!loading && tab === "exports" && (
              <div className="grid gap-5 lg:grid-cols-2">
                <section className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-slate-200">Labeled Dataset</h2>
                    <Database className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div className="mt-5 grid gap-4 sm:grid-cols-2">
                    <label className="text-[10px] font-bold uppercase text-slate-600">Start date<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="mt-1.5 h-9 w-full rounded-md border border-[#263044] bg-[#080b12] px-3 text-xs text-slate-300" /></label>
                    <label className="text-[10px] font-bold uppercase text-slate-600">End date<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="mt-1.5 h-9 w-full rounded-md border border-[#263044] bg-[#080b12] px-3 text-xs text-slate-300" /></label>
                    <label className="text-[10px] font-bold uppercase text-slate-600 sm:col-span-2">Timeframe<select value={exportTimeframe} onChange={(event) => setExportTimeframe(event.target.value)} className="mt-1.5 h-9 w-full rounded-md border border-[#263044] bg-[#080b12] px-3 text-xs text-slate-300"><option value="">All timeframes</option><option value="1m">1 minute</option><option value="5m">5 minutes</option><option value="15m">15 minutes</option></select></label>
                  </div>
                  <button onClick={exportDataset} className="mt-5 flex h-9 items-center gap-2 rounded-md bg-cyan-600 px-4 text-xs font-bold text-white hover:bg-cyan-500"><Download className="h-4 w-4" />Export CSV</button>
                </section>

                <section className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-slate-200">Research Records</h2>
                    <GitBranch className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div className="mt-5 divide-y divide-[#1a2230]">
                    {[
                      ["Pattern observations", data?.research_coverage.pattern_observations || 0],
                      ["Feature lineage records", data?.research_coverage.feature_lineage_records || 0],
                      ["Dataset metadata records", data?.research_coverage.metadata_records || 0],
                      ["Completed labels", data?.completed_labels || 0],
                    ].map(([label, value]) => (
                      <div key={String(label)} className="flex items-center justify-between py-3 text-xs"><span className="text-slate-500">{label}</span><span className="font-mono font-bold text-slate-300">{formatNumber(Number(value))}</span></div>
                    ))}
                  </div>
                </section>
              </div>
            )}
          </div>
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
