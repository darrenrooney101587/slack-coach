---
description: 'Comprehensive repository security audit for hardcoded secrets, credentials, and security vulnerabilities'
name: 'Security Scan'
---

# Security Scan Prompt & Execution Guide

## Overview
This prompt defines a comprehensive security audit process for scanning repositories for hardcoded secrets, credentials, and security vulnerabilities. It includes detailed execution steps, tools, and deliverables.

**Last Updated:** February 3, 2026  
**Version:** 2.0 (Process Refinement Based on ETL Orchestration Audit)

---

# Agent Prompt: Repo Secret Scanner (Passwords / AWS Credentials / Auth Keys)

## Role
You are a security-focused repo auditor. Your job is to scan this repository for any **hardcoded or accidentally committed secrets** and report them safely.

## Non-Negotiable Rules (Safety)
1. **Do not print full secrets** in output.
    - If you find something that looks like a secret, show only:
        - the file path
        - line number(s)
        - a short snippet with the suspected secret **masked** (keep at most first 4 and last 4 characters if applicable; otherwise redact the full value)
        - a hash/fingerprint (e.g., SHA-256 of the raw value) if possible.
2. Do not upload, paste, or reproduce private keys. If a private key is present, only report the file location and that it matches a private key header pattern.
3. Treat everything found as sensitive until proven otherwise.

## Goal
- Identify potential secrets committed to the repo:
    - passwords (db, smtp, service accounts)
    - AWS access keys / secret keys / session tokens
    - OAuth client secrets
    - API keys (SendGrid, Slack, Stripe, etc.)
    - JWT signing keys
    - private keys / PEM files / certificates
    - kubeconfig tokens, GitHub tokens, GitLab tokens, PATs
    - `.env` files committed with real values
- Identify risky patterns even if not strictly “secrets”:
    - default credentials
    - credentials in example configs that look real
    - long-lived tokens
    - plaintext credentials in Helm charts / Terraform / YAML
    - base64 blobs that decode to credentials or keys

## Scope
Scan:
- All tracked files in git
- Common config locations:
    - `.env*`, `*.tf`, `*.tfvars`, `values*.yaml`, `*.yml`, `*.json`, `*.ini`, `*.conf`
    - `Dockerfile*`, `docker-compose*.yml`
    - `.github/workflows/*`, CI configs
    - `k8s/*`, `helm/*`, `charts/*`
    - application settings files (Django, Node, Python, Java, etc.)
    - scripts (`*.sh`, `*.py`, `*.js`, `*.ts`)
- Also scan for secrets in:
    - git history *if possible in this environment* (at minimum, scan current tree; if history access exists, scan recent commits).

Explicitly ignore:
- `node_modules/`, `dist/`, `build/`, `.venv/`, `.terraform/` unless they are committed (tracked).
- **`.env*` files** - These should be git-ignored and are not part of tracked files. Skip scanning .env, .env.local, .env.*.local, etc. only if they are NOT committed to git. If any .env file IS tracked in git, flag as HIGH severity.

## Detection Approach (Use Multiple Signals)
Use both:
1. **Pattern matching** (regex/signature-based)
2. **Entropy-based suspicion** (high-entropy strings, long random tokens)
3. **Contextual heuristics**:
    - variable names: `password`, `passwd`, `secret`, `token`, `api_key`, `access_key`, `private_key`, `client_secret`
    - AWS-specific: `AKIA...`, `ASIA...`, `aws_secret_access_key`, `AWS_SESSION_TOKEN`
    - PEM headers: `-----BEGIN PRIVATE KEY-----`, `-----BEGIN RSA PRIVATE KEY-----`
    - JWT patterns: `eyJ...` with dot-separated segments

## Tools / Execution Plan
1. Produce a repo inventory summary:
    - languages present
    - config systems (Terraform/Helm/K8s/Django/etc.)
    - where secrets are likely to appear
2. Run (or emulate) the following scans where possible:
    - `git grep` across the repo for keyword hits
    - regex scans for known token formats
    - scan for `.env` files and check whether they’re committed
    - search for PEM/cert headers
    - look for base64 blobs and decode small ones safely to see if they resemble keys/JSON tokens (do NOT print decoded sensitive values)
3. If allowed, recommend enabling **pre-commit** + CI scanning:
    - `gitleaks` (preferred)
    - `trufflehog`
    - GitHub Advanced Security secret scanning (if applicable)

## Output Format (Strict)
Return a report with these sections:

### 1) Summary
- total findings by severity (Critical/High/Medium/Low)
- whether any **immediate rotation** is recommended

### 2) Findings (Table)
For each finding include:
- Severity
- Type (AWS key / API key / password / private key / token / suspicious entropy / etc.)
- File path
- Line number(s)
- Masked snippet (no full secrets)
- Why it’s likely a secret (pattern match, entropy, context)
- Recommended action (rotate, remove, move to secret manager, etc.)

### 3) Remediation Plan
- Immediate containment (revoke/rotate, invalidate tokens)
- Code changes (move to env vars, secret manager, K8s secrets, AWS SSM Parameter Store/Secrets Manager)
- Git cleanup options:
    - If secrets are committed: propose `git filter-repo` or BFG steps (do not execute unless asked)
- Add preventions:
    - `.gitignore` updates
    - pre-commit hooks
    - CI job to fail builds on secret detection

### 4) False Positives / Notes
- Anything suspicious but likely benign, with rationale.

## Severity Guidance
- Critical: private keys, AWS access keys, production tokens, anything granting direct access
- High: client secrets, long-lived API keys, DB passwords, service tokens
- Medium: example creds that might be real, partial creds, internal endpoints w/ auth hints
- Low: weak patterns or placeholders clearly labeled as dummy

## Constraints
- Do not change files unless explicitly instructed.
- Do not rotate credentials; only recommend steps.
- Provide exact file paths and line numbers for every finding.

---

# EXECUTION PROCESS (Based on ETL Orchestration Audit - Feb 2026)

## Phase 1: Repository Inventory & Preparation (30 minutes)

### 1.1 Gather Repository Information
```bash
find . -type f \( -name "*.py" -o -name "*.yml" -o -name "*.yaml" -o -name "*.tf" \
  -o -name "*.tfvars" -o -name "*.sh" -o -name "*.json" -o -name ".env*" \
  -o -name "Dockerfile*" -o -name "docker-compose*" \) \
  ! -path "./.git/*" ! -path "./__pycache__/*" ! -path "./.terraform/*" | sort
```

### 1.2 Document Repository Profile
- Languages present (Python, Go, Node, etc.)
- Configuration systems (Terraform, Helm, K8s, docker-compose, etc.)
- Deployment targets (EKS, RDS, S3, Lambda, etc.)
- CI/CD platform (.github/workflows, GitLab CI, Jenkins, etc.)
- Expected secret locations based on framework

### 1.3 Identify Key Files to Scan
Priority order:
1. Environment configuration files (`.env*`, `values*.yaml`, `terraform.tfvars`)
2. Infrastructure-as-code (Terraform, Helm, K8s manifests)
3. Docker/container definitions (Dockerfile, docker-compose)
4. Application source code (especially anything handling auth/secrets)
5. Deployment scripts (bash, Python, shell)
6. CI/CD workflows (.github/workflows, build scripts)

---

## Phase 2: Pattern-Based Scanning (45 minutes)

### 2.1 Search for Common Secret Keywords
```bash
grep -r -i -E "(password|passwd|secret|token|api_key|access_key|private_key|client_secret)" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.tf" \
  --include="*.sh" --include="*.env" --include="*.json" | head -100

grep -r -E "AKIA|ASIA" --include="*.py" --include="*.yml" --include="*.yaml" \
  --include="*.tf" --include="*.sh" --include="*.env" --include="*.json"

grep -r -E "BEGIN PRIVATE KEY|BEGIN RSA PRIVATE KEY|BEGIN OPENSSH PRIVATE KEY|BEGIN CERTIFICATE" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.tf" \
  --include="*.sh" --include="*.env" --include="*.json" --include="*.pem" --include="*.key"

grep -r -E "eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.tf" \
  --include="*.sh" --include="*.env" --include="*.json"
```

### 2.2 Check Git Tracking
```bash
git ls-files | grep -E "\.env" && echo "WARNING: .env files are tracked!" || echo "✓ .env files are not tracked"
cat .gitignore | grep -E "\.env|\*\.env" && echo "✓ .env files are in .gitignore" || echo "⚠️ WARNING: .env not in .gitignore"
git ls-files | grep -E "\.pem|\.key|secret" && echo "WARNING: Sensitive files tracked!"
```

**IMPORTANT:** 
- If `.env*` files are **NOT tracked** (git-ignored): **OMIT from security scan** - no action needed
- If `.env*` files **ARE tracked**: **FLAG as HIGH severity** - need to remove from git history

### 2.3 File-by-File Analysis
For each critical file type, read and analyze:

**Environment Files (.env, .env.*):**
- Read entire content
- Check if secrets are placeholders (dummy/example) or real values
- Verify .gitignore includes *.env pattern

**Configuration Files (*.tf, values.yaml, docker-compose.yml):**
- Look for hardcoded credentials in plain text
- Check for base64-encoded secrets
- Look for default/weak credentials
- Check Terraform variables for credential references
- Look for AWS profile references vs. hardcoded keys

**Infrastructure Manifests (K8s YAML, Helm charts):**
- Check secret creation methods
- Look for credentials in ConfigMaps (should use Secrets)
- Check encryption configuration
- Look for hardcoded service account tokens

**Shell Scripts (*.sh):**
- Look for credentials passed as environment variables
- Check for credentials in command arguments
- Look for PGPASSWORD or similar env var usage
- Check for credentials stored in temp files
- Look for credentials in function parameters

**Source Code (*.py, *.js, etc.):**
- Look for hardcoded credentials in code
- Check for credential handling patterns
- Look for os.environ.get() with defaults
- Check for boto3 client initialization with credentials
- Look for authentication token handling

**CI/CD Workflows (.github/workflows/*.yml):**
- Check for secrets in workflow files
- Look for credential passing between jobs
- Check for secure secret handling
- Look for credentials in logs

### 2.4 Read High-Priority Files in Full
Use `read_file` tool to read complete content of:
- `.env` file (check if actually tracked and if so, what's in it)
- `docker-compose.yml` (check for hardcoded passwords)
- Key Terraform files (main.tf, providers.tf, variables.tf)
- Deployment scripts (deploy_*.sh, manage.sh)
- CLI/main application files
- K8s resource files

---

## Phase 3: Contextual & Heuristic Analysis (30 minutes)

### 3.1 Entropy-Based Analysis
For strings that look suspicious:
- High entropy (looks random) + variable name containing "password/secret/key"
- Very long strings that decode to credentials
- Base64 blobs that contain credential-like patterns when decoded

### 3.2 Configuration Pattern Analysis
- Default credentials (username: admin, password: admin)
- Placeholder credentials marked as "dummy" but still risky
- Example credentials that look realistic
- Credentials passed as CLI arguments or environment variables
- Credentials stored in Terraform state (very high risk)
- Credentials in shell variables (process listing visibility)

### 3.3 Infrastructure Risk Analysis
- Where credentials are stored (state files, K8s secrets, S3, etc.)
- Encryption status (at rest, in transit)
- Access control (who can read/modify)
- Audit logging capabilities
- Credential rotation procedures

---

## Phase 4: Comprehensive Reporting (60 minutes)

### 4.1 Create Security Findings Report (SECURITY_FINDINGS.md)
**Simple Markdown Format:**

```markdown
# Security Scan Findings

**Scan Date:** [date]  
**Repository:** [repo path]  
**Total Findings:** [count]

## Critical Findings
| File | Line(s) | Severity | Type | Issue |
|------|---------|----------|------|-------|
| path/to/file.ext | 42 |CRITICAL | AWS Key | [brief description] |

## High Findings
| File | Line(s) | Severity | Type | Issue |
|------|---------|----------|------|-------|
| path/to/file.ext | 15-20 | HIGH | Password | [brief description] |

## Medium Findings
| File | Line(s) | Severity | Type | Issue |
|------|---------|----------|------|-------|
| path/to/file.ext | 50 | MEDIUM | Config | [brief description] |

## Low Findings
| File | Line(s) | Severity | Type | Issue |
|------|---------|----------|------|-------|
| path/to/file.ext | 8 | LOW | Example | [brief description] |

## Summary
- **Critical:** 0
- **High:** 0
- **Medium:** 0
- **Low:** 0
```

---

## Phase 5: Documentation & Archival (10 minutes)

### 5.1 Archive Findings
- Store `SECURITY_FINDINGS.md` in `.github/reports/security/` with timestamp
- Include scan metadata (date, repository, scanner version)

---

### Scanning Tools
```bash
brew install gitleaks
gitleaks detect --source . -v
pip install detect-secrets
detect-secrets scan > .secrets.baseline
pip install truffleHog
truffleHog filesystem . --only-verified --fail
```

### Pre-Commit Setup
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Git Operations
```bash
git ls-files | grep -E "\.env|secret"
cat .gitignore | grep -E "env|secret"
git filter-repo --path path/to/file --invert-paths
```

---

## Expected Deliverables

After completing the scan, you should have created:

- [ ] `SECURITY_FINDINGS.md` - Single markdown file with findings table
  - File paths
  - Line numbers
  - Severity levels (CRITICAL, HIGH, MEDIUM, LOW)
  - Brief issue descriptions

**Total Deliverables:** 2 files (findings report + automation setup)

---

## Execution Timeline

| Phase | Duration | Output |
|-------|----------|--------|
| Phase 1: Repository Inventory | 30 min | Organized scan plan |
| Phase 2: Pattern-Based Scanning | 45 min | Preliminary findings |
| Phase 3: Contextual Analysis | 30 min | Verified findings |
| Phase 4: Reporting | 60 min | SECURITY_FINDINGS.md |
| Phase 5: Archival & Setup | 10 min | Pre-commit hooks |
| **TOTAL** | **175 min (2.9 hrs)** | **2 deliverables** |

---

## Key Metrics to Track

- **Scan Coverage:** % of tracked files scanned (aim for 100%)
- **Findings by Severity:** Count critical/high/medium/low
- **False Positives:** Track and document rationale
- **Files Modified:** Count files needing changes (from SECURITY_FINDINGS.md)
- **Effort Estimate:** Total hours to remediate
- **Timeline:** Weeks to full remediation

---

## Quality Checklist

Before finalizing the scan:

- [ ] All findings have specific file paths
- [ ] All findings have line numbers
- [ ] Severity levels are correctly assigned
- [ ] Brief descriptions explain the issue
- [ ] All findings are verified (not false positives)
- [ ] SECURITY_FINDINGS.md is properly formatted
