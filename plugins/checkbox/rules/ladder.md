# Odoo change policy (checkbox)

This project uses a fit-gap policy for Odoo changes. Project profile: {profile_line}.
Policy level: {mode}.

Before any change to Odoo code, the change goes through these rungs, in order,
stopping at the first one that holds. Understanding comes first: the business need
is restated in one sentence and the code the change would touch is read.

0. Understand — who does what, when, with which data. At most one clarifying question.
1. Skip — a process change, training, or report filter may make the change unnecessary.
2. Standard — the feature may already exist in {version} {edition}. Evidence comes from
   `checkbox search` or the standard-scout agent, not from memory.
3. Configure — settings, groups, record rules via UI, routes, pricelists, templates.
4. No-code — automation rules, server actions{studio_clause}. Python in a server action
   is still code and gets a risk tier.
5. Module — an Odoo app or an OCA module on branch {version}. Third-party code is owned
   code: its upgrade cost goes on the card.
6. Code — only the gap, at the least invasive extension point: view/report inheritance,
   then fields, then a linked model, then `_prepare_*`/`_get_*` hook overrides with
   super(), and only then core business methods (always tier red).
{hosting_clause}

Every rung answer is recorded in a decision card at `.checkbox/decisions/NNNN-slug.md`
(format: `/checkbox:ladder`). Cards are created with status `proposed`; approval is done
by a human with `checkbox approve`, never by the agent.

Risk tiers: green (views, reports, non-stored fields), amber (stored computes,
defaults/onchanges on transactional models, access rights, crons), red (posting,
validation, reconciliation, valuation, taxes, sequences, record rules, sudo, raw SQL,
public controllers). Red changes are read line by line by a human and reviewed by the
ledger-reviewer agent before approval.

Never: copying core method bodies, monkeypatching, raw SQL writes on ledger tables,
sudo() used to bypass access rights.
