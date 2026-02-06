# DevVault CLI Contract (v0.1)

This document freezes the public CLI interface implemented by `devvault/cli.py`.
Internal refactors must not break this contract.

## Commands

### devvault scan
Scan for development projects.

Usage:
- devvault
- devvault scan [roots ...] [--json] [--depth N] [--limit N] [--top N] [--include TEXT] [--output PATH]

Arguments:
- roots: directories to scan (default: ~/dev)

Options:
- --json: output results as JSON
- --depth N: max scan depth (default: 4)
- --limit N: display limit for human output formatting (default: 30)
- --top N: only include N most recently modified projects (0 = all; default: 0)
- --include TEXT: filter projects by substring match against path
- --output PATH: write output to file instead of stdout

Backwards-compat behavior:
- `devvault` defaults to `devvault scan`
- `devvault <roots...>` becomes `devvault scan <roots...>`
- real subcommands like `devvault backup ...` remain unchanged

Output:
- Human mode: may print a short status line before results.
- JSON mode: prints JSON only to stdout.
- If `--output PATH` is set, output is written to the file and a status line is printed to stdout:
  - scan always prints: `Wrote report to: <PATH>`

---

### devvault backup
Create a snapshot backup.

Usage:
- devvault backup <source_root> <backup_root> [--dry-run] [--json] [--output PATH]

Arguments:
- source_root: directory to back up
- backup_root: destination root where snapshots are created

Options:
- --dry-run: plan only; do not write any data
- --json: output results as JSON
- --output PATH: write output to file instead of printing to stdout

Output:
- Human mode: prints a short summary (backup id/path/dry-run)
- JSON mode: prints JSON only to stdout
- If `--output PATH` is set:
  - in JSON mode: writes JSON to file and prints nothing
  - in human mode: writes text to file and prints: `Wrote report to: <PATH>`

---

### devvault restore
Restore a snapshot into an empty destination directory.

Usage:
- devvault restore <snapshot_dir> <destination_dir> [--json] [--output PATH]

Arguments:
- snapshot_dir: snapshot directory to restore from
- destination_dir: empty destination directory to restore into

Options:
- --json: output results as JSON
- --output PATH: write output to file instead of printing to stdout

Output:
- Human mode: prints a short completion summary
- JSON mode: prints JSON only to stdout
- If `--output PATH` is set:
  - in JSON mode: writes JSON to file and prints nothing
  - in human mode: writes text to file and prints: `Wrote report to: <PATH>`

---

### devvault verify
Verify a snapshot without restoring.

Usage:
- devvault verify <snapshot_dir> [--json] [--output PATH]

Arguments:
- snapshot_dir: snapshot directory to verify

Options:
- --json: output results as JSON
- --output PATH: write output to file instead of printing to stdout

Output:
- Human mode: prints a short completion summary
- JSON mode: prints JSON only to stdout
- If `--output PATH` is set:
  - in JSON mode: writes JSON to file and prints nothing
  - in human mode: writes text to file and prints: `Wrote report to: <PATH>`

## Exit codes
- 0: success
- 1: runtime error (DevVault raised a RuntimeError)
- 2: usage / invalid input (argparse / CLI parsing)

## Output rules
- Errors are written to stderr.
- When `--json` is used *without* `--output`, stdout contains JSON only.
- With `--output`, stdout may include a human status line depending on the command (documented above).
