"""Dasein eval harness. Runs on the MacBook (codex = ChatGPT subscription, claude-sub = Claude subscription),
generates S6 + scores on the Studio over ssh. Writes ~/tell-data/eval/results.json (+ results.md) on the Studio.

  python3 eval.py [--adapter ~/tell/adapters/rft1] [--skip-gen]
"""
import argparse, concurrent.futures as cf, json, os, random, re, shlex, subprocess, tempfile, time

HOME = os.path.expanduser("~")
W = os.path.join(HOME, "Projects/tell/train/_eval")  # local work dir (gitignored)
os.makedirs(W, exist_ok=True)
CODEX = [os.path.join(HOME, ".local/bin/codex"), "exec", "-m", "gpt-6-astra", "--skip-git-repo-check"]
CLAUDE = [os.path.join(HOME, ".local/bin/claude-sub"), "-p", "--setting-sources", ""]
# Baselines must not see Min's global memory (CLAUDE.md / AGENTS.md / codex memories): isolated homes + cwd.
ISO = os.environ.get("EVAL_ISO", "/private/tmp/claude-501/dasein-iso")  # OUTSIDE any git repo
os.makedirs(os.path.join(ISO, "codexhome"), exist_ok=True)
if not os.path.exists(os.path.join(ISO, "codexhome", "auth.json")):
    os.symlink(os.path.join(HOME, ".codex/auth.json"), os.path.join(ISO, "codexhome", "auth.json"))
CODEX_ENV = {**os.environ, "CODEX_HOME": os.path.join(ISO, "codexhome")}


def sh_studio(cmd, inp=None, timeout=900):
    return subprocess.run(["ssh", "studio", cmd], input=inp, capture_output=True, text=True, timeout=timeout).stdout


def scp_from(remote, local):
    subprocess.run(["scp", "-q", f"studio:{remote}", local], check=True)


def clean(t):
    t = re.sub(r"[*#`]+", "", t or "")
    t = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", t)
    return t.strip()


def gpt(prompt):
    d = tempfile.mkdtemp(dir=ISO)
    f = os.path.join(d, "out.txt")
    subprocess.run(CODEX + ["--output-last-message", f, prompt], cwd=d, env=CODEX_ENV, stdin=subprocess.DEVNULL,
                   capture_output=True, text=True, timeout=600)
    return clean(open(f).read()) if os.path.exists(f) else ""


def claude_model(prompt, model):
    return subprocess.run(CLAUDE + ["--model", model], input=prompt, capture_output=True, text=True, timeout=600, cwd=ISO).stdout


def claude(prompt):
    return clean(subprocess.run(CLAUDE, input=prompt, capture_output=True, text=True, timeout=600, cwd=ISO).stdout)


# ---------------------------------------------------------------- tasks
def load_inputs():
    for f in ["context/today_2026-11-11.json", "context/recent_days.json", "context/fewshot.json"]:
        scp_from(f"~/tell-data/{f}", os.path.join(W, os.path.basename(f)))
    try:
        scp_from("~/tell-data/context/followup_person.txt", os.path.join(W, "followup_person.txt"))
    except Exception:
        open(os.path.join(W, "followup_person.txt"), "w").write("")
    scp_from("~/tell/sft_fallback/valid.jsonl", os.path.join(W, "valid.jsonl"))
    scp_from("~/tell/sft_fallback/train.jsonl", os.path.join(W, "train.jsonl"))
    today = json.load(open(os.path.join(W, "today_2026-11-11.json")))
    recent = json.load(open(os.path.join(W, "recent_days.json")))
    return today, recent


def ctx_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=0)


def said_lines(obj):
    out = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "min_said" and isinstance(v, str):
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


PRIVATE = re.compile(r"influencer|angel|round\b|discord|supabase|slack|million views|1M\+?|\bSF\b|san francisco|january|100-200k|"
                     r"valuation|stealth|fundrais|investor|lawyer|legal|payment|flight|\bfund\b", re.I)


def public(o):
    """Public-safe context for ALL systems: drop events/opinions that touch internal strategy, money or ops."""
    if isinstance(o, dict):
        return {k: public(v) for k, v in o.items()}
    if isinstance(o, list):  # drop leaf items (events, opinions), never whole containers like a day
        container = lambda v: isinstance(v, dict) and any(isinstance(x, list) and x and isinstance(x[0], dict) for x in v.values())
        keep = lambda v: container(v) or not PRIVATE.search(json.dumps(v, ensure_ascii=False))
        return [public(v) for v in o if keep(v)]
    return o


def build_tasks(today, recent):
    today, recent = public(today), public(recent)
    rows = [json.loads(l)["messages"] for l in open(os.path.join(W, "valid.jsonl"))]
    reps = [m for m in rows if m[1]["content"].startswith("Task: Someone just said")
            and 10 <= len(m[2]["content"].split()) <= 45 and len(m[1]["content"].split()) >= 14]
    random.seed(7)
    reps = random.sample(reps, 3)
    msgs = [re.search(r'said to you: "(.*)" Reply\.', m[1]["content"], re.S).group(1) for m in reps]
    shots = json.load(open(os.path.join(W, "fewshot.json")))[:10]
    ops = today.get("spiky_opinions") or []
    opinion = ops[1] if len(ops) > 1 else "half-way launches don't work"
    person = open(os.path.join(W, "followup_person.txt")).read().strip()
    met = [e for e in today.get("timeline", []) if "c0mpiled" in e.get("place", "")]
    tasks = [
        {"id": "day-blog", "label": "Day blog", "prompt": "Write a short blog post about my day today.",
         "context": ctx_text(today), "human": " ".join(said_lines(today))},
        {"id": "recent-essay", "label": "Last few days", "prompt": "Write a 300-word essay about my last few days.",
         "context": ctx_text(recent), "human": " ".join(said_lines(recent))},
        {"id": "followup", "label": "Follow-up message", "prompt": "Write a follow-up message to someone I met today.",
         "context": (("Person (from gbrain):\n" + person + "\n\n") if person else "") + "Today:\n" + ctx_text(met or today),
         "human": " ".join(said_lines(met or today))},
        {"id": "opinion", "label": "Spiky opinion", "prompt": f"Write a short blog post (about 200 words) with my take on this: {opinion}",
         "context": ctx_text({"my_opinions_today": ops, "timeline": today.get("timeline", [])}), "human": opinion},
        {"id": "replies", "label": "3 replies", "prompt": "Write my reply to each of these 3 messages. One short reply each, numbered 1-3.\n"
         + "\n".join(f'{i+1}. "{m}"' for i, m in enumerate(msgs)), "context": "", "messages": msgs,
         "human": "\n".join(f"{i+1}. {m[2]['content']}" for i, m in enumerate(reps))},
    ]
    return tasks, shots


STYLE = ("Write like Minsung Park. "
         "Match his voice from these real lines of his:\n{shots}\n\n")
SYSTEMS = [
    {"id": "S1", "name": "Vanilla GPT", "vendor": "openai", "desc": "gpt-6-astra, task prompt only"},
    {"id": "S2", "name": "Vanilla Claude", "vendor": "anthropic", "desc": "Claude, task prompt only"},
    {"id": "S3", "name": "GPT + style prompt", "vendor": "openai", "desc": "gpt-6-astra, 'write like Minsung' + 10 real lines"},
    {"id": "S4", "name": "Claude + style prompt", "vendor": "anthropic", "desc": "Claude, 'write like Minsung' + 10 real lines"},
    {"id": "S5", "name": "Claude + full context", "vendor": "anthropic", "desc": "Claude, style prompt + 10 real lines + full retrieved context"},
    {"id": "S6", "name": "Dasein", "vendor": "tell", "desc": "open models only: Qwen3-8B LoRA post-trained on Min + large open model, real context, best-of-n reranked by dasein-score"},
]
PLAIN = "\n\nPlain text only: no markdown, no headings, no emoji."


def baseline_prompt(sysid, task, shots):
    p = task["prompt"] + PLAIN
    if sysid in ("S3", "S4", "S5"):
        p = STYLE.format(shots="\n".join(f"- {s}" for s in shots)) + p
    if sysid == "S5" and task["context"]:
        p = f"My context (real notes, timeline, messages):\n{task['context']}\n\n" + p
    return p


GMI_MODEL = os.environ.get("GMI_MODEL", "")
S6_LOG = []


def run_s6(task, adapter, n=8):
    def best(prompt, ctx):
        sh_studio(f"mkdir -p ~/tell/tmp && cat > ~/tell/tmp/p.txt", prompt)
        sh_studio(f"cat > ~/tell/tmp/c.txt", ctx)
        out = sh_studio(f"cd ~/tell/train && ~/voice-lora/venv/bin/python gen.py best --adapter {adapter} "
                        f"--prompt-file ~/tell/tmp/p.txt --context-file ~/tell/tmp/c.txt --n {n} --max-tokens 480"
                        + (f" --gmi-model {GMI_MODEL}" if GMI_MODEL else "") + " 2>/dev/null", timeout=1800)
        r = json.loads(out.strip().splitlines()[-1])
        S6_LOG.append({"task": task["id"], "prompt": prompt, "candidates": [{k: c[k] for k in ("source", "score", "text")} for c in r["candidates"]]})
        return r["best"]["text"]
    if task["id"] == "replies":  # trained on single replies: one best-of-n each
        outs = [best('Someone just said to you: "' + m + '" Reply.', "") for m in task["messages"]]
        return "\n".join(f"{i+1}. {o}" for i, o in enumerate(outs))
    return best(task["prompt"], task["context"])


def score(text, context, judge=True):
    out = sh_studio("curl -s -XPOST 127.0.0.1:8790/score --data-binary @-", json.dumps({"text": text, "context": context, "judge": judge}), timeout=400)
    return json.loads(out)


JUDGE = ("Two texts were written for the same task. One or both may be written by AI. "
         "Which one reads more like a real person actually wrote it? Answer with exactly one letter: A or B.\n\n"
         "TASK: {task}\n\nTEXT A:\n{a}\n\nTEXT B:\n{b}\n")


def pairwise(task, ta, tb, judge_fn, seed):
    r = random.Random(seed)
    flip = r.random() < 0.5
    a, b = (tb, ta) if flip else (ta, tb)
    ans = judge_fn(JUDGE.format(task=task, a=a, b=b)).strip().upper()
    m = re.search(r"\b([AB])\b", ans)
    if not m:
        return None
    first_wins = (m.group(1) == "A")
    return (not first_wins) if flip else first_wins  # True = ta judged more human


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="~/tell/adapters/sft1")
    ap.add_argument("--skip-gen", action="store_true", help="reuse _eval/gen.json")
    ap.add_argument("--baselines-only", action="store_true")
    a = ap.parse_args()
    today, recent = load_inputs()
    tasks, shots = build_tasks(today, recent)
    gp = os.path.join(W, os.environ.get("GEN", "gen.json"))
    want = os.environ.get("SYS", "S1,S2,S3,S4,S5,S6").split(",")
    gen = json.load(open(gp)) if (a.skip_gen and os.path.exists(gp)) else {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(10) as ex:
        futs = {}
        for t in tasks:
            for s in [x for x in ["S1", "S2", "S3", "S4", "S5"] if x in want]:
                k = f"{t['id']}|{s}"
                if k not in gen:
                    fn = gpt if s in ("S1", "S3") else claude
                    futs[ex.submit(fn, baseline_prompt(s, t, shots))] = k
        for t in ([] if "S6" not in want else tasks):  # S6 sequential on the Studio GPU, while baselines run
            k = f"{t['id']}|S6"
            if k not in gen:
                gen[k] = run_s6(t, a.adapter)
                print("S6", t["id"], f"{time.time()-t0:.0f}s", flush=True)
        for f in cf.as_completed(futs):
            gen[futs[f]] = f.result()
            print("done", futs[f], f"{time.time()-t0:.0f}s", flush=True)
    json.dump(gen, open(gp, "w"), ensure_ascii=False, indent=1)
    if S6_LOG:
        json.dump(S6_LOG, open(os.path.join(W, "s6_candidates.json"), "w"), ensure_ascii=False, indent=1)
    if a.baselines_only:
        return

    outputs = []
    with cf.ThreadPoolExecutor(4) as ex:
        tmap = {t["id"]: t for t in tasks}
        futs = {ex.submit(score, txt, tmap[k.split("|")[0]]["context"]): k for k, txt in gen.items()}
        for f in cf.as_completed(futs):
            tid, sid = futs[f].split("|")
            r = f.result()
            outputs.append({"task": tid, "system": sid, "text": gen[futs[f]], "score": r["score"], "spans": r["spans"], "parts": r["parts"]})
    outputs.sort(key=lambda o: (o["task"], o["system"]))
    # human reference scored too (not a system; for the table)
    human_scores = {t["id"]: score(t["human"], t["context"]) for t in tasks if t["human"]}

    # blind pairwise: S6 vs every other system, two judges
    jobs = [(t, s, j) for t in tasks for s in ["S1", "S2", "S3", "S4", "S5"] for j in ("claude", "astra")]
    pw = []
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(pairwise, t["prompt"], gen[f"{t['id']}|S6"], gen[f"{t['id']}|{s}"],
                          claude if j == "claude" else gpt, hash((t["id"], s, j)) & 0xffff): (t["id"], s, j) for t, s, j in jobs}
        for f in cf.as_completed(futs):
            tid, s, j = futs[f]
            pw.append({"task": tid, "vs": s, "judge": j, "s6_more_human": f.result()})

    bench = []
    for s in SYSTEMS:
        os_ = [o for o in outputs if o["system"] == s["id"]]
        nw = sum(len(o["text"].split()) for o in os_) or 1
        nslop = sum(sum(1 for sp in o["spans"] if sp["kind"] == "slop") for o in os_)
        bench.append({"system": s["id"], "tell_score": round(sum(o["score"] for o in os_) / len(os_), 4),
                      "grounding": round(sum(o["parts"]["grounding"] for o in os_) / len(os_), 4),
                      "p_human": round(sum(o["parts"]["p_human"] for o in os_) / len(os_), 4),
                      "slop_per_100w": round(100 * nslop / nw, 2)})
    res = {"version": 1, "mock": False, "systems": SYSTEMS,
           "tasks": [{k: t[k] for k in ("id", "label", "prompt", "human")} for t in tasks],
           "outputs": [{k: o[k] for k in ("task", "system", "text", "score", "spans")} for o in outputs],
           "bench": bench, "pairwise": pw,
           "human_reference": {k: {"score": v["score"], **{x: v["parts"][x] for x in ("p_human", "grounding", "slop_per_100w")}} for k, v in human_scores.items()},
           "contexts": {t["id"]: t["context"] for t in tasks}}
    json.dump(res, open(os.path.join(W, "results.json"), "w"), ensure_ascii=False, indent=1)

    md = ["| System | dasein-score | p_human | grounding | slop/100w | S6 judged more human (vs this) |", "|---|---|---|---|---|---|"]
    for b in bench:
        v = [p["s6_more_human"] for p in pw if p["vs"] == b["system"] and p["s6_more_human"] is not None]
        md.append(f"| {b['system']} {next(s['name'] for s in SYSTEMS if s['id']==b['system'])} | {b['tell_score']:.3f} | {b['p_human']:.3f} | "
                  f"{b['grounding']:.3f} | {b['slop_per_100w']:.2f} | {'-' if b['system']=='S6' else f'{sum(v)}/{len(v)}'} |")
    md.append("")
    md.append("Human reference (Min's real words): " + ", ".join(f"{k} {v['score']:.3f}" for k, v in res["human_reference"].items()))
    open(os.path.join(W, "results.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    names = {x["id"]: x["name"] for x in SYSTEMS}
    d3 = ["# Dasein demo: 3 tasks", "",
          "Systems: S1 vanilla GPT (gpt-6-astra), S2 vanilla Claude, S6 Dasein (open models only, real context, best-of-n by dasein-score).",
          "Baselines ran with Min's global memory files stripped (isolated CODEX_HOME / --setting-sources \"\", cwd outside any repo).", ""]
    for tid in ("day-blog", "recent-essay", "followup"):
        t = next(x for x in tasks if x["id"] == tid)
        d3 += [f"## {t['label']}: \"{t['prompt']}\"", ""]
        for sid in ("S1", "S2", "S6"):
            o = next(x for x in outputs if x["task"] == tid and x["system"] == sid)
            v = [p["s6_more_human"] for p in pw if p["task"] == tid and p["vs"] == sid and p["s6_more_human"] is not None]
            d3 += [f"### {sid} {names[sid]}: dasein-score {o['score']:.3f} (p_human {o['parts']['p_human']:.2f}, grounding {o['parts']['grounding']:.2f}, slop/100w {o['parts']['slop_per_100w']:.1f})"
                   + (f", blind judges picked Dasein as more human {sum(v)}/{len(v)}" if sid != "S6" else ""), "", o["text"], ""]
    d3 += ["## Full bench (5 tasks, S1-S6)", ""] + md
    open(os.path.join(W, "demo3.md"), "w").write("\n".join(d3) + "\n")
    sh_studio("mkdir -p ~/tell-data/eval")
    subprocess.run(["scp", "-q", os.path.join(W, "demo3.md"), "studio:tell-data/eval/demo3.md"], check=True)
    for f in ("results.json", "results.md", "gen.json") + (("s6_candidates.json",) if S6_LOG else ()):
        subprocess.run(["scp", "-q", os.path.join(W, f), f"studio:tell-data/eval/{f}"], check=True)


if __name__ == "__main__":
    main()
