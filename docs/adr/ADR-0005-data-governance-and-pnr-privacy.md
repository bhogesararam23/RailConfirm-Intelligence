# ADR-0005: Data governance, authorized access and PNR privacy

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer
- **Related:** docs/data/DATA_ACQUISITION.md, docs/SECURITY_AND_PRIVACY.md

## Context

The product may eventually retrieve live PNR status and retain observations for research. Access to a web page does not automatically grant permission to automate requests, retain results, redistribute data or use them for ML training. PNRs and detailed travel context can be linkable personal information.

## Decision

Use only data sources whose access method and relevant storage, model-training, publication and commercial-use rights are documented. Live tracking requires a provider integration that has been separately verified and approved. Do not bypass access controls or treat scraping as a substitute for authorization.

Minimize collected personal data; passenger names are not needed for probability prediction. Before enabling tracking, implement access control, redacted logs, defined retention and deletion, and secure identifier handling.

## Alternatives considered

- **Assume all public web content is reusable:** Rejected because access and reuse permissions differ.
- **Store raw PNRs in ordinary application records and logs:** Rejected because it increases exposure and linkage risk.
- **Build around unofficial scraping first:** Rejected because access, stability and permitted use are not established.

## Consequences

- Data acquisition can be the project's critical path.
- Provider selection must evaluate rights as well as price and API reliability.
- Tracking will remain disabled until the necessary permissions and controls are verified.
- Research exports must be de-identified and comply with source restrictions.

## Validation

Before a provider integration is enabled, review the contract/terms, access method, rate limits, permitted retention and ML use. Test redaction, deletion and access controls. Review this ADR if the purpose, data types, provider or retention policy changes materially.
