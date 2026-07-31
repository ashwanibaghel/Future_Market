import sqlite3
import glob
import os

print("=== DEEP DB TIMESTAMP INSPECTION ===")
db_paths = glob.glob("E:/Future Stock/**/*.db", recursive=True)

for db_path in db_paths:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cur.fetchall()
        for t in tables:
            tname = t[0]
            cur.execute(f'SELECT count(*) FROM "{tname}";')
            count = cur.fetchone()[0]
            if count > 0:
                print(f"\nDB: {db_path} | Table: {tname} | Rows: {count}")
                cur.execute(f'SELECT * FROM "{tname}" LIMIT 1;')
                cols = [desc[0] for desc in cur.description]
                print(f"  Cols: {cols}")
                time_cols = [c for c in cols if 'time' in c or 'date' in c or 'created' in c]
                if time_cols:
                    tc = time_cols[0]
                    cur.execute(f'SELECT min("{tc}"), max("{tc}") FROM "{tname}";')
                    min_t, max_t = cur.fetchone()
                    print(f"  Time Range ({tc}): {min_t} ---> {max_t}")
        conn.close()
    except Exception as e:
        pass
