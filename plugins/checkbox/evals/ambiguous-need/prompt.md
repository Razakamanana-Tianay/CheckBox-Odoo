---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [rung0]
description: >
  Rung 0 (docs/ARCHITECTURE.md §4.1): "at most one clarifying question" --
  the ladder text (rules/ladder.md line 10, skills/ladder/SKILL.md's own
  "Understand first" step) already states this clearly. Real runs
  (2026-09-15, two separate sessions) consistently score 0.5: no premature
  card (correct), but 3 clarifying questions instead of at most 1. This is
  kept as a real, reproducible finding, not loosened to match the
  behavior -- the grader enforces what the ladder itself already claims to
  do. Worth a follow-up on the ladder skill's rung-0 instruction strength
  if it doesn't improve with model updates.
---

Customers should get reminders.
