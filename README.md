# renovate-config

Central Renovate preset for the Peanut ecosystem. Change policy here once; all repos inherit on their next Renovate run.

## Presets

- **`default.json`** — base policy, **no auto-merge**. For repos without a real PR test gate.
- **`automerge.json`** — extends `default` + CI-gated auto-merge of safe updates (patch, dev-dep minor/patch, lockfile maintenance). For repos with a real PR test gate.

## Onboard a repo

Add a `renovate.json` to the repo root.

**Strong CI** (auto-merge safe updates):

```json
{ "$schema": "https://docs.renovatebot.com/renovate-schema.json", "extends": ["local>peanutgraphic/renovate-config:automerge"] }
```

**Thin CI** (PRs only, human merges):

```json
{ "$schema": "https://docs.renovatebot.com/renovate-schema.json", "extends": ["local>peanutgraphic/renovate-config"] }
```

A repo graduates from `default` to `:automerge` once it gains a real PR test gate (e.g. after the static-analysis / CI gap-fill rollout).

## Security model

Dependabot security **alerts** are enabled fleet-wide as the detector; Dependabot security **updates** (auto-PRs) are OFF. Renovate owns all fix PRs (`vulnerabilityAlerts`), so the two never compete.

## Auto-merge safety

`automerge.json` only ever auto-merges **patch**, **dev-dependency minor/patch**, and **lockfile maintenance** — and only after branch status checks pass. Major versions and production-dependency minors always require a human. The preset is only extended by repos that have a real PR test gate; everything else extends `default.json` and never auto-merges.
