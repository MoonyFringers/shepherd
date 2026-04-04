---
status: "accepted"
date: 2026-03-30
decision-makers:
  - '@luca-c-xcv'
  - '@feed3r'
  - '@giubacc'
consulted: []
informed: []
---

# Introduce Dual-Licensing Model (AGPL-3.0-only + Proprietary Commercial) with CLA

## Context and Problem Statement

Shepherd Core Stack is distributed exclusively under the GNU Affero General
Public License v3 (ADR-0001). The AGPL fulfils the project's commitment to
software freedom but prevents commercial adoption by organizations that cannot
or will not comply with its copyleft and network-use source-disclosure
obligations.

To sustain the project financially while preserving the open-source
distribution, Moony Fringers will offer a separate proprietary commercial
license as a second tier alongside the AGPL. Dual-licensing under this model
requires that Moony Fringers holds sufficient rights over all Contributions —
specifically, the ability to sublicense contributions under terms other than
the AGPL. This right cannot be assumed from a simple "contributions are
licensed under the project license" statement; a formal Contributor License
Agreement (CLA) is required.

Additionally, this ADR establishes the AGPL variant as `AGPL-3.0-only`
(replacing the prior "version 3 or any later version" phrasing in source
headers). Locking to a specific version prevents ambiguity if a future AGPL
release changes terms in a way that conflicts with the commercial tier.

## Decision Drivers

* The AGPL's copyleft obligations deter commercial adoption.
* Moony Fringers needs a sustainable revenue model to fund continued
  development.
* Contributors must retain copyright ownership; full assignment is not
  acceptable.
* The dual-licensing model is legally sound only if Moony Fringers holds a
  sublicensable license over all Contributions.
* The CLA must be enforced automatically on new PRs to prevent coverage gaps.
* Existing contributors must retroactively confirm consent before the commercial
  tier can apply to their past contributions.

## Considered Options

* Keep AGPL-only — no commercial tier.
* Dual-license with copyright assignment CLA (contributors transfer full
  ownership to Moony Fringers).
* **Dual-license with license-grant CLA** (contributors keep copyright, grant
  Moony Fringers a broad sublicensable license). ← chosen
* Adopt a source-available non-AGPL license (e.g., BSL, SSPL) instead of a
  true proprietary commercial tier.

## Decision Outcome

Chosen option: **"Dual-license with license-grant CLA"**, because it enables
the commercial tier without requiring contributors to surrender copyright.
The license-grant model is well-precedented (Apache ICLA, MongoDB CLA,
HashiCorp CLA) and legally sufficient for sublicensing to commercial customers.

The CLA (see `CLA.md`) grants Moony Fringers a perpetual, worldwide,
non-exclusive, royalty-free, irrevocable, sublicensable copyright and patent
license over each Contribution, while the contributor retains full copyright
ownership.

### Consequences

* **Good**, because AGPL distribution is unchanged — all open-source users
  continue to receive the same rights they have today.
* **Good**, because contributors retain copyright; the ask is smaller and more
  contributor-friendly than full assignment.
* **Good**, because the CLA Assistant GitHub Action automates enforcement for
  all future contributions without manual gating.
* **Good**, because the commercial tier provides a sustainable revenue path
  without forking or fragmenting the codebase.
* **Bad**, because retroactive consent is required from all existing
  contributors. If any contributor refuses, their contributions must be audited
  and either rewritten or a separate resolution reached before the commercial
  tier can cover that code.
* **Bad**, because new contributors must sign the CLA before their first PR is
  merged, adding a small onboarding step.
* **Bad**, because the CLA Assistant requires a `PERSONAL_ACCESS_TOKEN` secret
  with `repo` scope in the repository settings.

### Confirmation

* `CLA.md` exists at the repository root and is referenced by the CLA
  Assistant workflow.
* `LICENSE-COMMERCIAL` exists at the repository root.
* `.github/workflows/cla.yaml` is active and blocks PR merges for unsigned
  contributors.
* `.github/cla_signatures.json` captures all signatures (including retroactive
  consent from existing contributors).
* All existing contributors have signed or a documented resolution exists for
  any exceptions.
* `CONTRIBUTION_GUIDELINES.md` references the CLA and explains the signing
  process.
* `README.md` reflects dual licensing with updated badges and a License section.
* Python source file headers use `SPDX-License-Identifier: AGPL-3.0-only` and
  reference both `LICENSE` and `LICENSE-COMMERCIAL`.

## Pros and Cons of the Options

### Keep AGPL-only

* **Good**, because no legal complexity is added.
* **Good**, because contributor experience is unchanged.
* **Bad**, because no sustainable commercial revenue path exists.

### Dual-license with copyright assignment CLA

* **Good**, because Moony Fringers gains unrestricted control over the
  codebase.
* **Bad**, because full assignment deters contributors who are not willing to
  surrender copyright.
* **Bad**, because assignment agreements are more legally burdensome in some
  jurisdictions.

### Dual-license with license-grant CLA

* **Good**, because contributors retain copyright ownership.
* **Good**, because it is legally sufficient to enable sublicensing.
* **Neutral**, because it is a well-known model with abundant precedent.
* **Bad**, because all existing contributions must be retroactively covered.

### Source-available non-AGPL license (BSL, SSPL)

* **Good**, because it can be implemented without a CLA.
* **Bad**, because it would break the commitment to AGPL open-source
  distribution made in ADR-0001.
* **Bad**, because BSL and SSPL are not OSI-approved; the project would no
  longer be open-source in the canonical sense.

## More Information

* [CLA.md](../../CLA.md) — the operative Contributor License Agreement
* [LICENSE-COMMERCIAL](../../LICENSE-COMMERCIAL) — commercial license notice
  and contact information
* [ADR-0001](0001-shepherd-core-stack-license.md) — original AGPL license
  decision
* [CLA Assistant GitHub Action](https://github.com/contributor-assistant/github-action)
* [Apache ICLA](https://www.apache.org/licenses/icla.pdf) — reference model
  for license-grant CLAs
