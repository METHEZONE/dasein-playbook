"""Dasein-final v2 (demo writer): open model (DeepSeek-V3 on GMI) plans -> writes -> gates -> rubric rerank.

  plan:   find the day's real question / irony + the 1-2 events that bear on it (4 plans)
  write:  2 drafts per plan in Min's voice, interpretation + restraint, target length (8 candidates)
  gate:   length within +-25% of target, slop/100w <= 1.5, no invented specifics (heuristic, then judge)
  rerank: reward v2 = mean of Claude-sonnet and Astra 7-criterion rubric (0..1) x 0.8 + dasein-score v1 x 0.2

  python3 dasein_final.py [task ids...]   -> _eval/dasein_final.json (+ prints winners)
"""
import concurrent.futures as cf, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as E  # reuses tasks, isolated gpt()/claude(), score()

TARGET = {"day-blog": 150, "recent-essay": 300, "followup": 90, "opinion": 200}

RULES = """How real people write (follow all of these):
1. Meaning over inventory. Pick one or two moments and say what they meant. Most of the day is left out on purpose.
2. A throughline: one question, tension or irony that the piece is really about.
3. Restraint. Never name an emotion (no "inspiring", "grateful", "excited", "proud"). Let a concrete detail carry it.
4. Self-awareness and dry humor about your own situation.
5. Stance. Say what you actually think, and leave some things unsaid.
6. End on a feeling or an open question, never a summary or a lesson.
7. Only use facts that are in the context, exactly as stated: who did what, in what order, which day, which numbers.
   Never merge separate events, never add a reaction or a quote that isn't there. If unsure, leave it out.
   Never claim a conversation that the context doesn't show.
8. This will be public. Leave out internal strategy and ops: fundraising plans, the US/SF move timeline, Discord or
   influencer launch plans, infra/Supabase/Slack/agent-ops details, money. Keep to the human experience of the day.
   Never claim someone said something unless the context quotes or records it.
Voice: first person, plain spoken English of a Korean founder who thinks fast. Short sentences, some fragments, no polish.
Banned: delve, journey, testament, tapestry, landscape, game-changer, "not just X but Y", "at the end of the day", em dashes, hashtags, emoji, markdown, headings, a title line."""


def gmi(messages, temp=0.9, max_tokens=900):
    out = subprocess.run(["ssh", "studio", "~/voice-lora/venv/bin/python ~/tell/train/gmi.py"],
                         input=json.dumps({"messages": messages, "temperature": temp, "max_tokens": max_tokens}),
                         capture_output=True, text=True, timeout=300)
    return out.stdout.strip()


def voice_block(shots, task):
    own = re.findall(r'"min_said": "([^"]+)"', task["context"])
    return ("Real lines of mine (match this voice, do not quote them unless they fit):\n" + "\n".join(f"- {s}" for s in shots)
            + ("\n\nThings I actually said in this period:\n" + "\n".join(f"- {s}" for s in own[:20]) if own else ""))


def plans(task, n=4):
    p = (f"Context about my life (real notes, timeline, my words):\n{task['context']}\n\nTask I will write next: {task['prompt']}\n\n"
         "Before writing, find the REAL QUESTION or irony underneath this material, the thing I actually care about. "
         "Then pick the one or two events that bear on it, and an ending that lands on a feeling or open question. "
         'Return ONLY JSON: {"question": "<one sentence>", "events": ["<event 1>", "<event 2>"], "ending": "<one line idea>"}')
    def one(i):
        t = gmi([{"role": "user", "content": p}], temp=1.0, max_tokens=400)
        m = re.search(r"\{.*\}", t, re.S)
        try:
            return json.loads(m.group()) if m else None
        except Exception:
            return None
    with cf.ThreadPoolExecutor(n) as ex:
        return [x for x in ex.map(one, range(n)) if x]


TASK_RULES = {
    "day-blog": "Exactly ONE throughline. Use at most TWO events from the day; do not list or recap the rest. End on a line you feel, not a summary.",
    "recent-essay": "Exactly ONE throughline across the days. Use at most THREE moments; leave the rest out. Zero invented details. End on a felt line or open question.",
}
WRITERS = ("deepseek", "astra", "claude")


def draft(task, plan, shots, temp, writer="deepseek"):
    tw = TARGET.get(task["id"], 150)
    sysm = "You are Minsung Park, writing as yourself.\n\n" + RULES + "\n\n" + voice_block(shots, task)
    user = (f"My context:\n{task['context']}\n\nTask: {task['prompt']}\nLength: about {tw} words.\n\n"
            f"What this piece is really about: {plan['question']}\nBuild it around: {'; '.join(plan.get('events', []))}\n"
            f"Ending idea: {plan.get('ending', '')}\n\nWrite it now. Plain text only.")
    user += "\n" + TASK_RULES.get(task["id"], "")
    if writer == "deepseek":
        t = gmi([{"role": "system", "content": sysm}, {"role": "user", "content": user}], temp=temp, max_tokens=900)
    elif writer == "astra":
        t = E.gpt(sysm + "\n\n" + user)
    else:
        t = E.claude_model(sysm + "\n\n" + user, "sonnet")
    t = E.clean(t)
    t = re.sub(r"(?<=\w)[ \t]*[—–][ \t]*(?=\w)", ", ", t)
    t = re.sub(r"(?<=\w) - (?=\w)", ", ", t)
    t = re.sub(r"[ \t]+[-—–][ \t]*$", ",", t, flags=re.M)
    t = re.sub(r"^[ \t]*[-—–][ \t]*", "", t, flags=re.M)
    t = re.sub(r"[—–]", ",", t)
    return t


RUBRIC = """You are grading whether a short piece reads like a real person wrote it (not a log, not an AI).
Score each criterion 1-5:
1 meaning: picks 1-2 moments and says what they meant (vs listing events)
2 throughline: a real question/tension/irony holds it together
3 restraint: emotion implied through specifics, never named; no slop phrases
4 selection: most material left out on purpose
5 self_awareness: irony or humor about the writer's own situation
6 stance: a clear point of view, with things left unsaid
7 ending: lands on a feeling or open question, not a summary
Also list invented_facts: specific names/numbers/events in the TEXT that are NOT supported by the CONTEXT (empty list if none; if no context is given, list nothing).
Return ONLY JSON: {{"meaning":n,"throughline":n,"restraint":n,"selection":n,"self_awareness":n,"stance":n,"ending":n,"invented_facts":[...]}}

TASK: {task}

CONTEXT:
{context}

TEXT:
{text}
"""
CRIT = ["meaning", "throughline", "restraint", "selection", "self_awareness", "stance", "ending"]


def rubric(task, text, context):
    p = RUBRIC.format(task=task, context=context[:9000] or "(none)", text=text)
    res = {}
    for name, fn in (("claude", lambda q: E.claude_model(q, "sonnet")), ("astra", E.gpt)):
        try:
            j = json.loads(re.search(r"\{.*\}", fn(p), re.S).group())
            res[name] = {"score": sum(float(j[c]) for c in CRIT) / (5 * len(CRIT)), "invented": j.get("invented_facts", []),
                         **{c: j[c] for c in CRIT}}
        except Exception as e:
            res[name] = {"error": str(e)[:100]}
    ok = [v["score"] for v in res.values() if "score" in v]
    inv = sorted({x for v in res.values() for x in v.get("invented", []) if isinstance(x, str)})
    return {"rubric": round(sum(ok) / len(ok), 4) if ok else None, "invented": inv, "judges": res}


PRIVATE = re.compile(r"influencer|angel|round\b|discord|supabase|slack|million views|1M|\bSF\b|san francisco|january|100-200k|"
                     r"valuation|stealth|fundrais|investor|lawyer|legal|payment|flight", re.I)


def run_task(task, shots):
    tw = TARGET.get(task["id"], 150)
    ps = plans(task)
    jobs = [(p, w) for p in ps[:4] for w in WRITERS]
    with cf.ThreadPoolExecutor(12) as ex:
        texts = list(ex.map(lambda pw: draft(task, pw[0], shots, 0.8, pw[1]), jobs))
    cands = []
    for (p, writer), t in zip(jobs, texts):
        if not t:
            continue
        s1 = E.score(t, task["context"], judge=False)
        n = len(t.split())
        cands.append({"text": t, "plan": p, "writer": writer, "words": n, "v1": s1["score"], "slop_per_100w": s1["parts"]["slop_per_100w"],
                      "p_human": s1["parts"]["p_human"], "grounding_h": s1["parts"]["grounding"],
                      "gate_len": 0.75 * tw <= n <= 1.25 * tw, "gate_slop": s1["parts"]["slop_per_100w"] <= 1.5,
                      "gate_private": not PRIVATE.search(t)})
    passed = [c for c in cands if c["gate_len"] and c["gate_slop"] and c["gate_private"]] or [c for c in cands if c["gate_private"]] or cands
    passed.sort(key=lambda c: -c["v1"])
    finalists = passed[:6]
    with cf.ThreadPoolExecutor(6) as ex:
        rubs = list(ex.map(lambda c: rubric(task["prompt"], c["text"], task["context"]), finalists))
    for c, r in zip(finalists, rubs):
        c.update(r)
        c["v2"] = round(0.8 * (r["rubric"] or 0) + 0.2 * c["v1"] - 0.02 * min(10, len(r["invented"])), 4)
        c["gate_grounded"] = not r["invented"]
    clean_ = [c for c in finalists if c["gate_grounded"]]  # no fallback: fact-failing drafts go to revise.py, never straight to best
    best = max(clean_, key=lambda c: c["v2"]) if clean_ else {"text": "", "v2": -1, "v1": 0, "words": 0, "invented": ["no grounded finalist"]}
    return {"task": task["id"], "prompt": task["prompt"], "target_words": tw, "plans": ps, "candidates": cands, "best": best}


def main():
    today, recent = E.load_inputs()
    tasks, shots = E.build_tasks(today, recent)
    want = sys.argv[1:] or ["day-blog", "recent-essay", "followup"]
    tasks = [t for t in tasks if t["id"] in want]
    with cf.ThreadPoolExecutor(len(tasks)) as ex:
        out = list(ex.map(lambda t: run_task(t, shots), tasks))
    path = os.path.join(E.W, "dasein_final.json")
    prev = json.load(open(path)) if os.path.exists(path) else {}
    prev.update({o["task"]: o for o in out})
    json.dump(prev, open(path, "w"), ensure_ascii=False, indent=1)
    for o in out:
        b = o["best"]
        print(f"\n=== {o['task']} | v2 {b['v2']} rubric {b.get('rubric')} v1 {b['v1']} words {b['words']} invented {b.get('invented')}\n{b['text']}")


if __name__ == "__main__":
    main()
