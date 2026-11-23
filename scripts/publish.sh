#!/usr/bin/env bash
# One-shot publish: public repo + GitHub Pages + first live sweep.
# Needs the GitHub CLI logged in as the repo owner:  gh auth login
#   bash scripts/publish.sh            (repo name defaults to composio-app-research)
set -euo pipefail
NAME="${1:-composio-app-research}"
OWNER="$(gh api user --jq .login)"
cd "$(dirname "$0")/.."

[ -d .git ] || { git init -q -b main; git add -A; git commit -qm "Toolkit Readiness Atlas: agent, data, verification, interactive case study"; }

if ! gh repo view "$OWNER/$NAME" >/dev/null 2>&1; then
  gh repo create "$OWNER/$NAME" --public --source . --remote origin --push \
    --description "Multi-agent research pipeline + interactive case study: auth, access, API surface, MCP and buildability for 100 apps"
else
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$NAME.git"
  git push -u origin main
fi

# GitHub Pages served by the pipeline workflow
gh api -X POST "repos/$OWNER/$NAME/pages" -f build_type=workflow >/dev/null 2>&1 \
  || gh api -X PUT "repos/$OWNER/$NAME/pages" -f build_type=workflow >/dev/null 2>&1 || true

# First run: live sweep of all 100 apps -> rebuild -> tests -> commit -> deploy
gh workflow run pipeline.yml -R "$OWNER/$NAME" -f sweep=true
sleep 5
echo "Watching the pipeline run (≈5 min)…"
gh run watch -R "$OWNER/$NAME" "$(gh run list -R "$OWNER/$NAME" --workflow pipeline.yml -L 1 --json databaseId --jq '.[0].databaseId')" --exit-status || true

echo
echo "Repo:      https://github.com/$OWNER/$NAME"
echo "Live page: https://$OWNER.github.io/$NAME/"
echo "LLM agent: add the GEMINI_API_KEY secret, then Actions -> research-agent -> Run workflow (mode=eval)."
