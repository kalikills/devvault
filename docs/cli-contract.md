# DevVault CLI Contract (v0.1)

This document freezes the public CLI interface. Internal refactors must not break this contract.

## Commands
- devvault scan [roots ...] [--json] [--depth N] [--limit N] [--top N] [--include TEXT] [--output PATH]
- devvault snapshot <path> --dest <vault_dir> [--label TEXT] [--json]
- devvault report <path> [--format text|json]
- devvault verify --dest <vault_dir> [--json]
- devvault restore --dest <vault_dir> --to <path> [--snapshot <id>] [--json]

## Output rules
- Default: human-readable text to stdout
- Errors to stderr
- --json outputs JSON only (no logs mixed into stdout)

## Exit codes
- 0: success
- 2: usage / invalid input
- 3: scan or snapshot failed (runtime error)
- 4: verify failed (integrity mismatch)
- 5: restore failed
