import sqlite3
import os
import glob
import csv

print("=== SQLite Database Inspection (intraday.db) ===")
if os.path.exists("intraday.db"):
    conn = sqlite3.connect("intraday.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print("Tables in DB:", len(tables), tables[:5])
    
    total_db_rows = 0
    sample_table = None
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        count = cursor.fetchone()[0]
        total_db_rows += count
        if count > 0 and sample_table is None:
            sample_table = table
            
    print("Total rows across all tables in sqlite DB:", total_db_rows)
    if sample_table:
        print(f"Sample table '{sample_table}' schema:")
        cursor.execute(f"PRAGMA table_info(\"{sample_table}\")")
        print(cursor.fetchall())
        cursor.execute(f"SELECT * FROM \"{sample_table}\" LIMIT 2")
        print(cursor.fetchall())
    conn.close()
else:
    print("intraday.db does not exist")

print("\n=== Parquet Files (historical/) ===")
parquet_files = glob.glob("historical/*.parquet")
print("Number of parquet files:", len(parquet_files))
for pf in parquet_files[:5]:
    print(f"  {os.path.basename(pf)} size: {os.path.getsize(pf)} bytes")

print("\n=== Feature Engineered Stock Data CSV ===")
csv_path = "feature_engineered_stock_data.csv"
if os.path.exists(csv_path):
    print("CSV Size:", os.path.getsize(csv_path), "bytes")
    # Read headers
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        print("Columns in CSV:", headers)
        print("Total columns in CSV:", len(headers))
        
        # Read first row
        first_row = next(reader)
        print("First row values:", dict(zip(headers[:10], first_row[:10])))
        
    # Count rows without loading entire file in memory
    print("Counting rows in CSV...")
    row_count = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        for _ in f:
            row_count += 1
    print("Total rows in CSV (including header):", row_count)
else:
    print("CSV does not exist")
