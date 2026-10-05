#!/usr/bin/env bash
# Validate every skill against the Agent Skills spec with the reference
# validator (https://github.com/agentskills/agentskills/tree/main/skills-ref).
set -euo pipefail
cd "$(dirname "$0")/.."
status=0
for skill in skills/*/; do
  [ -f "$skill/SKILL.md" ] || continue
  uvx --from skills-ref agentskills validate "$skill" || status=1
done
exit $status
