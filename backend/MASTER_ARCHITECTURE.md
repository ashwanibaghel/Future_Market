# PROJECT: OI Lens
# DOCUMENT TYPE: Master Engineering Blueprint
# STATUS: Active Execution Document
# AUTHOR: Chief Architect
# VERSION: 2.0

===========================================================
PROJECT VISION
===========================================================

OI Lens is NOT a trading bot.

OI Lens is a Quantitative Research Platform capable of:

1. Collecting historical market data.
2. Building research-grade datasets.
3. Running leakage-free historical simulations.
4. Evaluating thousands of trading strategies.
5. Building an AI-ready Decision Lake.
6. Supporting future AI models without redesigning the architecture.

Every engineering decision must support these goals.

===========================================================
CURRENT STATUS
===========================================================

Completed

✓ NIFTY historical acquisition
✓ Production-grade acquisition engine
✓ Resume checkpoints
✓ Replay index
✓ Raw archive
✓ Canonical parquet
✓ Validation pipeline

Running

• BANKNIFTY acquisition

===========================================================
ENGINEERING PRINCIPLES
===========================================================

1. Every module must be independent.
2. No module should depend on unfinished downloads.
3. Research consumes ONLY verified datasets.
4. Raw data is immutable.
5. Canonical data is immutable.
6. Derived data is reproducible.
7. No future data leakage is allowed.

===========================================================
SYSTEM ARCHITECTURE
===========================================================

The platform consists of independent pipelines:

Pipeline 1: Acquisition
Responsibilities: Download, Archive, Validate, Checkpoint, Replay Index, Dataset Registry

Pipeline 2: Feature Engineering
Responsibilities: Transform canonical data into research features (PCR, OI Change, IV, Volume, ATM Shift, Max Pain, Support, Resistance, VWAP, Volatility, Momentum, Derived Indicators). Output: Feature Dataset.

Pipeline 3: Historical Replay Engine
Responsibilities: Replay historical markets exactly as if they were live. Prediction at 10:30 may only access data available until 10:30 (No future data leakage). Output: Prediction Event.

Pipeline 4: Strategy Engine
Responsibilities: Run multiple independent strategies (OI, PCR, VWAP, Momentum, Breakout, Support/Resistance). Each produces Prediction, Confidence, Reason, Expected Direction, Expected Holding Time.

Pipeline 5: Evaluation Engine
Responsibilities: Compare predictions against actual outcomes (PnL, Win Rate, Reward, Drawdown, MAE, MFE, Best Possible Entry/Exit, False Buy/Sell, Accuracy). Store every evaluation.

Pipeline 6: Decision Lake
Responsibilities: Store every research event permanently (Timestamp, Features, Prediction, Confidence, Strategy Version, Market Context, Outcome, Reward, PnL, Evaluation Metrics, Decision Reason).

===========================================================
PLUGIN ARCHITECTURE
===========================================================

Every indicator, strategy, evaluator, and AI model must be a plugin. No hardcoded business logic.

===========================================================
DATA FLOW
===========================================================

Downloader -> Raw Archive -> Canonical Dataset -> Feature Engine -> Replay Engine -> Strategy Engine -> Evaluation Engine -> Decision Lake -> Future AI Dataset

===========================================================
MULTI-TRACK EXECUTION
===========================================================

Track A: Continue historical acquisition (BANKNIFTY -> Constituent Stocks -> Sector Indices -> India VIX -> Macro Data).
Track B: Immediately begin research platform development using verified NIFTY data (Sprint 6).

===========================================================
DATA QUALITY POLICY
===========================================================

Every monthly partition must pass Checksum, Replay Validation, Schema Validation, Duplicate Detection, Missing Data Validation. Only verified partitions become Research Ready.

===========================================================
NEXT EXECUTION SPRINT
===========================================================

Sprint 6: Research Platform Foundation
Objectives:
1. Create Feature Engineering Engine.
2. Create Replay Engine.
3. Create Strategy Plugin Framework.
4. Create Evaluation Engine.
5. Create Decision Lake Schema.

===========================================================
FUTURE ROADMAP
===========================================================

Sprint 7: Constituent Intelligence
Sprint 8: Meta Strategy Layer
Sprint 9: AI Learning Pipeline

===========================================================
NON-NEGOTIABLE RULES
===========================================================

- No future leakage.
- No mutable historical data.
- No overwriting verified partitions.
- No strategy-specific code inside the core engine.
- Everything must be modular, reproducible, and explainable.

===========================================================
END OF MASTER BLUEPRINT
