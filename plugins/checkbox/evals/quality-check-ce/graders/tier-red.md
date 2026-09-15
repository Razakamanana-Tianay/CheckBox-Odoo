---
type: regex
target: trace
pattern: "tier:\\s*red"
flags: i
weight: 2
---

Red recall is the one §11.2 metric with a 100% target -- the classifier is
deterministic, so the card must agree with it. Weighted 2x: a case that
gets the verdict right but the tier wrong is a worse failure than a wording
miss elsewhere in this suite.
