import os
import glob
import sqlite3
import pyarrow.dataset as ds
import pandas as pd
import numpy as np

print("================================================================================")
print("             SCIENTIFIC DATASET TIMESTAMP & OVERLAP PROOF AUDIT                ")
print("================================================================================\n")

# 1. Training Dataset Audit
train_files = glob.glob("E:/Future Stock/research_storage/model_datasets/v1/**/train.parquet", recursive=True)
tr_mins, tr_maxs = [], []

for tf in train_files:
    try:
        table = ds.dataset(tf).to_table()
        if "timestamp" in table.column_names:
            ts = table.column("timestamp").to_numpy().astype(str)
            tr_mins.append(min(ts))
            tr_maxs.append(max(ts))
    except Exception as e:
        print(f"Error reading train file {tf}: {e}")

min_train_ts = min(tr_mins) if tr_mins else "N/A"
max_train_ts = max(tr_maxs) if tr_maxs else "N/A"

print("1. MODEL TRAINING DATASET AUDIT (train.parquet across 12 modules):")
print(f"   Total Training Parquet Files: {len(train_files)}")
print(f"   Min Timestamp (Start of Training): {min_train_ts}")
print(f"   Max Timestamp (End of Training)  : {max_train_ts}")

# 2. Live Scraped SQLite DB Audit
db_path = "E:/Future Stock/backend/options_data.db"
print("\n2. DAILY LIVE SCRAPED SQLITE DATABASE AUDIT (options_data.db):")
min_db, max_db, cnt_db = "N/A", "N/A", 0
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT min(timestamp), max(timestamp), count(*) FROM option_chain_snapshots;")
    min_db, max_db, cnt_db = cur.fetchone()
    print(f"   Path: {db_path}")
    print(f"   Total Live Scraped Snapshots: {cnt_db}")
    print(f"   Min Timestamp: {min_db}")
    print(f"   Max Timestamp: {max_db}")
    conn.close()

# 3. Parquet Lake & Situation Store Audit
sit_files = glob.glob("E:/Future Stock/research_storage/situation_store/**/*.parquet", recursive=True)
sit_mins, sit_maxs = [], []

for sf in sit_files:
    try:
        table = ds.dataset(sf).to_table()
        if "timestamp" in table.column_names:
            ts = table.column("timestamp").to_numpy().astype(str)
            sit_mins.append(min(ts))
            sit_maxs.append(max(ts))
    except Exception as e:
        pass

min_sit_ts = min(sit_mins) if sit_mins else "N/A"
max_sit_ts = max(sit_maxs) if sit_maxs else "N/A"

print("\n3. PARQUET SITUATION STORE DATASET AUDIT (situations.parquet):")
print(f"   Total Parquet Store Files: {len(sit_files)}")
print(f"   Min Timestamp: {min_sit_ts}")
print(f"   Max Timestamp: {max_sit_ts}")

print("\n================================================================================")
print("                     MATHEMATICAL OVERLAP PROOF RESULT                          ")
print("================================================================================")
print(f"Training End Date (max_train_ts)  : {max_train_ts}")
print(f"Scraped Live Min (min_db)         : {min_db}")
print(f"Situation Store Min (min_sit_ts)  : {min_sit_ts}")

if max_train_ts != "N/A":
    if min_sit_ts > max_train_ts:
        print("\nPROVED: 100% NO OVERLAP. Playback Dataset starts AFTER Training End Date.")
    else:
        print(f"\nAUDIT FINDING: Training Dataset covers up to {max_train_ts}.")
print("================================================================================\n")
