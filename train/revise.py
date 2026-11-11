"""Fact-fix pass for Dasein-final: take the top finalists per task, hand DeepSeek the judges' invented-fact list,
make the smallest edit that removes or corrects each one (cut it, don't replace it with new detail), re-score with reward v2."""
import concurrent.futures as cf, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as E
import dasein_final as D

FIX = """Here is a short piece I wrote, my real context, and a list of claims in it that are NOT supported by the context.
Make the smallest possible edit: delete or correct each unsupported claim so every fact matches the context exactly
(who, what, which day, order, counts). Do not add any new detail, scene, quote or reaction. Keep my voice, the throughline
and the ending. Keep it about the same length. Return only the revised piece, plain text.

CONTEXT:
{context}

UNSUPPORTED CLAIMS:
{inv}

PIECE:
{text}
"""


def fix(task, c):
    c = dict(c)
    t = D.gmi([{"role": "user", "content": FIX.format(context=task["context"], inv="\n".join(f"- {x}" for x in c["invented"]), text=c["text"])}],
              temp=0.3, max_tokens=900)
    t = D.re.sub(r"(?<=\w)[ \t]*[—–][ \t]*(?=\w)", ", ", E.clean(t))
    s1 = E.score(t, task["context"], judge=False)
    r = D.rubric(task["prompt"], t, task["context"])
    return {"text": t, "words": len(t.split()), "v1": s1["score"], **r, "revised_from": c["v2"],
            "v2": round(0.8 * (r["rubric"] or 0) + 0.2 * s1["score"] - 0.02 * min(10, len(r["invented"])), 4),
            "gate_private": not E.PRIVATE.search(t), "writer": c.get("writer", "deepseek") + "+fix"}


def main():
    today, recent = E.load_inputs()
    tasks, _ = E.build_tasks(today, recent)
    T = {t["id"]: t for t in tasks}
    p = os.path.join(E.W, "dasein_final.json")
    fin = json.load(open(p))
    want = sys.argv[1:] or list(fin)
    jobs = []
    for tid, o in [(k, fin[k]) for k in want]:
        top = sorted([c for c in o["candidates"] if "v2" in c and c.get("invented")], key=lambda c: -c["v2"])[:4]
        jobs += [(tid, c) for c in top]
    with cf.ThreadPoolExecutor(len(jobs)) as ex:
        res = list(ex.map(lambda j: (j[0], fix(T[j[0]], j[1])), jobs))
    for tid, r in res:
        fin[tid].setdefault("revised", []).append(r)
    tw = D.TARGET
    for tid, o in [(k, fin[k]) for k in want]:  # final pick: privacy + length gates, then fewest invented (0 is a hard gate for the essay), then v2
        pool = [c for c in o["candidates"] if "v2" in c] + o.get("revised", [])
        pool = [c for c in pool if not E.PRIVATE.search(c["text"]) and 0.75 * tw[tid] <= len(c["text"].split()) <= 1.25 * tw[tid]] or pool
        zero = [c for c in pool if not c.get("invented")]
        if tid == "recent-essay" and zero:
            pool = zero
        o["best"] = max(pool, key=lambda c: (c["v2"] - 0.05 * min(5, len(c.get("invented", [])))))
    json.dump(fin, open(p, "w"), ensure_ascii=False, indent=1)
    for tid, o in [(k, fin[k]) for k in want]:
        b = o["best"]
        print(f"\n=== {tid} | v2 {b['v2']} rubric {b.get('rubric')} invented {len(b.get('invented', []))} words {b['words']} revised={'revised_from' in b}\n{b['text']}")


if __name__ == "__main__":
    main()
