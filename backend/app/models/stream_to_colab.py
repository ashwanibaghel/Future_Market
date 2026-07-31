"""
🏛️ OI Lens — DIRECT COLAB BASE64 CHUNK STREAMER

Streams remote_gpu_training_package.zip (113 MB) in 10 MB base64 chunks
directly to Colab interactive session via python.
"""

import os
import sys
import base64
import time

zip_path = r"E:\Future Stock\remote_gpu_training_package.zip"

if not os.path.exists(zip_path):
    print("Zip file not found:", zip_path)
    sys.exit(1)

with open(zip_path, "rb") as f:
    raw_bytes = f.read()

b64_str = base64.b64encode(raw_bytes).decode("ascii")
chunk_size = 5000000  # 5 million chars per chunk (~3.7 MB binary)
total_chunks = (len(b64_str) + chunk_size - 1) // chunk_size

print(f"Total base64 string length: {len(b64_str):,} chars across {total_chunks} chunks.")

# Write chunks to local temp text files for streaming
out_dir = r"E:\Future Stock\tmp\b64_chunks"
os.makedirs(out_dir, exist_ok=True)

for idx in range(total_chunks):
    chunk_data = b64_str[idx*chunk_size : (idx+1)*chunk_size]
    chunk_file = os.path.join(out_dir, f"chunk_{idx:02d}.b64")
    with open(chunk_file, "w", encoding="ascii") as f:
        f.write(chunk_data)
    print(f" [+] Generated {chunk_file} ({len(chunk_data):,} chars)")

print("ALL CHUNKS GENERATED READY FOR STREAMING!")
