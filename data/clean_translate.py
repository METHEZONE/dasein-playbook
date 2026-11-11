"""Clean STT noise + translate Min's Korean turns to casual English via local gemma. Resumable.
usage: clean_translate.py raw.jsonl out.jsonl [N]"""
import json, sys, re, urllib.request, os, time
URL = "http://127.0.0.1:18080/v1/chat/completions"
SYS = """You clean speech-to-text transcripts of one person, Min (Korean startup founder, blunt, casual, fast talker), and translate them.
For each numbered item (JSON with "ctx" = what the other person said before, "t" = Min's raw STT text) return:
 "ko": the cleaned Korean text (fix obvious STT mishearings and stutter repeats using ctx, keep his words, tone, slang, sentence length; do not add ideas; if it is already English keep as is),
 "en": natural casual spoken English of it, as a blunt 20s native speaker would say it. Preserve bluntness, slang level, hedges and sentence length. No polishing, no softening.
 "ctx_en": short English rendering of ctx (empty if ctx empty),
 "ok": false if the text is unintelligible, mostly noise, or clearly not Min's own statement (e.g. an interviewer reading something), else true.
Output ONLY a JSON array of objects {"i":n,"ko":..,"en":..,"ctx_en":..,"ok":..}."""
B = int(os.environ.get('B', 8))
BACKEND = os.environ.get('BACKEND', 'gemma')  # 'claude' = fallback when the local llama slot is busy
W = int(os.environ.get('W', 1))


def call(items):
    if BACKEND == 'claude':
        import subprocess
        p = SYS + "\n\nINPUT:\n" + json.dumps([{"i": i, "ctx": (o["context"][-1]["text"][:250] if o["context"] else ""), "t": o["reply"]} for i, o in enumerate(items)], ensure_ascii=False)
        out = subprocess.run([os.path.expanduser("~/.local/bin/claude-sub"), "-p", "--model", "sonnet", p], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=900).stdout
        return json.loads(re.search(r"\[.*\]", out, re.S).group(0))
    body = {"model": "gemma-4-31b-heretic", "temperature": 0.3, "max_tokens": 4000,
            "messages": [{"role": "system", "content": SYS},
                         {"role": "user", "content": json.dumps([{"i": i, "ctx": (o["context"][-1]["text"][:250] if o["context"] else ""), "t": o["reply"]} for i, o in enumerate(items)], ensure_ascii=False)}]}
    r = urllib.request.urlopen(urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=900)
    txt = json.load(r)["choices"][0]["message"]["content"]
    return json.loads(re.search(r"\[.*\]", txt, re.S).group(0))


src = [json.loads(l) for l in open(sys.argv[1])]
N = int(sys.argv[3]) if len(sys.argv) > 3 else len(src)
from concurrent.futures import ThreadPoolExecutor
def work(s):
    items = src[s:s + B]
    for _ in range(2):
        try: res = call(items); break
        except Exception as e: print("fail", s, e, flush=True); res = []
    rows = []
    for r in res:
        try: o = items[r["i"]]
        except Exception: continue
        if r.get("ok") and r.get("en") and r.get("ko"):
            rows.append({**o, "ko": r["ko"], "en": r["en"], "ctx_en": r.get("ctx_en", "")})
    return s, rows
donef = sys.argv[2] + ".done"
done = set(map(int, open(donef).read().split())) if os.path.exists(donef) else set()
with open(sys.argv[2], "a") as fh, ThreadPoolExecutor(W) as ex:
    for s, rows in ex.map(work, [x for x in range(0, N, B) if x not in done]):
        for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush(); open(donef, "a").write(f"{s} ")
        print(s, len(rows), flush=True)
