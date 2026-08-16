#!/usr/bin/env python3
"""Prove the runtime-lane rules still bind in the MERGED config.

A packageRule that matches nothing is the exact failure this preset exists to
prevent: it reads as enforcement and enforces nothing. Validating the JSON
proves only that Renovate can parse it, not that any rule ever fires, and not
that a later rule does not quietly undo an earlier one.

So this replays Renovate's documented precedence -- iterate packageRules in
order, merge every rule that matches, last write wins -- against a table of
concrete (datasource, package, updateType) cases and asserts the outcome.

The ordering trap is real and already bit once: `default.json` used to define a
broad "non-major dependencies" group in the same file that extended the lanes.
Because presets merge BEFORE a config's own rules, that group landed last and
swallowed the lane grouping. The grouping rules now live in their own preset,
extended first, and `test_grouping_does_not_swallow_lanes` is what keeps that
from silently regressing.
"""

import importlib.util
import os
import sys

# build-merged-config.py is hyphenated (it is primarily a CLI), so it cannot be
# imported by name. Load it by path rather than duplicating the merge order --
# two copies of that ordering would be two things to keep in step.
_spec = importlib.util.spec_from_file_location(
    "build_merged_config",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "build-merged-config.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build = _mod.build


def matches_name(patterns, name):
    for p in patterns:
        if p == name:
            return True
        if p.startswith("**/"):
            suffix = p[3:]
            if name == suffix or name.endswith("/" + suffix):
                return True
    return False

def rule_matches(rule, datasource, name, update_type, dep_type):
    if "matchDatasources" in rule and datasource not in rule["matchDatasources"]:
        return False
    if "matchPackageNames" in rule and not matches_name(rule["matchPackageNames"], name):
        return False
    if "matchUpdateTypes" in rule and update_type not in rule["matchUpdateTypes"]:
        return False
    if "matchDepTypes" in rule and dep_type not in rule["matchDepTypes"]:
        return False
    return True


def resolve(rules, datasource, name, update_type, dep_type="dependencies"):
    """Apply every matching rule in order; later values overwrite earlier ones."""
    out = {}
    for rule in rules:
        if rule_matches(rule, datasource, name, update_type, dep_type):
            for k, v in rule.items():
                if k.startswith("match") or k.startswith("exclude") or k == "description":
                    continue
                out[k] = v
    return out


FAILURES = []


def check(label, actual, expected):
    if actual != expected:
        FAILURES.append(f"{label}\n     expected {expected!r}\n     actual   {actual!r}")
    else:
        print(f"  ok  {label}")


def main():
    rules = build()["packageRules"]

    # --- Lane changes must require an explicit human decision -----------------
    # Node's lane is major 22; PHP/MariaDB/ClickHouse lanes are pinned at MINOR
    # granularity, so a minor bump already leaves the approved lane.
    lane_cases = [
        ("docker", "node", "major"),
        ("node-version", "node", "major"),
        ("docker", "php", "minor"),
        ("docker", "php", "major"),
        ("docker", "mariadb", "minor"),
        ("docker", "clickhouse/clickhouse-server", "minor"),
        ("docker", "mysql", "major"),
        ("docker", "postgres", "major"),
        ("docker", "redis", "major"),
        # registry-prefixed images must not escape the lane
        ("docker", "ghcr.io/peanut/php", "minor"),
        ("docker", "docker.io/library/mariadb", "minor"),
    ]
    for ds, name, ut in lane_cases:
        r = resolve(rules, ds, name, ut)
        check(
            f"lane change needs approval: {name} {ut}",
            (r.get("dependencyDashboardApproval"), r.get("automerge")),
            (True, False),
        )

    # --- In-lane updates stay automatable, and stay grouped -------------------
    # Repos cross-check engines.node / packageManager / .nvmrc / CI / container
    # in a fail-closed contract, so a partial bump is red. Grouping is what
    # makes an in-lane Node update mergeable at all.
    check(
        "in-lane node patch is grouped",
        resolve(rules, "docker", "node", "patch").get("groupName"),
        "node runtime lane",
    )
    check(
        "in-lane node minor is grouped",
        resolve(rules, "node-version", "node", "minor").get("groupName"),
        "node runtime lane",
    )
    check(
        "in-lane php patch is grouped",
        resolve(rules, "docker", "php", "patch").get("groupName"),
        "php runtime lane",
    )

    # This is the regression guard for the ordering trap described in the
    # module docstring. If the grouping rules ever land after the lane rules
    # again, groupName here becomes "non-major dependencies" and the lane
    # grouping is silently gone.
    check(
        "test_grouping_does_not_swallow_lanes",
        resolve(rules, "docker", "node", "patch").get("groupName"),
        "node runtime lane",
    )

    # MySQL's lane is major-granular, so a MINOR bump is ordinary work and must
    # NOT demand dashboard approval -- otherwise the lane rules over-block and
    # people learn to approve everything without reading.
    check(
        "mysql minor is ordinary, not a lane change",
        resolve(rules, "docker", "mysql", "minor").get("dependencyDashboardApproval"),
        None,
    )

    # --- Digests never auto-merge --------------------------------------------
    # Digest pinning is the immutability contract for production-classified
    # stacks; moving one is an approved rollout, not a bot merge. `automerge`
    # must be False even though automerge.json's own rules are merged LAST.
    for name in ["postgres", "clickhouse/clickhouse-server", "node", "cgr.dev/chainguard/minio"]:
        check(
            f"digest never auto-merges: {name}",
            resolve(rules, "docker", name, "digest").get("automerge"),
            False,
        )

    # --- Ordinary dependencies are untouched ---------------------------------
    # The lanes must not become a blanket brake on the whole fleet.
    check(
        "ordinary npm patch still auto-merges",
        resolve(rules, "npm", "some-library", "patch").get("automerge"),
        True,
    )
    check(
        "ordinary npm patch needs no approval",
        resolve(rules, "npm", "some-library", "patch").get("dependencyDashboardApproval"),
        None,
    )
    check(
        "ordinary npm major is not silently approved",
        resolve(rules, "npm", "some-library", "major").get("dependencyDashboardApproval"),
        None,
    )

    print()
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} lane assertion(s) did not hold:\n")
        for f in FAILURES:
            print(f"  ✗ {f}\n")
        return 1
    print("All runtime-lane assertions hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
