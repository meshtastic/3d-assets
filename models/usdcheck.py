#!/usr/bin/env python3
# /// script
# requires-python = "==3.13.*"  # one Python everywhere, so every machine builds the same models
# dependencies = ["usd-core==25.11"]
# ///
"""Check USDZ files against the ARKit rules, like `usdchecker --arkit`.

The usd-core package on PyPI doesn't ship the usdchecker command, so this calls
the same compliance checker from Python and runs anywhere usd-core does. It is
pinned to 25.11: later versions replace the checker with a validation framework
that has no ARKit rules.

usage: usdcheck.py <file.usdz>...
"""

import sys

from pxr import UsdUtils
from pxr.UsdUtils.complianceChecker import ShaderPropertyTypeConformanceChecker

# usd-core has no shader definitions for UsdPreviewSurface (the usdShaders
# plugin isn't in it), so the rule that checks shader input types against them
# can't run and throws. Every other ARKit rule runs.
SKIPPED = (ShaderPropertyTypeConformanceChecker,)


def check(path):
    checker = UsdUtils.ComplianceChecker(arkit=True)
    checker._rules = [r for r in checker._rules if not isinstance(r, SKIPPED)]
    checker.CheckCompliance(path)
    problems = [f"error: {e}" for e in checker.GetErrors()]
    problems += [f"failed: {f}" for f in checker.GetFailedChecks()]
    for warning in checker.GetWarnings():
        print(f"{path}: warning: {warning}")
    for problem in problems:
        print(f"{path}: {problem}")
    if not problems:
        print(f"{path}: passed ARKit checks (shader input types not checked)")
    return not problems


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-1])
    results = [check(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
