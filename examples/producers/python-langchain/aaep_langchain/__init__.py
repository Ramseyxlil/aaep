"""
AAEP integration for LangChain agents.

Provides LangChainAAEPHandler, a BaseCallbackHandler subclass that emits
AAEP events as a LangChain agent runs. The handler is non-invasive: it
observes LangChain's callbacks and translates them to AAEP without
modifying agent behavior.

Public API:

    from aaep_langchain import LangChainAAEPHandler, make_aaep_handler

    # Option 1: instantiate directly
    handler = LangChainAAEPHandler(send_event=my_transport)

    # Option 2: convenience factory with sensible defaults
    handler = make_aaep_handler(send_event=my_transport)

    # Attach to any LangChain runnable
    agent_executor.invoke(
        {"input": "..."},
        config={"callbacks": [handler]},
    )

See README.md for full usage and design notes.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"

from aaep_langchain.callback_handler import (
    LangChainAAEPHandler,
    make_aaep_handler,
)


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    # Public API
    "LangChainAAEPHandler",
    "make_aaep_handler",
]
