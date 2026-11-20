# release-gate

A fail-closed release gate: one small Python script that decides whether a
directory of release artifacts is fit to publish — and refuses, loudly and
with an itemized reason, when anything is off.

## What it does

Given a directory containing a release (binaries, archives, installers —
any files), the gate runs five checks:

1. **SCAN** — the directory exists and contains at least one artifact.
2. **INTEGRITY** — no artifact is zero bytes (a truncated or placeholder
   upload fails here).
3. **EXPECTED** — every artifact named with `--expect` is present.
4. **SEAL** — SHA-256 hashes of every artifact are written to `SHA256SUMS`
   inside the release directory.
5. **VERIFY** (with `--verify`) — every artifact is re-hashed and compared
   against the sealed `SHA256SUMS`. A changed byte, a missing file, or a
   file that was never sealed is a failure.

Every run — pass or fail — is appended to a hash-chained ledger
(`gate-ledger.jsonl`): each entry records the SHA-256 of every artifact and
chains to the previous entry, so a PASS is bound to the exact bytes that
were checked. Change one byte afterwards and the old PASS no longer
describes the release; verify mode will fail, and the ledger shows both
runs.

## Why fail-closed

Most release checklists fail *open*: a step that errors, times out, or is
skipped quietly counts as done. This gate fails *closed*:

- There is **no override flag**. No `--force`, no `--skip-checks`.
- A check that throws an error is recorded as a FAIL, not skipped.
- Sealing is refused if any earlier check failed.
- The exit code is the contract: `0` means every check ran and passed,
  `1` means **do not publish**.

If the gate cannot prove the release is good, it says the release is bad.
That is the whole design.

## Requirements

Python 3, standard library only. Nothing to install — copy
`release_gate.py` anywhere and run it.

## Usage

Seal a release (run before publishing):

```
python3 release_gate.py ./release-1.2.0 \
    --expect app-linux.tar.gz --expect app-windows.zip
```

Verify a release against its seal (run after downloading, mirroring, or
any time the bytes may have changed):

```
python3 release_gate.py ./release-1.2.0 --verify
```

Options:

- `--expect NAME` — artifact that must be present; repeatable.
- `--verify` — verify against `SHA256SUMS` instead of sealing.
- `--sums-name NAME` — checksum file name (default `SHA256SUMS`).
- `--ledger PATH` — ledger location (default: `gate-ledger.jsonl` beside
  the script).

## Worked example

```
$ python3 release_gate.py ./my-release --expect app-linux.tar.gz --expect app-windows.zip
RELEASE GATE v1.0 — SEAL — /path/to/my-release
  SCAN: PASS
  INTEGRITY: PASS
  EXPECTED: PASS
  SEAL: PASS
  sha256 beef56d69d6f6aad…  app-linux.tar.gz
  sha256 3cc7202f22b94a9a…  app-windows.zip
VERDICT: PASS — ledger entry #1 (hash-chained) in gate-ledger.jsonl
```

One byte is appended to `app-linux.tar.gz` afterwards — a corrupted or
replaced download — and verify catches it:

```
$ python3 release_gate.py ./my-release --verify
RELEASE GATE v1.0 — VERIFY — /path/to/my-release
  SCAN: PASS
  INTEGRITY: PASS
  VERIFY: FAIL
  sha256 d851c003df7447c6…  app-linux.tar.gz
  sha256 3cc7202f22b94a9a…  app-windows.zip
  detail: VERIFY: app-linux.tar.gz: checksum mismatch
VERDICT: FAIL — ledger entry #3 (hash-chained) in gate-ledger.jsonl
```

(exit code 1 — the release does not ship.)

## Exit codes

| Code | Meaning |
| ---- | ------- |
| `0`  | PASS — every check ran and passed; the release is sealed / verified. |
| `1`  | FAIL — do not publish. The output names each failed check and why. |

## Tests

```
python3 tests/self_test.py
```

Runs the gate against the fixture releases in `tests/fixtures/` (a good
release, a release whose checksums no longer match, and a zero-byte
artifact) and asserts the exit codes, the named failed checks, and the
ledger hash-chain. Fixtures are copied to a temporary directory first, so
the test never modifies this repository.

## License

MIT — see [LICENSE](LICENSE).

## Part of the Nova Ops shelf

release-gate is one tool on the [Nova Ops](https://github.com/elias-hivemind)
shelf — local-first tools, verified working before they are trusted:

- **[Elias HiveMind](https://github.com/elias-hivemind/obsidian-elias-hivemind)** —
  an Obsidian plugin for offline summaries, tags, links, and digests.
  No API key, no account, no telemetry.
- **[nova-ops-nim-mcp](https://github.com/elias-hivemind/nova-ops-nim-mcp)** —
  an MCP server for NIM video generation, built for MCP clients.

---

Built by **Nova Ops** — local-first tools that run on your own machine,
verified working before they are trusted.
