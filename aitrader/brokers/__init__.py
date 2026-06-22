"""Broker drivers for aitrader.

Concrete Broker implementations and their connection-ownership machinery.
The broker MCP server is the sole owner of broker connections: it
instantiates the connection/pool, runs the ib_async callback pump in its own
daemon thread, and handles reconnect. See ibkr_connection.py / ibkr_pool.py.
"""
