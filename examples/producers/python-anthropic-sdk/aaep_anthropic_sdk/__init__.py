"""
AAEP integration for the Anthropic Python SDK.

Provides AnthropicAAEPAdapter, which wraps `anthropic.Anthropic()` calls
and emits AAEP events for every step of an agent session: model invocations,
streaming output, tool use (with safety-gated confirmation), and session
lifecycle events.

Public API:

    from aaep_anthropic_sdk import AnthropicAAEPAdapter, make_adapter

    # Option 1: instantiate directly
    adapter = AnthropicAAEPAdapter(
        send_event=my_transport,
        model="claude-opus-4-7",
    )

    # Option 2: convenience factory
    adapter = make_adapter(send_event=my_transport)

    # Run a session
    session_id = await adapter.run_session(
        user_message="Tell me about retirement planning.",
        tools=[...],
        tool_handlers={...},
    )

See README.md for full usage and design notes.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"

from aaep_anthropic_sdk.adapter import (
    AnthropicAAEPAdapter,
    make_adapter,
)


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    # Public API
    "AnthropicAAEPAdapter",
    "make_adapter",
]
