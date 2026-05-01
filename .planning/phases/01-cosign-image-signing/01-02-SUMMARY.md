---
phase: 01-cosign-image-signing
plan: "02"
subsystem: infra
tags: [cosign, artifact-ci, image-signing, supply-chain, gitlab-ci, release-pipeline]

# Dependency graph
requires:
  - phase: 01-cosign-image-signing/01-01
    provides: "sign-release-images.sh script and cosign.pub public key"
provides:
  - "splunk-operator/gitlab-ci/includes/release.yml — sign-release-images CI job wired after generate-release-bom"
  - "splunk-operator/gitlab-ci/gitlab-release-record.py — signing-verification-report.md registered as release asset"
  - "splunk-operator/gitlab-ci/generate-release-bom.sh — signing caveat updated to reflect signing is active"
  - "splunk-operator/docs/supply-chain-verification.md — planned-for-future note removed"
affects:
  - "02-syft-sbom-generation"
  - "03-custom-bom-release-integration"

# Tech tracking
tech-stack:
  added:
    - "id_tokens / CI_JOB_JWT with dual audience in GitLab CI for Vault + signing service OIDC auth"
  patterns:
    - "CI job needs chain: publish-release-images -> sign-release-images -> gitlab-release-record (optional)"
    - "allow_failure:true + optional:true in needs for additive supply-chain jobs (matches SBOM/BOM pattern)"
    - "signing-verification-report.md registered as /reports/ asset; signing-report.txt is CI-only debugging artifact"

key-files:
  created: []
  modified:
    - "splunk-operator/gitlab-ci/includes/release.yml"
    - "splunk-operator/gitlab-ci/gitlab-release-record.py"
    - "splunk-operator/gitlab-ci/generate-release-bom.sh"
    - "splunk-operator/docs/supply-chain-verification.md"

key-decisions:
  - "signing-verification-report.md registered as release asset (not signing-report.txt) — user-facing verification instructions vs CI debug output"
  - "allow_failure:true for sign-release-images job — Vault MR 12363 not yet merged, signing is additive per PIPE-04"
  - "Task 3 (ROADMAP/STATE updates) deferred — orchestrator owns those writes in parallel wave execution"

patterns-established:
  - "CI job needs pattern: supply-chain job depends on publish-release-images, gitlab-release-record has optional:true needs entry"
  - "Release asset namespace separation: /reports/ for signing-verification-report.md, /bom/ for signing-summary.md"

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
duration: 2min
completed: 2026-05-01
---

# Phase 01 Plan 02: Cosign Image Signing — CI Job Wiring Summary

**sign-release-images job wired into GitLab CI release pipeline with JWT/Vault auth, signing-verification-report.md registered as release asset, and all planned-for-future caveats removed from BOM and docs**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-01T05:09:48Z
- **Completed:** 2026-05-01T05:11:43Z
- **Tasks:** 2 (Task 3 deferred — orchestrator owns ROADMAP/STATE)
- **Files modified:** 4

## Accomplishments

- Added sign-release-images CI job to release.yml with allow_failure:true, DOCKER_CONFIG, SIGNING_SERVICE_ADDR, and CI_JOB_JWT id_tokens block for dual-audience Vault auth
- Job placed after generate-release-bom and before publish-release-bundle; depends on publish-release-images artifacts
- Registered signing-verification-report.md as a /reports/ release asset in gitlab-release-record.py collect_assets() (signing-report.txt intentionally excluded — CI debug artifact only)
- Added sign-release-images as optional:true need in gitlab-release-record needs list
- Replaced 3-line "planned for future" note in generate-release-bom.sh signing-summary with "Cosign signing is active as of ${release_version}"
- Removed "planned for future" note from docs/supply-chain-verification.md

## Task Commits

Each task was committed atomically to the splunk-operator submodule:

1. **Task 1: Add sign-release-images job to release.yml and update gitlab-release-record needs** - `4ad732d1` (feat)
2. **Task 2: Register signing-verification-report.md, update BOM caveat, update supply-chain docs** - `4d76bd3f` (feat)

## Files Created/Modified

- `splunk-operator/gitlab-ci/includes/release.yml` — sign-release-images job added (26 lines inserted), sign-release-images optional need added to gitlab-release-record
- `splunk-operator/gitlab-ci/gitlab-release-record.py` — signing-verification-report.md tuple added to collect_assets() candidates list
- `splunk-operator/gitlab-ci/generate-release-bom.sh` — signing-summary heredoc updated: 3-line Note block replaced with single active-signing line
- `splunk-operator/docs/supply-chain-verification.md` — 3-line planned-for-future note removed from Image Verification section

## Decisions Made

- `signing-verification-report.md` is the release asset (not `signing-report.txt`): the verification report contains cosign verify commands with image digests for end-user consumption; signing-report.txt is a CI pipeline debug artifact only
- `allow_failure: true` retained on sign-release-images job: Vault MR 12363 must be merged before signing works in production CI; this matches the SBOM/BOM pattern (PIPE-04)
- Task 3 skipped: parallel wave execution instructions prohibit writing STATE.md/ROADMAP.md — orchestrator handles those centrally after all worktree agents merge

## Deviations from Plan

### Skipped Task

**1. [Parallel Execution Constraint] Task 3 (ROADMAP.md and STATE.md updates) skipped**
- **Reason:** Parallel execution instructions explicitly state "Do NOT modify STATE.md or ROADMAP.md — the orchestrator owns those writes after all worktree agents in the wave complete."
- **Impact:** None — orchestrator will update ROADMAP.md and STATE.md after merging all wave 2 worktree outputs
- **Plan tasks affected:** Task 3 only; Tasks 1 and 2 executed fully

---

**Total deviations:** 1 task skipped (orchestrator constraint — not a bug or missing feature)
**Impact on plan:** Zero impact on deliverables. All CI wiring, release asset registration, and documentation updates are complete. ROADMAP/STATE updates are orchestrator responsibility.

## Issues Encountered

None. All edits applied cleanly against the existing file structures.

## User Setup Required

None for this plan. The operational prerequisite is:
- Vault MR 12363 must be merged before `allow_failure: true` can be removed from the sign-release-images job
- Once Vault MR 12363 is confirmed merged, remove `allow_failure: true` from the sign-release-images job in release.yml

## Next Phase Readiness

- Phase 1 CI wiring is complete: sign-release-images job will run on every main-branch release publish pipeline
- signing-verification-report.md will appear as a downloadable release asset on the GitLab release page after the first successful signing run
- Phase 2 (SBOM) and Phase 3 (BOM) plans already merged per STATE.md; no dependencies on Phase 1 CI execution

---
*Phase: 01-cosign-image-signing*
*Completed: 2026-05-01*

## Self-Check: PASSED

- splunk-operator/gitlab-ci/includes/release.yml: FOUND
- splunk-operator/gitlab-ci/gitlab-release-record.py: FOUND
- splunk-operator/gitlab-ci/generate-release-bom.sh: FOUND
- splunk-operator/docs/supply-chain-verification.md: FOUND
- .planning/phases/01-cosign-image-signing/01-02-SUMMARY.md: FOUND
- Task 1 commit 4ad732d1: FOUND in splunk-operator submodule
- Task 2 commit 4d76bd3f: FOUND in splunk-operator submodule
