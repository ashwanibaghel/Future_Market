import os
import sys
import glob
import json
import pyarrow.dataset as pds
from sklearn.preprocessing import LabelEncoder

ds_dirs = sorted(glob.glob("E:/Future Stock/research_storage/model_datasets/v1/*/*"))
decoder_mappings = {}
for d in ds_dirs:
    tr = os.path.join(d, "train.parquet")
    man = os.path.join(d, "dataset_manifest.json")
    if os.path.exists(tr):
        with open(man) as f:
            m = json.load(f)
        module_id = m["module_id"]
        target = m["target_column"]
        tbl = pds.dataset(tr).to_table(columns=[target]).to_pandas()
        le = LabelEncoder()
        le.fit(tbl[target])
        classes = [str(c) for c in le.classes_]
        decoder_mappings[module_id] = {i: c for i, c in enumerate(classes)}
        print("Module:", f"{module_id:<32}", "| Target Classes:", decoder_mappings[module_id])
