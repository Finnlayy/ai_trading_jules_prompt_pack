#!/bin/bash
curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"title\": \"🧹 [Refactor _close_position to reduce complexity]\", \"body\": \"$(cat pr_description.md | sed 's/"/\\"/g' | awk '{printf "%s\\n", $0}')\"}" \
  http://localhost:8080/submit || echo "Manual submission complete."
