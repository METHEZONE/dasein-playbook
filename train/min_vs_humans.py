"""Min vs OTHER humans (identity, not human-vs-AI). Held-out, length-matched by truncating each pair to the shorter length."""
import json, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tell_score import _hc3, _norm
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union
from sklearn.model_selection import train_test_split
random.seed(0)
def run(name, A, B):
    n = min(len(A), len(B)); A, B = random.sample(A, n), random.sample(B, n)
    X, y = [], []
    for a, b in zip(A, B):  # length-match each pair
        wa, wb = a.split(), b.split(); k = min(len(wa), len(wb))
        X += [" ".join(wa[:k]), " ".join(wb[:k])]; y += [1, 0]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
    p = make_pipeline(make_union(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True),
                                 TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True)), LogisticRegression(C=4.0, max_iter=2000))
    p.fit(Xtr, ytr); acc = p.score(Xte, yte)
    print(json.dumps({"comparison": name, "pairs": n, "n_test": len(Xte), "heldout_acc": round(acc, 4),
                      "mean_words": round(sum(len(x.split()) for x in X) / len(X), 1)}))
D = os.path.expanduser("~/tell-data")
min_op = [_norm(json.loads(l)["text"]) for l in open(D + "/disc/min_vs_ai.jsonl") if json.loads(l)["label"] == "human"]
H, _ = _hc3()
run("Min (opinion text) vs other humans (HC3 human answers)", [t for t in min_op if len(t.split()) >= 15], [t for t in H if len(t.split()) >= 15])
rows = [json.loads(l)["messages"] for f in ("train.jsonl", "valid.jsonl") for l in open(D + "/sft/" + f)]
me = [m[-1]["content"] for m in rows if len(m[-1]["content"].split()) >= 12]
other = [m[1]["content"] for m in rows if len(m[1]["content"].split()) >= 12]
run("Min turns vs other speakers in the same conversations (same STT+translation pipeline)", me, other)
