import os, re, csv, statistics, sys

ROOT = "latency_under_load_logs"

if not os.path.isdir(ROOT):
    print(f"❌ Folder '{ROOT}' not found. Run the collector first or cd to the right place.")
    sys.exit(1)

# Accept both dot and comma decimals in folder names like:
# load_25pct_50.00Mbps  OR  load_25pct_50,00Mbps
load_dir_pat = re.compile(r"load_(\d+)pct_([\d\.,]+)Mbps")

# Linux ping footer (covers mdev or stddev)
rtt_footer = re.compile(r"rtt min/avg/max/(?:mdev|stddev) = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms")

rows = []

for root, dirs, files in os.walk(ROOT):
    base = os.path.basename(root)
    load_pct = None
    rate_mbps = None

    m = load_dir_pat.match(base)
    if m:
        load_pct = int(m.group(1))
        rate_str = m.group(2).replace(',', '.')   # fix comma decimals
        try:
            rate_mbps = float(rate_str)
        except ValueError:
            rate_mbps = None

    for fn in sorted(files):
        if not fn.startswith("ping_") or not fn.endswith(".txt"):
            continue
        path = os.path.join(root, fn)
        with open(path, "r", errors="ignore") as f:
            text = f.read()

        mt = rtt_footer.search(text)
        if not mt:
            # No standard Linux ping footer; skip
            continue

        rtt_min, rtt_avg, rtt_max, rtt_mdev = map(float, mt.groups())
        one_way = rtt_avg / 2.0

        rows.append({
            "load_pct": load_pct,
            "bg_rate_Mbps": rate_mbps,
            "subdir": base,
            "file": fn,
            "RTT_min_ms": rtt_min,
            "RTT_avg_ms": rtt_avg,
            "RTT_max_ms": rtt_max,
            "RTT_mdev_ms": rtt_mdev,
            "OneWayLatency_ms": one_way,
        })

if not rows:
    print("❌ No valid ping logs found under 'latency_under_load_logs/'.")
    print("   Ensure subfolders like 'load_25pct_50,00Mbps/' contain ping_*.txt with Linux ping footer.")
    sys.exit(1)

csv_name = "latency_under_load_results.csv"
with open(csv_name, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print("✅ Processing complete.")
print(f"Per-batch results saved to {csv_name}\n")

# Aggregate by load level; skip items without parsed load/rate
agg = {}
for r in rows:
    if r["load_pct"] is None or r["bg_rate_Mbps"] is None:
        continue
    key = (r["load_pct"], r["bg_rate_Mbps"])
    agg.setdefault(key, []).append(r)

print("--- Aggregate by load level ---")
for (lpct, rate) in sorted(agg.keys(), key=lambda k: (k[0], k[1])):
    items = agg[(lpct, rate)]
    rtt_avgs = [it["RTT_avg_ms"] for it in items]
    oneways  = [it["OneWayLatency_ms"] for it in items]
    mean_rtt = statistics.mean(rtt_avgs)
    min_rtt, max_rtt = min(rtt_avgs), max(rtt_avgs)
    mean_ow  = statistics.mean(oneways)
    min_ow,  max_ow  = min(oneways), max(oneways)
    print(f"Load {lpct}% (~{rate:.2f} Mbps): "
          f"Mean RTT {mean_rtt:.3f} ms (min {min_rtt:.3f}, max {max_rtt:.3f}); "
          f"Mean 1-way {mean_ow:.3f} ms (min {min_ow:.3f}, max {max_ow:.3f})")
