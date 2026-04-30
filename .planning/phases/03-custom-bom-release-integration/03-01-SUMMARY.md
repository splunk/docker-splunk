---
phase: 03-custom-bom-release-integration
plan: "01"
subsystem: gitlab-ci
tags:
  - sbom
  - bom
  - crane
  - cyclonedx
  - supply-chain
  - ci-pipeline

dependency_graph:
  requires:
    - "02-01: generate-release-sbom.sh (pipeline-common.sh ensure_syft pattern reference)"
  provides:
    - "CRANE_VERSION=0.20.2 pin in .env"
    - "ensure_crane() bootstrapper in pipeline-common.sh"
    - "generate-release-bom.sh producing CycloneDX JSON + text BOM + signing summary"
  affects:
    - "03-02: CI job wiring will reference generate-release-bom.sh"

tech_stack:
  added:
    - "crane 0.20.2 (github.com/google/go-containerregistry) - OCI image manifest digest resolution"
  patterns:
    - "POSIX sh CI script following generate-release-sbom.sh structure"
    - "ensure_<tool>() bootstrapper pattern with version pin in .env"
    - "CycloneDX 1.5 JSON BOM generation via jq"
    - "WORKFLOW_SLUG output directory convention (PIPE-01)"

key_files:
  created:
    - splunk-operator/gitlab-ci/generate-release-bom.sh
  modified:
    - splunk-operator/.env
    - splunk-operator/gitlab-ci/lib/pipeline-common.sh

decisions:
  - "crane_arch uses x86_64 (not amd64) for amd64 hosts to match go-containerregistry release asset naming (go-containerregistry_Linux_x86_64.tar.gz)"
  - "os_title uses uname -s (title-case: Linux/Darwin) for crane URL, separate from lowercase os_name used by syft"
  - "CycloneDX crane_version passed as jq --arg to avoid shell interpolation inside jq program string"
  - "Distroless image only resolves linux/amd64 platform digest (no arm64 variant for distroless)"

metrics:
  duration: "~2 minutes"
  completed: "2026-04-30T21:44:27Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 03 Plan 01: Custom BOM Generation - Summary

**One-liner:** CycloneDX 1.5 JSON + human-readable text BOM via crane digest resolution, with ensure_crane() bootstrapper and CRANE_VERSION=0.20.2 pin.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Pin CRANE_VERSION in .env and add ensure_crane to pipeline-common.sh | 49fdd88 | splunk-operator/.env, splunk-operator/gitlab-ci/lib/pipeline-common.sh |
| 2 | Create generate-release-bom.sh | 9837520 | splunk-operator/gitlab-ci/generate-release-bom.sh |

## What Was Built

### Task 1: CRANE_VERSION pin + ensure_crane()

`splunk-operator/.env` now contains `CRANE_VERSION=0.20.2` appended after `SYFT_VERSION=1.43.0`, following the no-v-prefix convention established in Phase 2.

`pipeline-common.sh` gained `ensure_crane()` at the end of the file, immediately after `ensure_syft()`. The function follows the exact same pattern:
- Accepts `ci_bin_dir` and `crane_version` positional args
- Calls `require_nonempty` on `crane_version`
- Early-returns if binary already exists
- Detects OS/arch and maps to crane's release asset naming (title-case OS, `x86_64` for amd64)
- Downloads from `github.com/google/go-containerregistry/releases/download/v{ver}/go-containerregistry_{OS}_{arch}.tar.gz`
- Extracts `crane` binary with `tar -xzC`
- Sets `chmod 0755`

### Task 2: generate-release-bom.sh

New script at `splunk-operator/gitlab-ci/generate-release-bom.sh` that:

1. Sources `pipeline-common.sh` (PIPE-02)
2. Reads `.env` via `load_repo_dotenv` for CRANE_VERSION (D-03)
3. Reads `release-image-contract.env` for image refs (PIPE-03) — RELEASE_IMAGE, RELEASE_DISTROLESS_IMAGE
4. Installs crane via `ensure_crane()` and jq via `ensure_jq()`
5. Authenticates to registry via `docker_login_registry`
6. Resolves 5 digests: standard manifest, standard amd64, standard arm64, distroless manifest, distroless amd64
7. Produces `bom-v{VERSION}.json` — CycloneDX 1.5 JSON with 2 components (standard + distroless), each with `purl: pkg:oci/...`, `hashes: [{alg: SHA-256, content: <hex>}]`, and `properties` for variant and platforms (BOM-01, BOM-03)
8. Produces `bom-v{VERSION}.txt` — human-readable table with IMAGE_NAME, TAG, DIGEST, PLATFORM columns, 5 rows (BOM-02)
9. Produces `signing-summary.md` — cosign verify placeholder commands, digest table, and grype/trivy SBOM inspection commands
10. Records all key values in context file via `append_context` (PIPE-01 convention)
11. Writes `summary.txt` with component count

All outputs land in `ci-output/${WORKFLOW_SLUG}-output/` (PIPE-01).

## Deviations from Plan

None - plan executed exactly as written.

The crane_version `--arg crane_ver` approach was used (instead of shell string interpolation in the jq program literal) to keep the jq program clean and avoid escaping. This is a minor implementation detail not covered in the plan but results in cleaner code.

## Requirements Satisfied

| Requirement | Status | Evidence |
|-------------|--------|----------|
| BOM-01: CycloneDX JSON BOM with all managed images | Satisfied | bom-v{VERSION}.json with bomFormat=CycloneDX, specVersion=1.5 |
| BOM-02: Human-readable text BOM with IMAGE_NAME/TAG/DIGEST/PLATFORM | Satisfied | bom-v{VERSION}.txt with 4-column table header |
| BOM-03: Digests and purl fields in BOM | Satisfied | purl: pkg:oci/... and hashes: [{alg: SHA-256}] per component |
| PIPE-01: Output convention ci-output/${WORKFLOW_SLUG}-output/ | Satisfied | output_dir uses WORKFLOW_SLUG |
| PIPE-02: Sources pipeline-common.sh | Satisfied | Line 11: . "${CI_PROJECT_DIR}/gitlab-ci/lib/pipeline-common.sh" |
| PIPE-03: Reads release-image-contract.env | Satisfied | require_file + load_optional_env_file on contract_file |
| PIPE-04: allow_failure compatible | Satisfied | set -eu with no side effects that block CI; crane digest failure exits cleanly |

## Threat Mitigations Applied

| Threat | Mitigation |
|--------|------------|
| T-03-01: Tampering - crane binary download | CRANE_VERSION=0.20.2 pinned; HTTPS via curl -fsSL; chmod 0755 enforced |
| T-03-05: Repudiation - which pipeline generated BOM | BOM metadata.timestamp + context file records crane_version, digests, image refs |

## Known Stubs

None. All outputs are dynamically generated at runtime from live crane digest resolution.

## Self-Check: PASSED

- splunk-operator/.env: FOUND (CRANE_VERSION=0.20.2)
- splunk-operator/gitlab-ci/lib/pipeline-common.sh: FOUND (ensure_crane at line 737)
- splunk-operator/gitlab-ci/generate-release-bom.sh: FOUND (executable, 248 lines)
- Task 1 commit 49fdd88: confirmed
- Task 2 commit 9837520: confirmed
