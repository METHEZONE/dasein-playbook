"""Finish the independent qwen judge: S1-S4 (1 run per task) + selector-vs-random on Dasein's saved 12-draft pools
(4 random drafts per task, seed 0). Sequential, qwen alias only. Merges into _eval/headline.json and results.json."""
import json, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as E
import headline as Hd
from build_results import real_invented

W = E.W


def main():
    today, recent = E.load_inputs()
    tasks, _ = E.build_tasks(today, recent)
    T = {t["id"]: t for t in tasks if t["id"] in ("day-blog", "recent-essay", "followup")}
    base = json.load(open(os.path.join(W, "gen_base.json")))
    fin = json.load(open(os.path.join(W, "dasein_final.json")))
    hp = os.path.join(W, "headline.json")
    head = json.load(open(hp))
    rnd = random.Random(0)
    items = [(tid, s, 0, base[f"{tid}|{s}"]) for tid in T for s in ("S1", "S2", "S3", "S4")]
    for tid in T:
        pool = [c["text"] for c in fin[tid]["candidates"] if c.get("text")]
        for i, t in enumerate(rnd.sample(pool, min(4, len(pool)))):
            items.append((tid, "RANDOM", i, t))
    have = {(h["task"], h["system"], h["seed"]) for h in head}
    for tid, s, k, text in items:
        if (tid, s, k) in have:
            continue
        r = {"task": tid, "system": s, "seed": k, "text": text, **Hd.judge(T[tid], text)}
        head.append(r)
        json.dump(head, open(hp, "w"), ensure_ascii=False, indent=1)
        print(tid, s, k, r["rubric"], r.get("error", ""), flush=True)

    res = json.load(open(os.path.join(W, "results.json")))
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None
    for b in res["bench"]:
        hs = [h for h in head if h["system"] == b["system"] and h.get("rubric") is not None]
        if b["system"] in ("S5", "S7"):
            med = json.load(open(os.path.join(W, "median_seed.json")))
            hs = [h for h in hs if h["seed"] == med[f"{h['task']}|{b['system']}c"]]
        b["headline_qwen27b_rubric"] = mean([h["rubric"] for h in hs])
        b["headline_qwen27b_invented"] = sum(len(real_invented(h["invented"])) for h in hs) if hs else None
        b["headline_n"] = len(hs)
        if b["system"] in ("S1", "S2", "S3", "S4"):
            b["runs_note"] = "1 run per task (no seeds); v2_range is across the 3 tasks"
        elif b["system"] == "S6":
            b["runs_note"] = "1 pipeline run per task; v2_range is across the 3 tasks"
        else:
            b["runs_note"] = "3 seeds per task; headline judged on the median seed"
    sel = {}
    for tid in T:
        r = [h["rubric"] for h in head if h["task"] == tid and h["system"] == "RANDOM" and h.get("rubric") is not None]
        p = [h["rubric"] for h in head if h["task"] == tid and h["system"] == "S6" and h.get("rubric") is not None]
        sel[tid] = {"dasein_pick": p[0] if p else None, "random_draft_mean": mean(r), "random_draft_scores": r}
    res["selector_vs_random"] = {"judge": "qwen3.8-27b-heretic (independent of selection)", "n_random_per_task": 4,
                                 "per_task": sel,
                                 "dasein_pick_mean": mean([v["dasein_pick"] for v in sel.values()]),
                                 "random_mean": mean([x for v in sel.values() for x in v["random_draft_scores"]])}
    json.dump(res, open(os.path.join(W, "results.json"), "w"), ensure_ascii=False, indent=1)
    os.system(f"scp -q {os.path.join(W, 'results.json')} studio:tell-data/eval/results.json")
    print(json.dumps(res["selector_vs_random"], indent=1))
    print([(b["system"], b["headline_qwen27b_rubric"], b["headline_n"]) for b in res["bench"]])


if __name__ == "__main__":
    main()
