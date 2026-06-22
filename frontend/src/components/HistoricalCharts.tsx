"use client";

import React, { useState, useMemo } from "react";
import { Clock, HelpCircle, Layers, Activity, TrendingUp } from "lucide-react";
import { formatIST } from "@/lib/timeUtils";

interface TrendPoint {
  timestamp: string;
  spot_price: number;
  pcr: number;
  average_iv: number;
  total_call_oi: number;
  total_put_oi: number;
  support: number | null;
  secondary_support: number | null;
  resistance: number | null;
  secondary_resistance: number | null;
}

interface HistoricalChartsProps {
  trends: TrendPoint[];
  loading: boolean;
  error: string | null;
}

// Sleek reusable SVG Line Chart Component
interface SleekLineChartProps {
  title: string;
  data: any[];
  keys: string[];
  colors: string[];
  labels: string[];
  formatY: (val: number) => string;
  formatX: (ts: string) => string;
  showThresholds?: boolean;
}

function SleekLineChart({
  title,
  data,
  keys,
  colors,
  labels,
  formatY,
  formatX,
  showThresholds = false
}: SleekLineChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const padding = { left: 60, right: 20, top: 30, bottom: 40 };
  const width = 600;
  const height = 250;
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Calculate min and max values across all lines to set Y scale
  const { yMin, yMax } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    data.forEach((d) => {
      keys.forEach((k) => {
        const val = d[k];
        if (val !== null && val !== undefined) {
          if (val < min) min = val;
          if (val > max) max = val;
        }
      });
    });

    // Handle single value or flat line
    if (min === max) {
      min -= 1;
      max += 1;
    } else if (min === Infinity || max === -Infinity) {
      min = 0;
      max = 100;
    }

    // Add 10% padding
    const range = max - min;
    return {
      yMin: min - range * 0.1,
      yMax: max + range * 0.1
    };
  }, [data, keys]);

  // Generate SVG coordinate points for each key/line
  const linesPoints = useMemo(() => {
    if (data.length === 0) return [];
    return keys.map((key) => {
      return data.map((d, i) => {
        const val = d[key] ?? yMin;
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        const y = padding.top + chartHeight - ((val - yMin) / (yMax - yMin)) * chartHeight;
        return { x, y, val, timestamp: d.timestamp };
      });
    });
  }, [data, keys, yMin, yMax, chartWidth, chartHeight, padding.left, padding.top]);

  // Generate paths and fills
  const paths = useMemo(() => {
    return linesPoints.map((points) => {
      if (points.length === 0) return { line: "", fill: "" };
      const lineD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
      const fillD = `${lineD} L ${points[points.length - 1].x} ${padding.top + chartHeight} L ${points[0].x} ${padding.top + chartHeight} Z`;
      return { line: lineD, fill: fillD };
    });
  }, [linesPoints, chartHeight, padding.top]);

  // Hover Handler
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (data.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xPixel = e.clientX - rect.left;
    const pct = xPixel / rect.width;
    const svgX = pct * width;
    
    const relativeX = svgX - padding.left;
    let idx = Math.round((relativeX / chartWidth) * (data.length - 1));
    if (idx < 0) idx = 0;
    if (idx >= data.length) idx = data.length - 1;
    setHoveredIdx(idx);
  };

  const handleMouseLeave = () => {
    setHoveredIdx(null);
  };

  // Generate Grid lines (Y axis helper grid)
  const gridLines = useMemo(() => {
    const lines = [];
    const step = (yMax - yMin) / 4;
    for (let i = 0; i <= 4; i++) {
      const val = yMin + step * i;
      const y = padding.top + chartHeight - (i / 4) * chartHeight;
      lines.push({ y, val });
    }
    return lines;
  }, [yMin, yMax, chartHeight, padding.top]);

  // X Axis timestamps (e.g. 5 ticks)
  const xTicks = useMemo(() => {
    if (data.length < 2) return [];
    const ticks = [];
    const count = Math.min(data.length, 5);
    const step = Math.floor((data.length - 1) / (count - 1));
    for (let i = 0; i < count; i++) {
      const idx = Math.min(i * step, data.length - 1);
      const x = padding.left + (idx / (data.length - 1)) * chartWidth;
      ticks.push({ x, ts: data[idx].timestamp });
    }
    return ticks;
  }, [data, chartWidth, padding.left]);

  const activePoint = hoveredIdx !== null ? data[hoveredIdx] : null;

  return (
    <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4 relative select-none">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-black text-slate-300 uppercase tracking-widest">{title}</h3>
        
        {/* Legends */}
        <div className="flex items-center gap-4">
          {labels.map((lbl, idx) => (
            <div key={lbl} className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-400">
              <span className="w-2.5 h-1.5 rounded-sm" style={{ backgroundColor: colors[idx] }} />
              <span>{lbl}</span>
            </div>
          ))}
        </div>
      </div>

      {/* SVG Chart Area */}
      <div className="relative w-full h-[220px]">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full cursor-crosshair overflow-visible"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Custom Glow filter */}
          <defs>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            {colors.map((color, idx) => (
              <linearGradient key={idx} id={`gradient-${idx}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity="0.25" />
                <stop offset="100%" stopColor={color} stopOpacity="0.0" />
              </linearGradient>
            ))}
          </defs>

          {/* Grid lines */}
          {gridLines.map((line, i) => (
            <g key={i}>
              <line
                x1={padding.left}
                y1={line.y}
                x2={padding.left + chartWidth}
                y2={line.y}
                className="stroke-slate-800/40"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              <text
                x={padding.left - 8}
                y={line.y + 4}
                className="text-[10px] font-mono font-bold fill-slate-500 text-right"
                textAnchor="end"
              >
                {formatY(line.val)}
              </text>
            </g>
          ))}

          {/* Threshold Lines for PCR */}
          {showThresholds && (
            <>
              {/* Put heavy threshold (Bullish signal) */}
              {yMin < 1.2 && yMax > 1.2 && (
                <g>
                  <line
                    x1={padding.left}
                    y1={padding.top + chartHeight - ((1.2 - yMin) / (yMax - yMin)) * chartHeight}
                    x2={padding.left + chartWidth}
                    y2={padding.top + chartHeight - ((1.2 - yMin) / (yMax - yMin)) * chartHeight}
                    className="stroke-emerald-500/20"
                    strokeWidth="1"
                  />
                  <text
                    x={padding.left + chartWidth - 5}
                    y={padding.top + chartHeight - ((1.2 - yMin) / (yMax - yMin)) * chartHeight - 4}
                    className="text-[8px] font-bold fill-emerald-500/40 text-right"
                    textAnchor="end"
                  >
                    BULLISH (1.20)
                  </text>
                </g>
              )}
              {/* Call heavy threshold (Bearish signal) */}
              {yMin < 0.8 && yMax > 0.8 && (
                <g>
                  <line
                    x1={padding.left}
                    y1={padding.top + chartHeight - ((0.8 - yMin) / (yMax - yMin)) * chartHeight}
                    x2={padding.left + chartWidth}
                    y2={padding.top + chartHeight - ((0.8 - yMin) / (yMax - yMin)) * chartHeight}
                    className="stroke-rose-500/20"
                    strokeWidth="1"
                  />
                  <text
                    x={padding.left + chartWidth - 5}
                    y={padding.top + chartHeight - ((0.8 - yMin) / (yMax - yMin)) * chartHeight - 4}
                    className="text-[8px] font-bold fill-rose-500/40 text-right"
                    textAnchor="end"
                  >
                    BEARISH (0.80)
                  </text>
                </g>
              )}
            </>
          )}

          {/* X Axis ticks */}
          {xTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={tick.x}
                y1={padding.top + chartHeight}
                x2={tick.x}
                y2={padding.top + chartHeight + 4}
                className="stroke-slate-800"
                strokeWidth="1"
              />
              <text
                x={tick.x}
                y={padding.top + chartHeight + 15}
                className="text-[9px] font-mono fill-slate-500"
                textAnchor="middle"
              >
                {formatX(tick.ts)}
              </text>
            </g>
          ))}

          {/* Under-line Gradients */}
          {paths.map((p, idx) => (
            <path
              key={`fill-${idx}`}
              d={p.fill}
              fill={`url(#gradient-${idx})`}
              pointerEvents="none"
            />
          ))}

          {/* Main Lines */}
          {paths.map((p, idx) => {
            const isSRdashed = title.toLowerCase().includes("support") && idx > 0;
            return (
              <path
                key={`line-${idx}`}
                d={p.line}
                fill="none"
                stroke={colors[idx]}
                strokeWidth={isSRdashed ? "1.5" : "2"}
                strokeDasharray={isSRdashed ? "4 4" : "none"}
                filter="url(#glow)"
                pointerEvents="none"
              />
            );
          })}

          {/* Hover state components */}
          {hoveredIdx !== null && activePoint && (
            <g>
              {/* Vertical line indicator */}
              <line
                x1={padding.left + (hoveredIdx / (data.length - 1)) * chartWidth}
                y1={padding.top}
                x2={padding.left + (hoveredIdx / (data.length - 1)) * chartWidth}
                y2={padding.top + chartHeight}
                className="stroke-indigo-500/30"
                strokeWidth="1"
              />

              {/* Glowing Dots on hovered line points */}
              {linesPoints.map((points, lineIdx) => {
                const pt = points[hoveredIdx];
                if (!pt || pt.val === null) return null;
                return (
                  <g key={lineIdx}>
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r="5"
                      fill={colors[lineIdx]}
                      className="animate-ping opacity-45"
                    />
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r="4"
                      fill={colors[lineIdx]}
                      stroke="#0d1117"
                      strokeWidth="1.5"
                    />
                  </g>
                );
              })}
            </g>
          )}
        </svg>

        {/* Floating Tooltip Box */}
        {hoveredIdx !== null && activePoint && (
          <div
            className="absolute top-2 z-10 bg-[#060810]/95 border border-[#1e2433] rounded-xl p-3 shadow-2xl flex flex-col gap-1.5 pointer-events-none text-[10px] min-w-[140px] backdrop-blur-md"
            style={{
              left: `${Math.min(
                Math.max(
                  15,
                  (padding.left + (hoveredIdx / (data.length - 1)) * chartWidth) / width * 100 - 20
                ),
                70
              )}%`
            }}
          >
            <div className="flex items-center gap-1 font-bold text-slate-500">
              <Clock className="w-3 h-3 text-slate-600" />
              <span>
                {formatIST(activePoint.timestamp)}
              </span>
            </div>
            
            <div className="h-px bg-slate-800/40 my-0.5" />

            <div className="flex flex-col gap-1">
              {keys.map((k, idx) => (
                <div key={k} className="flex justify-between items-center gap-4">
                  <span className="font-semibold text-slate-400">{labels[idx]}:</span>
                  <span className="font-bold font-mono text-slate-200" style={{ color: colors[idx] }}>
                    {formatY(activePoint[k])}
                  </span>
                </div>
              ))}
              
              {/* If S/R chart, show spot price for comparison */}
              {title.toLowerCase().includes("support") && !keys.includes("spot_price") && (
                <div className="flex justify-between items-center gap-4 border-t border-slate-800/40 pt-1 mt-1">
                  <span className="font-semibold text-slate-400">Spot Price:</span>
                  <span className="font-bold font-mono text-sky-400">
                    ₹{activePoint.spot_price.toLocaleString("en-IN")}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function HistoricalCharts({ trends, loading, error }: HistoricalChartsProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 bg-[#0d1117]/40 border border-[#1e2433] rounded-2xl">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-500 text-xs font-semibold">Loading historical trend analytics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-16 text-center bg-rose-500/5 border border-rose-500/10 rounded-2xl">
        <p className="text-rose-400 font-bold mb-2">Trend Analysis Offline</p>
        <p className="text-slate-500 text-xs">{error}</p>
      </div>
    );
  }

  if (!trends || trends.length === 0) {
    return (
      <div className="py-24 text-center bg-[#0d1117]/30 border border-[#1e2433]/40 rounded-2xl text-slate-500 text-xs">
        No historical trends accumulated. <br />
        Trends will automatically start showing after 2 or more snapshots are recorded.
      </div>
    );
  }

  // Format Helper functions
  const formatYValue = (v: number) => v.toFixed(2);
  const formatYPercent = (v: number) => `${v.toFixed(1)}%`;
  const formatYInteger = (v: number) => {
    if (v >= 10000000) return (v / 10000000).toFixed(2) + " Cr";
    if (v >= 100000) return (v / 100000).toFixed(2) + " L";
    if (v >= 1000) return (v / 1000).toFixed(1) + "K";
    return v.toString();
  };
  const formatYPrice = (v: number) => `₹${Math.round(v).toLocaleString("en-IN")}`;
  
  const formatXTick = (ts: string) => {
    return formatIST(ts);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* 1. PCR Trend */}
      <SleekLineChart
        title="Put-Call Ratio (PCR)"
        data={trends}
        keys={["pcr"]}
        colors={["#818cf8"]}
        labels={["PCR"]}
        formatY={formatYValue}
        formatX={formatXTick}
        showThresholds
      />

      {/* 2. IV Trend */}
      <SleekLineChart
        title="Average Implied Volatility (IV)"
        data={trends}
        keys={["average_iv"]}
        colors={["#fbbf24"]}
        labels={["IV"]}
        formatY={formatYPercent}
        formatX={formatXTick}
      />

      {/* 3. Call vs Put Open Interest */}
      <SleekLineChart
        title="Calls vs Puts Open Interest"
        data={trends}
        keys={["total_call_oi", "total_put_oi"]}
        colors={["#f43f5e", "#10b981"]}
        labels={["Call OI", "Put OI"]}
        formatY={formatYInteger}
        formatX={formatXTick}
      />

      {/* 4. S/R Dynamic Bands */}
      <SleekLineChart
        title="Dynamic S/R Bands vs Spot"
        data={trends}
        keys={["spot_price", "support", "resistance"]}
        colors={["#38bdf8", "#059669", "#dc2626"]}
        labels={["Spot Price", "Support (S1)", "Resistance (R1)"]}
        formatY={formatYPrice}
        formatX={formatXTick}
      />
    </div>
  );
}
