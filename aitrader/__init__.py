"""aitrader — infrastructure for a persistent autonomous AI trader.

This package contains ZERO trading logic. It is plumbing only: broker/data
primitives, a clock/scheduler, and a journal — exposed as MCP servers. The
runtime is ccloop (the agent runs in a run dir; see CLAUDE.md). Every decision
(what to trade, when, how much, when to exit) is made by the AI agent through
reasoning — never by code in this package.

See CLAUDE.md (the Founding Design Brief) for the hard boundary between
infrastructure (allowed here) and cognition (NEVER here).
"""

__version__ = "1.7.4"
