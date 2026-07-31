import os
import sys
import json
import logging
import subprocess

logger = logging.getLogger("acquisition.sync_dhan_raw_lake")

DEFAULT_VPS_HOST = "ubuntu@161.118.183.231"
DEFAULT_KEY_PATH = "E:/Future Stock/ssh-key-2026-06-21 (1).key"
LOCAL_TARGET_DIR = "E:/Future Stock/research_storage/raw"


def sync_dhan_raw_files(vps_host: str = DEFAULT_VPS_HOST, key_path: str = DEFAULT_KEY_PATH):
    """
    Syncs all 5,300+ compressed 2021-2025 Dhan historical payload files (.json.gz)
    from Oracle VPS to local research storage.
    """
    os.makedirs(LOCAL_TARGET_DIR, exist_ok=True)

    logger.info("Syncing 5-year raw Dhan payload archive from %s...", vps_host)

    # Execute tar stream for raw/dhan archive
    tar_cmd = f"ssh -o StrictHostKeyChecking=no -i \"{key_path}\" {vps_host} \"tar -czf - -C /home/ubuntu/research_storage raw\" | tar -xzf - -C \"{LOCAL_TARGET_DIR}\""

    logger.info("Executing stream: %s", tar_cmd)
    res = subprocess.run(tar_cmd, shell=True, capture_output=True, text=True)

    # Count downloaded files
    dhan_dir = os.path.join(LOCAL_TARGET_DIR, "raw", "dhan")
    if not os.path.exists(dhan_dir):
        dhan_dir = os.path.join(LOCAL_TARGET_DIR, "dhan")

    total_files = 0
    total_bytes = 0

    for root, dirs, files in os.walk(LOCAL_TARGET_DIR):
        for f in files:
            total_files += 1
            total_bytes += os.path.getsize(os.path.join(root, f))

    logger.info("Sync complete! Total files: %d, Total Size: %.2f MB", total_files, total_bytes / (1024 * 1024))
    print(f"SYNC COMPLETE! Total Files: {total_files}, Total Size: {total_bytes / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    sync_dhan_raw_files()
