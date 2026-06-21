import csv
import os

csv_path = "feature_engineered_stock_data.csv"
if os.path.exists(csv_path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        dt_idx = headers.index('datetime')
        
        first_row = next(reader)
        first_dt = first_row[dt_idx]
        
        # Read last row by reading in a loop
        last_dt = None
        for row in reader:
            if row:
                last_dt = row[dt_idx]
                
        print("CSV Date Range:")
        print("  Start Date:", first_dt)
        print("  End Date:", last_dt)
