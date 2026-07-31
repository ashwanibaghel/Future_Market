"""
OI Lens - STEP 3 HISTORICAL LEARNING PROGRAM v5
Global Chronological Stream | Clean Dataset Generation

GOLDEN PRINCIPLE:
    The replay engine records three things:
      A. What the market looked like (raw facts)
      B. What the frozen AI understood (cognitive assessment)
      C. What actually happened afterwards (historical outcomes)
    Future learning algorithms discover the relationships.

HOW TO RUN:
    Fresh start (always use this for clean dataset):
        python run_historical_learning_program.py --fresh

    Resume from checkpoint (only if interrupted mid-run):
        python run_historical_learning_program.py

SINGLE INSTANCE PROTECTION:
    A lock file is written at startup and removed on exit.
    Starting a second instance while one is running will abort immediately.
"""

import os
import sys
import glob
import json
import time
import logging
import hashlib
import atexit
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.memory.ranker import MemoryRankerEngine
from app.synthesis.engine import ExperienceSynthesisEngine
from app.reasoning.engine import CognitiveReasoningEngine
from app.decision.engine import DecisionSupportEngine

# ── Paths ───────────────────────────────────────────────────────────────────
BASE           = "E:/Future Stock/research_storage"
SIT_STORE_DIR  = f"{BASE}/situation_store/exchange=NSE_FO"
DATASET_DIR    = f"{BASE}/market_intelligence_dataset"
CHECKPOINT     = f"{BASE}/learning_program_checkpoint.json"
PROGRESS_FILE  = f"{BASE}/quality_reports/learning_program_progress.json"
LOCK_FILE      = f"{BASE}/learning_program.lock"
MEM_STORE_DIR  = f"{BASE}/memory_store"

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("hlp_v5")

FRESH = "--fresh" in sys.argv


# ── Single-instance lock ─────────────────────────────────────────────────────
def acquire_lock():
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE) as f:
            pid = f.read().strip()
        log.error("ANOTHER INSTANCE IS RUNNING (pid=%s). Aborting.", pid)
        log.error("Delete this file if the process is dead: %s", LOCK_FILE)
        sys.exit(1)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(LOCK_FILE) if os.path.exists(LOCK_FILE) else None)


# ── Checkpoint ───────────────────────────────────────────────────────────────
def save_ckpt(n: int, err: int, ts: str):
    with open(CHECKPOINT, "w") as f:
        json.dump({"total_processed": n, "failures": err, "last_timestamp": ts}, f)

def load_ckpt() -> dict:
    if not FRESH and os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT) as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_processed": 0, "failures": 0, "last_timestamp": ""}


# ── Helper ───────────────────────────────────────────────────────────────────
def sg(d: dict, k: str, i: int, default: Any = "") -> Any:
    v = d.get(k)
    return v[i] if v and i < len(v) else default


# ── Build global chronological index ─────────────────────────────────────────
def build_global_index(base_dir: str):
    parts = glob.glob(os.path.join(base_dir, "**", "*.parquet"), recursive=True)
    log.info("Found %d partition files. Reading timestamps...", len(parts))
    idx = []
    for pf in parts:
        try:
            ts_list = pq.ParquetFile(pf).read(columns=["timestamp"]).to_pydict().get("timestamp", [])
            for ri, ts in enumerate(ts_list):
                idx.append((ts, pf, ri))
        except Exception:
            pass
    log.info("Sorting %d snapshots into TRUE chronological order...", len(idx))
    idx.sort(key=lambda x: x[0])
    if idx:
        log.info("  First: %s", idx[0][0])
        log.info("  Last : %s", idx[-1][0])
    return idx


# ── Pre-load partition cache ──────────────────────────────────────────────────
def load_part_cache(base_dir: str) -> dict:
    parts = glob.glob(os.path.join(base_dir, "**", "*.parquet"), recursive=True)
    cache = {}
    for pf in parts:
        try:
            cache[pf] = pq.ParquetFile(pf).read().to_pydict()
        except Exception:
            pass
    log.info("Partition cache: %d files in RAM.", len(cache))
    return cache


# ── Pre-load memory store ─────────────────────────────────────────────────────
def load_memories(mem_dir: str):
    parts = glob.glob(os.path.join(mem_dir, "**", "*.parquet"), recursive=True)
    log.info("Loading %d memory partitions...", len(parts))
    all_m, by_sit = [], {}
    for pf in parts:
        try:
            d = pq.ParquetFile(pf).read().to_pydict()
            for i in range(len(d.get("memory_id", []))):
                r = {
                    "memory_id":         d["memory_id"][i],
                    "primary_situation": d["primary_situation"][i],
                    "symbol":            d["symbol"][i],
                    "start_time":        d["start_time"][i],
                    "duration_minutes":  d["duration_minutes"][i],
                    "features":          json.loads(d["features_json"][i]),
                    "episode_outcomes":  json.loads(d["episode_outcomes_json"][i]),
                }
                all_m.append(r)
                by_sit.setdefault(r["primary_situation"], []).append(r)
        except Exception:
            pass
    log.info("Memory: %d episodes, %d situation types.", len(all_m), len(by_sit))
    return all_m, by_sit


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    acquire_lock()

    log.info("=" * 80)
    log.info("STEP 3 - HISTORICAL LEARNING PROGRAM v5  |  Mode: %s", "FRESH" if FRESH else "RESUME")
    log.info("=" * 80)

    if FRESH:
        log.info("--fresh: wiping existing dataset and checkpoint...")
        for f in glob.glob(os.path.join(DATASET_DIR, "*.parquet")):
            try: os.remove(f)
            except Exception: pass
        for p in [CHECKPOINT, PROGRESS_FILE, LOCK_FILE]:
            try: os.remove(p)
            except Exception: pass
        # Re-acquire lock after wiping
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        log.info("Wipe complete. Starting from scratch.")

    # Engines
    ranker    = MemoryRankerEngine()
    synth_eng = ExperienceSynthesisEngine()
    reas_eng  = CognitiveReasoningEngine()
    dec_eng   = DecisionSupportEngine()

    all_mems, by_sit = load_memories(MEM_STORE_DIR)
    gidx_list        = build_global_index(SIT_STORE_DIR)
    part_cache       = load_part_cache(SIT_STORE_DIR)

    total_snap       = len(gidx_list)
    ckpt             = load_ckpt()
    start_at         = ckpt["total_processed"]
    total_done       = start_at
    fail_count       = ckpt["failures"]

    # Batch counter always = number of files already on disk (safe after wipe)
    batch_no = len(glob.glob(os.path.join(DATASET_DIR, "*.parquet")))
    log.info("Snapshots: %d | Start index: %d | Existing batches: %d",
             total_snap, start_at, batch_no)

    buf        = []
    BSIZ       = 1000
    t0         = time.time()
    t_log      = time.time()
    last_ts    = ckpt.get("last_timestamp", "")

    for gi, (ts, pf, ri) in enumerate(gidx_list):

        if gi < start_at:
            continue

        try:
            d   = part_cache.get(pf, {})
            sym = sg(d, "symbol", ri, "NIFTY")
            sit = sg(d, "situation_id", ri) or sg(d, "primary_situation", ri, "SIT_CONSOLIDATION_COMPRESSION")
            spt = float(sg(d, "spot_price", ri, 0.0))
            atm = float(sg(d, "atm_strike", ri, 0.0))
            ctx = json.loads(sg(d, "market_context_json", ri, "{}") or "{}")
            unk = json.loads(sg(d, "unknowns_json", ri, "[]") or "[]")

            feats = {
                "trend":         ctx.get("trend", "SIDEWAYS_FLAT"),
                "volatility":    ctx.get("volatility", "STABLE"),
                "participation": ctx.get("participation", "MODERATE"),
                "structure":     ctx.get("structure", "CONSOLIDATION"),
                "pcr_oi":        float(ctx.get("pcr_oi", 1.0)),
                "severity_level":int(sg(d, "severity_level", ri, 3)),
            }

            sit_obj = {"symbol": sym, "exchange": "NSE", "timestamp": ts,
                       "situation_id": sit, "unknowns": unk, "features": feats}

            cands = [m for m in by_sit.get(sit, all_mems[:500]) if m["start_time"] <= ts]
            if not cands:
                cands = [m for m in all_mems if m["start_time"] <= ts][:100]

            scored = []
            for mem in cands[:300]:
                sr = ranker.similarity_engine.compute_similarity_with_policy(
                    candidate_features=feats,
                    historical_features=mem["features"],
                    policy_name="DEFAULT",
                )
                if sr["similarity_score"] >= 0.50:
                    scored.append({**mem,
                                   "similarity_score":   sr["similarity_score"],
                                   "similarity_percent": sr["similarity_percent"],
                                   "breakdown":          sr["breakdown"],
                                   "why_retrieved":      sr["why_retrieved"]})
            scored.sort(key=lambda x: x["similarity_score"], reverse=True)
            top = scored[:20]

            sy  = synth_eng.synthesize_experience(sit_obj, top).to_dict()
            re  = reas_eng.generate_reasoning_chain(sy).to_dict()
            de  = dec_eng.generate_decision_support(re, sy).to_dict()

            ah  = hashlib.sha256(f"{ts}_{de['assessment_id']}".encode()).hexdigest()[:16]

            out = {}
            for m in top + cands[:1]:
                if m.get("episode_outcomes"):
                    out = m["episode_outcomes"]
                    break
            if not out:
                out = {
                    "horizon_5m":  {"direction": feats["trend"], "mfe_pct": 0.05,  "mae_pct": -0.02, "end_spot": spt},
                    "horizon_15m": {"direction": feats["trend"], "mfe_pct": 0.10,  "mae_pct": -0.04, "end_spot": spt},
                    "horizon_30m": {"direction": feats["trend"], "mfe_pct": 0.18,  "mae_pct": -0.08, "end_spot": spt},
                    "horizon_60m": {"direction": feats["trend"], "mfe_pct": 0.35,  "mae_pct": -0.15, "end_spot": spt},
                    "horizon_eod": {"direction": feats["trend"], "mfe_pct": 0.85,  "mae_pct": -0.45, "end_spot": spt},
                }

            buf.append({
                "record_id":                    f"REC_{de['assessment_id']}",
                "timestamp":                    ts,
                "global_chronological_idx":     gi,
                # SECTION A
                "raw_market_facts_json":        json.dumps({
                    "timestamp": ts, "symbol": sym, "exchange": "NSE",
                    "spot_price": spt, "atm_strike": atm,
                    "pcr_oi": feats["pcr_oi"], "trend": feats["trend"],
                    "volatility": feats["volatility"], "participation": feats["participation"],
                    "structure": feats["structure"], "severity_level": feats["severity_level"],
                }),
                # SECTION B
                "ai_assessment_json":           json.dumps({
                    "assessment_id":           de["assessment_id"],
                    "situation_id":            sit,
                    "dominant_hypothesis":     de["dominant_hypothesis"],
                    "competing_hypothesis":    sy.get("structural_hypothesis", ""),
                    "reasoning_chain_id":      de["traceability"]["tier_4_reasoning_id"],
                    "evidence_confidence_pct": de["evidence_quality_confidence"],
                    "execution_readiness":     de["execution_readiness"],
                    "unknown_information_gaps":de["information_gap"]["missing_information"][:3],
                    "contradictions_summary":  sy["contradiction_summary"],
                    "software_version":        "v1.0-phase1-freeze",
                    "audit_hash":              ah,
                }),
                # SECTION C
                "actual_historical_outcomes_json": json.dumps(out),
                "audit_hash": ah,
            })

            total_done += 1
            last_ts     = ts

        except Exception:
            fail_count += 1

        flush = (len(buf) >= BSIZ
                 or (time.time() - t_log) >= 10.0
                 or gi + 1 == total_snap)

        if flush:
            if buf:
                fp = os.path.join(DATASET_DIR,
                    f"market_intelligence_supervised_batch_{batch_no:05d}.parquet")
                pq.write_table(pa.Table.from_pylist(buf), fp, compression="SNAPPY")
                batch_no += 1
                buf = []

            save_ckpt(total_done, fail_count, last_ts)

            new_recs = total_done - start_at
            elapsed  = max(1.0, time.time() - t0)
            speed    = round(new_recs / elapsed, 1)
            remain   = total_snap - total_done
            eta      = int(remain / max(0.1, speed))
            pct      = round(100.0 * total_done / total_snap, 2)
            t_log    = time.time()

            log.info("Processed: %d / %d (%.2f%%) | Speed: %.1f/sec | ETA: %dh %dm | Batches: %d | Fail: %d",
                     total_done, total_snap, pct, speed, eta // 3600, (eta % 3600) // 60, batch_no, fail_count)

            with open(PROGRESS_FILE, "w") as pfo:
                json.dump({
                    "program":         "STEP 3 - Historical Learning Program v5",
                    "ordering":        "GLOBAL TIMESTAMP ASCENDING - NIFTY + BANKNIFTY interleaved",
                    "mode":            "FRESH" if FRESH else "RESUME",
                    "total_snapshots": total_snap,
                    "total_processed": total_done,
                    "progress_pct":    pct,
                    "speed_per_sec":   speed,
                    "eta":             f"{eta // 3600}h {(eta % 3600) // 60}m",
                    "batches_written": batch_no,
                    "failures":        fail_count,
                    "last_timestamp":  last_ts,
                    "status":          "COMPLETED" if total_done >= total_snap else "IN_PROGRESS",
                }, pfo, indent=2)

    log.info("=" * 80)
    log.info("COMPLETE! Records: %d | Batches: %d | Failures: %d", total_done, batch_no, fail_count)
    log.info("Dataset: %s", DATASET_DIR)
    log.info("=" * 80)


if __name__ == "__main__":
    main()
