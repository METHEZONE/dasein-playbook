# results.json schema (v1)

Written by W2 to `~/tell-data/eval/results.json` on the Studio. The site imports `web/data/results.json` at build time
(`scripts/sync.sh` copies it from the Studio). Everything not marked required has a safe default.

```jsonc
{
  "version": 1,
  "mock": false,                       // true while the data is placeholder
  "systems": [                         // exactly S1..S6, in order
    { "id": "S1", "name": "Vanilla GPT", "vendor": "openai" | "anthropic" | "tell", "desc": "no context" }
  ],
  "tasks": [
    { "id": "day-blog", "label": "Day blog", "prompt": "Write a blog post about my day",
      "human": "Minsung's real text for this task (used as the 'Human' contestant in /duel)" }
  ],
  "outputs": [                         // one per (task, system)
    { "task": "day-blog", "system": "S6",
      "text": "plain text, no markdown, no emoji",
      "score": 0.87,                   // dasein-score 0..1 (from dasein-score API :8790)
      "spans": [                       // optional; char offsets into `text` (JS string index), non-overlapping
        { "start": 0, "end": 12, "kind": "slop" },                   // AI-ism (red)
        { "start": 20, "end": 41, "kind": "unsupported" },           // invented specific (yellow)
        { "start": 50, "end": 80, "kind": "grounded",                // supported by memory (green)
          "source": "from ring recording 14:02, Taipei" }
      ] }
  ],
  "bench": [                           // one per system; feeds /bench
    { "system": "S6", "tell_score": 0.87,   // metric 1: voice match, 0..1 (reward model)
      "grounding": 0.91,                    // metric 2: share of specifics supported by memory, 0..1
      "slop_per_100w": 0.4 }                         // metric 3: AI-isms per 100 words (lower is better)
  ],
  "paper_url": "/dasein-bench.pdf"       // optional
}
```

If an output has no `slop` spans, the site highlights AI-isms itself with a lexicon (`lib/slop.js`).
Human votes (Elo, "fooled %") are collected live by the site, not in this file.
