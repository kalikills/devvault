# DevVault

DevVault is a fast command-line tool that scans your machine for development projects, estimates backup size, and highlights risk signals like missing version control.

Built for developers who want a quick answer to:

> "What do I actually need to back up?"

---

## Features

- 🔍 Automatically detects development projects  
- 💾 Estimates total backup size (excluding git + environments)  
- ⚠️ Flags projects without version control  
- 📄 Export reports to text or JSON  
- 🎯 Filter results and show most recent projects  
- ⚡ Fast recursive scanning  

---

## Installation

Clone the repo and install in editable mode:

```bash
pip install -e .
```

This will expose the CLI:

```bash
devvault
```

---

## Usage

### Scan your default dev folder
```bash
devvault ~/dev
```

### Export a report
```bash
devvault ~/dev --output report.txt
```

### Write JSON for automation
```bash
devvault ~/dev --output report.json
```

(JSON is automatically selected when using `.json`.)

### Show only the most recent projects
```bash
devvault ~/dev --top 5
```

### Filter by name
```bash
devvault ~/dev --include scanner
```

---

## Why DevVault Exists

Most developers assume they know what needs backing up — until they lose something.

DevVault gives you a fast, high-level backup plan in seconds.

No guesswork.

---

## Requirements

- Python 3.10+

---

## License

PolyForm Strict License 1.0.0
# devvault
# devvault
