"""Extract Min's stated views from cleaned turns (claude-sub fallback). usage: opinions.py ct_all.jsonl opinions.jsonl"""
import json, sys, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor
P = """Below are numbered things Min (blunt Korean startup founder) said, in English. For each that states a real opinion, belief, claim or judgment (about products, startups, AI, people-in-general, strategy; not logistics or small talk), output {"i":n,"topic":"short neutral question a friend could ask to get that view, in English","opinion":"his view as first-person casual English, kept in his own words, <=60 words, no added ideas"}. Skip the rest. Output ONLY a JSON array.\\n\\n"""
rows = [json.loads(l) for l in open(sys.argv[1])]
rows = [r for r in rows if len(r["en"]) >= 90]
B = 25
def work(s):
    items = rows[s:s + B]
    p = P + json.dumps([{"i": i, "t": r["en"]} for i, r in enumerate(items)], ensure_ascii=False)
    try:
        out = subprocess.run([os.path.expanduser("~/.local/bin/claude-sub"), "-p", "--model", "sonnet", p], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=900).stdout
        res = json.loads(re.search(r"\[.*\]", out, re.S).group(0))
    except Exception as e:
        print("fail", s, e, flush=True); return []
    return [{"session": items[x["i"]]["session"], "src": items[x["i"]]["src"], "ts": items[x["i"]]["ts"], "topic": x["topic"], "opinion": x["opinion"], "source_en": items[x["i"]]["en"]} for x in res if isinstance(x.get("i"), int) and x["i"] < len(items)]
with open(sys.argv[2], "w") as fh, ThreadPoolExecutor(6) as ex:
    for r in ex.map(work, range(0, len(rows), B)):
        for o in r: fh.write(json.dumps(o, ensure_ascii=False) + "\n")
        fh.flush()
