"use client";

import React, { useState } from "react";

interface StrikeData {
  strike: number;
  call_oi: number;
  call_change_oi: number;
  call_volume: number;
  call_iv: number;
  call_ltp: number;
  call_bid: number;
  call_ask: number;
  put_oi: number;
  put_change_oi: number;
  put_volume: number;
  put_iv: number;
  put_ltp: number;
  put_bid: number;
  put_ask: number;
}

interface OptionChainTableProps {
  strikes: StrikeData[];
  spotPrice: number;
}

export default function OptionChainTable({ strikes, spotPrice }: OptionChainTableProps) {
  const [filterATM, setFilterATM] = useState(true);

  // Helper to format large numbers (e.g. 150000 -> 150k, 1200000 -> 1.2M)
  const formatNumber = (num: number) => {
    if (num >= 1_000_000) {
      return (num / 1_000_000).toFixed(1) + "M";
    }
    if (num >= 1_000) {
      return (num / 1_000).toFixed(0) + "k";
    }
    return num.toString();
  };

  // Find ATM strike (closest to spotPrice)
  const atmStrike = strikes.reduce((prev, curr) => {
    return Math.abs(curr.strike - spotPrice) < Math.abs(prev.strike - spotPrice) ? curr : prev;
  }, strikes[0]);

  // Find max values for highlighting
  const maxCallOI = Math.max(...strikes.map((s) => s.call_oi), 1);
  const maxPutOI = Math.max(...strikes.map((s) => s.put_oi), 1);
  const maxCallChange = Math.max(...strikes.map((s) => Math.abs(s.call_change_oi)), 1);
  const maxPutChange = Math.max(...strikes.map((s) => Math.abs(s.put_change_oi)), 1);
  const maxCallVol = Math.max(...strikes.map((s) => s.call_volume), 1);
  const maxPutVol = Math.max(...strikes.map((s) => s.put_volume), 1);

  // Filter strikes around ATM (+/- 10 strikes) if filter is enabled
  const displayedStrikes = filterATM
    ? (() => {
        const atmIndex = strikes.findIndex((s) => s.strike === atmStrike.strike);
        const start = Math.max(0, atmIndex - 8);
        const end = Math.min(strikes.length, atmIndex + 9);
        return strikes.slice(start, end);
      })()
    : strikes;

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Table Controls */}
      <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-pulse"></span>
          Option Chain
        </h3>
        <button
          onClick={() => setFilterATM(!filterATM)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            filterATM
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
              : "bg-slate-800 text-slate-400 hover:bg-slate-700"
          }`}
        >
          {filterATM ? "Showing ATM +/- 8 Strikes" : "Showing All Strikes"}
        </button>
      </div>

      {/* Grid Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 text-xs uppercase font-semibold tracking-wider">
              {/* Calls Side */}
              <th className="px-3 py-3 text-center border-r border-slate-800 bg-indigo-950/20 text-indigo-400" colSpan={4}>
                Calls (Bullish State)
              </th>
              {/* Strike */}
              <th className="px-4 py-3 text-center bg-slate-900 text-slate-200">
                Strike
              </th>
              {/* Puts Side */}
              <th className="px-3 py-3 text-center border-l border-slate-800 bg-emerald-950/20 text-emerald-400" colSpan={4}>
                Puts (Bearish State)
              </th>
            </tr>
            <tr className="bg-slate-950/40 border-b border-slate-800 text-slate-400 text-[10px] uppercase font-bold tracking-wider">
              {/* Calls headers */}
              <th className="px-3 py-2 text-right">OI</th>
              <th className="px-3 py-2 text-right">Chg OI</th>
              <th className="px-3 py-2 text-right">Volume</th>
              <th className="px-3 py-2 text-right border-r border-slate-800 text-indigo-300">LTP</th>
              
              {/* Strike Header */}
              <th className="px-4 py-2 text-center bg-slate-900/60 font-black">Strike Price</th>
              
              {/* Puts headers */}
              <th className="px-3 py-2 text-left border-l border-slate-800 text-emerald-300">LTP</th>
              <th className="px-3 py-2 text-left">Volume</th>
              <th className="px-3 py-2 text-left">Chg OI</th>
              <th className="px-3 py-2 text-left">OI</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-xs font-mono">
            {displayedStrikes.map((s) => {
              const isATM = s.strike === atmStrike.strike;
              
              // Call highlights
              const isCallOIMax = s.call_oi === maxCallOI;
              const isCallVolMax = s.call_volume === maxCallVol;
              
              // Put highlights
              const isPutOIMax = s.put_oi === maxPutOI;
              const isPutVolMax = s.put_volume === maxPutVol;

              return (
                <tr
                  key={s.strike}
                  className={`transition-colors hover:bg-slate-800/40 ${
                    isATM ? "bg-indigo-950/10 border-y border-indigo-500/20" : ""
                  }`}
                >
                  {/* CALLS DATA */}
                  {/* Call OI */}
                  <td className={`px-3 py-2.5 text-right font-medium ${
                    isCallOIMax ? "text-indigo-400 font-bold bg-indigo-500/10" : "text-slate-300"
                  }`}>
                    {formatNumber(s.call_oi)}
                  </td>
                  {/* Call Chg OI */}
                  <td className={`px-3 py-2.5 text-right font-medium ${
                    s.call_change_oi > 0 ? "text-emerald-500" : s.call_change_oi < 0 ? "text-rose-500" : "text-slate-500"
                  }`}>
                    {s.call_change_oi > 0 ? "+" : ""}
                    {formatNumber(s.call_change_oi)}
                  </td>
                  {/* Call Volume */}
                  <td className={`px-3 py-2.5 text-right ${
                    isCallVolMax ? "text-yellow-400 font-bold bg-yellow-500/10" : "text-slate-400"
                  }`}>
                    {formatNumber(s.call_volume)}
                  </td>
                  {/* Call LTP */}
                  <td className="px-3 py-2.5 text-right border-r border-slate-800 text-indigo-200 bg-indigo-950/5">
                    ₹{s.call_ltp.toFixed(1)}
                  </td>

                  {/* STRIKE PRICE */}
                  <td className={`px-4 py-2.5 text-center font-bold text-sm bg-slate-900 border-x border-slate-800 ${
                    isATM ? "text-yellow-400 border-x-indigo-500/40" : "text-slate-200"
                  }`}>
                    {s.strike}
                    {isATM && <span className="block text-[8px] text-yellow-400/80 font-normal uppercase tracking-widest mt-0.5">ATM</span>}
                  </td>

                  {/* PUTS DATA */}
                  {/* Put LTP */}
                  <td className="px-3 py-2.5 text-left border-l border-slate-800 text-emerald-200 bg-emerald-950/5">
                    ₹{s.put_ltp.toFixed(1)}
                  </td>
                  {/* Put Volume */}
                  <td className={`px-3 py-2.5 text-left ${
                    isPutVolMax ? "text-yellow-400 font-bold bg-yellow-500/10" : "text-slate-400"
                  }`}>
                    {formatNumber(s.put_volume)}
                  </td>
                  {/* Put Chg OI */}
                  <td className={`px-3 py-2.5 text-left font-medium ${
                    s.put_change_oi > 0 ? "text-emerald-500" : s.put_change_oi < 0 ? "text-rose-500" : "text-slate-500"
                  }`}>
                    {s.put_change_oi > 0 ? "+" : ""}
                    {formatNumber(s.put_change_oi)}
                  </td>
                  {/* Put OI */}
                  <td className={`px-3 py-2.5 text-left font-medium ${
                    isPutOIMax ? "text-emerald-400 font-bold bg-emerald-500/10" : "text-slate-300"
                  }`}>
                    {formatNumber(s.put_oi)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend Footer */}
      <div className="flex flex-wrap gap-4 items-center justify-start px-6 py-3 border-t border-slate-800 bg-slate-950/30 text-[10px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 bg-indigo-500/25 border border-indigo-500/40 rounded"></span> Max Call/Put OI (Primary Resistance/Support)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 bg-yellow-500/25 border border-yellow-500/40 rounded"></span> Unusual Volume Activity
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 bg-indigo-950/30 border border-indigo-500/20 rounded"></span> At The Money (ATM) Strike
        </span>
      </div>
    </div>
  );
}
