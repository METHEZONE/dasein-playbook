"""Headline judge, independent of selection: local qwen3.8-27b-heretic (llama-swap :18080, qwen alias ONLY, sequential).
Same 7-criterion rubric + invented-facts list. Scores Dasein (S6) and S1/S2/S5/S7 (all seeds) on the 3 demo tasks.
-> _eval/headline.json"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as E
import dasein_final as D

W = E.W


def qwen(prompt):
    body = json.dumps({"model": "qwen3.8-27b-heretic", "messages": [{"role": "user", "content": prompt}], "temperature": 0,
                       "max_tokens": 700, "chat_template_kwargs": {"enable_thinking": False}})
    out = subprocess.run(["ssh", "studio", "curl -s -m 300 http://127.0.0.1:18080/v1/chat/completions -H 'content-type: application/json' --data-binary @-"],
                         input=body, capture_output=True, text=True, timeout=330).stdout
    return json.loads(out)["choices"][0]["message"]["content"]


def judge(task, text):
    try:
        t = qwen(D.RUBRIC.format(task=task["prompt"], context=task["context"][:9000], text=text))
        t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
        j = json.loads(re.search(r"\{.*\}", t, re.S).group())
        return {"rubric": round(sum(float(j[c]) for c in D.CRIT) / (5 * len(D.CRIT)), 4),
                "invented": [x for x in j.get("invented_facts", []) if isinstance(x, str)]}
    except Exception as e:
        return {"rubric": None, "invented": [], "error": str(e)[:150]}


def main():
    today, recent = E.load_inputs()
    tasks, _ = E.build_tasks(today, recent)
    T = {t["id"]: t for t in tasks if t["id"] in ("day-blog", "recent-essay", "followup")}
    base = json.load(open(os.path.join(W, "gen_base.json")))
    seeds = json.load(open(os.path.join(W, "fair_seeds.json")))
    fin = json.load(open(os.path.join(W, "dasein_final.json")))
    # baselines first (seed 0 only: the qwen slot is ~100 s/call and shared), Dasein last; S1/S2 refuse without context -> not judged
    med = json.load(open(os.path.join(W, "median_seed.json")))
    items = [(o["task"], {"S5c": "S5", "S7c": "S7"}[o["system"]], o["seed"], o["text"]) for o in seeds
             if o["task"] in T and o["seed"] == med[f"{o['task']}|{o['system']}"]]
    if os.environ.get("WITH_S6", "1") == "1":
        items = [(tid, "S6", 0, fin[tid]["best"]["text"]) for tid in T] + items
    p = os.path.join(W, "headline.json")
    done = {(r["task"], r["system"], r["seed"], r["text"]): r for r in (json.load(open(p)) if os.path.exists(p) else [])}
    res = []
    for tid, s, k, text in items:  # sequential on purpose: one llama slot, shared with core-2d
        r = done.get((tid, s, k, text)) or {"task": tid, "system": s, "seed": k, "text": text, **judge(T[tid], text)}
        res.append(r)
        json.dump(res, open(p, "w"), ensure_ascii=False, indent=1)
        print(tid, s, k, r["rubric"], len(r["invented"]), r.get("error", ""), flush=True)


if __name__ == "__main__":
    main()
