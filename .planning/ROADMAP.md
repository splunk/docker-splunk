# Roadmap: CSPL-4768 SBOM Generation & Signing

**Created:** 2026-04-29
**Phases:** 3
**Granularity:** Coarse

## Phase Overview

| # | Phase | Goal | Requirements | Plans |
|---|-------|------|--------------|-------|
| 1 | Cosign Image Signing | All release images signed in GitLab CI | SIGN-01..04, PIPE-01..04 | 2 plans |
| 2 | Syft SBOM Generation | CycloneDX SBOM for operator images | SBOM-01..04 | 2 plans |
| 3 | Custom BOM & Release Integration | Full BOM + docs + release artifact attachment | BOM-01..04, DOC-01..02 | 2 plans |

## Phase Details

### Phase 1: Cosign Image Signing

**Goal:** All released operator images (standard, distroless, ARM) are Cosign-signed in the GitLab CI release pipeline, with signatures pushed to both ECR and DockerHub, and verified post-signing.

**Requirements:** SIGN-01, SIGN-02, SIGN-03, SIGN-04, PIPE-01, PIPE-02, PIPE-03, PIPE-04

**Success Criteria:**
1. Running `cosign verify --key cosign.pub splunk/splunk-operator:$VERSION` succeeds for all image variants
2. `sign-release-images` job completes successfully in GitLab CI without breaking existing release flow
3. Signing job reads image refs from `release-image-contract.env` (not hardcoded)
4. Public key (`cosign.pub`) is committed to the repository root

**Key risks:**
- ECR token expiry during long pipelines
- Multi-registry signing (must sign on both ECR and DockerHub independently)

**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md — Create sign-release-images.sh script and commit cosign.pub
- [x] 01-02-PLAN.md — Wire sign-release-images job, register verification report, remove future-release caveats

---

### Phase 2: Syft SBOM Generation

**Goal:** Syft generates CycloneDX SBOMs for the standard and distroless operator images, uploaded as release artifacts.

**Requirements:** SBOM-01, SBOM-02, SBOM-03, SBOM-04

**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — Pin SYFT_VERSION, add ensure_syft to pipeline-common.sh, create generate-release-sbom.sh script
- [x] 02-02-PLAN.md — Wire SBOM job into release.yml and register assets in gitlab-release-record.py

**Success Criteria:**
1. `sbom-operator-v{VERSION}.cyclonedx.json` contains non-empty `components` array with Go modules
2. `sbom-operator-v{VERSION}-distroless.cyclonedx.json` is generated with at minimum Go binary modules
3. Both SBOMs appear as assets in the GitLab release
4. Syft version is pinned in the install script (not `latest`)

**Key risks:**
- Distroless image may produce minimal SBOM (expected behavior)
- DockerHub rate limiting during scan

---

### Phase 3: Custom BOM & Release Integration

**Goal:** Custom BOM enumerates all managed container images, verification documentation is written, and all artifacts are integrated into the GitLab release record.

**Requirements:** BOM-01, BOM-02, BOM-03, BOM-04, DOC-01, DOC-02

**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — Pin CRANE_VERSION, add ensure_crane to pipeline-common.sh, create generate-release-bom.sh script
- [ ] 03-02-PLAN.md — Wire BOM job into release.yml, register BOM assets in gitlab-release-record.py, create docs/supply-chain-verification.md

**Success Criteria:**
1. `bom-v{VERSION}.json` is valid CycloneDX with all managed images listed
2. `bom-v{VERSION}.txt` is human-readable with image names, versions, and digests
3. GitLab release includes: SBOM files, BOM files, signing summary
4. Docs contain working `cosign verify` and SBOM consumption commands
5. `gitlab-release-record` job attaches all new artifacts

**Key risks:**
- Managed image list may change between releases (must source from .env)

---

## Dependencies

```
Phase 1 (Signing) ← independent, can start immediately
Phase 2 (SBOM)   ← independent of Phase 1 (but nice to have signing for SBOM attestation later)
Phase 3 (BOM)    ← depends on Phase 2 (integrates SBOM + BOM into release)
```

Phases 1 and 2 can run in parallel. Phase 3 depends on both.

## Milestones

- **M1:** First signed release from GitLab CI (Phase 1 complete)
- **M2:** First release with SBOM artifacts (Phase 2 complete)
- **M3:** Full supply chain artifacts matching splunk-ai-operator pattern (Phase 3 complete)
