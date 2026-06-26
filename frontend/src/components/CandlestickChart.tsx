"use client";

import React, { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";
import { Activity, TrendingUp, Calendar } from "lucide-react";

interface CandlestickChartProps {
  symbol: string;
}

interface CandleData {
  time: number; // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

const TIMEFRAMES = [
  { label: "1D", range: "1d", interval: "5m" },
  { label: "5D", range: "5d", interval: "15m" },
  { label: "1M", range: "1mo", interval: "1h" },
  { label: "3M", range: "3mo", interval: "1d" },
  { label: "1Y", range: "1y", interval: "1d" },
];

// Helper to compute EMA (Exponential Moving Average) for trend detection
function calculateEMA(data: CandleData[], period: number): { time: number; value: number }[] {
  if (data.length < period) return [];
  const k = 2 / (period + 1);
  let emaVal = data.slice(0, period).reduce((sum, item) => sum + item.close, 0) / period;
  const emaPoints = [{ time: data[period - 1].time, value: emaVal }];

  for (let i = period; i < data.length; i++) {
    emaVal = data[i].close * k + emaVal * (1 - k);
    emaPoints.push({ time: data[i].time, value: emaVal });
  }
  return emaPoints;
}

export default function CandlestickChart({ symbol }: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any | null>(null);
  const candlestickSeriesRef = useRef<any | null>(null);
  const volumeSeriesRef = useRef<any | null>(null);
  const emaSeriesRef = useRef<any | null>(null);

  const [timeframe, setTimeframe] = useState(TIMEFRAMES[3]); // Default: 3M
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Interactive Hover Info State
  const [hoverData, setHoverData] = useState<{
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    time: string;
  } | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchChartData() {
      setLoading(true);
      setError(null);
      try {
        const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        const res = await fetch(
          `${BACKEND_URL}/api/market-chart?symbol=${symbol}&range=${timeframe.range}&interval=${timeframe.interval}`
        );
        if (!res.ok) {
          throw new Error("Failed to fetch market chart data");
        }
        const data = await res.json();
        if (data.error) {
          throw new Error(data.error);
        }
        
        if (!active) return;

        const candles: CandleData[] = data.candles || [];
        if (candles.length === 0) {
          throw new Error("No candlestick data available for this symbol.");
        }

        // Initialize or update lightweight-chart
        if (!chartRef.current && chartContainerRef.current) {
          const chart: any = createChart(chartContainerRef.current, {
            layout: {
              background: { type: ColorType.Solid, color: "#0d1117" },
              textColor: "#94a3b8",
            },
            grid: {
              vertLines: { color: "#1f2937" },
              horzLines: { color: "#1f2937" },
            },
            rightPriceScale: {
              borderColor: "#1e2433",
            },
            timeScale: {
              borderColor: "#1e2433",
              timeVisible: timeframe.interval.endsWith("m") || timeframe.interval.endsWith("h"),
            },
            crosshair: {
              mode: 1, // Magnet mode
              vertLine: {
                color: "#6366f1",
                width: 1,
                style: 3,
                labelBackgroundColor: "#6366f1",
              },
              horzLine: {
                color: "#6366f1",
                width: 1,
                style: 3,
                labelBackgroundColor: "#6366f1",
              },
            },
          });

          chartRef.current = chart;

          // Add Candlestick Series
          const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: "#22c55e",
            downColor: "#ef4444",
            borderVisible: false,
            wickUpColor: "#22c55e",
            wickDownColor: "#ef4444",
          });
          candlestickSeriesRef.current = candlestickSeries;

          // Add Volume Series at the bottom
          const volumeSeries = chart.addSeries(HistogramSeries, {
            color: "#3b82f6",
            priceFormat: {
              type: "volume",
            },
            priceScaleId: "volume-scale", // Custom price scale to position at the bottom
          });
          
          chart.priceScale("volume-scale").applyOptions({
            scaleMargins: {
              top: 0.8, // Takes up the bottom 20% of chart
              bottom: 0,
            },
          });
          volumeSeriesRef.current = volumeSeries;

          // Add EMA line series overlay for trend
          const emaSeries = chart.addSeries(LineSeries, {
            color: "#fbbf24",
            lineWidth: 1.5,
            title: "EMA 9",
            priceScaleId: "right",
          });
          emaSeriesRef.current = emaSeries;

          // Handle resizing
          const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
              chartRef.current.applyOptions({
                width: chartContainerRef.current.clientWidth,
              });
            }
          };
          window.addEventListener("resize", handleResize);

          // Crosshair tooltip tracking
          chart.subscribeCrosshairMove((param: any) => {
            if (
              param.point === undefined ||
              !param.time ||
              param.point.x < 0 ||
              param.point.y < 0
            ) {
              setHoverData(null);
            } else {
              const candle = param.seriesData.get(candlestickSeries);
              const volume = param.seriesData.get(volumeSeries);
              
              if (candle) {
                // Formatting time nicely
                let timeStr = "";
                if (typeof param.time === "number") {
                  const date = new Date(param.time * 1000);
                  timeStr = timeframe.interval.endsWith("d")
                    ? date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
                    : date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) + " " + date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
                }

                setHoverData({
                  open: (candle as any).open,
                  high: (candle as any).high,
                  low: (candle as any).low,
                  close: (candle as any).close,
                  volume: volume ? (volume as any).value : 0,
                  time: timeStr,
                });
              }
            }
          });

          // Store cleaner function
          (chart as any)._cleanupResize = () => {
            window.removeEventListener("resize", handleResize);
          };
        }

        // Apply options and set data
        if (chartRef.current && candlestickSeriesRef.current && volumeSeriesRef.current && emaSeriesRef.current) {
          // Format time based on interval requirements (unix timestamp number for lightweight-charts)
          const formattedCandles = candles.map((c) => ({
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }));

          const volumeData = candles.map((c) => ({
            time: c.time,
            value: c.volume || 0,
            color: c.close >= c.open ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)",
          }));

          candlestickSeriesRef.current.setData(formattedCandles);
          volumeSeriesRef.current.setData(volumeData);

          // Calculate and set EMA 9
          const ema9Data = calculateEMA(candles, 9);
          emaSeriesRef.current.setData(ema9Data);

          // Fit all candles inside the view
          chartRef.current.timeScale().fitContent();
          
          // Apply timeScale options for time visibility
          chartRef.current.timeScale().applyOptions({
            timeVisible: timeframe.interval.endsWith("m") || timeframe.interval.endsWith("h"),
          });
        }
      } catch (err: any) {
        console.error(err);
        if (active) setError(err.message || "Failed to load chart");
      } finally {
        if (active) setLoading(false);
      }
    }

    fetchChartData();

    return () => {
      active = false;
    };
  }, [symbol, timeframe]);

  // Cleanup chart on unmount
  useEffect(() => {
    return () => {
      if (chartRef.current) {
        if ((chartRef.current as any)._cleanupResize) {
          (chartRef.current as any)._cleanupResize();
        }
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, []);

  return (
    <div className="bg-[#0d1117] border border-[#1e2433] rounded-2xl p-5 flex flex-col gap-4 relative">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1e2433]/60 pb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-black text-slate-200 uppercase tracking-wider">
            {symbol} Candlestick Chart
          </h3>
        </div>

        {/* Timeframe selector */}
        <div className="flex items-center gap-1 bg-[#131920] border border-[#1e2433] rounded-lg p-0.5 self-start sm:self-auto">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.label}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${
                timeframe.label === tf.label
                  ? "bg-indigo-500 text-white shadow-md shadow-indigo-500/10"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* OHLC hover legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[10px] font-mono bg-[#131920]/40 border border-[#1e2433]/30 rounded-xl px-4 py-2.5 min-h-[36px]">
        {hoverData ? (
          <>
            <span className="text-slate-500 font-sans font-semibold flex items-center gap-1">
              <Calendar className="w-3 h-3 text-slate-600" /> {hoverData.time}:
            </span>
            <span>
              O: <span className={hoverData.close >= hoverData.open ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>{hoverData.open.toFixed(2)}</span>
            </span>
            <span>
              H: <span className="text-slate-200 font-bold">{hoverData.high.toFixed(2)}</span>
            </span>
            <span>
              L: <span className="text-slate-200 font-bold">{hoverData.low.toFixed(2)}</span>
            </span>
            <span>
              C: <span className={hoverData.close >= hoverData.open ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>{hoverData.close.toFixed(2)}</span>
            </span>
            {hoverData.volume > 0 && (
              <span>
                Vol: <span className="text-blue-400 font-bold">{hoverData.volume.toLocaleString("en-IN")}</span>
              </span>
            )}
            <span className="text-amber-400 font-semibold font-sans flex items-center gap-1 ml-auto">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> EMA 9 Trend
            </span>
          </>
        ) : (
          <span className="text-slate-500 font-sans font-medium flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-slate-600" /> Hover over chart to view OHLC values and trend data
          </span>
        )}
      </div>

      {/* Chart Canvas */}
      <div className="relative w-full h-[350px] min-h-[300px]">
        {loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-[#0d1117]/85 gap-3 rounded-xl border border-[#1e2433]/40">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-slate-500 text-xs font-semibold">Loading live trend candlesticks...</p>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-[#0d1117] border border-[#1e2433] rounded-xl text-center px-4">
            <p className="text-rose-400 font-bold mb-2">Failed to load chart</p>
            <p className="text-slate-500 text-xs max-w-sm">{error}</p>
          </div>
        )}

        <div ref={chartContainerRef} className="w-full h-full" />
      </div>
    </div>
  );
}
