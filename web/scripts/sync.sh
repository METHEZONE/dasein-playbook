#!/bin/sh
# Pull the latest eval results + paper from their sources, then redeploy.
set -e
cd "$(dirname "$0")/.."
scp studio:tell-data/eval/results.json data/results.json
cp ~/orca/projects/CORE/projects/c0mpiled-taipei/paper/dasein-bench.pdf public/dasein-bench.pdf
vercel deploy --prod --yes
