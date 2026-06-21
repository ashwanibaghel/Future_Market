"use client";

import React, { useMemo } from "react";
import { Gauge, ShieldCheck, Award } from "lucide-react";

interface EdgeMetric {
  market_state: string;
  samples: number;
  success_60m?: number;
  confidence?: string;
  status: string;
}

interface EdgePerformanceChartProps {
  metrics?: EdgeMetric[];
}

export default function EdgePerformanceChart({ metrics = [] }: EdgePerformanceChartProps) {
  // Filter for valid metrics and sort by success rate descending
  const activeMetrics = useMemo(() => {
    return metrics
      .filter((m) => m.status === "SUCCESS" && m.success_60m !== undefined)
      .sort((a, b) => (b.success_60m || 0) - (a.success_60m || 0));
  }, [metrics]);

  if (activeMetrics.length === 0) {
    return (
      <div className="w-full bg-[#0d1117]/80 border border-[#1e2433] rounded-xl p-6 text-center text-slate-500 text-xs">
        No active signal outcomes available to evaluate performance.
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-2xl flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/40">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
          <Award className="w-4.5 h-4.5 text-indigo-400" />
          Edge Lab Performance Chart (60m Window)
        </h3>
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
          Success Rankings
        </span>
      </div>

      {/* Bar Chart list */}
      <div className="flex flex-col gap-4">
        {activeMetrics.map((item) => {
          const successRate = item.success_60m || 0;
          
          // Determine colors based on success rate
          let barColor = "bg-rose-500";
          let textColor = "text-rose-400";
          if (successRate >= 60) {
            barColor = "bg-emerald-500";
            textColor = "text-emerald-400";
          } else if (successRate >= 45) {
            barColor = "bg-amber-500";
            textColor = "text-amber-400";
          }

          // Determine confidence style
          const conf = item.confidence || "LOW";
          let confStyle = "text-slate-400 bg-slate-800/50 border-slate-700/30";
          if (conf === "HIGH") {
            confStyle = "text-emerald-400 bg-emerald-500/10 border-emerald-500/25";
          } else if (conf === "MEDIUM") {
            confStyle = "text-amber-400 bg-amber-500/10 border-amber-500/25";
          }

          return (
            <div key={item.market_state} className="flex flex-col gap-1.5 p-3 rounded-lg bg-slate-950/20 border border-slate-800/30 hover:border-slate-800/60 transition-all">
              
              {/* Top metadata line */}
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-slate-200 uppercase tracking-tight">
                  {item.market_state}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-semibold text-slate-500">
                    {item.samples} samples
                  </span>
                  <span className={`text-[8px] font-black uppercase tracking-wider px-2 py-0.5 rounded border ${confStyle}`}>
                    {conf} Confidence
                  </span>
                </div>
              </div>

              {/* Bar and percent row */}
              <div className="flex items-center gap-3">
                {/* Progress bar container */}
                <div className="flex-1 h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800/40 relative">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${successRate}%` }}
                  />
                </div>

                {/* Percentage value */}
                <span className={`text-sm font-black font-mono w-12 text-right ${textColor}`}>
                  {successRate.toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
