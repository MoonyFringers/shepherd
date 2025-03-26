---
status: "proposed"
date: 2025-03-26
decision-makers:
  - '@luca-c-xcv'
  - '@feed3r'
  - '@giubacc'
---

# Change Shepherd's Core Project License from MIT to AGPL

## Context and Problem Statement

The Shepherd's core project is currently licensed under the MIT License,
which is a permissive open-source license. While this provides flexibility
and encourages adoption, it also allows third parties to use the software
in proprietary systems without contributing improvements back to the community.

To ensure that modifications and improvements to the software remain open-source,
we are considering switching the Shepherd's core project to the
Affero General Public License (AGPL), which enforces stronger copyleft provisions,
including network use.

Additionally, the licensing model for plugins will be evaluated separately in a
future Architectural Decision Record (ADR).

## Decision Drivers

- Promote software freedom by ensuring modifications remain open-source.
- Prevent proprietary use of the software without contributing improvements
  back.
- Align with other AGPL-licensed dependencies or ecosystem standards.
- Maintain compatibility with open-source contributors and users who support
  strong copyleft licenses.
- Reduce the risk of closed-source forks leveraging the software without
  contributing back.

## Considered Options

- Keep the MIT License.
- Switch to the AGPL License.
- Choose an alternative strong copyleft license (e.g., GPLv3, LGPL).

## Decision Outcome

Chosen option: **"Switch to the AGPL License"**, because it ensures that
modifications to the software, including those used over a network, remain
open-source. This choice aligns with the project's long-term goal of protecting
software freedom and preventing proprietary forks.
Moreover:

- The license does not impose restrictions on personal or internal
  use of the software. If the software is neither distributed nor offered
  as a network service, there is no requirement to release the source code.

- Software covered by the AGPL cannot be distributed with DRM
  (Digital Rights Management).

### Consequences

- **Good**, because all modifications, even those deployed as SaaS, must be
  open-sourced.
- **Good**, because it encourages contributions from users who modify the
  software.
- **Bad**, because some companies and developers may avoid using the software
  due to the AGPL’s strict copyleft requirements.
- **Bad**, because changing the license requires consent from all contributors
  or rewriting affected code.

### Confirmation

To confirm compliance with the new license:

- Update all license headers and documentation to reflect the AGPL license.
- Notify all contributors and ensure they agree to the license change.
- Conduct a legal review to ensure compliance with AGPL requirements.
- Monitor adoption and contributions after the license change to assess its
  impact.

## Pros and Cons of the Options

### Keep the MIT License

- **Good**, because it maximizes adoption by allowing unrestricted use.
- **Good**, because it simplifies licensing and legal considerations.
- **Neutral**, because it enables both open-source and proprietary use cases.
- **Bad**, because modifications can be kept closed-source, reducing
  contributions.

### Switch to the AGPL License

- **Good**, because it ensures all modifications remain open-source.
- **Good**, because it aligns with the philosophy of software freedom.
- **Neutral**, because some open-source projects avoid AGPL due to its strict
  copyleft nature.
- **Bad**, because it may limit adoption by businesses wary of AGPL obligations.

## More Information

Links:

- [MIT License](https://opensource.org/licenses/MIT)
- [AGPL License](https://www.gnu.org/licenses/agpl-3.0.html)
- [Comparison of Open Source Licenses](https://choosealicense.com/)
