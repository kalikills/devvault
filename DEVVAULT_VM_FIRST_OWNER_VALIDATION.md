# DevVault — First Owner VMware Validation Checklist

## Purpose
Validate that a brand-new paying customer (owner) can complete full DevVault setup on a clean machine using only onboarding credentials and UI.

This is the launch authority test.

---

# PASS CRITERIA

The flow must succeed WITHOUT:

- Manual file edits
- Pre-seeded identity
- Local owner fallback
- Token workaround
- Developer intervention

---

# PHASE 0 — CLEAN ENVIRONMENT

## Requirements
- Fresh Windows VM
- No prior DevVault install state
- No copied configs from host
- Dedicated VMware NAS share

## Verify
Test-Path "$env:APPDATA\DevVault"
Test-Path "C:\ProgramData\DevVault"

Expected:
- No business identity present

---

# PHASE 1 — PURCHASE / PROVISIONING

## Action
- Trigger new Stripe purchase

## Expected
- Customer created
- Subscription created
- Fleet created
- Owner onboarding email sent

## Verify email contains:
- Owner email
- Temporary password
- Install instructions

---

# PHASE 2 — INSTALL DEVVAULT

## Action
- Install DevVault on VM

## Expected
- App launches clean
- No pre-existing business state
- Business UI accessible

---

# PHASE 3 — FIRST OWNER SIGN-IN

## Action
- Sign in using:
  - Email from onboarding
  - Temporary password

## Expected
- Sign-in succeeds
- If required:
  - Forced password reset prompt appears
  - Permanent password can be set

## Result
- Valid business admin session established

---

# PHASE 4 — NAS SETUP

## Action
- Navigate to NAS configuration
- Enter VMware NAS path
- Perform NAS login

## Expected
- Credentials validated (not blind save)
- NAS structure initialized (.devvault)
- App restarts if required

---

# PHASE 5 — OWNER SEAT ACTIVATION

## Action
- Activate/enroll this machine as owner seat

## Expected
- Seat activation succeeds
- Seat is active server-side
- Seat visible in Business Console

---

# PHASE 6 — SYSTEM VALIDATION

## Verify:

### Dashboard
- Seats Used is correct
- NAS status correct
- Protection status correct

### Seat Management
- Owner seat visible
- Status = active
- Role = owner

### Admin Tools
- Accessible
- No authorization errors

### Backup / Protection
- Can detect unprotected state
- Can run backup

### Session Behavior
- Sign out works
- Sign in works again
- No stale sessions

---

# FAIL CONDITIONS

Any of the following = FAILURE:

- Password login fails on clean machine
- Password reset cannot be completed
- Requires seat token to complete initial setup
- Requires local owner fallback before seat activation
- Requires manual config edits
- Seat activation depends on pre-existing identity
- Dashboard inconsistent after setup

---

# REQUIRED LAUNCH TRUTH

A brand-new paying owner must be able to complete setup using only:

- Onboarding email
- Temporary password
- DevVault UI
- NAS configuration
