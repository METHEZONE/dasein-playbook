"""Context-matched baselines for the demo tasks: Claude-sonnet and Astra get the SAME context, length target and
content constraints (facts only, public-safe) as Dasein, with a plain prompt (no Dasein writing method).
Scored with the same reward v2 (rubric x2 judges + dasein-score v1).  -> _eval/fair_baselines.json"""
import concurrent.futures as cf, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval as E
import dasein_final as D

CONSTRAINTS = ("Only use facts that are in the context. This will be public: leave out fundraising plans, the US move "
               "timeline, Discord/influencer launch plans, infra and ops details, money. Plain text only, no markdown, no emoji.")


def prompt(task):
    return (f"My context (real notes, timeline, my own words):\n{task['context']}\n\nTask: {task['prompt']}\n"
            f"Length: about {D.TARGET.get(task['id'], 150)} words. Write it as me, first person. {CONSTRAINTS}")


def one(task, sysid):
    p = prompt(task)
    text = E.clean(E.claude_model(p, "sonnet") if sysid == "S5c" else E.gpt(p))
    v1 = E.score(text, task["context"], judge=False)
    r = D.rubric(task["prompt"], text, task["context"])
    v2 = round(0.8 * (r["rubric"] or 0) + 0.2 * v1["score"] - 0.02 * min(10, len(r["invented"])), 4)
    return {"task": task["id"], "system": sysid, "text": text, "words": len(text.split()), "v1": v1["score"],
            "p_human": v1["parts"]["p_human"], "slop_per_100w": v1["parts"]["slop_per_100w"], **r, "v2": v2}


def main():
    today, recent = E.load_inputs()
    tasks, _ = E.build_tasks(today, recent)
    tasks = [t for t in tasks if t["id"] in ("day-blog", "recent-essay", "followup")]
    seeds = int(os.environ.get("SEEDS", "1"))
    with cf.ThreadPoolExecutor(18) as ex:
        jobs = [(t, s, k) for t in tasks for s in ("S5c", "S7c") for k in range(seeds)]
        out = list(ex.map(lambda tsk: {**one(tsk[0], tsk[1]), "seed": tsk[2]}, jobs))
    json.dump(out, open(os.path.join(E.W, os.environ.get("OUT", "fair_baselines.json")), "w"), ensure_ascii=False, indent=1)
    for o in out:
        print(f"\n=== {o['task']} {o['system']} | v2 {o['v2']} rubric {o['rubric']} v1 {o['v1']} words {o['words']} invented {len(o['invented'])}\n{o['text']}")


if __name__ == "__main__":
    main()
