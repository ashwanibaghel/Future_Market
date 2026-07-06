import json
import logging
from datetime import datetime, time
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import OptionChainSnapshot, TradingSignal, ManualTraderDecision, DailyReport
from app.engine.outcomes import evaluate_trading_signals, get_success_threshold_points

logger = logging.getLogger(__name__)

def pearson_correlation(x, y):
    n = len(x)
    if n < 2:
        return 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_x2 = sum(val**2 for val in x)
    sum_y2 = sum(val**2 for val in y)
    p_sum = sum(val_x * val_y for val_x, val_y in zip(x, y))
    
    num = p_sum - (sum_x * sum_y / n)
    den = ((sum_x2 - sum_x**2 / n) * (sum_y2 - sum_y**2 / n))**0.5
    if den == 0:
        return 0.0
    return round(num / den, 3)

def generate_daily_validation_report(db: Session, date_str: str, version: str = "v2.5") -> DailyReport:
    """
    Generates a comprehensive daily validation report for the specified date and engine version.
    """
    logger.info(f"Generating daily validation report for {date_str} (version: {version})...")
    
    # 1. Trigger outcome evaluation first to ensure all outcomes are evaluated
    try:
        evaluate_trading_signals(db)
    except Exception as e:
        logger.error(f"Error evaluating trading signals during validation: {str(e)}")

    # Parse date boundary
    start_dt = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(f"{date_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    # 2. Gather Snapshots
    snapshots = db.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.timestamp >= start_dt,
        OptionChainSnapshot.timestamp <= end_dt
    ).order_by(OptionChainSnapshot.timestamp.asc()).all()
    
    total_snapshots = len(snapshots)
    success_snapshots = sum(1 for s in snapshots if s.collection_status == "SUCCESS")
    success_rate = (success_snapshots / total_snapshots * 100.0) if total_snapshots > 0 else 0.0
    
    # 3. Gather Signals
    signals = db.query(TradingSignal).filter(
        TradingSignal.timestamp >= start_dt,
        TradingSignal.timestamp <= end_dt,
        TradingSignal.signal_version == version
    ).all()
    
    total_signals = len(signals)
    buy_call_count = sum(1 for s in signals if s.signal_type == "BUY_CALL")
    buy_put_count = sum(1 for s in signals if s.signal_type == "BUY_PUT")
    no_trade_count = sum(1 for s in signals if s.signal_type == "NO_TRADE")
    
    # Compute system stats
    system_wins = 0
    system_losses = 0
    system_flats = 0
    correct_avoidances = 0
    missed_opportunities = 0
    
    confusion = {
        "BUY_CALL": {"actual_bullish": 0, "actual_bearish": 0, "actual_range": 0},
        "BUY_PUT": {"actual_bullish": 0, "actual_bearish": 0, "actual_range": 0},
        "NO_TRADE": {"actual_bullish": 0, "actual_bearish": 0, "actual_range": 0}
    }
    
    patterns = {}
    phases = {}
    rule_contributions = {}
    all_contributions_by_rule = {} # {rule_name: [list_of_contributions]}
    
    for sig in signals:
        # Determine actual market movement direction based on outcome
        move_60m = sig.move_60m_points or 0.0
        threshold = get_success_threshold_points(sig.symbol, sig.spot_price)
        
        actual_regime = "actual_range"
        if move_60m >= threshold:
            actual_regime = "actual_bullish"
        elif move_60m <= -threshold:
            actual_regime = "actual_bearish"
            
        sig_type = sig.signal_type
        if sig_type in confusion:
            confusion[sig_type][actual_regime] += 1
            
        # Parse signal inputs for metadata
        inputs = {}
        try:
            inputs = json.loads(sig.signal_inputs) if sig.signal_inputs else {}
        except Exception:
            pass
            
        engine_feat = inputs.get("engine_features", {})
        pattern_id = engine_feat.get("pattern_id", "N/A")
        market_phase = engine_feat.get("market_phase", "N/A")
        
        # Track pattern metrics
        if pattern_id not in patterns:
            patterns[pattern_id] = {"total": 0, "wins": 0, "losses": 0, "avoidances": 0, "missed": 0, "avg_move": 0.0}
        patterns[pattern_id]["total"] += 1
        patterns[pattern_id]["avg_move"] += move_60m
        
        # Track market phase metrics
        if market_phase not in phases:
            phases[market_phase] = {"total": 0, "wins": 0, "losses": 0, "avoidances": 0, "missed": 0}
        phases[market_phase]["total"] += 1
        
        # Compute outcomes
        if sig_type in ["BUY_CALL", "BUY_PUT"]:
            # Evaluate outcomes
            outcome = sig.outcome_60m
            if outcome == "WIN":
                system_wins += 1
                patterns[pattern_id]["wins"] += 1
                phases[market_phase]["wins"] += 1
            elif outcome == "LOSS":
                system_losses += 1
                patterns[pattern_id]["losses"] += 1
                phases[market_phase]["losses"] += 1
            else:
                system_flats += 1
        elif sig_type == "NO_TRADE":
            outcome = sig.outcome_60m
            if outcome == "CORRECT_AVOIDANCE":
                correct_avoidances += 1
                patterns[pattern_id]["avoidances"] += 1
                phases[market_phase]["avoidances"] += 1
            elif outcome == "MISSED_OPPORTUNITY":
                missed_opportunities += 1
                patterns[pattern_id]["missed"] += 1
                phases[market_phase]["missed"] += 1
                
        # Parse rule contribution stats
        reasons = {}
        try:
            reasons = json.loads(sig.reasons) if sig.reasons else {}
        except Exception:
            pass
            
        for rule_name, rule_data in reasons.items():
            if isinstance(rule_data, dict):
                contrib = rule_data.get("contribution", 0.0)
                if rule_name not in all_contributions_by_rule:
                    all_contributions_by_rule[rule_name] = []
                all_contributions_by_rule[rule_name].append(contrib)
                
                # Group average contributions by signal outcome
                is_win = sig.outcome_60m == "WIN"
                if rule_name not in rule_contributions:
                    rule_contributions[rule_name] = {"winning_avg": 0.0, "losing_avg": 0.0, "win_count": 0, "loss_count": 0}
                if is_win:
                    rule_contributions[rule_name]["winning_avg"] += contrib
                    rule_contributions[rule_name]["win_count"] += 1
                else:
                    rule_contributions[rule_name]["losing_avg"] += contrib
                    rule_contributions[rule_name]["loss_count"] += 1

    # Finalize pattern & phase win rates
    for p_id, p_data in patterns.items():
        p_data["avg_move"] = round(p_data["avg_move"] / p_data["total"], 2) if p_data["total"] > 0 else 0.0
        trade_count = p_data["wins"] + p_data["losses"]
        p_data["win_rate_pct"] = round((p_data["wins"] / trade_count * 100.0), 1) if trade_count > 0 else 0.0
        
    for ph_id, ph_data in phases.items():
        trade_count = ph_data["wins"] + ph_data["losses"]
        ph_data["win_rate_pct"] = round((ph_data["wins"] / trade_count * 100.0), 1) if trade_count > 0 else 0.0

    # Finalize rule average contributions
    for r_name, r_data in rule_contributions.items():
        r_data["winning_avg"] = round(r_data["winning_avg"] / r_data["win_count"], 2) if r_data["win_count"] > 0 else 0.0
        r_data["losing_avg"] = round(r_data["losing_avg"] / r_data["loss_count"], 2) if r_data["loss_count"] > 0 else 0.0

    # Calculate Pearson correlations between rule contributions
    rule_names = list(all_contributions_by_rule.keys())
    correlations = {}
    for i in range(len(rule_names)):
        r1 = rule_names[i]
        correlations[r1] = {}
        for j in range(len(rule_names)):
            r2 = rule_names[j]
            if r1 == r2:
                correlations[r1][r2] = 1.0
            else:
                correlations[r1][r2] = pearson_correlation(all_contributions_by_rule[r1], all_contributions_by_rule[r2])

    # 4. Manual vs System Decisions Comparison
    manual_decisions = db.query(ManualTraderDecision).filter(
        ManualTraderDecision.timestamp >= start_dt,
        ManualTraderDecision.timestamp <= end_dt
    ).all()
    
    manual_count = len(manual_decisions)
    matching_decisions = 0
    manual_wins = 0
    manual_losses = 0
    
    for md in manual_decisions:
        # Find closest system signal within 5 minutes
        closest_sig = None
        min_diff = None
        for sig in signals:
            diff = abs((sig.timestamp - md.timestamp).total_seconds())
            if diff <= 300: # 5 minutes
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest_sig = sig
                    
        if closest_sig:
            # Map manual action to system signal type
            md_action = "NO_TRADE" if md.decision_type == "STAY_OUT" else md.decision_type
            if md_action == closest_sig.signal_type:
                matching_decisions += 1
                
        # Track manual outcome if recorded
        if md.outcome_60m == "WIN":
            manual_wins += 1
        elif md.outcome_60m == "LOSS":
            manual_losses += 1
            
    agreement_rate = (matching_decisions / manual_count * 100.0) if manual_count > 0 else 0.0
    manual_win_rate = (manual_wins / (manual_wins + manual_losses) * 100.0) if (manual_wins + manual_losses) > 0 else 0.0
    system_total_trades = system_wins + system_losses
    system_win_rate = (system_wins / system_total_trades * 100.0) if system_total_trades > 0 else 0.0

    # 5. Dataset Quality Checker
    missing_greeks = 0
    missing_iv = 0
    outliers = 0
    collection_gaps = 0
    
    # Check collection gaps & outliers
    for i in range(len(snapshots)):
        snap = snapshots[i]
        
        # Check outliers: spot jump > 2.0% in 1 minute
        if i > 0:
            prev_snap = snapshots[i - 1]
            time_diff = (snap.timestamp - prev_snap.timestamp).total_seconds()
            if 0 < time_diff <= 90: # Consecutive snapshots
                spot_change = abs(snap.spot_price - prev_snap.spot_price) / prev_snap.spot_price * 100.0
                if spot_change > 2.0:
                    outliers += 1
                    
                # Check collection gaps: > 5 minutes gap during market hours (09:15 - 15:30)
                market_start = time(9, 15)
                market_end = time(15, 30)
                curr_time = snap.timestamp.time()
                if market_start <= curr_time <= market_end and time_diff > 300:
                    collection_gaps += 1
                    
        # Check missing Greeks & IV from strikes
        for strike in snap.strikes:
            if strike.call_delta == 0.0 and strike.put_delta == 0.0:
                missing_greeks += 1
                break # Only count once per snapshot
                
    # Prepare summary JSON
    summary_data = {
        "summary": {
            "total_snapshots": total_snapshots,
            "success_snapshots": success_snapshots,
            "success_rate_pct": round(success_rate, 2),
            "total_signals": total_signals,
            "buy_call_count": buy_call_count,
            "buy_put_count": buy_put_count,
            "no_trade_count": no_trade_count,
            "system_trades": system_total_trades,
            "system_win_rate_pct": round(system_win_rate, 2),
            "system_wins": system_wins,
            "system_losses": system_losses,
            "system_flats": system_flats,
            "correct_avoidances": correct_avoidances,
            "missed_opportunities": missed_opportunities
        },
        "confusion_matrix": confusion,
        "patterns": patterns,
        "phases": phases,
        "rules": {
            "contributions": rule_contributions,
            "correlations": correlations
        },
        "manual_vs_system": {
            "manual_decisions_count": manual_count,
            "agreement_rate_pct": round(agreement_rate, 2),
            "manual_win_rate_pct": round(manual_win_rate, 2),
            "manual_wins": manual_wins,
            "manual_losses": manual_losses
        },
        "data_quality": {
            "missing_greeks_snapshots": missing_greeks,
            "missing_iv_snapshots": missing_iv,
            "outliers_detected": outliers,
            "collection_gaps": collection_gaps
        }
    }
    
    # 6. Generate Markdown Content
    md = f"""# Quant Validation Report: {date_str} (Version: {version})

Generated at: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}

## 📊 Summary Statistics
- **Total Snapshots:** {total_snapshots} ({success_rate:.2f}% success rate)
- **Signals Generated:** {total_signals}
  - BUY_CALL: {buy_call_count}
  - BUY_PUT: {buy_put_count}
  - NO_TRADE: {no_trade_count}
- **System Outcome (V2.5 Calibrated):** {system_wins} Wins | {system_losses} Losses | {system_flats} Flats
- **System Win Rate:** {system_win_rate:.1f}%
- **Correct Avoidances (NO_TRADE):** {correct_avoidances}
- **Missed Opportunities (NO_TRADE):** {missed_opportunities}

---

## 🧩 Confusion Matrix (60-Minute Horizon)
| Predicted \\ Actual | Bullish Move | Bearish Move | Range-bound |
| :--- | :---: | :---: | :---: |
| **BUY_CALL** | {confusion["BUY_CALL"]["actual_bullish"]} | {confusion["BUY_CALL"]["actual_bearish"]} | {confusion["BUY_CALL"]["actual_range"]} |
| **BUY_PUT** | {confusion["BUY_PUT"]["actual_bullish"]} | {confusion["BUY_PUT"]["actual_bearish"]} | {confusion["BUY_PUT"]["actual_range"]} |
| **NO_TRADE** | {confusion["NO_TRADE"]["actual_bullish"]} | {confusion["NO_TRADE"]["actual_bearish"]} | {confusion["NO_TRADE"]["actual_range"]} |

---

## 📈 Pattern-wise Win Rates
| Pattern ID | Count | Win Rate (%) | Avg 60m Move (pts) | Avoidances | Missed |
| :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for p_id, p_d in patterns.items():
        md += f"| `{p_id}` | {p_d['total']} | {p_d['win_rate_pct']:.1f}% | {p_d['avg_move']} | {p_d['avoidances']} | {p_d['missed']} |\n"
        
    md += """
---

## 🌐 Market Phase Accuracy
| Market Phase | Count | Win Rate (%) | Avoidances | Missed |
| :--- | :---: | :---: | :---: | :---: |
"""
    for ph_id, ph_d in phases.items():
        md += f"| `{ph_id}` | {ph_d['total']} | {ph_d['win_rate_pct']:.1f}% | {ph_d['avoidances']} | {ph_d['missed']} |\n"

    md += """
---

## 🧠 Rule Average Contributions
| Rule Name | Avg Score (Winners) | Avg Score (Losers) |
| :--- | :---: | :---: |
"""
    for r_name, r_d in rule_contributions.items():
        md += f"| {r_name} | {r_d['winning_avg']:.2f} pts | {r_d['losing_avg']:.2f} pts |\n"

    md += f"""
---

## 🧑‍💻 Manual vs System Comparison
- **Uncle Ji's Decisions Count:** {manual_count}
- **System Agreement Rate:** {agreement_rate:.2f}%
- **Uncle Ji's Win Rate:** {manual_win_rate:.1f}% (Wins: {manual_wins} | Losses: {manual_losses})
- **System Win Rate:** {system_win_rate:.1f}%

---

## 🔍 Dataset Quality Audit
- **Snapshots with Gapped timestamps (>5m):** {collection_gaps}
- **Snapshots with Gapped Greeks/IV:** {missing_greeks}
- **Outlier Spot Price Movements (>2%):** {outliers}
"""

    # Check if a report for this date already exists
    report = db.query(DailyReport).filter(DailyReport.date == date_str).first()
    if not report:
        report = DailyReport(date=date_str)
        db.add(report)
        
    report.summary_json = json.dumps(summary_data)
    report.markdown_content = md
    db.commit()
    logger.info(f"Daily validation report saved successfully for {date_str}.")
    
    return report
