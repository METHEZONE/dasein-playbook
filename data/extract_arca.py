"""Extract Min's own turns from the Arca store + Claude Code transcripts -> raw jsonl (local only, never commit)."""
import sqlite3, json, re, glob, sys, os, collections
STORE = os.path.expanduser("~/Library/Application Support/ArcaVoice/accounts/4bcb396b/arca.store")
ME = {"Me", "나", "민성"}
BAD = re.compile(r"자막|시청해 주셔서|협찬|구독|좋아요|MBC|다음 영상|이 영상은|감사합니다\.?$")
def junk(t):
    w = t.split()
    return len(w) >= 4 and len(set(w)) / len(w) < 0.4 or bool(BAD.search(t))
db = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
sess = {r[0]: r for r in db.execute("select Z_PK, ZCREATEDAT+978307200, ZTITLE from ZRECORDINGSESSION")}
segs = collections.defaultdict(list)
for pk, s, ch, spk, t in db.execute("select Z5SEGMENTS, ZSTART, ZCHANNELRAW, ZSPEAKERKEY, ZTEXT from ZSTOREDSEGMENT order by Z_PK"):
    t = (t or "").strip()
    if not t or junk(t): continue
    if ch == "microphone":
        if spk in ME: role = "me"
        elif spk: role = "other"
        else: continue  # ambiguous speaker, drop
    else: role = "other"
    segs[pk].append((s, role, t))
out = []
for pk, L in segs.items():
    if pk not in sess: continue
    L.sort(key=lambda x: x[0]); turns = []
    for s, r, t in L:
        if turns and turns[-1][0] == r and s - turns[-1][2] < 8: turns[-1][1] += " " + t; turns[-1][2] = s
        else: turns.append([r, t, s])
    for i, (r, t, s) in enumerate(turns):
        if r != "me" or not (8 <= len(t) <= 700): continue
        ctx = [{"role": "other", "text": x[1][:400]} for x in turns[max(0, i - 2):i] if x[0] == "other"]
        out.append({"src": "arca", "session": pk, "ts": sess[pk][1], "title": sess[pk][2], "context": ctx, "reply": t})
# Claude Code typed messages
for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    last = ""
    for l in open(f, errors="ignore"):
        try: d = json.loads(l)
        except: continue
        c = d.get("message", {}).get("content") if isinstance(d.get("message"), dict) else None
        if d.get("type") == "assistant" and isinstance(c, list):
            last = " ".join(b.get("text", "") for b in c if b.get("type") == "text")[:300] or last
        elif d.get("type") == "user" and not d.get("isMeta") and not d.get("isSidechain") and isinstance(c, str) and not c.startswith("<") and 8 <= len(c) <= 700:
            out.append({"src": "claude", "session": os.path.basename(f), "ts": None, "context": [{"role": "other", "text": last}] if last else [], "reply": c})
seen = set(); res = []
for o in out:
    k = o["reply"][:60]
    if k in seen: continue
    seen.add(k); res.append(o)
with open(sys.argv[1], "w") as fh:
    for o in res: fh.write(json.dumps(o, ensure_ascii=False) + "\n")
print(len(res), collections.Counter(o["src"] for o in res), sum(bool(o["context"]) for o in res))
