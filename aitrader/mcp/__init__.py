"""MCP infrastructure servers for aitrader.

Three stdio servers, each pure infrastructure (ZERO trading logic):
    broker_server     exec + market data + broker time facts (owns its connection)
    scheduler_server  blocking waits over the broker's time facts
    journal_server    the agent's durable notebook + reconciliation records
"""
