<div align="center">

# Dasein

**RLHF for one person. A reward model fit to your own writing, plugged into your agent over MCP.**

[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)
[![Site](https://img.shields.io/badge/site-dasein.heyarca.app-black.svg)](https://dasein.heyarca.app)
[![Report](https://img.shields.io/badge/report-dasein--bench.pdf-black.svg)](https://dasein.heyarca.app/dasein-bench.pdf)

[![Dasein: AI has words. It doesn't have a world.](docs/hero.png)](https://dasein.heyarca.app)

</div>

## Quickstart

Paste this into Claude Code or Codex:

```
Set up dasein-one for me. Follow https://raw.githubusercontent.com/METHEZONE/dasein-playbook/main/dasein-one/SETUP_PROMPT.md step by step.
```

It installs, asks before reading anything, learns your voice from what you sent, and plugs into your agent over MCP. Your data stays in `~/.dasein` on your machine.

Or do it by hand:

```bash
git clone https://github.com/METHEZONE/dasein-playbook && cd dasein-playbook/dasein-one && uv sync
uv run dasein ingest ~/dasein-data --me "you@example.com"   # keeps only what you wrote -> ~/.dasein/mine.jsonl
uv run dasein fit                                            # fits ~/.dasein/reward.pkl, prints held-out accuracy
claude mcp add dasein -- uv --directory "$PWD" run dasein mcp
```

Your agent now has four tools: `relationship`, `score_as_me`, `remember`, `learn`.

## Why

AI writing sounds like nobody in particular because the model has no world. It doesn't know where you were today, who you talked to, or what you care about, so it fills the gap with the average of everyone.

Dasein grounds each piece of writing in your own records. It plans what to say from them, pools drafts from several writers, reranks those drafts with a human-likeness rubric, and fact-checks the winner against the records. The reward model is fit to you.

This is research code from a 4-hour hackathon build, not a library. It is published so you can copy the approach and run it on your own data. Expect to read and edit scripts.

**Built on [gbrain](https://github.com/garrytan/gbrain).** We run gbrain as our main memory graph, and `relationship()` reads it automatically when it's installed. If you're not using gbrain yet, go check it out. The setup prompt will offer to install it (it asks first).

## Features

- **Personal reward model.** `dasein fit` trains a small classifier on your text and reports two held-out numbers: you vs AI, and you vs other people.
- **MCP server for Claude Code and Codex.** `relationship(person)` before drafting, `score_as_me(candidates)` to pick a winner, `remember(person, field, text)` for relationship state, `learn(sent_text, person)` after you send.
- **Keeps learning.** Every text you actually send becomes a positive example. The model refits every 20 messages.
- **Local by default.** State lives in `~/.dasein/` (override with `DASEIN_HOME`). Optional local UI at `127.0.0.1:8799` via `uv run dasein ui`.
- **Full research pipeline.** Dataset builders, the dasein-score scorer, the plan-draft-gate-rerank writer, a fact-fix pass, and an eval harness with fair baselines.

## How it works

The loop: call `relationship(person)` before drafting, write about 4 drafts, pick the winner with `score_as_me`, and after you send, call `learn(sent_text, person)` with what you actually sent. Details in [`dasein-one/README.md`](dasein-one/README.md).

For Codex, register the same command (`uv --directory <repo>/dasein-one run dasein mcp`) as an MCP server. Or paste [`dasein-one/SETUP_PROMPT.md`](dasein-one/SETUP_PROMPT.md) into your agent and it will walk you through consent, import, fit, registration and a dry-run test.

## Results (honest version)

Measured on n=3 tasks (day blog, follow-up message, last-few-days essay) for one person. Treat these as a pilot, not a benchmark.

| Setup | Independent judge score |
|---|---|
| Dasein | **0.99** |
| Claude, same context | 0.64 |
| GPT, same context | 0.62 |

- **Independent judge:** local Qwen 27B with a 7-criterion rubric. It didn't take part in selection.
- **That judge is lenient.** It doesn't penalize invented facts, and a style prompt with no context also scores high on it. A high rubric score doesn't mean the text is true or that it reads like you.
- **Blind pairwise human-likeness is still a coin flip:** Dasein was picked as more human 4/12 times against Claude with the same context and 7/12 against GPT with the same context (2 judges x 2 orders x 3 tasks; both 95% CIs include 0.5). We claim no win there.
- **Classifier:** 91.9% held-out accuracy on HC3 (human vs ChatGPT), 97.4% on author-vs-AI. Telling the author apart from other humans is a separate and harder test (`train/min_vs_humans.py`).
- No weights were trained for the headline result. It comes from inference-time planning, best-of-n and reranking. LoRA/SFT code is included but wasn't the winning system.

Full numbers, setup and caveats: [dasein-bench.pdf](https://dasein.heyarca.app/dasein-bench.pdf).

## Bring your own data

Use text **you** wrote. Good sources:

- your sent mail (Gmail Takeout `.mbox`, filtered to messages from you)
- your notes (`.md` / `.txt`)
- chat exports, keeping only your own messages (WhatsApp-style text exports, Slack export JSON)
- transcripts of your own speech, if you have them

Drop other people's messages. They aren't needed to learn your voice, and you shouldn't be passing them to model APIs without consent. If you do use what correspondents wrote as "not me" negatives, keep that data local, as dasein-one does.

Put everything under a local folder outside this repo, for example `~/dasein-data/`. Never commit it (see Privacy).

`fit` reports "you vs AI" and "you vs other people". The second number is the one that matters. Below about 0.75, the scorer can't really tell you apart yet, and you need more of your own text.

The public repo doesn't ship the "other humans" negatives file. To get that second number, put one `{"text": ...}` per line from any public human-written corpus (Enron mail, HC3 human answers) in `dasein-one/data/other_humans.jsonl`, or run ingest with `--others` on your own exports. That file stays local. `data/ai_generic.jsonl` (ChatGPT answers from HC3, CC-BY-SA) is included.

## What's in the repo

| Path | What it is |
|---|---|
| `dasein-one/` | The part you can use today: a small personal reward model plus an MCP server for Claude Code or Codex. Tools: `relationship`, `score_as_me`, `remember`, `learn`. Start here. |
| `data/` | Dataset builders: extract your own turns from transcripts (`extract_arca.py`), clean and translate them (`clean_translate.py`), pull out stated opinions (`opinions.py`), build the classifier set (`disc.py`), build SFT files (`build_sft.py`). `data/sample/` holds 10 example lines written by the author. |
| `train/tell_score.py` | dasein-score, the scorer. It combines a human-vs-AI classifier, a fluency floor, grounding against your context, a slop-phrase penalty and a surprisal bonus. Can run as a small HTTP service. |
| `train/dasein_final.py` | The writer pipeline: plan, then write several drafts per plan, gate on length, slop and invented specifics, and rerank with the rubric. |
| `train/revise.py` | Fact-fix pass that removes facts the judges flagged as invented. |
| `train/gen.py`, `build_sft.py` | Best-of-n generation and rejection-sampling fine-tune data (MLX, LoRA adapters). |
| `train/eval.py`, `fair_baselines.py`, `headline*.py`, `build_results.py`, `min_vs_humans.py` | Eval harness: baselines with the same context, an independent judge, blind pairwise, and identity tests (you vs other people). |
| `web/` | The demo site. You don't need it to run anything. |

## The full pipeline (`data/` + `train/`)

The scripts take positional file arguments and some hardcoded locations. The setup they were written for is a MacBook driving a Mac Studio over ssh (host alias `studio`). Before running, set or edit these:

| What | Where it's used | What to do |
|---|---|---|
| Data root `~/tell-data` (`raw/`, `context/`, `disc/`, `eval/`) | `build_sft.py`, `min_vs_humans.py`, `tell_score.py`, `gen.py`, `eval.py` | Create this layout with your data, or edit the path at the top of each script |
| `ssh studio ...` / `scp studio:` | `eval.py`, `dasein_final.py`, `headline.py`, `build_results.py`, `headline2.py` | Point the `studio` alias in `~/.ssh/config` at your GPU box, or at `localhost` |
| OpenAI-compatible endpoint `http://127.0.0.1:18080/v1` | `clean_translate.py`, `headline.py` | Any OpenAI-compatible server works: llama.cpp `llama-server`, llama-swap, vLLM, LM Studio, or a hosted API |
| Hosted open model (DeepSeek-V3 via GMI Cloud) | `gen.py` (`GMI_BASE`), `gmi.py` | Set `GMI_BASE` to any OpenAI-compatible base URL. The key is read from `~/.gmi_key`. Keep keys out of the repo. |
| Base model for LoRA/MLX | `gen.py` | `TELL_BASE=<path or HF id>` (MLX format, e.g. a 4-bit Qwen3 8B) |
| Surprisal model | `tell_score.py` | `TELL_SURPRISAL_MODEL=<mlx model id>`, or `TELL_NO_SURPRISAL=1` to skip it |
| CLI LLM for extraction and judging | `data/disc.py`, `data/opinions.py`, `tell_score.py` | These call `~/.local/bin/claude-sub -p`. Swap in any CLI that reads a prompt and prints an answer. |
| Eval scratch dir | `eval.py` | `EVAL_ISO=<dir outside any git repo>` |
| Transcript source | `data/extract_arca.py` | Written for the Arca app's local store. Replace it with a reader for your own export. |

Rough order:

```bash
python3 data/clean_translate.py raw.jsonl ct_all.jsonl          # optional: clean STT noise / translate
python3 data/opinions.py ct_all.jsonl opinions.jsonl             # your stated views
python3 data/disc.py opinions.jsonl ct_all.jsonl ~/tell-data/disc
python3 train/tell_score.py fit                                  # fit the classifier, prints held-out accuracy
python3 train/dasein_final.py                                    # write: plan, draft, gate, rerank
python3 train/revise.py                                          # fix invented facts
python3 train/eval.py && python3 train/build_results.py          # score against baselines
```

Read each script's docstring before running it. Several are tied to the three demo tasks (day blog, follow-up message, recent essay).

## Privacy

- Keep your data on your machine. Everything here reads from local paths. The only network calls go to the LLM endpoints you configure.
- Never commit `data/` (other than `data/sample/`), `~/.dasein`, `*.pkl`, `_eval/`, `.env` or key files. `.gitignore` covers these, but check `git status` before you push.
- A hosted model API sees whatever context you send it. For private records, use a local model (llama.cpp, MLX).
- Leave other people's words out of anything you publish, and replace private names with roles.

## Prior art

This builds on existing work and isn't the first to try it:

- **DITTO** (Shaikh et al., ICLR 2025): uses a user's own demonstrations as preferred over model outputs to align to that one user.
- **P-RLHF** (personalized RLHF): user-conditioned reward models and policies.
- **VPL** (variational preference learning): latent per-user preferences in the reward model.
- **Panza**: a personalized email assistant fine-tuned on your sent mail and run locally.

What Dasein adds: grounding drafts in the day's actual records, per-recipient relationship state, a fact-check pass, and a scorer that keeps updating from what you actually send.

## Roadmap

Open work, in no particular order. None of it is done yet:

- [ ] one config file instead of hardcoded paths
- [ ] readers for more export formats (Gmail mbox, iMessage, Slack, Notion)
- [ ] a stricter judge that penalizes invented facts
- [ ] larger and more varied eval sets, and human blind tests

## Contributing

Issues and PRs are welcome, especially for anything on the roadmap.

Never include personal data in issues, PRs or test fixtures. Use synthetic text or text you wrote yourself and are fine publishing.

## License

MIT. See [LICENSE](LICENSE).

## Star history

[![Star History Chart](https://api.star-history.com/svg?repos=METHEZONE/dasein-playbook&type=Date)](https://star-history.com/#METHEZONE/dasein-playbook&Date)
