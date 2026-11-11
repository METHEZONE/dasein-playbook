"""Build mlx-lm chat SFT files. usage: build_sft.py ct_all.jsonl opinions.jsonl voice-lora-dir outdir"""
import json, sys, random, os, collections
random.seed(7)
SYS = "You are Minsung."
ct = [json.loads(l) for l in open(sys.argv[1])]
ops = [json.loads(l) for l in open(sys.argv[2])] if os.path.exists(sys.argv[2]) else []
def msg(u, a, ko=False): return {"messages": [{"role": "system", "content": SYS}, {"role": "user", "content": u}, {"role": "assistant", "content": a}]}
groups = collections.defaultdict(list)  # split by session so valid is not leaked from train
for r in ct:
    if r["context"]:
        groups[str(r["session"])].append(("pair", msg(r["ctx_en"] or r["context"][-1]["text"], r["en"]), msg(r["context"][-1]["text"], r["ko"])))
for o in ops:
    groups[str(o["session"])].append(("opinion", msg(o["topic"], o["opinion"]), None))
keys = sorted(groups); random.shuffle(keys)
cut = int(len(keys) * 0.9)
sets = {"train": keys[:cut], "valid": keys[cut:]}
os.makedirs(sys.argv[4], exist_ok=True); n = collections.Counter()
for name, ks in sets.items():
    with open(f"{sys.argv[4]}/{name}.jsonl", "w") as en, open(f"{sys.argv[4]}/{name}_ko.jsonl", "w") as ko:
        rows = [x for k in ks for x in groups[k]]
        # existing English pairs: keep their own train/valid split
        extra = [json.loads(l) for l in open(f"{sys.argv[3]}/{name}.jsonl")]
        for kind, e, k in rows:
            en.write(json.dumps(e, ensure_ascii=False) + "\n"); n[name, kind] += 1
            if k: ko.write(json.dumps(k, ensure_ascii=False) + "\n")
        for e in extra: en.write(json.dumps(e, ensure_ascii=False) + "\n"); n[name, "voice-lora"] += 1
print(dict(n))
