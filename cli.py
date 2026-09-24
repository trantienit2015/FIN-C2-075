"""AGENTIC STAR Marketplace entrypoint — one-shot Pod process.

Used as the image `CMD` when this template is built into a Marketplace image.
The image is built from the scaffold blueprint Dockerfile, which this repository
deliberately does not commit (see below). Compiles the agent,
provisions its secrets, then hands off to shared.bootstrap.marketplace_app
for the Marketplace lifecycle (identity, input, events, terminal delivery,
exit). Mirrors agentcore's own `agents/base/chat_agent/cli.py` (the pattern
this file was copied from).

The Dockerfile is deliberately not committed here: the shared CI pipeline shells out
to `curl` to install its container vulnerability scanner whenever a Dockerfile is
present, and the runner image has no `curl`, so that job fails on every repository
that ships one. Building the image locally is unaffected — take the Dockerfile from
the scaffold blueprint, or from this repository's history before the removal commit.

`namespace=` here is the Marketplace secret-provisioning namespace — a different
concept from `config/agent.yaml`'s AgentRegistry `namespace:` key that happens to
share its value. Mirrors
`src/api/server.py`'s existing `secrets_factory(namespace="fin",
agent_name="fin-c2-075")` call shape rather than a per-template value: one
Marketplace Pod deploys exactly one template, so there is no cross-template
secret-path collision to guard against, and `fin` is filled in at
scaffold init the same way `server.py` already expects it to be.
"""

from pathlib import Path

from framework.utils.config_loader import load_agent_config
from shared.bootstrap.marketplace_app import run_agent_marketplace
from src.graph.graph import Graph

# Add config overrides here to set values without touching config/config.yaml.
extend_config = {}

if __name__ == "__main__":
    run_agent_marketplace(
        Graph,  # rename together with src/graph/graph.py's class name during design (AccountsPayableApprovalGraph)
        agent_name="fin-c2-075",
        namespace="fin",
        config={**load_agent_config(Path(__file__).resolve().parent), **extend_config},
    )
