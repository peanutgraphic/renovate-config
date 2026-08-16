#!/usr/bin/env python3
"""Resolve the presets into the single config shape a consumer actually gets.

Renovate merges `extends` presets left-to-right and appends the config's own
packageRules last, so the LAST matching rule wins. Every preset here is written
against that ordering, which means validating the files individually is not
enough: a rule can be valid alone and be overridden to uselessness once merged.

This reproduces the resolution order for a repository on `:automerge`, the
strictest consumer:

    config:recommended  ->  grouping  ->  runtime-lanes  ->  automerge's own

Used by CI and by test-runtime-lanes.py. It performs no network access and
resolves nothing remotely; it only concatenates in the documented order.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return json.load(fh)


def build():
    grouping = load("grouping.json")
    lanes = load("runtime-lanes.json")
    default = load("default.json")
    automerge = load("automerge.json")

    merged = {
        k: v
        for k, v in default.items()
        if k not in ("extends", "$schema", "description")
    }
    merged["$schema"] = "https://docs.renovatebot.com/renovate-schema.json"
    merged["extends"] = ["config:recommended"]
    merged["packageRules"] = (
        grouping["packageRules"] + lanes["packageRules"] + automerge["packageRules"]
    )
    merged["lockFileMaintenance"] = automerge["lockFileMaintenance"]
    return merged


def main():
    merged = build()
    if len(sys.argv) > 1:
        out_dir = sys.argv[1]
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "renovate.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
            fh.write("\n")
        print(f"wrote {path} ({len(merged['packageRules'])} packageRules)")
    else:
        json.dump(merged, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
