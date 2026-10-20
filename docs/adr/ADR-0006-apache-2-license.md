# ADR-0006: Apache License 2.0 for original repository materials

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer

## Context

The project is intended to be a public research/software repository. A repository licence should permit reuse and modification while making patent terms and attribution/notice obligations explicit. Third-party railway data and provider rights are separate from the copyright in project code.

## Decision

License original software and documentation in this repository under Apache License 2.0, with a standard `LICENSE`, a project `NOTICE`, and a separate third-party data/services policy. Individual files or directories may specify a different licence when needed and clearly documented.

## Alternatives considered

- **MIT:** A simpler permissive licence, but without the same explicit patent grant framework.
- **GPL family:** A copyleft approach, not selected for the initial intended reuse model.
- **No licence:** Rejected because public visibility alone does not grant the intended reuse permissions.

## Consequences

- Contributors should understand that contributions to the covered work are under Apache-2.0 absent a separate agreement.
- Required licence text, notices and modification notices must be retained when redistributing.
- The licence does not authorize using railway data, service content, provider APIs, logos or trademarks.
- Any incompatible third-party material must be kept separate and governed by its own terms.

## Validation

Review if the project's intended distribution model changes, external assets introduce additional licence obligations, or a collaborator contributes under a separate agreement. This ADR records the project's choice; it is not legal advice.
