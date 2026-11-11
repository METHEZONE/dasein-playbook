"""Fallback SFT set from W1's cleaned+translated speech (raw/ct_*.jsonl) when ~/tell-data/sft isn't ready.
Two shapes: (1) reply to what the other person said, (2) monologue = consecutive Min turns in one session joined
into 80-220 words, prompted by the meeting topic. Output ~/tell/sft_fallback/{train,valid}.jsonl."""
import json, os, random, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen import build_messages

D = os.path.expanduser("~/tell-data/raw")
rows = []
for f in ["ct_all.jsonl", "ct_b.jsonl"]:
    p = os.path.join(D, f)
    if os.path.exists(p):
        rows += [json.loads(l) for l in open(p) if l.strip()]

def ok(t):
    return t and len(t.split()) >= 6 and not re.search(r"[가-힣]", t)

seen, out = set(), []
for r in rows:  # (1) replies
    en, ctx = (r.get("en") or "").strip(), (r.get("ctx_en") or "").strip()
    if not ok(en) or en in seen:
        continue
    seen.add(en)
    if len(ctx.split()) >= 3:
        out.append(build_messages(f'Someone just said to you: "{ctx}" Reply.', "") + [{"role": "assistant", "content": en}])

by = {}
for r in rows:
    if ok((r.get("en") or "").strip()):
        by.setdefault((r["src"], r["session"]), []).append(r)
for (src, s), rs in by.items():  # (2) monologues
    rs.sort(key=lambda r: r.get("ts") or 0)
    buf = []
    for r in rs + [None]:
        if r is not None:
            buf.append(r["en"].strip())
        n = sum(len(b.split()) for b in buf)
        if (r is None and n >= 80) or n >= 220:
            title = rs[0].get("title", "")
            out.append(build_messages(f"Talk through your take, out loud, on this topic: {title}", "")
                       + [{"role": "assistant", "content": " ".join(buf)}])
            buf = []

random.seed(0)
random.shuffle(out)
k = max(20, len(out) // 12)
od = os.path.expanduser("~/tell/sft_fallback")
os.makedirs(od, exist_ok=True)
for name, part in [("valid", out[:k]), ("train", out[k:])]:
    with open(os.path.join(od, name + ".jsonl"), "w") as f:
        f.writelines(json.dumps({"messages": m}, ensure_ascii=False) + "\n" for m in part)
print(len(out), "rows;", sum(1 for m in out if m[1]["content"].startswith("Task: Talk")), "monologues")
