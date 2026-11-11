"""Discriminator set (human=Min vs ai=vanilla LLM on the same topic) + few-shot lines. usage: disc.py opinions.jsonl ct.jsonl outdir"""
import json, sys, os, re, subprocess, random
from concurrent.futures import ThreadPoolExecutor
random.seed(3)
ops = [json.loads(l) for l in open(sys.argv[1])]
P = 'For each numbered question, write the answer a helpful AI assistant would give, 30-60 words each, plain prose. Output ONLY a JSON array of {"i":n,"text":...}.\n\n'
def work(s):
    items = ops[s:s + 25]
    p = P + json.dumps([{"i": i, "q": o["topic"]} for i, o in enumerate(items)], ensure_ascii=False)
    try:
        out = subprocess.run([os.path.expanduser("~/.local/bin/claude-sub"), "-p", "--model", "sonnet", p], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=900).stdout
        res = json.loads(re.search(r"\[.*\]", out, re.S).group(0))
    except Exception as e: print("fail", s, e); return []
    return [{"text": r["text"], "label": "ai", "topic": items[r["i"]]["topic"]} for r in res if r["i"] < len(items)] + [{"text": o["opinion"], "label": "human", "topic": o["topic"]} for o in items]
os.makedirs(sys.argv[3], exist_ok=True)
rows = []
with ThreadPoolExecutor(6) as ex:
    for r in ex.map(work, range(0, len(ops), 25)): rows += r
random.shuffle(rows)
with open(f"{sys.argv[3]}/min_vs_ai.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
# few-shot: Min's own typed English, opinionated and 12-35 words
ct = [json.loads(l) for l in open(sys.argv[2])]
cand = [r["reply"] for r in ct if r["src"] == "claude" and re.fullmatch(r"[\x00-\x7f]+", r["reply"]) and 12 <= len(r["reply"].split()) <= 35]
print(len(rows), len(cand))
json.dump(random.sample(cand, min(10, len(cand))), open("fewshot_candidates.json", "w"), ensure_ascii=False, indent=1)
