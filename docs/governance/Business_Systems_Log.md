# TSW Technologies LLC — Business Systems Log

Purpose:
Document all active business systems, SaaS platforms, cloud services,
governance controls, and operational infrastructure used by
TSW Technologies LLC.

This is NOT a decision log.
This is a living systems inventory.

---

# LEGAL & STRUCTURAL BASELINE

Entity: TSW Technologies LLC  
State: Alabama  
Structure: Single-Member LLC  
Managing Member: Braden Turner  

EIN: Issued (CP575 on file)  
EIN SHA256: D4EC144EAF81341D6FD091F748D113104C6EF5E06E6311EF63ECFA4B11C059E1  

Primary NAICS: 541511 — Custom Computer Programming Services  

Brand: Trustware Technologies  
Master Logo Version: v1.0  
Master SHA256: 2D8FE55A1DB1A5A2BDDF974699FC6739F886C286789AC96D8C01A6BBA1F1D061  

---

# CLOUD & INFRASTRUCTURE

## 2026-02-26 — AWS Account Baseline Established

Service: Amazon Web Services (AWS)  
Primary Region: us-east-1 (N. Virginia)  

Root Account:
- MFA Enabled
- Stored offline
- Not used for workloads

Primary Admin:
- IAM User: tsw-admin
- MFA enforced
- Used for operational deployment

Security Baseline:
- CloudTrail (multi-region)
- GuardDuty enabled
- Security Hub enabled
- Budget alerts active
- Cost Anomaly Detection active

Purpose:
License automation infrastructure for DevVault.

Services Used:
- API Gateway
- Lambda
- DynamoDB
- Secrets Manager
- KMS
- SES
- CloudWatch
- CloudTrail

Status:
Stage 2 Webhook MVP Operational (Sandbox)

---

# PAYMENT SYSTEMS

## 2026-02-26 — Stripe Activated (Sandbox)

Service: Stripe  
Purpose: Payment processing for DevVault annual subscriptions  
Mode: Sandbox  

Product:
DevVault — $99/year recurring

Webhook Events Active:
- checkout.session.completed
- invoice.paid

Status:
Webhook → Lambda → DynamoDB → SES flow operational.


## 2026-02-27 — Stripe Activated (Live)

Service: Stripe  
Purpose: Payment processing for DevVault annual subscriptions  
Mode: Live (payouts pending verification review)

Payouts:
- Bank: Relay Income
- Schedule: Daily

Product:
DevVault — $99/year recurring

Stripe Tax:
- Automatic Tax enabled (monitoring)
- Default product tax code: Downloadable Software — business use (txcd_10202003)

Status:
Payments enabled; payouts pending Stripe verification approval.
---

# EMAIL INFRASTRUCTURE

## 2026-02-27 — Operational Email Provider

Primary Provider: Zoho Mail  
Domain: trustware.dev  

Role-Based Mailboxes Active:
- no-reply@trustware.dev
- security@trustware.dev
- admin@trustware.dev
- infra@trustware.dev
- legal@trustware.dev
- licensing@trustware.dev
- support@trustware.dev
- billing@trustware.dev
- privacy@trustware.dev
- sales@trustware.dev

Purpose:
Operational separation, delegation readiness, brand authority.

Note:
Zoho used during early growth phase.
Future migration possible when scale requires.

---

## 2026-02-27 — SES Domain & Identity Verified

Service: Amazon SES  
Domain: trustware.dev  
Mode: Sandbox  

Sender Email: licensing@trustware.dev  
Reply-To: support@trustware.dev  

DKIM: Configured  
Webhook signature verification: Enforced  

Deliverability:
Functional (spam classification expected until production access granted).

---

# DNS & WEB

## 2026-02-26 — Cloudflare Authority

Service: Cloudflare  

DNS:
- trustware.dev managed via Cloudflare DNS
- SES DKIM records hosted in Cloudflare
- Future security rules configurable

Hosting:
- Cloudflare Pages
- Landing page live
- Landing page live (initial)
- Policy pages stabilized under clean URLs on 2026-02-27 (/privacy, /terms)

Status:
Active

---

# BANKING

## 2026-02-27 — Relay Financial (Approved)

Service: Relay Financial  
Purpose: 4-Account financial discipline model  

Accounts:
- Income
- Operating
- Tax Reserve
- Profit Hold
- Infrastructure RD

Allocation Policy:
25 / 5 / 25 / 45

Automation:
- Daily Profit First auto-transfer rule active
- Keep $0 in Income
- Allocation policy enforced automatically

Status:
Active (Approved)
---

# SECURITY POSTURE SNAPSHOT

As of 2026-02-27:

- AWS MFA enforced (root + admin)
- Stripe 2FA enabled
- Cloudflare secured
- Zoho Mail secured
- SES DKIM configured
- Stripe webhook signature validation enforced
- DynamoDB idempotency enforced (license_id key)

Operational maturity level:
Early-stage production capable (sandbox).

---

System Classification:
Pre-Revenue Infrastructure Build Phase

## 2026-02-27 — trustware.dev deployment stabilized (Cloudflare Pages)
- Resolved non-updating site by removing conflicting Cloudflare projects and recreating a single Pages project connected to GitHub (kalikills/trustware.dev, branch main).
- Verified production updates via curl checks (root HTML, asset MIME types).
- Confirmed canonical routing: /index.html → / (301).
- Confirmed logo renders and serves as image/png from /assets/logo/trustware-logo.png.
- Added and deployed Privacy + Terms pages; confirmed clean URLs live:
  - /privacy (200)
  - /terms (200)
  - /devvault (200)
- Repo hygiene: ignored local backup files and removed temporary deploy marker after verification.



## 2026-02-28 — Local Development Preview Server (Standardized)

System: Python Built-in HTTP Server  
Command:
  cd C:\Users\Lboyb
  python -m http.server 15000

Purpose:
- Local beta preview of trustware.dev before Cloudflare deployment
- Zero caching conflicts
- No Windows HTTP.sys port reservation issues
- Lightweight, industry-standard static preview method

Status:
Active (Development Only)


## 2026-02-28 — Developer Preview Command Automation

System: PowerShell Profile Command (webstart)

Function:
- One-command launch of local preview server
- Auto browser open
- Zero custom HTTP infrastructure
- Python http.server backend

Purpose:
- Frictionless beta validation before Cloudflare deployment
- Standardized internal development workflow

Status:
Active


## 2026-02-28 — Trustware.dev Public Surface Stabilized

- Header navigation converted to product-first model:
  Products | Architecture | Security | Company | Docs
- Footer standardized across all pages:
  Privacy · Terms · Contact
- Converted anchor-based navigation to directory-based routing:
  /architecture/
  /security/
  /company/
  /docs/
  /privacy/
  /terms/
  /contact/
- Unified watermark rendering globally via CSS (fixed background)
- Removed legacy hero pseudo-element watermark
- Added subtle scroll reveal animation (non-blocking, CSS-based)
- Tightened section spacing for subpages
- Expanded subpages with structured content blocks (cards + key/value layout)

Status: Public marketing surface structurally complete.
## 2026-03-02 — DevVault Transactional Email Delivery Standardized on Zoho SMTP

SES:
- SES production access request denied by AWS Trust & Safety (deliverability risk for new sender profile).
- SES remains available for sandbox/testing only.

Zoho SMTP (Production Delivery Path):
- Delivery path: Stripe LIVE webhook → Lambda → DynamoDB → Zoho SMTP → Customer inbox
- Secret: devvault/zoho_smtp (Secrets Manager)
- Lambda env var: ZOHO_SMTP_SECRET_NAME=devvault/zoho_smtp
- IAM: Lambda execution role allowed secretsmanager:GetSecretValue for devvault/zoho_smtp
- From: licensing@trustware.dev (Zoho “Send mail as” enabled)
- Reply-To: support@trustware.dev
- Status: Active (production)
## 2026-03-02 — Launch Hardening Phase Activated

Status:
- Entered operator-mode hardening for DevVault production launch.

Planned hardening sequence:
1) CloudWatch alarm for SMTP failures and Lambda errors
2) DynamoDB email_status tracking for license delivery
3) Stripe payout + Relay allocation validation (25/5/25/45)
4) IAM least privilege review on Lambda execution role
5) Website finalization: DevVault About page with screenshots + walkthrough

## 2026-03-02 — Production SMTP Failure Monitoring Enabled

- CloudWatch metric filter monitors SMTP send failures in production Lambda.
- Alarm configured for immediate notification (>=1 failure in 5 minutes).
- SNS topic DevVault-Alerts sends to admin@trustware.dev.
- Monitoring validated with controlled failure injection.

Status: Active.

## 2026-03-02 — DevVault revenue pipeline validated (Stripe -> AWS -> email delivery)
- Validated Stripe Checkout subscription flow driving automated license issuance:
  - Event: evt_1T6kI249uHKcWjOjiYDgPkNt (test)
  - Subscription: sub_1T6kI049uHKcWjOjkGCt4O6Q
  - License issued: 03179549f7adfc71acd24253d2340f04
  - Seats: 10, Plan: core, Term: annual
- Confirmed end-to-end delivery: license email sent and received; system records email_status=sent.

Operational hardening / governance:
- Resolved Lambda permission gap to Secrets Manager for Stripe API key retrieval by adding explicit role policy.
- Increased webhook Lambda resources for reliability during external calls (Stripe + SMTP).

### Explicit IAM Resources (Stripe Secret Keys)
Policy Name: DevVault-StripeSecretKeysRead
Role: DevVault-StripeWebhook-LambdaRole
Region: us-east-1
Account: 692829982768

Allowed Actions:
- secretsmanager:GetSecretValue
- secretsmanager:DescribeSecret

Allowed Resources:
- arn:aws:secretsmanager:us-east-1:692829982768:secret:stripe/secret_key_test-jcK1M8
- arn:aws:secretsmanager:us-east-1:692829982768:secret:stripe/secret_key_live-LznPyv

Purpose:
- Permit webhook runtime to retrieve Stripe API keys required for subscription lookup and entitlement issuance.
- Scoped strictly to required secrets to maintain least-privilege posture.


## 2026-03-02 — Stripe Seat-Based Subscription Model Activated


Product Model:
DevVault (Recurring Annual Subscription)


Tiers:
- Core — $249 / seat / year
- Pro — $499 / seat / year
- Business — $999 / seat / year


Seat Authority:
- Stripe subscription item quantity is source-of-truth.
- Webhook performs Stripe API lookup with secret key.


Webhook Enhancements:
- Idempotent license issuance.
- Duplicate resend protection.
- Seats persisted in DynamoDB.
- Seats embedded in signed .dvlic payload.


Status:
Validated in test mode; production-ready.

## 2026-03-02 — Stripe Webhooks (LIVE) Aligned to Prod Lambda + Secrets Manager
- LIVE webhook endpoint: we_1T5b9W49uHKcWjOjdBVCWCOK -> Lambda URL (us-east-1)
- Enabled events: checkout.session.completed only
- Signing secret stored in Secrets Manager and referenced by Prod Lambda via STRIPE_WEBHOOK_SECRET_ARN
## 2026-03-03 — Lambda IAM Tightened to Exact Secret ARNs (Least Privilege)
- Updated attached policy DevVault-StripeWebhook-LambdaPolicy default version to v4.
- Secrets Manager access narrowed from wildcard patterns to exact ARNs:
  - stripe/webhook_signing_secret_live-Sen7ro
  - devvault/license_signing_secret_prod-p6eHNw
  - devvault/zoho_smtp-lhCJH9
  - stripe/secret_key_live-LznPyv
- DynamoDB permissions unchanged (DevVault-License-Ledger + indexes only).

## 2026-03-03 — trustware.dev Local Preview Incident & Recovery

Issue:
- Homepage (index.html) was overwritten by an older variant during cross-chat edits.
- webstart command disappeared due to incorrect PowerShell profile path (OneDrive profile active).

Impact:
- Local preview served incorrect layout.
- Temporary operational confusion.

Resolution:
- Restored index.html from index.html.bak_anim (last known stable state).
- Repaired footer links (Privacy · Terms · Contact).
- Re-created webstart in active PS7 profile:
  C:\Users\Lboyb\OneDrive\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
- Created timestamped production backups in:
  C:\Trustware\Backups

Backups Created:
- trustware-site-2026-03-03_0054.zip
- trustware-site-2026-03-03_0056.zip

Status:
System restored and hardened.


## 2026-03-03 — Relay 4-Account Structure Verified
- Verified Relay accounts exist: Income (Checking), Operating (Checking), Tax Reserve (Savings), Profit Hold (Savings), Infrastructure R&D (Checking)
- Screenshot captured as verification evidence
- Status: ACTIVE
- Logged at: 2026-03-03 13:10:07

## 2026-03-03 — Desktop backup/restore hardened (scanner engines)
- Replaced Desktop GUI backup path from CLI runner execution to direct engine calls:
  - Backup: scanner.backup_engine.BackupEngine via scanner.adapters.filesystem.OSFileSystem
  - Restore: scanner.restore_engine.RestoreEngine via OSFileSystem
- Added backup preflight in GUI (counts/bytes/symlink policy/unreadables) + operator confirmation gate.
- Split workers:
  - _BackupPreflightWorker (preflight only)
  - _BackupExecuteWorker (execute only)
- UI threading stabilized:
  - Confirmation shown via QTimer.singleShot(0, ...) to prevent flash-close / thread-context issues.
- Restore safety improved:
  - Refuses non-empty destination
  - Added OneDrive destination warning + second confirmation (sync/lock risk).
- Noted field issue: Vault drive disconnect can raise WinError 121 during backup staging (.incomplete-*).
- Outstanding UX issue: QMessageBox confirm dialog still renders too vertical; needs custom QDialog (wide layout, scrollable details, shows vault capacity/free space).


## 2026-03-04 — DevVault Desktop Qt: Backup preflight/execute wiring restored + stabilized
- Restored/validated Qt Desktop backup flow using scanner engines directly:
  - Preflight: BackupEngine(OSFileSystem()).preflight(BackupRequest(...))
  - Execute:  BackupEngine(OSFileSystem()).execute(BackupRequest(...))
- Preflight summary shown to operator before execute:
  - file count, total bytes, symlinks skipped, unreadables + samples
  - vault disk usage displayed (total/free) using disk_usage on pending vault path
- Worker/thread model:
  - _BackupPreflightWorker in QThread
  - _BackupExecuteWorker in QThread after operator confirmation
  - Confirmation scheduled on UI thread (prevents focus/flash-close issues)
- Thread lifecycle hardened after observing shutdown errors:
  - Removed blocking waits from UI handlers
  - Cleanup now occurs on thread.finished via cleanup hooks
- Verified end-to-end backups complete successfully; operator-decline path returns UI to idle.

Outstanding:
- Confirmation dialog still uses QMessageBox; later UX upgrade can move to custom wide QDialog.



## 2026-03-05 — Company Documentation Hygiene (Operational Control)

- Canonical governance docs remain in C:\Trustware\Company (no root .bak files).
- Backups stored in hidden C:\Trustware\Company\_bak with auto-prune (Keep=30).
- Temporary artifacts stored in hidden C:\Trustware\Company\_artifacts.
- Infrastructure artifacts stored in C:\Trustware\Company\infra.
- PowerShell profile (PS7 OneDrive) standardized with helper functions to enforce this workflow.

### Addendum — 2026-03-05 (Profile Baseline + Safety Guard)

- Enforced stable PS7 profile baseline for Trustware helper functions (prevents profile corruption/duplication issues).
- Edit-CompanyLog hardened:
  - Accepts filename-only when operating in Company folder
  - Refuses any path outside C:\Trustware\Company


### Addendum — 2026-03-05 (DevVault Operator Command)

Standardized DevVault operator launch helper:

dvstart → cd C:\dev\devvault; python -m devvault_desktop

Purpose:
- Prevents path mistakes when launching DevVault
- Establishes a consistent operator workflow
- Used during DevVault desktop development and validation


## 2026-03-05 — DevVault removable-drive disconnect handling validated

- Verified operator-safe refusal when vault media is unplugged during backup execution.
- UI now surfaces a clear backup failure popup:
  - Vault drive disconnected during backup.
- Removed prior ambiguous operator-facing symptom:
  - [Errno 22] Invalid argument
- Business impact: improves customer safety, reduces ambiguity during backup media failure, and hardens DevVault desktop behavior for real-world USB/external-drive usage.

## 2026-03-05 — PowerShell Operator Convenience: dvstart Command Added

- Added `dvstart` to PowerShell 7 profile to launch DevVault quickly:
  - Starts DevVault from `C:\dev\devvault` using `python -m devvault_desktop`
  - Implemented as a profile function for repeatable operator workflow

## 2026-03-05 — DevVault Desktop Backup Cancel Reliability Improved

### Operational change
DevVault desktop backup cancellation now uses a real engine-integrated cancel path instead of UI-only interruption behavior.

### Outcome
- Operator can cancel backup execution without the prior full-run continuation behavior.
- No finalized backup snapshot is left after cancel.
- Cancellation logging is cleaner and operator-facing.
- Scan UI button exists but is not yet wired to a live action.

## 2026-03-07 — DevVault Licensing Distribution

Customer licenses obtained via:

https://trustware.dev/

License installation paths supported by DevVault:

• C:\ProgramData\DevVault\license.dvlic  
• %APPDATA%\DevVault\license.dvlic  

Format: dvlic.v2  
Signature: Ed25519  
Verification: embedded public key in devvault/licensing.py
