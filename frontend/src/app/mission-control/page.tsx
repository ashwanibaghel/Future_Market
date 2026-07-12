"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Database,
  FlaskConical,
  Gauge,
  GitBranch,
  Network,
  RefreshCw,
  ShieldCheck,
  Target,
  Wrench,
} from "lucide-react";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import { useMarketData } from "@/context/MarketDataContext";

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type Tab = "dashboard" | "dataset" | "roadmap" | "research" | "execution" | "repair" | "cto";

interface ScoreCard { score: number; status: "READY" | "DEGRADED" | "BLOCKED" }
interface Recommendation { id: string; title: string; confidence: number; priority_score?: number; expected_impact: Record<string, number>; risks: string[]; affected_modules: string[] }
interface EvidenceItem { id: string; severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"; finding: string; metric: string; value: number | string | null; target: number | string | null }
interface Phase { phase: string; title: string; completion_pct: number; completed_tasks: number; total_tasks: number; status: string; modules: string[] }
interface AutoRepairAction { id: string; title: string; severity: string; can_auto_run: boolean; repair_type: string; reason: string; expected_impact: Record<string, number>; safety_rule: string; status: string }

interface MissionControlOverview {
  roadmap: { overall_completion_pct: number; current_stage: string; phases: Phase[] };
  scores: { dataset_health: ScoreCard; ml_readiness: ScoreCard; project_completion: ScoreCard; mission_control_health: ScoreCard };
  dataset: {
    total_samples: number;
    label_coverage: number;
    completed_label_coverage: number;
    missing_iv_pct: number;
    missing_pcr_pct: number;
    missing_greeks_pct: number;
    missing_oi_pct: number;
    collection_gaps: number;
    duplicate_records: number;
    lineage_coverage: number;
    crawl_success_pct: number;
    average_latency_ms: number;
  };
  replay: { status: string; total_replay_days: number; full_replay_days: number; average_session_coverage_pct: number; hindsight_coverage_pct: number; capabilities: Record<string, boolean> };
  pattern_intelligence: { status: string; unique_patterns: number; pattern_observations: number; mature_patterns: number; emerging_patterns: number; sparse_patterns: number; top_lifecycles: Array<{ pattern_id: string; timeframe: string; observed_count: number; reliability_status: string }> };
  rule_audit: { status: string; total_signals_audited: number; accuracy_pct: number; average_confidence: number; signal_quality: { resolved_pct: number; active_signal_pct: number; calibration_gap: number }; rule_contributions: Array<{ rule: string; usage_count: number; coverage_pct: number; status: string }>; rejection_reasons: Array<{ reason: string; count: number; coverage_pct: number }> };
  experiments: { status: string; experiments: Array<{ id: string; title: string; confidence: number; validation_method: string; expected_impact: Record<string, number>; production_mutation_allowed: boolean }> };
  execution_intelligence: { status: string; readiness: Record<string, number>; counts: Record<string, number>; blockers: string[] };
  training_forecast: {
    ready_now: boolean;
    training_scope: string;
    scope_note: string;
    ignored_symbol_filter: string | null;
    first_model_name: string;
    target_samples: number;
    target_full_labels: number;
    target_market_sessions: number;
    current_samples: number;
    current_full_labels: number;
    current_market_sessions: number;
    avg_samples_per_market_day: number;
    market_days_needed: number;
    forecast_training_date: string;
    assumption: string;
    blockers: string[];
    rolling_window_days: number;
    rolling_samples_per_day: number;
    rolling_full_labels_per_day: number;
    quality_score: number;
    readiness_gates: Array<{ key: string; label: string; passed: boolean; value: number; target: number; missing: string }>;
    forecast_rates: Record<string, { samples_per_day: number; full_labels_per_day: number; confidence?: number }>;
    next_target: { title: string; model: string; training_date: string; market_days_needed: number; why_this_first: string; blockers: string[]; action: string };
    model_forecasts: Array<{
      key: string;
      name: string;
      priority: number;
      ready: boolean;
      training_date: string;
      market_days_needed: number;
      readiness_score: number;
      forecast_windows: Record<string, { training_date: string; market_days_needed: number; confidence: number; daily_samples_rate: number; daily_labels_rate: number }>;
      target_samples: number;
      current_samples: number;
      target_full_labels: number;
      current_full_labels: number;
      target_market_sessions: number;
      current_market_sessions: number;
      extra_requirement: string;
      extra_target: number;
      extra_current: number;
      readiness_gates: Array<{ key: string; label: string; passed: boolean; value: number; target: number; missing: string }>;
      training_quality_estimate: {
        if_trained_today: { low: number; high: number; center: number };
        after_5_more_trading_days: { low: number; high: number; center: number };
        after_monthly_expiry_cycle: { low: number; high: number; center: number };
        basis: string;
      };
      justification: { ready: boolean; summary: string; missing_data: string[]; failed_gates: Array<{ key: string; label: string; missing: string }> };
      blockers: string[];
    }>;
  };
  auto_repair: { status: string; actions: AutoRepairAction[]; summary: { total_actions: number; auto_runnable: number; needs_approval: number }; hard_limits: string[] };
  knowledge_graph: { question_bank: Record<string, string[]> };
  ai_cto: { bottlenecks: string[]; recommended_next_sprint: Recommendation[]; deployment_gate: string };
  evidence: EvidenceItem[];
  recommendations: Recommendation[];
}

function formatNumber(value: number, digits = 0) {
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function color(value: number) {
  if (value >= 85) return "text-emerald-300";
  if (value >= 60) return "text-amber-300";
  return "text-rose-300";
}

function badgeTone(status: string) {
  if (["READY", "PASS", "Good", "READY_TO_RUN"].includes(status)) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (["DEGRADED", "WARN", "Needs work"].includes(status)) return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return "border-rose-500/30 bg-rose-500/10 text-rose-300";
}

function Progress({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-slate-200">{label}</span>
        <span className={`font-mono text-sm font-bold ${color(value)}`}>{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[#1a2230]">
        <div className="h-full rounded-full bg-cyan-500" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
      {detail && <div className="mt-1.5 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}

function Card({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase text-slate-500">{label}</span>
        <Icon className="h-4 w-4 text-cyan-400" />
      </div>
      <div className="mt-3 font-mono text-2xl font-bold text-slate-100">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{detail}</div>
    </div>
  );
}

function InfoList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) {
    return <div className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{empty}</div>;
  }
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item} className="rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">{item}</div>
      ))}
    </div>
  );
}

export default function MissionControlPage() {
  const { symbol, setSymbol, selectedDate } = useMarketData();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [data, setData] = useState<MissionControlOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (symbol) params.set("symbol", symbol);
    if (selectedDate) params.set("market_date", selectedDate);
    fetch(`${BACKEND_URL}/api/mission-control/overview?${params.toString()}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Mission Control request failed");
        return response.json() as Promise<MissionControlOverview>;
      })
      .then((payload) => {
        setData(payload);
        setError(null);
        setLastSync(new Date());
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setError(requestError instanceof Error ? requestError.message : "Mission Control request failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      });
    return () => controller.abort();
  }, [symbol, selectedDate, refreshNonce]);

  const currentPhase = useMemo(() => {
    if (!data) return null;
    return data.roadmap.phases.find((phase) => phase.phase === data.roadmap.current_stage) || data.roadmap.phases[0];
  }, [data]);

  const datasetNeeds = data ? [
    data.dataset.label_coverage < 95 ? `Labels 95%+ chahiye. Abhi ${data.dataset.label_coverage.toFixed(1)}% hai.` : "",
    data.dataset.missing_iv_pct > 5 ? `Missing IV 5% se neeche lana hai. Abhi ${data.dataset.missing_iv_pct.toFixed(1)}% hai.` : "",
    data.dataset.missing_greeks_pct > 5 ? `Missing Greeks 5% se neeche lana hai. Abhi ${data.dataset.missing_greeks_pct.toFixed(1)}% hai.` : "",
    data.dataset.collection_gaps > 0 ? `${data.dataset.collection_gaps} crawl gaps repair karne hain.` : "",
    data.dataset.duplicate_records > 0 ? `${data.dataset.duplicate_records} duplicate derived rows training se filter karne hain.` : "",
  ].filter(Boolean) : [];
  const primaryModelForecast = data?.training_forecast.model_forecasts[0] || null;

  const refresh = () => {
    setRefreshing(true);
    setRefreshNonce((value) => value + 1);
  };

  const tabs: Array<[Tab, string, React.ComponentType<{ className?: string }>]> = [
    ["dashboard", "Home", Gauge],
    ["dataset", "Dataset", Database],
    ["roadmap", "Roadmap", Target],
    ["research", "Research", FlaskConical],
    ["execution", "Execution", Network],
    ["repair", "Auto Repair", Wrench],
    ["cto", "AI CTO", Bot],
  ];

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
          title="Execution Model"
          subtitle="Dataset, roadmap, training date, and auto repair"
        />

        <main className="flex-1 overflow-y-auto pb-24 md:pb-8">
          <div className="sticky top-0 z-10 border-b border-[#1e2433] bg-[#080b12]/95 px-4 py-3 backdrop-blur md:px-6">
            <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto">
              {tabs.map(([value, label, Icon]) => (
                <button
                  key={value}
                  onClick={() => setTab(value)}
                  className={`flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-xs font-semibold ${
                    tab === value ? "bg-cyan-500/15 text-cyan-300" : "text-slate-500 hover:bg-[#131923] hover:text-slate-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="mx-auto max-w-6xl p-4 md:p-6">
            {loading && <div className="flex h-72 items-center justify-center"><RefreshCw className="h-6 w-6 animate-spin text-cyan-400" /></div>}
            {!loading && error && (
              <div className="flex items-center justify-between rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
                <span>{error}</span>
                <button onClick={refresh} className="rounded-md border border-rose-500/30 p-2" title="Retry"><RefreshCw className="h-4 w-4" /></button>
              </div>
            )}

            {!loading && !error && data && currentPhase && (
              <div className="space-y-5">
                {tab === "dashboard" && (
                  <>
                    <section className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-5">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="text-[11px] font-bold uppercase text-cyan-200">System Decision</div>
                          <h1 className="mt-2 text-2xl font-black tracking-tight text-slate-100">
                            Ab target: {data.training_forecast.next_target.title}
                          </h1>
                          <p className="mt-2 max-w-3xl text-sm leading-6 text-cyan-100/80">
                            {data.training_forecast.next_target.action} Reason: {data.training_forecast.next_target.why_this_first}
                          </p>
                          <div className="mt-3 inline-flex rounded-md border border-cyan-300/20 bg-cyan-950/30 px-3 py-2 text-xs text-cyan-100">
                            Training forecast combined data par hai: {data.training_forecast.scope_note}
                          </div>
                        </div>
                        <div className="rounded-lg border border-cyan-400/30 bg-[#06131d] p-4 lg:w-72">
                          <div className="text-[10px] font-bold uppercase text-cyan-200/70">Expected Training Date</div>
                          <div className="mt-2 font-mono text-3xl font-black text-cyan-200">{data.training_forecast.next_target.training_date}</div>
                          <div className="mt-1 text-xs text-cyan-100/70">
                            {data.training_forecast.next_target.market_days_needed} market days needed
                          </div>
                        </div>
                      </div>
                      <div className="mt-4 grid gap-2 md:grid-cols-2">
                        {data.training_forecast.next_target.blockers.length ? data.training_forecast.next_target.blockers.map((blocker) => (
                          <div key={blocker} className="rounded-md border border-cyan-300/20 bg-cyan-950/30 px-3 py-2 text-sm text-cyan-50">
                            Blocker: {blocker}
                          </div>
                        )) : (
                          <div className="rounded-md border border-emerald-300/20 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-100">
                            Current target is ready for training.
                          </div>
                        )}
                      </div>
                    </section>

                    <section className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div>
                          <div className="flex flex-wrap gap-2">
                            <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-bold uppercase text-cyan-300">Mission Control</span>
                            <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold uppercase text-emerald-300">No auto trading changes</span>
                          </div>
                          <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-100">Simple Execution Model Dashboard</h1>
                          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                            Yahan tumhe seedha dikhega: dataset ki halat, model training kab shuru hogi, current phase kya hai, aur system next kya improve karega.
                          </p>
                        </div>
                        <div className="rounded-lg border border-[#263044] bg-[#080b12] p-4 md:w-64">
                          <div className="text-[10px] font-bold uppercase text-slate-500">First ML Training Date</div>
                          <div className="mt-2 font-mono text-2xl font-black text-cyan-300">{data.training_forecast.forecast_training_date}</div>
                          <div className="mt-1 text-xs text-slate-500">{data.training_forecast.ready_now ? "Ready now" : `${data.training_forecast.market_days_needed} market days needed`}</div>
                        </div>
                      </div>
                    </section>

                    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <Card label="Current Phase" value={currentPhase.title} detail={`${currentPhase.completion_pct}% complete`} icon={Target} />
                      <Card label="Dataset Quality" value={`${data.scores.dataset_health.score.toFixed(1)}%`} detail={data.scores.dataset_health.status} icon={Database} />
                      <Card label="ML Readiness" value={`${data.scores.ml_readiness.score.toFixed(1)}%`} detail={data.training_forecast.first_model_name} icon={Gauge} />
                      <Card label="Auto Repairs" value={`${data.auto_repair.summary.total_actions}`} detail={`${data.auto_repair.summary.auto_runnable} safe actions`} icon={Wrench} />
                    </section>

                    <section className="grid gap-5 lg:grid-cols-[1fr_0.9fr]">
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <h2 className="text-base font-bold text-slate-100">Training Start Calculation</h2>
                        <div className="mt-4 space-y-4">
                          <Progress label="Samples collected" value={Math.min(100, (data.training_forecast.current_samples / data.training_forecast.target_samples) * 100)} detail={`${data.training_forecast.current_samples}/${data.training_forecast.target_samples} samples`} />
                          <Progress label="Full labels" value={Math.min(100, (data.training_forecast.current_full_labels / data.training_forecast.target_full_labels) * 100)} detail={`${data.training_forecast.current_full_labels}/${data.training_forecast.target_full_labels} labels`} />
                          <Progress label="Market sessions" value={Math.min(100, (data.training_forecast.current_market_sessions / data.training_forecast.target_market_sessions) * 100)} detail={`${data.training_forecast.current_market_sessions}/${data.training_forecast.target_market_sessions} sessions`} />
                          <div className="rounded-md border border-[#263044] bg-[#080b12] px-3 py-2 text-xs text-slate-500">{data.training_forecast.assumption}</div>
                        </div>
                      </div>
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <h2 className="text-base font-bold text-slate-100">Dataset Improve Karne Ke Liye</h2>
                        <div className="mt-4"><InfoList items={datasetNeeds} empty="Dataset ke main checks healthy lag rahe hain." /></div>
                      </div>
                    </section>

                    <section className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                      <h2 className="text-base font-bold text-slate-100">All ML Model Training Dates</h2>
                      <div className="mt-4 overflow-x-auto">
                        <div className="mb-3 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
                          Ye dates selected symbol ke liye nahi hain. Ye poore combined dataset ke basis par hain.
                        </div>
                        <table className="w-full min-w-[760px] text-left text-xs">
                          <thead className="text-slate-600">
                            <tr>
                              <th className="py-2">Priority</th>
                              <th>Model</th>
                              <th>Training Date</th>
                              <th>Days Needed</th>
                              <th>Samples</th>
                              <th>Labels</th>
                              <th>Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#1a2230]">
                            {data.training_forecast.model_forecasts.map((model) => (
                              <tr key={model.key}>
                                <td className="py-2 font-mono text-cyan-300">#{model.priority}</td>
                                <td className="font-semibold text-slate-200">{model.name}</td>
                                <td className="font-mono text-slate-300">{model.training_date}</td>
                                <td className="font-mono text-slate-400">{model.market_days_needed}</td>
                                <td className="font-mono text-slate-400">{model.current_samples}/{model.target_samples}</td>
                                <td className="font-mono text-slate-400">{model.current_full_labels}/{model.target_full_labels}</td>
                                <td>
                                  <span className={`rounded-md border px-2 py-1 text-[10px] font-bold ${badgeTone(model.ready ? "READY" : "DEGRADED")}`}>
                                    {model.ready ? "READY" : "PENDING"}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  </>
                )}

                {tab === "dataset" && (
                  <>
                    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <Card label="Samples" value={formatNumber(data.dataset.total_samples)} detail="Feature rows" icon={Database} />
                      <Card label="Labels" value={`${data.dataset.label_coverage.toFixed(1)}%`} detail="Full labels" icon={CheckCircle2} />
                      <Card label="Lineage" value={`${data.dataset.lineage_coverage.toFixed(1)}%`} detail="Explainability" icon={GitBranch} />
                      <Card label="Crawl Success" value={`${data.dataset.crawl_success_pct.toFixed(1)}%`} detail={`${data.dataset.average_latency_ms} ms avg latency`} icon={Gauge} />
                    </section>
                    <section className="grid gap-5 lg:grid-cols-2">
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <h2 className="text-base font-bold text-slate-100">Quality Scores</h2>
                        <div className="mt-4 space-y-4">
                          <Progress label="Dataset health" value={data.scores.dataset_health.score} />
                          <Progress label="Label coverage" value={data.dataset.label_coverage} />
                          <Progress label="Lineage coverage" value={data.dataset.lineage_coverage} />
                          <Progress label="Provider stability" value={data.dataset.crawl_success_pct} />
                        </div>
                      </div>
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <h2 className="text-base font-bold text-slate-100">Problems</h2>
                        <div className="mt-4 space-y-2">
                          {[
                            `Missing IV: ${data.dataset.missing_iv_pct.toFixed(1)}%`,
                            `Missing PCR: ${data.dataset.missing_pcr_pct.toFixed(1)}%`,
                            `Missing Greeks: ${data.dataset.missing_greeks_pct.toFixed(1)}%`,
                            `Missing OI: ${data.dataset.missing_oi_pct.toFixed(1)}%`,
                            `Crawl gaps: ${data.dataset.collection_gaps}`,
                            `Duplicate rows: ${data.dataset.duplicate_records}`,
                          ].map((item) => <div key={item} className="rounded-md border border-[#263044] bg-[#080b12] px-3 py-2 text-sm text-slate-300">{item}</div>)}
                        </div>
                      </div>
                    </section>
                  </>
                )}

                {tab === "roadmap" && (
                  <section className="grid gap-4 lg:grid-cols-3">
                    {data.roadmap.phases.map((phase) => (
                      <div key={phase.phase} className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <div className="flex items-center justify-between gap-3">
                          <h2 className="text-base font-bold text-slate-100">{phase.title}</h2>
                          <span className={`rounded-md border px-2 py-1 text-[10px] font-bold ${badgeTone(phase.status)}`}>{phase.status}</span>
                        </div>
                        <div className="mt-4"><Progress label={`${phase.completed_tasks}/${phase.total_tasks} tasks`} value={phase.completion_pct} /></div>
                        <div className="mt-4 space-y-1">{phase.modules.map((module) => <div key={module} className="text-xs text-slate-500">{module}</div>)}</div>
                      </div>
                    ))}
                  </section>
                )}

                {tab === "research" && (
                  <>
                    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <Card label="Replay Days" value={formatNumber(data.replay.total_replay_days)} detail={`${data.replay.average_session_coverage_pct}% coverage`} icon={Gauge} />
                      <Card label="Patterns" value={formatNumber(data.pattern_intelligence.unique_patterns)} detail={`${data.pattern_intelligence.pattern_observations} observations`} icon={GitBranch} />
                      <Card label="Signals Audited" value={formatNumber(data.rule_audit.total_signals_audited)} detail={`${data.rule_audit.accuracy_pct}% accuracy`} icon={Target} />
                      <Card label="Experiments" value={formatNumber(data.experiments.experiments.length)} detail="Replay validation first" icon={FlaskConical} />
                    </section>
                    <section className="grid gap-5 lg:grid-cols-2">
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <h2 className="text-base font-bold text-slate-100">Pattern Intelligence</h2>
                        <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                          <div><div className="font-mono text-xl text-emerald-300">{data.pattern_intelligence.mature_patterns}</div><div className="text-xs text-slate-500">Mature</div></div>
                          <div><div className="font-mono text-xl text-cyan-300">{data.pattern_intelligence.emerging_patterns}</div><div className="text-xs text-slate-500">Emerging</div></div>
                          <div><div className="font-mono text-xl text-amber-300">{data.pattern_intelligence.sparse_patterns}</div><div className="text-xs text-slate-500">Sparse</div></div>
                        </div>
                        <div className="mt-4 space-y-2">{data.pattern_intelligence.top_lifecycles.slice(0, 5).map((p) => <div key={`${p.timeframe}-${p.pattern_id}`} className="flex justify-between rounded-md border border-[#263044] bg-[#080b12] px-3 py-2 text-xs"><span className="truncate text-slate-300">{p.pattern_id}</span><span className="text-cyan-300">{p.reliability_status}</span></div>)}</div>
                      </div>
                      <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                        <h2 className="text-base font-bold text-slate-100">Rule Audit</h2>
                        <div className="mt-4 space-y-4">
                          <Progress label="Resolved signals" value={data.rule_audit.signal_quality.resolved_pct} />
                          <Progress label="Active signals" value={data.rule_audit.signal_quality.active_signal_pct} />
                          <div className="text-sm text-slate-500">Calibration gap: <span className="font-mono text-amber-300">{data.rule_audit.signal_quality.calibration_gap}</span></div>
                          {data.rule_audit.rule_contributions.slice(0, 5).map((rule) => <div key={rule.rule} className="flex justify-between rounded-md border border-[#263044] bg-[#080b12] px-3 py-2 text-xs"><span className="text-slate-300">{rule.rule}</span><span className="text-cyan-300">{rule.coverage_pct}%</span></div>)}
                        </div>
                      </div>
                    </section>
                  </>
                )}

                {tab === "execution" && (
                  <section className="grid gap-5 lg:grid-cols-2">
                    <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                      <h2 className="text-base font-bold text-slate-100">Future Execution Models</h2>
                      <div className="mt-4 space-y-4">{Object.entries(data.execution_intelligence.readiness).map(([model, value]) => <Progress key={model} label={model.replaceAll("_", " ")} value={value} />)}</div>
                    </div>
                    <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                      <h2 className="text-base font-bold text-slate-100">What Is Blocking It</h2>
                      <div className="mt-4"><InfoList items={data.execution_intelligence.blockers} empty="Execution model blockers abhi nahi mile." /></div>
                      <div className="mt-4 divide-y divide-[#1a2230]">{Object.entries(data.execution_intelligence.counts).map(([key, value]) => <div key={key} className="flex justify-between py-2 text-xs"><span className="text-slate-500">{key.replaceAll("_", " ")}</span><span className="font-mono text-slate-300">{formatNumber(value)}</span></div>)}</div>
                    </div>
                  </section>
                )}

                {tab === "repair" && (
                  <section className="space-y-5">
                    <div className="grid gap-4 md:grid-cols-3">
                      <Card label="Repair Actions" value={formatNumber(data.auto_repair.summary.total_actions)} detail={data.auto_repair.status} icon={Wrench} />
                      <Card label="Safe Auto Run" value={formatNumber(data.auto_repair.summary.auto_runnable)} detail="No raw overwrite" icon={ShieldCheck} />
                      <Card label="Needs Approval" value={formatNumber(data.auto_repair.summary.needs_approval)} detail="Formula/deploy changes" icon={AlertTriangle} />
                    </div>
                    <div className="grid gap-3">
                      {data.auto_repair.actions.map((action) => (
                        <div key={action.id} className="rounded-lg border border-[#202838] bg-[#0d1117] p-4">
                          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div>
                              <div className="text-sm font-bold text-slate-100">{action.title}</div>
                              <div className="mt-1 text-xs text-slate-500">{action.reason}</div>
                              <div className="mt-2 text-xs text-emerald-300">{action.safety_rule}</div>
                            </div>
                            <span className={`rounded-md border px-2 py-1 text-[10px] font-bold ${badgeTone(action.status)}`}>{action.status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4">
                      <h2 className="text-sm font-bold text-emerald-200">Hard Limits</h2>
                      <div className="mt-2 space-y-1">{data.auto_repair.hard_limits.map((item) => <div key={item} className="text-xs text-emerald-100/80">{item}</div>)}</div>
                    </div>
                  </section>
                )}

                {tab === "cto" && (
                  <section className="grid gap-5 lg:grid-cols-2">
                    <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                      <h2 className="text-base font-bold text-slate-100">Next Sprint Priority</h2>
                      <div className="mt-4 space-y-3">{data.ai_cto.recommended_next_sprint.slice(0, 5).map((item) => <div key={item.id} className="rounded-md border border-[#263044] bg-[#080b12] p-3"><div className="flex justify-between gap-3"><span className="text-sm font-semibold text-slate-200">{item.title}</span><span className="font-mono text-xs text-cyan-300">{item.priority_score}</span></div><div className="mt-1 text-xs text-slate-500">Confidence {Math.round(item.confidence * 100)}%</div></div>)}</div>
                    </div>
                    <div className="rounded-lg border border-[#202838] bg-[#0d1117] p-5">
                      <h2 className="text-base font-bold text-slate-100">Simple Q&A</h2>
                      <div className="mt-4 space-y-3">{Object.entries(data.knowledge_graph.question_bank).map(([question, answers]) => <div key={question} className="rounded-md border border-[#263044] bg-[#080b12] p-3"><div className="text-sm font-bold text-cyan-300">{question}</div><div className="mt-2 space-y-1">{answers.slice(0, 5).map((answer) => <div key={answer} className="text-xs text-slate-500">{answer}</div>)}</div></div>)}</div>
                    </div>
                  </section>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
