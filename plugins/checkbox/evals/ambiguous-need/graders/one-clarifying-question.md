---
type: llm
focus: last_message
---

Rung 0 (docs/ARCHITECTURE.md §4.1): "What is the business need in one
sentence? Who does what, when, and with which data? ... At most one
clarifying question." "Customers should get reminders" names no trigger,
no channel, no data source, and no recipient scope.

PASS if the response asks exactly one clarifying question about the need
(e.g. what should trigger a reminder, which customers, what channel) and
does not propose a verdict, a card, or a solution yet.

FAIL if it asks zero questions and guesses at a solution, asks more than
one question, or jumps straight to a verdict/card without clarifying
first.
