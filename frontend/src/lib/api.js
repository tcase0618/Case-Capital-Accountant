const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    },
    ...options
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = payload.detail;
      }
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(message);
  }

  return response.json();
}

export const api = {
  health: () => request("/health"),
  dashboard: () => request("/api/dashboard"),
  companies: (query = "") => request(`/api/companies${query ? `?q=${encodeURIComponent(query)}` : ""}`),
  company: (ticker) => request(`/api/companies/${ticker}`),
  filings: (ticker) => request(`/api/companies/${ticker}/filings`),
  facts: (ticker, params = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    });
    const suffix = search.size > 0 ? `?${search.toString()}` : "";
    return request(`/api/companies/${ticker}/facts${suffix}`);
  },
  canonicalFacts: (ticker, params = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    });
    const suffix = search.size > 0 ? `?${search.toString()}` : "";
    return request(`/api/companies/${ticker}/canonical-facts${suffix}`);
  },
  statements: (ticker, statementType = "") =>
    request(`/api/companies/${ticker}/statements${statementType ? `?statement_type=${encodeURIComponent(statementType)}` : ""}`),
  research: (ticker) => request(`/api/companies/${ticker}/research-records`),
  timeMachine: (ticker, asOfDate) =>
    request(`/api/companies/${ticker}/time-machine?as_of_date=${encodeURIComponent(asOfDate)}`),
  taxonomy: (category = "") =>
    request(`/api/taxonomy${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  ingestFilings: (ticker) => request(`/api/companies/${ticker}/ingest/filings`, { method: "POST" }),
  ingestCompanyFacts: (ticker) => request(`/api/companies/${ticker}/ingest/companyfacts`, { method: "POST" }),
  normalize: (ticker) => request(`/api/companies/${ticker}/normalize`, { method: "POST" }),
  importCoverage: ({ universeName, tickerBlob }) =>
    request("/api/coverage/import", {
      method: "POST",
      body: JSON.stringify({
        universe_name: universeName,
        ticker_blob: tickerBlob
      })
    }),
  reports: () => request("/api/reports"),
  reportMachineStatus: () => request("/api/reports/status"),
  cacheStatus: () => request("/api/cache/status"),
  runReportMachineOnce: () => request("/api/reports/run-once", { method: "POST" }),
  buyBoard: () => request("/api/buy-board"),
  futureBoard: () => request("/api/future-board"),
  buyBoardStatus: () => request("/api/buy-board/status"),
  refreshBuyBoard: () => request("/api/buy-board/refresh", { method: "POST" }),
  ibkrStatus: () => request("/api/integrations/ibkr"),
  marketQuote: (ticker) => request(`/api/companies/${ticker}/market-quote`)
};
