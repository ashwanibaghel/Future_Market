import glob
import json
import os

manifests = sorted(glob.glob("E:/Future Stock/research_storage/trained_models/v1/**/model_manifest.json", recursive=True))

print("\n" + "="*90)
print("CONSOLIDATED 12-MODULE QUANTITATIVE ENGINE PERFORMANCE BOARD")
print("="*90)
print(f"| {'Module ID':<30} | {'Layer':<20} | {'Accuracy':<10} | {'LogLoss':<10} | {'Macro F1':<10} | {'Status':<20} |")
print("|" + "-"*32 + "|" + "-"*22 + "|" + "-"*12 + "|" + "-"*12 + "|" + "-"*12 + "|" + "-"*22 + "|")

for m in manifests:
    d = json.load(open(m, encoding="utf-8"))
    mod_id = d.get("module_id", "UNKNOWN")
    layer = d.get("layer_name", "UNKNOWN")
    metrics = d.get("metrics", {})
    acc = str(metrics.get("test_accuracy", "N/A"))
    loss = str(metrics.get("test_log_loss", "N/A"))
    f1 = str(metrics.get("test_macro_f1", "N/A"))
    status = d.get("deployment_status", "RESEARCH_VALIDATED")
    print(f"| {mod_id:<30} | {layer:<20} | {acc:<10} | {loss:<10} | {f1:<10} | {status:<20} |")

print("="*90 + "\n")
