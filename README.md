# FIN-C2-075 — Financial Accounts Payable Intelligent Processing & Approval Agent

> **Category**: Cat 2 (a multi-step pipeline for a specific use case)
> **Industry**: Finance

## Overview

Takes a vendor invoice through the accounts-payable pipeline end to end: it extracts the invoice
fields (vendor, amount, purchase-order number, due date, qualified-invoice registration number),
performs a 3-way match against the purchase order and the goods-receipt record, flags any
discrepancy it finds, routes the invoice to the right approver by amount tier, schedules the bank
payment once an approval exists, posts the journal entry, and emits an audit record with the bank
account details redacted.

Every decision in the pipeline is deterministic — the 3-way match tolerances, the amount tiers that
pick an approver, and the registration-number validation are plain rules, not model output, so the
same invoice always produces the same verdict and the audit record can be reproduced later. **No
language model is called anywhere in this template**, which also means it needs no model API key.

Two safety properties are built in rather than configured in. A payment is never scheduled without
an explicit approval decision, so an invoice that has not been approved leaves the agent marked as
awaiting review instead of being paid. And the bank-account details are redacted on the way out, in
the node that produces the audit document, so they cannot reach the caller even if the rest of the
record is passed along.

Approval routing is a human-in-the-loop step. On a deployment that can deliver approval feedback
back to a running agent, the pipeline pauses and waits for the approver. On a one-shot deployment
that has no such channel, the wait is skipped by configuration and the invoice is returned marked
`pending_review` — the conservative path, not an automatic approval. The tiers and that policy
switch both live in `config/config.yaml`.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
```

See `docs/` for the design specification and the test specification.

## Customising

1. Adjust `config/` for your own environment and policies — in particular the amount tiers that
   select an approver, and whether the approval step blocks and waits for a human.
2. Replace the purchase-order and goods-receipt sources with your own systems of record.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.

---
