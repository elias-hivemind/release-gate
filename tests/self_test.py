#!/usr/bin/env python3
"""Self-test for release_gate.py.

Runs the gate against fixture release directories and asserts the
fail-closed contract:

  * a known-good release SEALS (exit 0) and VERIFIES (exit 0);
  * a tampered artifact FAILS verify (exit 1) and names the check;
  * a stale SHA256SUMS FAILS verify (exit 1) and names the check;
  * a zero-byte artifact FAILS seal (exit 1) and names the check;
  * a missing --expect artifact FAILS (exit 1) and names the check;
  * an unsealed directory FAILS verify (exit 1) and names the check;
  * every run is appended to a hash-chained ledger, and the chain
    actually verifies.

Fixtures are copied into a temporary directory first, so running this
test never modifies the fixtures in this repository.

Usage:  python3 tests/self_test.py
Exit 0 = all tests passed, 1 = at least one test failed.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "..", "release_gate.py")
FIXTURES = os.path.join(HERE, "fixtures")

RESULTS = []


def run_gate(args, ledger):
    proc = subprocess.run(
        [sys.executable, GATE, *args, "--ledger", ledger],
        capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def check(name, ok, why=""):
    RESULTS.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {why}" if why and not ok else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="release-gate-selftest-")
    ledger = os.path.join(tmp, "gate-ledger.jsonl")
    try:
        # 1. SEAL a known-good release -> PASS, exit 0, SHA256SUMS written.
        good = os.path.join(tmp, "good")
        shutil.copytree(os.path.join(FIXTURES, "good"), good)
        rc, out = run_gate([good, "--expect", "app-linux.tar.gz",
                            "--expect", "app-windows.zip"], ledger)
        check("seal good release exits 0", rc == 0, f"rc={rc}\n{out}")
        check("seal good release prints VERDICT: PASS", "VERDICT: PASS" in out)
        check("seal writes SHA256SUMS",
              os.path.isfile(os.path.join(good, "SHA256SUMS")))

        # 2. VERIFY the untouched release -> PASS, exit 0.
        rc, out = run_gate([good, "--verify"], ledger)
        check("verify untouched release exits 0", rc == 0, f"rc={rc}\n{out}")
        check("verify untouched release prints VERDICT: PASS", "VERDICT: PASS" in out)

        # 3. TAMPER one byte, then VERIFY -> FAIL, exit 1, names VERIFY.
        with open(os.path.join(good, "app-linux.tar.gz"), "ab") as fh:
            fh.write(b"X")
        rc, out = run_gate([good, "--verify"], ledger)
        check("verify tampered release exits 1", rc == 1, f"rc={rc}\n{out}")
        check("tamper failure names the VERIFY check",
              "VERIFY: FAIL" in out and "checksum mismatch" in out)

        # 4. Bad fixture: SHA256SUMS no longer matches an artifact -> FAIL.
        bad = os.path.join(tmp, "bad")
        shutil.copytree(os.path.join(FIXTURES, "bad"), bad)
        rc, out = run_gate([bad, "--verify"], ledger)
        check("verify stale-sums fixture exits 1", rc == 1, f"rc={rc}\n{out}")
        check("stale-sums failure names the VERIFY check",
              "VERIFY: FAIL" in out and "checksum mismatch" in out)

        # 5. Empty fixture: zero-byte artifact -> FAIL, names INTEGRITY.
        empty = os.path.join(tmp, "empty")
        shutil.copytree(os.path.join(FIXTURES, "empty"), empty)
        rc, out = run_gate([empty], ledger)
        check("seal empty-artifact release exits 1", rc == 1, f"rc={rc}\n{out}")
        check("empty-artifact failure names the INTEGRITY check",
              "INTEGRITY: FAIL" in out)

        # 6. Missing --expect artifact -> FAIL, names EXPECTED.
        good2 = os.path.join(tmp, "good2")
        shutil.copytree(os.path.join(FIXTURES, "good"), good2)
        rc, out = run_gate([good2, "--expect", "no-such-file.bin"], ledger)
        check("seal with missing expected artifact exits 1", rc == 1, f"rc={rc}\n{out}")
        check("missing-artifact failure names the EXPECTED check",
              "EXPECTED: FAIL" in out)

        # 7. VERIFY a directory that was never sealed -> FAIL, names VERIFY.
        rc, out = run_gate([good2, "--verify"], ledger)
        check("verify unsealed release exits 1", rc == 1, f"rc={rc}\n{out}")
        check("unsealed failure names the VERIFY check", "VERIFY: FAIL" in out)

        # 8. The ledger is hash-chained: each entry's prev is the SHA-256
        #    of the previous raw line, GENESIS for the first.
        with open(ledger, "rb") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        chain_ok = len(lines) >= 7
        prev = "GENESIS"
        for ln in lines:
            entry = json.loads(ln)
            if entry.get("prev") != prev:
                chain_ok = False
                break
            prev = hashlib.sha256(ln).hexdigest()
        check("ledger hash-chain verifies", chain_ok,
              f"{len(lines)} entries")

        passed = sum(1 for _, ok in RESULTS if ok)
        print(f"\nSELF-TEST: {passed}/{len(RESULTS)} checks passed")
        return 0 if passed == len(RESULTS) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
