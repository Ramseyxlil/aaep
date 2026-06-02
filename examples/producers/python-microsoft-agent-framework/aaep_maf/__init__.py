"""
AAEP integration for Microsoft Agent Framework (MAF).

Provides MAFAAEPMiddleware, which slots into the MAF middleware chain and
emits AAEP events for every step of an agent's execution: model invocations,
streaming output, tool/function calls (with safety-gated confirmation), and
session lifecycle events.

Designed for compatibility with Azure OpenAI, Azure AI Foundry, and the
broader Microsoft AI stack. Forward-compatible with eventual Microsoft
Narrator AAEP subscription.

Public API:

    from aaep_maf import MAFAAEPMiddleware, make_middleware

    # Option 1: instantiate directly
    middleware = MAFAAEPMiddleware(
        send_event=my_transport,
        model="gpt-4o",
    )

    # Option 2: convenience factory
    middleware = make_middleware(send_event=my_transport)

    # Attach to any MAF agent
    agent.add_middleware(middleware)

    # AAEP events emit automatically as the agent runs
    result = await agent.invoke("...")

See README.md for full usage and design notes, and README's "Microsoft
Narrator forward compatibility" section for AT integration plans.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"

from aaep_maf.middleware import (
    MAFAAEPMiddleware,
    make_middleware,
)


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    # Public API
    "MAFAAEPMiddleware",
    "make_middleware",
]
