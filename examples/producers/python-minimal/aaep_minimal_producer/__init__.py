"""
AAEP Minimal Producer — reference implementation of the manual loop pattern.

This package demonstrates how to emit AAEP events from a Python agent without
using any agent framework. It is intended as a learning resource and as a
starting template for custom integrations.

Public API:

    from aaep_minimal_producer import AAEPEmitter, AgentLoop, make_id

    # Create an emitter for your transport
    emitter = AAEPEmitter(send_event=my_send_function)

    # Build an agent loop with a mock LLM and tool registry
    agent = AgentLoop(emitter, llm_client=my_llm, tool_registry=my_tools)

    # Run a session
    await agent.run("Tell me about retirement planning.")

See README.md for full usage instructions and Quickstart for the simplest
possible AAEP producer.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"

from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    StreamCoalescer,
    make_id,
    classify_error_category,
)
from aaep_minimal_producer.agent import AgentLoop


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    # Public API
    "AAEPEmitter",
    "StreamCoalescer",
    "AgentLoop",
    "make_id",
    "classify_error_category",
]
