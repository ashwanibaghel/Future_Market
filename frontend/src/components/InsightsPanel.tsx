"use client";

import React from "react";
import { MessageSquare, Flame, CheckCircle, AlertTriangle, HelpCircle } from "lucide-react";
import { formatIST } from "@/lib/timeUtils";

interface Insight {
  id: number;
  timestamp: string;
  category: string;
  insight_text: string;
  confidence_level: string; // LOW, MEDIUM, HIGH
}

interface InsightsPanelProps {
  insights?: Insight[];
}

export default function InsightsPanel({ insights = [] }: InsightsPanelProps) {
  
  const getConfidenceBadge = (level: string) => {
    switch (level.toUpperCase()) {
      case "HIGH":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "MEDIUM":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      default:
        return "text-rose-400 bg-rose-500/10 border-rose-500/20";
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category.toUpperCase()) {
      case "BUILDUP":
        return <Flame className="w-4 h-4 text-orange-400" />;
      case "VOLATILITY":
        return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      default:
        return <MessageSquare className="w-4 h-4 text-indigo-400" />;
    }
  };

  // Default fallback insights for initial dashboard view
  const defaultInsights: Insight[] = [
    {
      id: 1,
      timestamp: new Date().toISOString(),
      category: "BUILDUP",
      insight_text: "Fresh Strong Long Build-Up detected near 24000 strike. Call OI increased by +95%.",
      confidence_level: "HIGH"
    },
    {
      id: 2,
      timestamp: new Date().toISOString(),
      category: "VOLATILITY",
      insight_text: "Implied Volatility (IV) expanding rapidly on puts. Expect volatility compression post-expiry.",
      confidence_level: "MEDIUM"
    },
    {
      id: 3,
      timestamp: new Date().toISOString(),
      category: "BUILDUP",
      insight_text: "Primary Support S1 strengthening at 23900 as Put writing increases (+20k contracts).",
      confidence_level: "HIGH"
    }
  ];

  const activeInsights = insights.length > 0 ? insights : defaultInsights;

  return (
    <div className="w-full bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-xl p-6 shadow-2xl flex flex-col gap-4">
      <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
        <MessageSquare className="w-4.5 h-4.5 text-indigo-400" />
        Generated Insights (V1)
      </h3>

      <div className="flex flex-col gap-3">
        {activeInsights.map((insight) => (
          <div
            key={insight.id}
            className="bg-slate-950/40 border border-slate-850 hover:border-slate-800 transition-colors p-4 rounded-xl flex items-start gap-4"
          >
            {/* Category Icon */}
            <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
              {getCategoryIcon(insight.category)}
            </div>

            {/* Content info */}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-200 font-semibold leading-relaxed">
                {insight.insight_text}
              </p>
              
              <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                <span>{insight.category}</span>
                <span className="w-1.5 h-1.5 bg-slate-850 rounded-full"></span>
                <span>
                  {formatIST(insight.timestamp, { hour: '2-digit', minute: '2-digit', hour12: true })}
                </span>
              </div>
            </div>

            {/* Confidence indicator badge */}
            <div className={`px-2 py-0.5 rounded border text-[9px] font-black uppercase tracking-wider ${getConfidenceBadge(insight.confidence_level)}`}>
              {insight.confidence_level}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
