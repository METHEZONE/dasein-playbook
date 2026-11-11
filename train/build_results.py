"""Assemble ~/tell-data/eval/results.json (web/data/schema.md v1) + results.md + demo3.md from the eval pieces.
Every output gets the same reward v2 (rubric x2 judges, 0.8) + dasein-score v1 (0.2) - 0.02/invented fact.
Blind pairwise: Dasein vs each context-matched baseline, 2 judges x 2 orders. Wilson 95% CI, no win claimed unless CI > 0.5."""
import concurrent.futures as cf, hashlib, json, math, os, random, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as E
import dasein_final as D

W = E.W
SYSTEMS = [
    {"id": "S1", "name": "Vanilla GPT", "vendor": "openai", "desc": "gpt-6-astra, task prompt only (memory files stripped)"},
    {"id": "S2", "name": "Vanilla Claude", "vendor": "anthropic", "desc": "Claude, task prompt only (memory files stripped)"},
    {"id": "S3", "name": "GPT + style prompt", "vendor": "openai", "desc": "gpt-6-astra, 'write like Minsung' + 10 real lines, no context"},
    {"id": "S4", "name": "Claude + style prompt", "vendor": "anthropic", "desc": "Claude, 'write like Minsung' + 10 real lines, no context"},
    {"id": "S5", "name": "Claude + same context", "vendor": "anthropic", "desc": "Claude Sonnet given the same public-filtered context, length and constraints as Dasein, plain prompt; median of 3 seeds shown"},
    {"id": "S6", "name": "Dasein", "vendor": "tell", "desc": "writer-agnostic: public-filtered real context + gbrain, 'real question' planning, 12 drafts (DeepSeek-V3 on GMI, Astra, Claude) under the 7 human-writing constraints, gates (length, slop, privacy, invented facts), reranked by dasein-score v2, fact-fix pass"},
]
EXTRA = {"id": "S7", "name": "GPT + same context", "vendor": "openai", "desc": "gpt-6-astra given the same context and constraints as Dasein, plain prompt; median of 3 seeds shown"}


def real_invented(xs):
    """Judges sometimes put non-issues in invented_facts ("is supported", "(accurate)", "an omission"). Same rule for every system."""
    out = []
    for x in xs or []:
        if not isinstance(x, str):
            continue
        neg = re.search(r"not supported|unsupported|isn't supported|not established|not in (the )?context|invented|not stated|not mentioned", x, re.I)
        if re.search(r"no unsupported|no invented|\(accurate\)|omission|not an invented|\(fine\)$", x, re.I) and not re.search(r"^'.*' is invented", x):
            continue
        if re.search(r"\bsupported\b|accurate|\bfine\b", x, re.I) and not neg:
            continue
        if re.search(r"invented (sentiment|reflection|framing)|sentiment, not a fact", x, re.I):
            continue  # opinions/reflections are not factual claims
        out.append(x)
    return out


def wilson(k, n):
    if n == 0:
        return (0, 0, 1)
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 3), round(c - h, 3), round(c + h, 3))


def reward(task, text):
    v1 = E.score(text, task["context"], judge=False)
    r = D.rubric(task["prompt"], text, task["context"])
    v2 = round(0.8 * (r["rubric"] or 0) + 0.2 * v1["score"] - 0.02 * min(10, len(r["invented"])), 4)
    return {"v2": v2, "v1": v1["score"], "rubric": r["rubric"], "invented": r["invented"], "spans": v1["spans"],
            "p_human": v1["parts"]["p_human"], "grounding": v1["parts"]["grounding"], "slop_per_100w": v1["parts"]["slop_per_100w"],
            "judges": r["judges"]}


def main():
    today, recent = E.load_inputs()
    tasks, shots = E.build_tasks(today, recent)
    tasks = [t for t in tasks if t["id"] in ("day-blog", "recent-essay", "followup")]  # replies dropped: leaked into sft2 train
    T = {t["id"]: t for t in tasks}
    base = json.load(open(os.path.join(W, "gen_base.json")))
    seeds = json.load(open(os.path.join(W, "fair_seeds.json")))
    med = json.load(open(os.path.join(W, "median_seed.json")))  # VS/demo shows each baseline's MEDIAN seed (by reward v2)
    fair = {(o["task"], o["system"]): o for o in seeds if o["seed"] == med[f"{o['task']}|{o['system']}"]}
    seedv2 = {}
    for o in seeds:
        ni = len(real_invented(o["invented"]))
        seedv2.setdefault(({"S5c": "S5", "S7c": "S7"}[o["system"]]), {}).setdefault(o["task"], []).append(
            (round(0.8 * (o["rubric"] or 0) + 0.2 * o["v1"] - 0.02 * min(10, ni), 4), ni))
    head = json.load(open(os.path.join(W, "headline.json"))) if os.path.exists(os.path.join(W, "headline.json")) else []
    H = {(h["task"], h["system"]): h for h in head if h.get("rubric") is not None}
    fin = json.load(open(os.path.join(W, "dasein_final.json")))
    s6rep = json.load(open(os.path.join(W, "s6_replies.json"))) if os.path.exists(os.path.join(W, "s6_replies.json")) else {}

    texts = {}
    for t in tasks:
        for s in ("S1", "S2", "S3", "S4"):
            texts[(t["id"], s)] = base[f"{t['id']}|{s}"]
        texts[(t["id"], "S5")] = fair[(t["id"], "S5c")]["text"] if (t["id"], "S5c") in fair else base[f"{t['id']}|S5"]
        if (t["id"], "S7c") in fair:
            texts[(t["id"], "S7")] = fair[(t["id"], "S7c")]["text"]
        if t["id"] in fin:
            texts[(t["id"], "S6")] = fin[t["id"]]["best"]["text"]
        elif t["id"] == "replies" and s6rep:
            texts[(t["id"], "S6")] = s6rep["text"]
    cache_p = os.path.join(W, "reward_cache.json")
    cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
    todo = [k for k in texts if f"{k[0]}|{k[1]}|{hashlib.md5(texts[k].encode()).hexdigest()[:10]}" not in cache]
    with cf.ThreadPoolExecutor(8) as ex:
        for k, r in zip(todo, ex.map(lambda k: reward(T[k[0]], texts[k]), todo)):
            cache[f"{k[0]}|{k[1]}|{hashlib.md5(texts[k].encode()).hexdigest()[:10]}"] = r
    json.dump(cache, open(cache_p, "w"), ensure_ascii=False)
    R = {k: dict(cache[f"{k[0]}|{k[1]}|{hashlib.md5(texts[k].encode()).hexdigest()[:10]}"]) for k in texts}
    for r in R.values():
        r["invented_raw"] = r["invented"]
        r["invented"] = real_invented(r["invented"])
        r["v2"] = round(0.8 * (r["rubric"] or 0) + 0.2 * r["v1"] - 0.02 * min(10, len(r["invented"])), 4)

    # blind pairwise, Dasein vs context-matched baselines, both orders, two judges
    jobs = []
    for t in tasks:
        if (t["id"], "S6") not in texts:
            continue
        for opp in ("S5", "S7"):
            if (t["id"], opp) in texts:
                for j in ("claude", "astra"):
                    for order in (0, 1):
                        jobs.append((t["id"], opp, j, order))
    def judge(job):
        tid, opp, j, order = job
        a, b = texts[(tid, "S6")], texts[(tid, opp)]
        if order:
            a, b = b, a
        fn = (lambda q: E.claude_model(q, "sonnet")) if j == "claude" else E.gpt
        ans = fn(E.JUDGE.format(task=T[tid]["prompt"], a=a, b=b)).strip().upper()
        m = re.search(r"\b([AB])\b", ans)
        if not m:
            return None
        return (m.group(1) == "A") != bool(order)  # True = Dasein judged more human
    with cf.ThreadPoolExecutor(12) as ex:
        pw = [{"task": jb[0], "vs": jb[1], "judge": jb[2], "dasein_first": jb[3] == 0, "dasein_more_human": r}
              for jb, r in zip(jobs, ex.map(judge, jobs))]

    outputs = [{"task": k[0], "system": k[1], "text": texts[k], "score": R[k]["v2"], "spans": R[k]["spans"]}
               for k in texts if k[1] != "S7"]
    bench = []
    for s in [x["id"] for x in SYSTEMS] + ["S7"]:
        ks = [k for k in texts if k[1] == s]
        if not ks:
            continue
        nw = sum(len(texts[k].split()) for k in ks) or 1
        sv = seedv2.get(s)
        allv = [v for t in sv for v, _ in sv[t]] if sv else [R[k]["v2"] for k in ks]
        hq = [H[(k[0], s)]["rubric"] for k in ks if (k[0], s) in H]
        hinv = [len(real_invented(H[(k[0], s)]["invented"])) for k in ks if (k[0], s) in H]
        bench.append({"system": s, "tell_score": round(sum(allv) / len(allv), 4), "v2_range": [round(min(allv), 4), round(max(allv), 4)],
                      "n_runs": len(allv), "headline_qwen27b_rubric": round(sum(hq) / len(hq), 4) if hq else None,
                      "headline_qwen27b_invented": sum(hinv) if hinv else None, "headline_n": len(hq),
                      "rubric": round(sum((R[k]["rubric"] or 0) for k in ks) / len(ks), 4),
                      "dasein_v1": round(sum(R[k]["v1"] for k in ks) / len(ks), 4),
                      "grounding": round(1 - min(1, sum(len(R[k]["invented"]) for k in ks) / (len(ks) * 10)), 4),
                      "invented_facts": sum(len(R[k]["invented"]) for k in ks),
                      "slop_per_100w": round(100 * sum(sum(1 for sp in R[k]["spans"] if sp["kind"] == "slop") for k in ks) / nw, 2),
                      "n_tasks": len(ks)})
    disc = json.loads(subprocess.run(["ssh", "studio", "cat ~/tell/train/disc_report.json"], capture_output=True, text=True).stdout or "{}")
    pair_summary = {}
    for opp in ("S5", "S7"):
        v = [p["dasein_more_human"] for p in pw if p["vs"] == opp and p["dasein_more_human"] is not None]
        pair_summary[opp] = {"dasein_wins": sum(v), "n": len(v), "rate_ci95": wilson(sum(v), len(v))}
    res = {"version": 1, "mock": False, "systems": SYSTEMS, "extra_systems": [EXTRA],
           "tasks": [{k: t[k] for k in ("id", "label", "prompt", "human")} for t in tasks],
           "outputs": outputs, "extra_outputs": [{"task": k[0], "system": "S7", "text": texts[k], "score": R[k]["v2"]} for k in texts if k[1] == "S7"],
           "pipeline_version": "v2.4 (frozen 21:15 Taipei)", "dasein_runs_per_task": 1, "baseline_seeds": 3,
           "dasein_winner_writer": {tid: fin[tid]["best"].get("writer") for tid in fin if tid in T},
           "bench": bench, "pairwise": pw, "pairwise_summary": pair_summary,
           "reward_model": {"name": "dasein-score", "v2": "0.8 x mean(Claude-sonnet, Astra) 7-criterion rubric + 0.2 x v1 - 0.02/invented fact; gates: length +-25%, slop, public-safety",
                            "v1_discriminator": disc},
           "gbrain_call": subprocess.run(["ssh", "studio", "cat ~/tell-data/context/gbrain_call.log"], capture_output=True, text=True).stdout[:3000]}
    json.dump(res, open(os.path.join(W, "results.json"), "w"), ensure_ascii=False, indent=1)

    names = {x["id"]: x["name"] for x in SYSTEMS + [EXTRA]}
    md = ["| System | HEADLINE rubric (qwen3.8-27b, not used in selection) | headline invented | reward v2, selection judges (mean [range], runs) | rubric (Claude+Astra) | invented (Claude+Astra) | slop/100w |", "|---|---|---|---|---|---|---|"]
    for b in bench:
        hq = "-" if b["headline_qwen27b_rubric"] is None else f"{b['headline_qwen27b_rubric']:.3f} (n={b['headline_n']})"
        md.append(f"| {b['system']} {names[b['system']]} | {hq} | {'-' if b['headline_qwen27b_invented'] is None else b['headline_qwen27b_invented']} | {b['tell_score']:.3f} [{b['v2_range'][0]:.2f}-{b['v2_range'][1]:.2f}] ({b['n_runs']}) | {b['rubric']:.3f} | {b['invented_facts']} | {b['slop_per_100w']:.2f} |")
    md += ["", "Blind pairwise (which reads more like a real person; 2 judges x 2 orders per task):"]
    for opp, v in pair_summary.items():
        md.append(f"- Dasein vs {opp} {names[opp]}: {v['dasein_wins']}/{v['n']} (rate {v['rate_ci95'][0]}, 95% CI {v['rate_ci95'][1]}-{v['rate_ci95'][2]})")
    open(os.path.join(W, "results.md"), "w").write("\n".join(md) + "\n")

    d3 = ["# Dasein demo: 3 tasks", "", "Each output shows reward v2 (rubric by Claude-sonnet + Astra, 0.8) + dasein-score v1 (0.2).", ""]
    for tid in ("day-blog", "recent-essay", "followup"):
        d3 += [f"## {T[tid]['label']}: \"{T[tid]['prompt']}\"", ""]
        for s in ("S1", "S2", "S5", "S7", "S6"):
            if (tid, s) in texts:
                r = R[(tid, s)]
                d3 += [f"### {s} {names[s]}: v2 {r['v2']:.3f}, rubric {r['rubric']}, invented {len(r['invented'])}, {len(texts[(tid, s)].split())} words", "", texts[(tid, s)], ""]
    d3 += ["## Bench", ""] + md
    open(os.path.join(W, "demo3.md"), "w").write("\n".join(d3) + "\n")
    subprocess.run(["ssh", "studio", "mkdir -p ~/tell-data/eval"])
    for f in ("results.json", "results.md", "demo3.md"):
        subprocess.run(["scp", "-q", os.path.join(W, f), f"studio:tell-data/eval/{f}"], check=True)
    print("\n".join(md))


if __name__ == "__main__":
    main()
