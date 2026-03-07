
## Completed (2026-03-02)
- [x] Stripe webhook end-to-end (TEST): checkout.session.completed -> subscription lookup -> DDB license issuance -> Zoho SMTP email sent
- [x] IAM fix: Lambda role permitted to read Stripe API key secrets in Secrets Manager (test+live ARNs)


## 2026-03-06 — DevVault Desktop Core Pipeline Verified

Completed:

✔ Backup Engine (preflight → confirm → execute → finalize)  
✔ Snapshot storage system (.devvault)  
✔ Snapshot index generation + rebuild  
✔ Restore system validation  
✔ Scanner project detection  
✔ Backup queue execution  
✔ Vault drive selector UI  

Status:
DevVault core functionality **operational and verified**.

Next Phase:
Scanner UX + operator workflow improvements.



## DevVault Development Checklist

### Core Backup Engine
- [x] Preflight system (file count / bytes / symlink detection)
- [x] Operator confirmation step
- [x] Backup execution pipeline
- [x] Atomic snapshot finalize
- [x] Incomplete snapshot recovery on startup
- [x] Manifest HMAC key initialization
- [x] Filesystem adapter abstraction
- [x] Windows atomic rename fix (os.replace)
- [x] Snapshot index generation
- [x] Snapshot index rebuild after backup

### Restore System
- [x] Snapshot discovery from index
- [x] Restore snapshot selector UI
- [x] Restore destination validation
- [x] Snapshot restore execution
- [x] Multiple snapshot restore support
- [x] Restore logging + result reporting

### Snapshot Storage
- [x] .devvault vault root structure
- [x] Snapshot directory structure
- [x] Snapshot naming format
- [x] Snapshot index file
- [x] Snapshot index rebuild tool

### Scanner System
- [x] Workspace scan roots
- [x] Project detection logic
- [x] Unprotected project detection
- [x] Operator warning prompt
- [x] Queue backup execution
- [x] Sequential backup processing

### Desktop UI (Qt)
- [x] DevVault main window
- [x] Locks background + watermark
- [x] Operation overlay system
- [x] Backup / Restore buttons
- [x] Scan button
- [x] Vault drive selector dropdown
- [x] Centered drive selector text
- [x] Snapshot restore dropdown
- [x] Backup location display
- [x] UI busy state protection

### Remaining Work

#### Scanner UX
- [ ] Scan results panel
- [x] Select / deselect projects before backup
- [x] Improve scan warning UX

#### Backup Queue UX
- [ ] Show queued backup progress
- [ ] Display current backup progress
- [ ] Queue completion summary

#### Snapshot UX
- [ ] Cleaner snapshot labels
- [ ] Sort snapshots newest → oldest

#### Vault Safety
- [ ] Detect vault drive disconnect
- [ ] Operator warning for vault removal

#### Operator Safety
- [ ] Cancel reliability during backups

## 2026-03-06 — Scanner UX Expansion Checkpoint

Completed:

✔ OneDrive-aware scan roots added for redirected user folders  
✔ Large data-folder detection added for Pictures / Videos / Downloads subfolders  
✔ Archive detection added for .zip / .7z / .rar / .tar / .gz / .bz2 / .xz (10 MB minimum)  
✔ Scan selection dialog now explains projects, data folders, and archive files  
✔ Large-folder zip suggestion popup added for high-file-count non-project folders  
✔ Scan results grouped into Projects / Data Folders / Archives  
✔ Scan dialog now displays folder file counts and archive sizes  

Status:
Scanner UX is now materially expanded beyond repo-only discovery and supports real operator data protection workflows.

### DevVault Licensing System — COMPLETE

✔ dvlic.v2 license format  
✔ Ed25519 signature verification  
✔ Runtime license state engine  
✔ Grace + Restricted logic  
✔ License install UI  
✔ Startup license state display  
✔ Backup enforcement gates  
✔ Scan queue enforcement fix  
✔ Tamper-resistance sanity check passed

Status: Ready for launch stage.
