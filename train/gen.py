"""Generation + best-of-n with tell_score, and rejection-sampling FT data builder.

  python gen.py rft  --adapter A --data D --out O [--n 8 --limit 40]   # build RFT winners set from D/train.jsonl prompts
  python gen.py best --adapter A --prompt-file P [--context-file C --n 8]  # S6: print JSON {best, candidates}
"""
import argparse, json, os, random, sys, time

import mlx.core as mx
from mlx_lm import load
from mlx_lm.generate import batch_generate
from mlx_lm.sample_utils import make_sampler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tell_score import tell_score

BASE = os.path.expanduser(os.environ.get("TELL_BASE", "~/work/voice-state/models/qwen3-8b-base-4bit"))
SYSTEM = "You are Minsung Park. Write exactly like you, in your own voice. Only state facts that appear in your context."


def build_messages(task, context=""):
    user = (f"My context (real notes, timeline, messages):\n{context}\n\n" if context else "") + f"Task: {task}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _ids(tok, messages):
    # Training renders assistant turns as "<think>\n\n</think>\n\n<text>"; without enable_thinking=False the
    # generation prompt stops before that block and the model's first token is garbage (stray CJK/Thai tokens).
    return tok.apply_chat_template(messages, add_generation_prompt=True, enable_thinking=False)


def sample(model, tok, messages, n=8, max_tokens=400, temp=0.9):
    ids = _ids(tok, messages)
    r = batch_generate(model, tok, [ids] * n, max_tokens=max_tokens, sampler=make_sampler(temp=temp, top_p=0.95))
    # the chat turn ends at <|im_end|>, which is not in the base model's eos set: cut there (else it rambles on)
    return [t.split("<|im_end|>")[0].split("<|endoftext|>")[0].strip() for t in r.texts]


GMI_BASE = os.environ.get("GMI_BASE", "https://api.gmi-serving.com/v1")


def gmi_sample(model_id, task, context, k=4, max_tokens=700):
    """Large open model on GMI Cloud (OpenAI-compatible). Key read from ~/.gmi_key, never printed."""
    import concurrent.futures as cf, urllib.request
    key = open(os.path.expanduser("~/.gmi_key")).read().strip()
    shots = json.load(open(os.path.expanduser("~/tell-data/context/fewshot.json")))[:10]
    sys_p = (SYSTEM + " These are real lines of yours, match this voice exactly (blunt, spoken, short sentences, no polish):\n"
             + "\n".join("- " + x for x in shots) + "\nPlain text only. No markdown, no emoji, no headings.")
    msgs = [{"role": "system", "content": sys_p}, build_messages(task, context)[1]]
    def one(i):
        body = json.dumps({"model": model_id, "messages": msgs, "max_tokens": max_tokens, "temperature": 0.9, "top_p": 0.95}).encode()
        req = urllib.request.Request(GMI_BASE + "/chat/completions", body, {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "curl/8.7.1"})
        try:
            t = json.loads(urllib.request.urlopen(req, timeout=120).read())["choices"][0]["message"]["content"]
            return __import__("re").sub(r"<think>.*?</think>", "", t, flags=__import__("re").S).strip()
        except Exception as e:
            print("gmi error", str(e)[:120], file=sys.stderr)
            return ""
    with cf.ThreadPoolExecutor(k) as ex:
        return list(ex.map(one, range(k)))


def target_words(task):
    import re
    m = re.search(r"(\d{2,4})[- ]word|~?(\d{2,4}) words", task)
    if m:
        return int(m.group(1) or m.group(2))
    t = task.lower()
    if "short blog" in t:
        return 220
    if "follow-up message" in t or "message" in t:
        return 90
    return 0


def best_of(model, tok, messages, context="", n=8, max_tokens=400, extra=(), task=""):
    cands = sample(model, tok, messages, n, max_tokens, temp=0.7) if n else []
    cands = [("lora", c) for c in cands] + [("gmi", c) for c in extra]
    scored = [{"text": c, "source": src, "words": len(c.split()), **tell_score(c, context)} for src, c in cands if c]
    tw = target_words(task)
    if tw:  # length prior (hard filter): best-of-n by a discriminator otherwise rewards short, blunt text
        ok = [d for d in scored if 0.75 * tw <= d["words"] <= 1.25 * tw]
        for d in scored:
            d["in_length"] = d in ok
        scored = ok + [d for d in scored if d not in ok] if ok else scored
        return sorted(ok, key=lambda d: -d["score"]) + sorted([d for d in scored if not d["in_length"]], key=lambda d: -d["score"]) if ok else sorted(scored, key=lambda d: -d["score"])
    return sorted(scored, key=lambda d: -d["score"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--adapter")
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--prompt-file")
    ap.add_argument("--context-file")
    ap.add_argument("--gmi-model", default="")
    ap.add_argument("--gmi-k", type=int, default=4)
    a = ap.parse_args()
    model, tok = load(BASE, adapter_path=a.adapter)
    try:
        tok.add_eos_token("<|im_end|>")
    except Exception:
        pass

    if a.cmd == "best":
        task = open(a.prompt_file).read().strip()
        ctx = open(a.context_file).read().strip() if a.context_file else ""
        extra = gmi_sample(a.gmi_model, task, ctx, a.gmi_k) if a.gmi_model else []
        res = best_of(model, tok, build_messages(task, ctx), ctx, a.n, a.max_tokens, extra, task)
        print(json.dumps({"best": res[0], "candidates": res}, ensure_ascii=False))
        return

    if a.cmd == "heldout":  # before/after number: mean dasein-score of fresh samples on held-out prompts
        rows = [json.loads(l) for l in open(os.path.join(a.data, "valid.jsonl"))]
        random.seed(5)
        random.shuffle(rows)
        mono = [r for r in rows if "topic:" in r["messages"][1]["content"] or "honest take" in r["messages"][1]["content"]]
        rest = [r for r in rows if r not in mono]
        rows = (mono[: a.limit // 2] + rest)[: a.limit]
        sc, ph, t0 = [], [], time.time()
        for r in rows:
            msgs = [m for m in r["messages"] if m["role"] != "assistant"]
            for c in sample(model, tok, msgs, a.n, a.max_tokens):
                d = tell_score(c, msgs[1]["content"]) if c else {"score": 0, "parts": {"p_human": 0}}
                sc.append(d["score"]); ph.append(d["parts"]["p_human"])
        print(json.dumps({"adapter": a.adapter, "prompts": len(rows), "samples": len(sc), "mean_score": round(sum(sc) / len(sc), 4),
                          "mean_p_human": round(sum(ph) / len(ph), 4), "secs": round(time.time() - t0)}))
        return

    if a.cmd == "rft":
        rows = [json.loads(l) for l in open(os.path.join(a.data, "train.jsonl"))]
        random.seed(0)
        random.shuffle(rows)
        mono = [r for r in rows if "topic:" in r["messages"][1]["content"]]
        rest = [r for r in rows if "topic:" not in r["messages"][1]["content"]]
        rows = mono[: a.limit * 6 // 10] + rest  # ~60% long-form prompts, the rest short replies
        rows = rows[: a.limit]
        random.shuffle(rows)
        os.makedirs(a.out, exist_ok=True)
        winners, log, t0 = [], [], time.time()
        for i, r in enumerate(rows[: a.limit]):
            msgs = [m for m in r["messages"] if m["role"] != "assistant"]
            ctx = next((m["content"] for m in msgs if m["role"] == "user"), "")
            res = best_of(model, tok, msgs, ctx, a.n, a.max_tokens)
            if not res:
                continue
            top, bot = res[0], res[-1]
            log.append({"i": i, "best": top["score"], "worst": bot["score"], "mean": sum(x["score"] for x in res) / len(res)})
            if top["score"] >= 0.3:
                winners.append({"messages": msgs + [{"role": "assistant", "content": top["text"]}]})
                with open(os.path.join(a.out, "dpo.jsonl"), "a") as f:
                    f.write(json.dumps({"prompt": msgs, "chosen": top["text"], "rejected": bot["text"],
                                        "margin": top["score"] - bot["score"]}, ensure_ascii=False) + "\n")
            print(f"[{i}] best={top['score']:.3f} mean={log[-1]['mean']:.3f} worst={bot['score']:.3f} {time.time()-t0:.0f}s", flush=True)
        # winners + the real data again so RFT doesn't drift away from Min's actual text
        real = [json.loads(l) for l in open(os.path.join(a.data, "train.jsonl"))][-max(len(winners), 1):]
        mix = winners + real
        random.shuffle(mix)
        k = max(1, len(mix) // 10)
        with open(os.path.join(a.out, "train.jsonl"), "w") as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in mix[k:])
        with open(os.path.join(a.out, "valid.jsonl"), "w") as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in mix[:k])
        json.dump(log, open(os.path.join(a.out, "rft_log.json"), "w"))
        print(json.dumps({"winners": len(winners), "mean_best": sum(l["best"] for l in log) / max(1, len(log)),
                          "mean_all": sum(l["mean"] for l in log) / max(1, len(log))}))


if __name__ == "__main__":
    main()
