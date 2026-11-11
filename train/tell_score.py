"""dasein-score (formerly tell-score): reward model for "does this read like a real person (Min) wrote it, and is it true to his context".

score = p_human(discriminator) x fluency_floor x grounding x slop_factor x (1 + surprisal_bonus), clipped to [0,1]

  tell_score(text, context="") -> {"score", "parts", "spans"}
  python tell_score.py fit        # train discriminator (HC3 + Min-vs-AI pairs) -> disc.pkl, prints held-out acc
  python tell_score.py serve      # HTTP POST /score {"text","context","judge":bool} on :8790
"""
import json, math, os, pickle, re, subprocess, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DISC_PATH = os.path.join(HERE, "disc.pkl")
SURPRISAL_MODEL = os.environ.get("TELL_SURPRISAL_MODEL", "mlx-community/Qwen2.5-3B-Instruct-4bit")

# ---------------------------------------------------------------- slop lexicon
SLOP = [
    "delve", "delving", "tapestry", "testament to", "in today's fast-paced", "fast-paced world", "ever-evolving",
    "ever-changing", "landscape", "navigate the", "navigating the", "realm", "embark", "journey", "unlock",
    "unleash", "elevate", "seamless", "seamlessly", "robust", "leverage", "harness", "game-changer", "game changer",
    "cutting-edge", "pivotal", "crucial", "vital", "paramount", "multifaceted", "nuanced", "intricate",
    "furthermore", "moreover", "additionally", "in conclusion", "overall,", "ultimately,", "it's important to note",
    "it is important to note", "it's worth noting", "it is worth noting", "a reminder that", "serves as a reminder",
    "i hope this", "let's dive", "dive into", "deep dive", "at the end of the day", "in essence", "beacon",
    "symphony", "vibrant", "bustling", "foster", "fostering", "resonate", "resonates", "profound", "transformative",
    "underscore", "underscores", "showcase", "showcasing", "commendable", "meticulous", "meticulously", "whimsical",
    "not just", "not only", "but also", "more than just", "isn't just", "it's not about", "a blend of",
    "i couldn't help but", "little did i know", "as i reflect", "reflecting on", "grateful for", "a sense of",
    "the power of", "the beauty of", "the art of", "stands as", "plays a crucial role", "rich tapestry",
    "in the heart of", "nestled", "captivating", "unwavering", "invaluable", "endeavor", "endeavour",
    "certainly!", "absolutely!", "great question", "as an ai", "here's a", "here is a", "—",
]
_SLOP_RE = re.compile("|".join(sorted((re.escape(s) for s in SLOP), key=len, reverse=True)), re.I)


def slop_spans(text):
    return [(m.start(), m.end()) for m in _SLOP_RE.finditer(text)]


def words(text):
    return re.findall(r"[A-Za-z0-9'’\-]+|[가-힣]+", text)


# ---------------------------------------------------------------- fluency floor
def fluency(text):
    """Punishes degenerate output (loops, near-empty). 1.0 for normal text."""
    w = [x.lower() for x in words(text)]
    if len(w) < 5:
        return 0.2
    if len(text.split()) < len(text) / 15:  # missing spaces / glued tokens
        return 0.1
    odd = len(re.findall(r"[^\x00-\x7F’‘“”—–…·°₩€£¥가-힣]", text)) / max(1, len(text))
    if odd > 0.003:  # stray scripts (Thai/Arabic/CJK tokens) = base-model degeneration, not a human signal
        return 0.05
    if re.search(r"^#{1,4} |\*\*", text, re.M):  # markdown in a 'plain text' task
        return 0.5
    tri = list(zip(w, w[1:], w[2:]))
    distinct3 = len(set(tri)) / max(1, len(tri))
    sents = [s.strip().lower() for s in re.split(r"[.!?\n]+", text) if len(s.strip()) > 8]
    dup_sent = 1 - len(set(sents)) / max(1, len(sents))
    f = min(1.0, distinct3 / 0.85) * (1 - dup_sent)
    return max(0.05, f)


# ---------------------------------------------------------------- discriminator
def _norm(t):
    t = t.replace("\\n", "\n")
    t = re.sub(r" ([,.;:!?)%])", r"\1", t)
    t = re.sub(r" (['’](s|t|re|ve|ll|d|m)\b)", r"\1", t)
    t = re.sub(r"\( ", "(", t)
    return re.sub(r"\s+", " ", t).strip()


def _chunks(t, n=120):
    """Split to ~n-word chunks so length is not a feature."""
    w = t.split()
    return [" ".join(w[i:i + n]) for i in range(0, len(w), n) if len(w[i:i + n]) >= 25]


def _hc3(max_per_file=1500):
    import random
    random.seed(0)
    H, A = [], []
    for f in ["open_qa", "reddit_eli5", "finance", "wiki_csai"]:
        p = os.path.expanduser(f"~/tell/hc3/{f}.jsonl")
        if not os.path.exists(p):
            continue
        rows = [json.loads(l) for l in open(p)]
        random.shuffle(rows)
        for r in rows[:max_per_file]:
            for h in r["human_answers"][:1]:
                H += _chunks(_norm(h))[:2]
            for a in r["chatgpt_answers"][:1]:
                A += _chunks(_norm(a))[:2]
    return H, A


def _min_pairs():
    """Min's real writing (human) vs AI text written for the same prompts (from W1 / our eval runs)."""
    H, A = [], []
    p = os.path.expanduser("~/tell-data/disc/min_vs_ai.jsonl")  # {"text","label": "human"|"ai"}
    if os.path.exists(p):
        for l in open(p):
            r = json.loads(l)
            (H if r["label"] == "human" else A).append(_norm(r["text"]))
    return H, A


def fit():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline, make_union

    from sklearn.model_selection import train_test_split as tts
    H, A = _hc3()
    mh, ma = _min_pairs()
    # split BEFORE upweighting so duplicated in-domain rows never straddle train/test
    Htr, Hte = tts(H, test_size=0.2, random_state=0)
    Atr, Ate = tts(A, test_size=0.2, random_state=0)
    mhtr, mhte = tts(mh, test_size=0.2, random_state=0) if mh else ([], [])
    matr, mate = tts(ma, test_size=0.2, random_state=0) if ma else ([], [])
    Xtr = Htr + Atr + mhtr * 3 + matr * 3
    ytr = [1] * len(Htr) + [0] * len(Atr) + [1] * len(mhtr) * 3 + [0] * len(matr) * 3
    pipe = make_pipeline(
        make_union(
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True, max_features=200000),
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True),
        ),
        LogisticRegression(C=4.0, max_iter=2000),
    )
    pipe.fit(Xtr, ytr)
    acc = lambda Xs, ys: round(float((pipe.predict(Xs) == ys).mean()), 4) if Xs else None
    import numpy as np
    rep = {"n_train": len(Xtr), "hc3_heldout_acc": acc(Hte + Ate, np.array([1] * len(Hte) + [0] * len(Ate))),
           "min_vs_ai_heldout_acc": acc(mhte + mate, np.array([1] * len(mhte) + [0] * len(mate))),
           "n_min_test": len(mhte) + len(mate), "hc3_human": len(H), "hc3_ai": len(A), "min_human": len(mh), "min_ai": len(ma)}
    X = H + A + mh * 3 + ma * 3
    y = [1] * len(H) + [0] * len(A) + [1] * len(mh) * 3 + [0] * len(ma) * 3
    pipe.fit(X, y)  # refit on everything for serving
    pickle.dump(pipe, open(DISC_PATH, "wb"))
    json.dump(rep, open(os.path.join(HERE, "disc_report.json"), "w"), indent=1)
    print(json.dumps(rep))
    return rep


_disc = None


def p_human(text):
    global _disc
    if _disc is None:
        _disc = pickle.load(open(DISC_PATH, "rb"))
    ch = _chunks(_norm(text)) or [_norm(text)]
    ps = _disc.predict_proba(ch)[:, 1]
    return float(sum(ps) / len(ps))


# ---------------------------------------------------------------- surprisal profile
_lm = None


def surprisal_profile(text):
    """Per-token surprisal under a small LM. Humans: spikier (higher CV), AI: flat and low."""
    global _lm
    if os.environ.get("TELL_NO_SURPRISAL"):
        return None
    import mlx.core as mx
    from mlx_lm import load
    if _lm is None:
        _lm = load(SURPRISAL_MODEL)
    model, tok = _lm
    ids = tok.encode(text)[:512]
    if len(ids) < 8:
        return None
    x = mx.array(ids)[None]
    logits = model(x[:, :-1]).astype(mx.float32)
    lp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
    tgt = mx.take_along_axis(lp, x[:, 1:, None], axis=-1).squeeze()
    s = (-tgt).tolist()
    m = sum(s) / len(s)
    sd = math.sqrt(sum((v - m) ** 2 for v in s) / len(s))
    spikes = sum(v > m + 2 * sd for v in s) / len(s)
    return {"mean": round(m, 3), "sd": round(sd, 3), "cv": round(sd / max(m, 1e-6), 3), "spike_rate": round(spikes, 4)}


def surprisal_bonus(prof):
    # ponytail: hand-set logistic on mean surprisal (ChatGPT prose ~1.5-2.0 nats on a 3B LM, human ~2.5-3.5).
    # Calibrated by `python tell_score.py calib`; refit if the surprisal model changes.
    if not prof:
        return 0.0
    c = json.load(open(os.path.join(HERE, "surprisal_calib.json"))) if os.path.exists(os.path.join(HERE, "surprisal_calib.json")) else {"mid": 2.4, "k": 3.0}
    z = 1 / (1 + math.exp(-c["k"] * (prof["mean"] - c["mid"])))
    if prof["mean"] > 5.5:  # gibberish, not a human signal
        return -0.3
    return 0.25 * (z - 0.5)  # in [-0.125, +0.125]


# ---------------------------------------------------------------- grounding
_STOP_CAPS = set("I I'm I've I'd I'll The A An And But So Then It It's This That We My Me You He She They Our "
                 "Today Yesterday Tomorrow Monday Tuesday Wednesday Thursday Friday Saturday Sunday If When What Why "
                 "How Also Just Not No Yes Ok Okay Oh Well Now Still".split())


def specifics(text):
    """Checkable specifics: numbers/times/money and proper-noun runs not at sentence start."""
    out = []
    for m in re.finditer(r"[$₩€]?\d[\d,:]*(?:\.\d+)?(?:\s?(?:%|am|pm|AM|PM|k\b|hours?|hrs?|minutes?|mins?|days?|people|won|USD|NTD|TWD))?", text):
        if len(m.group().strip()) >= 1:
            out.append((m.start(), m.end(), m.group().strip()))
    for m in re.finditer(r"\b([A-Z][a-zA-Z0-9]+(?:[ -][A-Z][a-zA-Z0-9]+)*)", text):
        tok = m.group(1)
        pre = text[:m.start()].rstrip()
        sent_start = (not pre) or pre[-1] in ".!?\n\"“"
        if tok in _STOP_CAPS or (sent_start and " " not in tok):  # sentence-initial single word: just capitalization
            continue
        out.append((m.start(), m.end(), tok))
    out.sort()
    merged = []
    for s in out:  # drop overlaps
        if merged and s[0] < merged[-1][1]:
            continue
        merged.append(s)
    return merged


def _in_context(spec, ctx_low):
    s = spec.lower().strip(" .,")
    if not s:
        return True
    if s in ctx_low:
        return True
    num = re.sub(r"[^\d]", "", s)
    if num and len(num) >= 1 and re.search(r"(?<!\d)" + re.escape(num) + r"(?!\d)", re.sub(r"[,]", "", ctx_low)):
        return True
    parts = [p for p in re.split(r"[ -]", s) if len(p) > 2]
    return bool(parts) and all(p in ctx_low for p in parts)


def grounding_heuristic(text, context):
    specs = specifics(text)
    if not context:
        # no context given: every specific is unsupported by definition, but don't nuke spec-free text
        return {"grounding": 1.0 if not specs else max(0.3, 1 - 0.08 * len(specs)), "n_specifics": len(specs),
                "spans": [(a, b, "unsupported", None) for a, b, _ in specs]}
    ctx_low = context.lower()
    spans, ok = [], 0
    for a, b, s in specs:
        if _in_context(s, ctx_low):
            ok += 1
            spans.append((a, b, "grounded", None))
        else:
            spans.append((a, b, "unsupported", None))
    n = len(specs)
    bad = n - ok
    g = 1.0 if n == 0 else (ok + 1) / (n + 1)
    g = g * (0.85 if n == 0 else 1.0)  # mild nudge: real posts about your day name real things
    g = max(0.1, g - 0.04 * max(0, bad - 1))
    return {"grounding": round(g, 3), "n_specifics": n, "n_supported": ok, "spans": spans}


JUDGE_PROMPT = """You check a text against the author's real context (notes, timeline, messages).
List every SPECIFIC claim in the TEXT (names, places, numbers, times, events, products, quotes).
For each, decide SUPPORTED (context states or clearly implies it) or UNSUPPORTED (invented / not in context).
Return ONLY JSON: {{"claims":[{{"quote":"<exact substring of TEXT>","supported":true|false,"source":"<short context pointer or empty>"}}]}}

CONTEXT:
{context}

TEXT:
{text}
"""


def grounding_judge(text, context, cmd=None):
    """LLM judge (claude-sub -p). Slow (~15s); used for eval, not inside best-of-n loops."""
    cmd = cmd or [os.path.expanduser("~/.local/bin/claude-sub"), "-p", "--model", "sonnet"]
    prompt = JUDGE_PROMPT.format(context=context[:12000], text=text)
    try:
        out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180).stdout
        j = json.loads(re.search(r"\{.*\}", out, re.S).group())
    except Exception as e:  # judge down -> fall back to heuristic, say so
        r = grounding_heuristic(text, context)
        r["judge_error"] = str(e)[:200]
        return r
    spans, ok = [], 0
    for c in j.get("claims", []):
        q = c.get("quote", "")
        i = text.find(q) if q else -1
        if c.get("supported"):
            ok += 1
        if i >= 0:
            spans.append((i, i + len(q), "grounded" if c.get("supported") else "unsupported", c.get("source") or None))
    n = len(j.get("claims", []))
    g = 0.85 if n == 0 else (ok + 0.5) / (n + 0.5)
    return {"grounding": round(g, 3), "n_specifics": n, "n_supported": ok, "spans": spans, "judge": True}


# ---------------------------------------------------------------- combine
def tell_score(text, context="", judge=False, surprisal=True):
    text = text.strip()
    ph = p_human(text)
    fl = fluency(text)
    ss = slop_spans(text)
    nw = max(1, len(words(text)))
    slop100 = 100 * len(ss) / nw
    slop_factor = math.exp(-0.35 * slop100)
    gr = grounding_judge(text, context) if (judge and context) else grounding_heuristic(text, context)
    prof = surprisal_profile(text) if surprisal else None
    bonus = surprisal_bonus(prof)
    score = ph * fl * gr["grounding"] * slop_factor * (1 + bonus)
    spans = [(a, b, "slop", None) for a, b in ss] + gr.pop("spans")
    spans.sort()
    clean = []
    for s in spans:  # non-overlapping, slop wins ties (sorted first by start)
        if clean and s[0] < clean[-1][1]:
            continue
        clean.append(s)
    return {
        "score": round(max(0.0, min(1.0, score)), 4),
        "parts": {"p_human": round(ph, 4), "fluency": round(fl, 3), "slop_per_100w": round(slop100, 2),
                  "slop_factor": round(slop_factor, 3), "surprisal": prof, "surprisal_bonus": round(bonus, 3), **gr},
        "spans": [{"start": a, "end": b, "kind": k, **({"source": src} if src else {})} for a, b, k, src in clean],
    }


dasein_score = tell_score  # product renamed to Dasein; tell_score kept as alias


def calib():
    """Fit surprisal midpoint on HC3 human vs ChatGPT chunks."""
    H, A = _hc3(max_per_file=40)
    hm = [surprisal_profile(t)["mean"] for t in H[:60]]
    am = [surprisal_profile(t)["mean"] for t in A[:60]]
    mh, ma = sum(hm) / len(hm), sum(am) / len(am)
    c = {"mid": round((mh + ma) / 2, 3), "k": round(4.0 / max(0.3, abs(mh - ma)), 3), "human_mean": round(mh, 3), "ai_mean": round(ma, 3),
         "acc_threshold": round((sum(v > (mh + ma) / 2 for v in hm) + sum(v <= (mh + ma) / 2 for v in am)) / (len(hm) + len(am)), 3)}
    json.dump(c, open(os.path.join(HERE, "surprisal_calib.json"), "w"))
    print(json.dumps(c))


def serve(port=8790):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    lock = threading.Lock()  # ponytail: one MLX model, one request at a time

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_OPTIONS(self):
            self._send(204, {})

        def do_GET(self):
            self._send(200, {"ok": True, "name": "dasein-score", "endpoint": "POST /score {text, context?, judge?}"})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n > 200000:
                    return self._send(413, {"error": "too large"})
                req = json.loads(self.rfile.read(n) or b"{}")
                text = str(req.get("text", ""))
                if not text.strip():
                    return self._send(400, {"error": "text required"})
                with lock:
                    self._send(200, tell_score(text, str(req.get("context", "")), bool(req.get("judge", False))))
            except Exception as e:
                self._send(500, {"error": str(e)[:300]})

    print(f"dasein-score on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "fit":
        fit()
    elif cmd == "calib":
        calib()
    elif cmd == "serve":
        serve()
    else:  # self-check
        slopy = ("In today's fast-paced world, it's important to note that AI is a game-changer. Furthermore, "
                 "it serves as a testament to the transformative power of technology, fostering a vibrant tapestry of innovation.")
        human = ("ok so taipei. slept 4 hours, tender demo half broken at 9am, fixed it in a 7-eleven. "
                 "judges didn't care about the auction thing, they cared that it actually routed. lesson noted.")
        a, b = tell_score(slopy, surprisal=False), tell_score(human, "Taipei Tender demo 9am 7-eleven auction routing", surprisal=False)
        print(a["score"], b["score"], a["parts"]["slop_per_100w"])
        assert b["score"] > a["score"], (a, b)
        assert fluency("I'm going to come out early. I'm going to come out early. I'm going to come out early.") < 0.5
        print("ok")
