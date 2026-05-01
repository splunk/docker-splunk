---
phase: 01-cosign-image-signing
plan: "01"
subsystem: infra
tags: [cosign, artifact-ci, image-signing, supply-chain, shell, gitlab-ci]

# Dependency graph
requires: []
provides:
  - "splunk-operator/cosign.pub — RSA-4096 PEM public key for cosign verify"
  - "splunk-operator/gitlab-ci/sign-release-images.sh — artifact-ci signing script for CI"
affects:
  - "02-syft-sbom-generation"
  - "03-custom-bom-release-integration"
  - "gitlab-ci/includes/release.yml (Plan 02 wires the CI job)"

# Tech tracking
tech-stack:
  added:
    - "artifact-ci (Splunk internal, wraps Cosign signing service)"
    - "cosign (public key distribution via cosign.pub)"
  patterns:
    - "generate-release-sbom.sh structure mirrored for all release signing scripts"
    - "contract-driven image refs: all image tags read from release-image-contract.env, never hardcoded"
    - "ci-output/${WORKFLOW_SLUG}-output/ convention for CI artifact placement (PIPE-01)"
    - "pipeline-common.sh sourced for all credential/env handling (PIPE-02)"

key-files:
  created:
    - "splunk-operator/cosign.pub"
    - "splunk-operator/gitlab-ci/sign-release-images.sh"
  modified: []

key-decisions:
  - "ECR signing deferred to future phase — SIGN-02 Phase 1 scope is DockerHub only (user decision 2026-05-01)"
  - "artifact-ci over raw cosign — uses Splunk internal signing service wrapping Cosign, no direct cosign binary calls in CI script"
  - "Multi-arch coverage via manifest signing — signing the standard multi-arch manifest covers linux/arm64 automatically, no separate per-platform sign call needed"
  - "allow_failure:true will be set in CI job (Plan 02) — signing is additive, not a release gate per T-01-06 mitigation"

patterns-established:
  - "Signing script pattern: source pipeline-common.sh, load contract, require_nonempty, login, sign, verify, write report files"
  - "Report output: signing-report.txt (human summary) + signing-verification-report.md (verification commands for consumers)"
  - "Context capture: append_context for all key values (sign_timestamp, image refs, status fields)"

requirements-completed:
  - SIGN-01
  - SIGN-02
  - SIGN-03
  - SIGN-04
  - PIPE-01
  - PIPE-02
  - PIPE-03
  - PIPE-04

# Metrics
duration: 3min
completed: 2026-05-01
---

# Phase 01 Plan 01: Cosign Image Signing — Script and Public Key Summary

**artifact-ci-based signing script (sign-release-images.sh) and RSA-4096 cosign.pub committed, enabling DockerHub image signing in GitLab CI release pipeline**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-01T05:01:28Z
- **Completed:** 2026-05-01T05:05:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Committed RSA-4096 PEM public key (cosign.pub) for end-user verification of signed operator images
- Created sign-release-images.sh following generate-release-sbom.sh structural pattern exactly
- Script signs both standard and distroless images via artifact-ci sign docker IMAGE -r docker.io
- Script performs CI-side round-trip verification via artifact-ci verify docker IMAGE after signing
- All image refs read from release-image-contract.env — no hardcoded tags anywhere in script
- Two release assets produced: signing-report.txt + signing-verification-report.md per PIPE-01

## Task Commits

Each task was committed atomically to the splunk-operator submodule:

1. **Task 1: Commit cosign.pub (RSA-4096 public key)** - `290b8506` (feat)
2. **Task 2: Create sign-release-images.sh** - `463aa713` (feat)

## Files Created/Modified

- `splunk-operator/cosign.pub` — RSA-4096 PEM public key (800 bytes) for `cosign verify --key cosign.pub IMAGE`
- `splunk-operator/gitlab-ci/sign-release-images.sh` — executable POSIX sh signing script, chmod 0755

## Decisions Made

- ECR signing excluded from this script per user decision 2026-05-01: SIGN-02 Phase 1 scope is DockerHub only. No `artifact-ci sign ... -r ecr` call is present.
- artifact-ci sign/verify used exclusively (not raw cosign binary) — matches Splunk internal signing service pattern and research anti-patterns.
- Multi-arch ARM coverage achieved implicitly by signing the standard multi-arch manifest — no per-platform sign call needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The worktree had an empty `splunk-operator/` directory (submodule not initialized), so files were created in the main repo's `splunk-operator/` submodule at `/home/vivekr/splunk-complete/splunk-operator/` and committed directly to that submodule's git repo.

## User Setup Required

None - no external service configuration required for this plan. The signing service integration (Vault MR 12363) and CI job wiring are handled in Plan 02.

## Next Phase Readiness

- `cosign.pub` is committed and ready for Plan 02 to reference in CI job definitions
- `sign-release-images.sh` is ready to be wired into `gitlab-ci/includes/release.yml` in Plan 02
- Plan 02 needs to add the `sign-release-images` CI job with `WORKFLOW_SLUG`, `allow_failure: true`, `id_tokens` block for Vault auth, and `needs: publish-release-images`
- Blocker to monitor: Vault MR 12363 must be merged before signing actually works in production CI

---
*Phase: 01-cosign-image-signing*
*Completed: 2026-05-01*

## Self-Check: PASSED

- splunk-operator/cosign.pub: FOUND
- splunk-operator/gitlab-ci/sign-release-images.sh: FOUND
- .planning/phases/01-cosign-image-signing/01-01-SUMMARY.md: FOUND
- Task 1 commit 290b8506: FOUND in splunk-operator submodule
- Task 2 commit 463aa713: FOUND in splunk-operator submodule
- SUMMARY commit 0d60cad: FOUND in worktree branch
