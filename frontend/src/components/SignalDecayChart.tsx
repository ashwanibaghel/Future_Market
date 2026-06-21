"use client";

import React, { useMemo } from "react";
import { TrendingDown, LineChart } from "lucide-react";

interface EdgeMetric {
  market_state: string;
  samples: number;
  success_15m?: number;
  success_30m?: number;
  success_60m?: number;
  status: string;
}

interface SignalDecayChartProps {
  metrics?: EdgeMetric[];
}

const STATE_PALETTE: Record<string, { stroke: string; glow: string; label: string }> = {
  "LONG BUILD-UP": { stroke: "#10b981", glow: "rgba(16, 185, 129, 0.4)", label: "Long Build-Up" },
  "SHORT BUILD-UP": { stroke: "#f43f5e", glow: "rgba(244, 63, 94, 0.4)", label: "Short Build-Up" },
  "SHORT COVERING": { stroke: "#6366f1", glow: "rgba(99, 102, 241, 0.4)", label: "Short Covering" },
  "LONG UNWINDING": { stroke: "#f59e0b", glow: "rgba(245, 158, 11, 0.4)", label: "Long Unwinding" },
};

const DEFAULT_LINE_STYLE = { stroke: "#94a3b8", glow: "rgba(148, 163, 184, 0.2)", label: "Neutral" };

export default function SignalDecayChart({ metrics = [] }: SignalDecayChartProps) {
  // Filter for valid metrics
  const activeMetrics = useMemo(() => {
    return metrics.filter(
      (m) =>
        m.status === "SUCCESS" &&
        m.success_15m !== undefined &&
        m.success_30m !== undefined &&
        m.success_60m !== undefined
    );
  }, [metrics]);

  // Chart Layout dimensions
  const width = 460;
  const height = 260;
  
  const paddingLeft = 50;
  const paddingRight = 30;
  const paddingTop = 30;
  const paddingBottom = 40;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // X points mapping
  const xPoints = [
    paddingLeft, // 15m
    paddingLeft + chartWidth / 2, // 30m
    paddingLeft + chartWidth, // 60m
  ];

  // Helper to convert rate to Y coordinate
  const getY = (rate: number) => {
    return paddingBottom + chartHeight - (rate / 100) * chartHeight + (paddingTop - paddingBottom);
  };

  if (activeMetrics.length === 0) {
    return (
      <div className="w-full bg-[#0d1117]/80 border border-[#1e2433] rounded-xl p-6 text-center text-slate-500 text-xs">
        No active signal outcomes available to plot decay curves.
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-5 shadow-2xl flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/40">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
          <LineChart className="w-4.5 h-4.5 text-indigo-400" />
          Signal Decay (15m → 30m → 60m)
        </h3>
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
          <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
          Stability Decay
        </span>
      </div>

      {/* SVG Canvas Container */}
      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible select-none">
          {/* Neon Glow definitions */}
          <defs>
            {activeMetrics.map((item, idx) => {
              const pal = STATE_PALETTE[item.market_state] || DEFAULT_LINE_STYLE;
              return (
                <filter key={`glow-${idx}`} id={`glow-filter-${idx}`} x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              );
            })}
          </defs>

          {/* Grid lines (Y-axis grid at 20%, 40%, 60%, 80%, 100%) */}
          {[0, 20, 40, 60, 80, 100].map((level) => {
            const y = getY(level);
            return (
              <g key={level} className="opacity-10">
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke="#ffffff"
                  strokeWidth="1"
                />
                <text
                  x={paddingLeft - 10}
                  y={y + 4}
                  fill="#ffffff"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="end"
                  fontWeight="bold"
                >
                  {level}%
                </text>
              </g>
            );
          })}

          {/* Vertical Grid lines at horizons */}
          {["15m", "30m", "60m"].map((label, idx) => {
            const x = xPoints[idx];
            return (
              <g key={label}>
                <line
                  x1={x}
                  y1={paddingTop}
                  x2={x}
                  y2={height - paddingBottom}
                  stroke="#334155"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                  className="opacity-30"
                />
                <text
                  x={x}
                  y={height - paddingBottom + 18}
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="middle"
                  fontWeight="bold"
                >
                  {label}
                </text>
              </g>
            );
          })}

          {/* Line plots for each market state */}
          {activeMetrics.map((item, idx) => {
            const pal = STATE_PALETTE[item.market_state] || DEFAULT_LINE_STYLE;
            
            const r15 = item.success_15m || 0;
            const r30 = item.success_30m || 0;
            const r60 = item.success_60m || 0;

            const y15 = getY(r15);
            const y30 = getY(r30);
            const y60 = getY(r60);

            const pathD = `M ${xPoints[0]} ${y15} L ${xPoints[1]} ${y30} L ${xPoints[2]} ${y60}`;

            return (
              <g key={item.market_state}>
                {/* Glow filter background path */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={pal.stroke}
                  strokeWidth="4"
                  opacity="0.15"
                  filter={`url(#glow-filter-${idx})`}
                />
                {/* Core solid path */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={pal.stroke}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* Circles / Markers */}
                <circle
                  cx={xPoints[0]}
                  cy={y15}
                  r="4"
                  fill="#0f172a"
                  stroke={pal.stroke}
                  strokeWidth="2"
                />
                <circle
                  cx={xPoints[1]}
                  cy={y30}
                  r="4"
                  fill="#0f172a"
                  stroke={pal.stroke}
                  strokeWidth="2"
                />
                <circle
                  cx={xPoints[2]}
                  cy={y60}
                  r="4"
                  fill="#0f172a"
                  stroke={pal.stroke}
                  strokeWidth="2"
                />

                {/* Values floating label (Only for the endpoint values to avoid clutter) */}
                <text
                  x={xPoints[2] + 8}
                  y={y60 + 3}
                  fill={pal.stroke}
                  fontSize="8"
                  fontFamily="monospace"
                  fontWeight="black"
                  textAnchor="start"
                >
                  {r60.toFixed(0)}%
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend Grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 pt-2 border-t border-slate-800/50">
        {activeMetrics.map((item) => {
          const pal = STATE_PALETTE[item.market_state] || DEFAULT_LINE_STYLE;
          const r15 = item.success_15m || 0;
          const r60 = item.success_60m || 0;
          const decay = r60 - r15;

          return (
            <div key={item.market_state} className="flex items-center justify-between text-[9px] font-bold text-slate-500 uppercase tracking-wider">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-1 rounded" style={{ backgroundColor: pal.stroke }} />
                <span className="text-slate-300 truncate max-w-[100px]">{pal.label}</span>
              </div>
              <span className={`font-mono ${decay < 0 ? "text-rose-400" : "text-emerald-400"}`}>
                {decay >= 0 ? "+" : ""}{decay.toFixed(1)}% decay
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
