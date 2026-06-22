/// <reference types="vite/client" />

// Runtime API configuration injected by the trader_ui server's /config.js
// route (see bin/trader_ui). Set via the --api-port / --api-host flags so the
// deployment can be reconfigured without rebuilding the bundle.
declare global {
  interface Window {
    __API_PORT__?: string;
    __API_HOST__?: string;
    // Explicit API base (overrides host:port). portd mode sets this to a
    // same-origin path like "/aitrader-api". See bin/trader_ui / src/api.ts.
    __API_BASE__?: string;
  }
}

export {};
