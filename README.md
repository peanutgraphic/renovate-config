# renovate-config

Central Renovate preset for the Peanut ecosystem. Change policy here once; all repos inherit on their next Renovate run.

## Presets

- **`default.json`** — base policy, **no auto-merge**. For repos without a real PR test gate.
- **`automerge.json`** — extends `default` + CI-gated auto-merge of safe updates (patch, dev-dep minor/patch, lockfile maintenance). For repos with a real PR test gate.
- **`grouping.json`** — generic batching of ordinary updates. Extended by `default`.
- **`runtime-lanes.json`** — the approved runtime and container image lanes. Extended by `default`, so every consumer inherits it.

## Runtime lanes

A *lane* is a program decision recorded in the parity tracker's Decision Log — PHP 8.4 for Laravel, Node 22 LTS, MariaDB 11.4 as the default server-backed transactional engine — not something a dependency bot should cross on a Monday morning.

`runtime-lanes.json` makes that distinction operational:

| Dependency | Lane granularity | Leaving the lane |
|---|---|---|
| `node`, `npm` | major (22 LTS) | dashboard approval + `lane-change` label |
| `php`, `mariadb`, `clickhouse` | **minor** (8.4, 11.4, 25.12) | dashboard approval + `lane-change` label |
| `mysql`, `postgres`, `redis`, `minio` | major | dashboard approval + `lane-change` label |

Lane changes are **surfaced, not blocked**. They appear on the dependency dashboard and wait for a person, so a new LTS is never hidden — it just never lands by itself.

In-lane updates stay automatable, but are **grouped**. Repos now cross-check `engines.node`, `packageManager`, `.nvmrc`, CI `setup-node` and the container base image in a fail-closed runtime contract, so a bump landing in only one of them turns CI red. Grouping them into a single branch is what makes an in-lane update mergeable at all.

### Container image digests never auto-merge

`digest` was deliberately removed from `automerge.json`. Digest pinning is the immutability contract for production-classified stacks, and moving one is an approved rollout with snapshot, canary and rollback — not something a bot does while you sleep. Digest PRs are still raised; a person merges them.

### Rule ordering is load-bearing

Renovate merges `extends` presets left-to-right and appends a config's **own** rules last, so **the last matching rule wins**. The grouping rules therefore live in their own preset extended *before* the lanes — when they lived inside `default.json` alongside the extend, the broad "non-major dependencies" group landed last and silently swallowed the lane grouping.

`scripts/test-runtime-lanes.py` replays that precedence against concrete cases and fails if it regresses. Both failure directions are proven by breaking them: restoring `digest` to the auto-merge list, and putting the grouping rules back after the lanes.

## CI

`.github/workflows/validate-presets.yml` runs on every PR and push to `main`:

1. strict `renovate-config-validator` over all four presets,
2. the same validator over the **resolved consumer shape**, because the presets are only ever consumed merged,
3. the lane assertions above.

Before this existed, nothing validated the preset at all — and every repo extending `local>peanutgraphic/renovate-config` picks up whatever is on `main` at its next run.

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
