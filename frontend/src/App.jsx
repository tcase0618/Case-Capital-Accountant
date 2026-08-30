import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useParams
} from "react-router-dom";
import {
  Activity,
  Archive,
  ArrowDownWideNarrow,
  ArrowUpDown,
  BarChart3,
  BookOpen,
  Building2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock3,
  Cpu,
  Database,
  FileSpreadsheet,
  Filter,
  FlaskConical,
  FolderKanban,
  Layers3,
  LayoutGrid,
  LineChart,
  ListFilter,
  Menu,
  Newspaper,
  Radar,
  RefreshCw,
  ScrollText,
  Search,
  ShieldCheck
} from "lucide-react";

import { api } from "./lib/api";
import caseCapitalLogo from "./assets/case-capital-logo.png";

const accent = "#c8a84b";
const accent2 = "#5eead4";
const dim = "#374151";
const muted = "#6b7280";
const labelLight = "#9ca3af";
const cardBg = "#0c0c12";
const pageBg = "#06060a";
const hairline = "0.5px solid rgba(255,255,255,0.06)";
const hairlineAccent = "0.5px solid rgba(200,168,75,0.18)";

const NAV = [
  { to: "/command-center", label: "COMMAND CENTER", short: "CC", icon: LayoutGrid, group: "CORE", color: accent, description: "Live pipeline, queue, workers, and system coverage." },
  { to: "/coverage", label: "COVERAGE", short: "CV", icon: FolderKanban, group: "CORE", color: "#4ade80", description: "Universe intake, registry, and company build operations." },
  { to: "/filings", label: "FILINGS", short: "FG", icon: Newspaper, group: "CORE", color: "#60a5fa", description: "SEC filing ledger with source access and operator review." },
  { to: "/facts", label: "FACTS LAB", short: "FX", icon: FlaskConical, group: "CORE", color: "#f59e0b", description: "Raw-to-canonical fact exploration and mapping quality." },
  { to: "/canonical", label: "CANONICAL", short: "CN", icon: Layers3, group: "ANALYSIS", color: "#a78bfa", description: "Canonical registry and mapped output review." },
  { to: "/time-machine", label: "TIME MACHINE", short: "TM", icon: Clock3, group: "ANALYSIS", color: "#f97316", description: "Point-in-time statement and warning snapshots." },
  { to: "/reports", label: "REPORTS", short: "RP", icon: ScrollText, group: "ANALYSIS", color: "#fb7185", description: "Ranked cached report book and machine status." },
  { to: "/buy-board", label: "BUY BOARD", short: "BB", icon: BarChart3, group: "ANALYSIS", color: "#4ade80", description: "Trade candidates, future upside, and profile cards." },
  { to: "/research", label: "RESEARCH", short: "RS", icon: BookOpen, group: "SYSTEM", color: "#e879f9", description: "Research records and statement snapshot history." }
];

const GROUP_META = {
  CORE: "Live intake and company build surfaces.",
  ANALYSIS: "Mapped outputs, reports, and candidate boards.",
  SYSTEM: "Research state, supporting artifacts, and QA."
};

const TerminalContext = createContext(null);

function App() {
  return (
    <BrowserRouter>
      <TerminalProvider>
        <Routes>
          <Route element={<CrtShell />}>
            <Route path="/" element={<CommandCenterPage />} />
            <Route path="/command-center" element={<CommandCenterPage />} />
            <Route path="/coverage" element={<CoveragePage />} />
            <Route path="/filings" element={<FilingsPage />} />
            <Route path="/facts" element={<FactsLabPage />} />
            <Route path="/canonical" element={<CanonicalPage />} />
            <Route path="/time-machine" element={<TimeMachinePage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/buy-board" element={<BuyBoardPage />} />
            <Route path="/buy-board/:ticker" element={<BuyBoardTickerProfilePage />} />
            <Route path="/research" element={<ResearchPage />} />
          </Route>
        </Routes>
      </TerminalProvider>
    </BrowserRouter>
  );
}

function TerminalProvider({ children }) {
  const [dashboard, setDashboard] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [search, setSearch] = useState("");
  const [ibkr, setIbkr] = useState(null);
  const [marketQuote, setMarketQuote] = useState(null);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [shellError, setShellError] = useState("");
  const [toast, setToast] = useState("");

  const refreshDashboard = useCallback(async () => {
    try {
      const data = await api.dashboard();
      setDashboard(data);
    } catch (error) {
      setShellError(error.message);
    }
  }, []);

  const refreshCompanies = useCallback(async (query = "") => {
    setLoadingCompanies(true);
    try {
      const data = await api.companies(query);
      setCompanies(data);
      setSelectedTicker((current) => {
        if (!data.length) {
          return "";
        }
        if (!current) {
          return data[0].ticker;
        }
        return data.some((item) => item.ticker === current) ? current : data[0].ticker;
      });
    } catch (error) {
      setShellError(error.message);
    } finally {
      setLoadingCompanies(false);
    }
  }, []);

  const refreshIbkrStatus = useCallback(async () => {
    try {
      const data = await api.ibkrStatus();
      setIbkr(data);
    } catch (error) {
      setIbkr({
        ok: false,
        connected: false,
        checked_at: new Date().toISOString(),
        reason: error.message
      });
    }
  }, []);

  const refreshMarketQuote = useCallback(async (ticker) => {
    if (!ticker) {
      setMarketQuote(null);
      return;
    }
    try {
      const data = await api.marketQuote(ticker);
      setMarketQuote(data);
    } catch (error) {
      setMarketQuote({
        ok: false,
        symbol: ticker,
        checked_at: new Date().toISOString(),
        reason: error.message
      });
    }
  }, []);

  useEffect(() => {
    refreshDashboard();
    refreshCompanies();
    refreshIbkrStatus();
    const timer = setInterval(() => {
      refreshDashboard();
      refreshCompanies(search);
      refreshIbkrStatus();
    }, 45000);
    return () => clearInterval(timer);
  }, [refreshDashboard, refreshCompanies, refreshIbkrStatus, search]);

  useEffect(() => {
    refreshMarketQuote(selectedTicker);
  }, [refreshMarketQuote, selectedTicker]);

  useEffect(() => {
    const handle = setTimeout(() => {
      refreshCompanies(search);
    }, 220);
    return () => clearTimeout(handle);
  }, [search, refreshCompanies]);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }
    const timer = setTimeout(() => setToast(""), 3200);
    return () => clearTimeout(timer);
  }, [toast]);

  const value = useMemo(
    () => ({
      dashboard,
      companies,
      selectedTicker,
      setSelectedTicker,
      search,
      setSearch,
      ibkr,
      marketQuote,
      loadingCompanies,
      shellError,
      setShellError,
      toast,
      setToast,
      refreshDashboard,
      refreshCompanies,
      refreshIbkrStatus,
      refreshMarketQuote
    }),
    [
      dashboard,
      companies,
      selectedTicker,
      search,
      ibkr,
      marketQuote,
      loadingCompanies,
      shellError,
      toast,
      refreshDashboard,
      refreshCompanies,
      refreshIbkrStatus,
      refreshMarketQuote
    ]
  );

  return <TerminalContext.Provider value={value}>{children}</TerminalContext.Provider>;
}

function useTerminal() {
  return useContext(TerminalContext);
}

function useClock() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return now;
}

function SystemBar() {
  const now = useClock();
  const { dashboard, selectedTicker, ibkr } = useTerminal();
  const ibkrLive = Boolean(ibkr?.ok && ibkr?.connected);
  const ibkrLabel = ibkrLive ? "IBKR RESEARCH LIVE" : "IBKR RESEARCH STANDBY";
  const ibkrColor = ibkrLive ? "#4ade80" : accent;
  const rawFacts = dashboard?.stats?.total_raw_facts || 0;
  const rawCoverage = dashboard?.stats?.companies_with_raw_facts || 0;
  const factDisplay = rawFacts > 0 || rawCoverage === 0
    ? formatCompactNumber(rawFacts)
    : `${formatCompactNumber(rawCoverage)} CO`;

  const dateStr = now.toLocaleDateString("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    month: "short",
    day: "2-digit",
    year: "numeric"
  }).toUpperCase();

  const timeStr = now.toLocaleTimeString("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });

  return (
    <div
      data-testid="system-bar"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 18,
        padding: "6px 18px",
        background: "#03030680",
        borderBottom: hairline,
        fontSize: 10,
        letterSpacing: "0.14em",
        color: muted,
        fontFamily: "JetBrains Mono, Courier New",
        backdropFilter: "blur(6px)"
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span className="dot dot-green pulse-dot" />
        <span style={{ color: "#4ade80", fontWeight: 700 }}>SEC/XBRL LIVE</span>
      </span>
      <span style={{ color: dim }}>|</span>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span
          className="dot pulse-dot"
          style={{ background: ibkrColor, boxShadow: `0 0 6px ${ibkrColor}66` }}
        />
        <span style={{ color: ibkrColor, fontWeight: 700 }}>{ibkrLabel}</span>
      </span>
      <span style={{ color: dim }}>|</span>
      <span style={{ color: labelLight }}>{dateStr}</span>
      <span style={{ color: dim }}>|</span>
      <span className="num" style={{ color: accent, fontWeight: 700 }}>
        {timeStr} ET<span className="blink">_</span>
      </span>
      <span style={{ color: dim }}>|</span>
      <span style={{ color: selectedTicker ? accent2 : muted, fontWeight: 700 }}>
        {selectedTicker || "NO TICKER SELECTED"}
      </span>
      <span style={{ marginLeft: "auto", display: "flex", gap: 14 }}>
        <span><span className="dot dot-green" /> <span style={{ marginLeft: 6 }}>CO {formatCompactNumber(dashboard?.stats?.total_companies || 0)}</span></span>
        <span><span className="dot dot-amber" /> <span style={{ marginLeft: 6 }}>FIL {formatCompactNumber(dashboard?.stats?.total_filings || 0)}</span></span>
        <span><span className="dot dot-teal" /> <span style={{ marginLeft: 6 }}>FACT {factDisplay}</span></span>
      </span>
    </div>
  );
}

function CrtShell() {
  const {
    companies,
    dashboard,
    selectedTicker,
    setSelectedTicker,
    search,
    setSearch,
    ibkr,
    marketQuote,
    loadingCompanies,
    shellError,
    setShellError,
    toast,
    setToast
  } = useTerminal();
  const location = useLocation();
  const routeMeta = NAV.find((item) => item.to === location.pathname) || NAV[0];
  const title = routeMeta.label;
  const tickerTape = dashboard?.ticker_tape || [];
  const activeCompany = companies.find((item) => item.ticker === selectedTicker);
  const selectedCoverageStatus = activeCompany?.coverage_status?.toUpperCase() || "BOOT";
  const quoteValue = marketQuote?.quote?.last ?? marketQuote?.quote?.close;
  const bidValue = marketQuote?.quote?.bid;
  const askValue = marketQuote?.quote?.ask;
  const ibkrState = ibkr?.ok && ibkr?.connected ? "LIVE" : "STANDBY";
  const ibkrStateColor = ibkrState === "LIVE" ? "#4ade80" : accent;
  const [companyRailCollapsed, setCompanyRailCollapsed] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [companySort, setCompanySort] = useState("status");
  const [companyFilter, setCompanyFilter] = useState("all");
  const filingTape = (dashboard?.recent_filings || []).map(
    (item) => `NEW SEC FILING // ${item.ticker} // ${item.form_type} // ${item.filing_date}`
  );
  const filteredCompanies = useMemo(() => {
    const filtered = companies.filter((company) => {
      if (companyFilter === "all") {
        return true;
      }
      if (companyFilter === "needs-reports") {
        return company.coverage_status !== "reports-ready";
      }
      if (companyFilter === "reports-ready") {
        return company.coverage_status === "reports-ready";
      }
      if (companyFilter === "needs-canonical") {
        return (company.canonical_facts_count || 0) === 0;
      }
      return true;
    });
    const sorted = [...filtered];
    if (companySort === "ticker") {
      sorted.sort((left, right) => left.ticker.localeCompare(right.ticker));
    } else if (companySort === "filings") {
      sorted.sort((left, right) => (right.filings_count || 0) - (left.filings_count || 0));
    } else {
      sorted.sort((left, right) => {
        if ((right.statement_snapshots_count || 0) !== (left.statement_snapshots_count || 0)) {
          return (right.statement_snapshots_count || 0) - (left.statement_snapshots_count || 0);
        }
        if ((right.canonical_facts_count || 0) !== (left.canonical_facts_count || 0)) {
          return (right.canonical_facts_count || 0) - (left.canonical_facts_count || 0);
        }
        return left.ticker.localeCompare(right.ticker);
      });
    }
    return sorted;
  }, [companies, companyFilter, companySort]);
  const pageFreshness = formatTimestampCompact(dashboard?.recent_filings?.[0]?.filing_date);
  const RouteIcon = routeMeta.icon;

  return (
    <>
      <div className="crt-vignette" />
      <div className="scanline-overlay" />
      <div className="crt-grain" />

      <div className="terminal-shell">
        <button
          type="button"
          className="mobile-shell-toggle"
          onClick={() => setSidebarOpen((value) => !value)}
        >
          {sidebarOpen ? <ChevronDown size={15} /> : <Menu size={15} />}
          {sidebarOpen ? "CLOSE RAIL" : "OPEN RAIL"}
        </button>
        <aside
          className={`terminal-sidebar ${sidebarOpen ? "is-open" : ""}`}
          style={{
            background: `linear-gradient(180deg, ${cardBg} 0%, ${pageBg} 100%)`,
            borderRight: hairline,
          }}
        >
          <Link to="/command-center" style={{ textDecoration: "none" }}>
            <div
              className="corner-brackets"
              style={{
                padding: "14px 12px",
                border: hairlineAccent,
                background: "linear-gradient(135deg, rgba(200,168,75,0.06) 0%, transparent 70%)",
                position: "relative",
                overflow: "hidden"
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                  top: "30%",
                  height: 1,
                  background: `linear-gradient(90deg, transparent, ${accent}80, transparent)`,
                  opacity: 0.4
                }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 14, position: "relative" }}>
                <CaseCapitalMark size={56} />
                <div>
                  <MicroLabel text="CASE CAPITAL / INTERNAL SYSTEMS" color={muted} />
                  <div style={{ fontSize: 8, color: muted, letterSpacing: "0.16em", marginTop: 4 }}>
                    ACCOUNTANT TERMINAL
                  </div>
                </div>
              </div>
            </div>
          </Link>

          <div style={{ padding: "10px 10px", border: hairline, background: "rgba(255,255,255,0.012)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
              <MicroLabel text="// COMPANY RAIL" color={dim} />
              <button
                type="button"
                onClick={() => setCompanyRailCollapsed((value) => !value)}
                style={{
                  background: "transparent",
                  border: `0.5px solid ${dim}`,
                  color: companyRailCollapsed ? muted : accent,
                  fontSize: 9,
                  padding: "4px 8px",
                  cursor: "pointer",
                  letterSpacing: "0.12em",
                  fontFamily: "JetBrains Mono"
                }}
              >
                {companyRailCollapsed ? "EXPAND" : "COLLAPSE"}
              </button>
            </div>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 8px",
                border: hairline,
                background: "#050509"
                }}
              >
                <Radar size={12} color={accent2} />
                <input
                  value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="SEARCH"
                style={{
                  width: "100%",
                  border: 0,
                  outline: 0,
                  background: "transparent",
                  color: "#e5e7eb",
                  fontSize: 10,
                  letterSpacing: "0.08em"
                }}
                />
              </label>
            {!companyRailCollapsed && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 8 }}>
                <MiniSelect
                  label="SORT"
                  value={companySort}
                  onChange={setCompanySort}
                  options={[
                    { value: "status", label: "STATUS" },
                    { value: "ticker", label: "TICKER" },
                    { value: "filings", label: "FILINGS" },
                  ]}
                />
                <MiniSelect
                  label="FILTER"
                  value={companyFilter}
                  onChange={setCompanyFilter}
                  options={[
                    { value: "all", label: "ALL" },
                    { value: "needs-reports", label: "QUEUE" },
                    { value: "reports-ready", label: "READY" },
                    { value: "needs-canonical", label: "NO CAN" },
                  ]}
                />
              </div>
            )}
            {!companyRailCollapsed && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "32px 1fr", gap: 8, padding: "7px 4px 0", color: dim, fontSize: 8, letterSpacing: "0.16em" }}>
                  <span>TICK</span>
                  <span>STATUS / COVERAGE</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 8 }}>
                  {loadingCompanies && <SkeletonList rows={5} compact />}
                  {!loadingCompanies && filteredCompanies.length === 0 && <div style={{ color: muted, fontSize: 10 }}>NO COMPANIES MATCH THIS FILTER</div>}
                  {filteredCompanies.slice(0, 24).map((company) => (
                    <button
                      key={company.ticker}
                      type="button"
                      onClick={() => setSelectedTicker(company.ticker)}
                      className="company-rail-row"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "6px 8px",
                        background: selectedTicker === company.ticker ? `${accent}10` : "transparent",
                        border: `0.5px solid ${selectedTicker === company.ticker ? `${accent}55` : "transparent"}`,
                        color: selectedTicker === company.ticker ? accent : labelLight,
                        textAlign: "left",
                        cursor: "pointer"
                      }}
                    >
                      <span style={{ width: 32, color: selectedTicker === company.ticker ? accent : dim, fontWeight: 700 }}>
                        {company.ticker}
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: "block", fontSize: 9, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {company.coverage_status}
                        </span>
                        <span style={{ display: "block", color: dim, fontSize: 8, marginTop: 2 }}>
                          FIL {formatCompactNumber(company.filings_count || 0)} | CAN {formatCompactNumber(company.canonical_facts_count || 0)}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <nav style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {["CORE", "ANALYSIS", "SYSTEM"].map((group) => (
              <div key={group} style={{ marginBottom: 6 }}>
                <div style={{ fontSize: 8, color: dim, letterSpacing: "0.22em", marginBottom: 4, paddingLeft: 4, fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}>
                  <span>{`// ${group}`}</span>
                  <span style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.04)" }} />
                </div>
                {NAV.filter((item) => item.group === group).map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/command-center"}
                    style={({ isActive }) => ({
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "7px 10px",
                      fontSize: 11.5,
                      color: isActive ? item.color : labelLight,
                      background: isActive ? `${item.color}10` : "transparent",
                      borderLeft: `3px solid ${isActive ? item.color : "transparent"}`,
                      textDecoration: "none",
                      letterSpacing: "0.08em",
                      fontWeight: isActive ? 700 : 500
                    })}
                  >
                    <item.icon size={14} strokeWidth={1.8} color={item.color} />
                    <span
                      style={{
                        width: 26,
                        height: 22,
                        minWidth: 26,
                        border: "0.5px solid rgba(255,255,255,0.12)",
                        background: "rgba(255,255,255,0.025)",
                        color: item.color,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 8,
                        fontWeight: 900,
                        letterSpacing: "0.06em"
                      }}
                    >
                      {item.short}
                    </span>
                    <span style={{ display: "grid", gap: 2 }}>
                      <span>{item.label}</span>
                      <span style={{ color: dim, fontSize: 8, letterSpacing: "0.12em" }}>{item.description}</span>
                    </span>
                  </NavLink>
                ))}
                <div style={{ color: dim, fontSize: 8, lineHeight: 1.45, letterSpacing: "0.12em", padding: "6px 10px 2px 40px" }}>
                  {GROUP_META[group]}
                </div>
              </div>
            ))}
          </nav>

          <div style={{ borderTop: hairline, paddingTop: 12 }}>
            <MicroLabel text="// SYSTEM HEALTH" color={dim} />
            <StatusRow label="INGEST" color="#4ade80" />
            <StatusRow label="FACTS" color={accent2} />
            <StatusRow label="CANONICAL" color={accent} />
            <StatusRow label="TIME MACHINE" color="#f97316" />
          </div>

          <div style={{ marginTop: "auto", fontSize: 8, color: dim, letterSpacing: "0.14em", paddingTop: 10, borderTop: hairline }}>
            <div>BUILD 0.2.0 | LOCAL</div>
            <div style={{ marginTop: 3, color: muted }}>Case Capital Accountant</div>
          </div>
        </aside>

        <main className="terminal-main">
          <div style={{ position: "sticky", top: 0, zIndex: 10 }}>
            <SystemBar />
            {location.pathname === "/command-center" && <FilingTape items={filingTape} />}
          </div>

          <div
            style={{
              padding: "22px 30px",
              borderBottom: hairline,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: `linear-gradient(180deg, ${cardBg} 0%, ${pageBg} 100%)`,
              gap: 10
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                <CaseCapitalMark size={28} compact />
                <RouteIcon size={16} color={routeMeta.color} />
                <div style={{ minWidth: 0 }}>
                  <MicroLabel text="CASE CAPITAL / ACCOUNTANT OPERATING SURFACE" color={muted} />
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 5, flexWrap: "wrap" }}>
                    <TopTag label="ROUTE" value={location.pathname.toUpperCase()} color={accent2} />
                    <TopTag label="TICKER" value={selectedTicker || "NONE"} color={selectedTicker ? accent : muted} />
                    <TopTag label="STATE" value={selectedCoverageStatus} color="#4ade80" />
                    <TopTag label="IBKR" value={ibkrState} color={ibkrStateColor} />
                    <TopTag label="LAST" value={formatQuoteValue(quoteValue)} color={quoteValue ? accent : muted} />
                    <TopTag label="BID/ASK" value={`${formatQuoteValue(bidValue)} / ${formatQuoteValue(askValue)}`} color={bidValue || askValue ? "#60a5fa" : muted} />
                    <TopTag label="FRESHNESS" value={pageFreshness} color={labelLight} />
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 9, color: muted, letterSpacing: "0.22em", display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: accent }}>#</span>
                CASE CAP ACCOUNTANT
                <span style={{ color: dim }}>|</span>
                <span style={{ color: accent2 }}>{location.pathname.toUpperCase()}</span>
              </div>
              <div
                style={{
                  fontSize: 26,
                  color: accent,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  marginTop: 6,
                  textShadow: "0 0 12px rgba(200,168,75,0.15)"
                }}
              >
                {title}
              </div>
              <div style={{ marginTop: 8, color: labelLight, fontSize: 11, lineHeight: 1.5, maxWidth: 760 }}>
                {routeMeta.description}
              </div>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button
                type="button"
                onClick={() => setCompanyRailCollapsed((value) => !value)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  minHeight: 34,
                  background: "rgba(255,255,255,0.018)",
                  border: "0.5px solid rgba(255,255,255,0.16)",
                  color: labelLight,
                  padding: "8px 11px",
                  cursor: "pointer",
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  fontFamily: "JetBrains Mono, Courier New",
                  fontWeight: 800
                }}
              >
                {companyRailCollapsed ? <ChevronRight size={13} strokeWidth={2} /> : <ChevronDown size={13} strokeWidth={2} />}
                RAIL
              </button>
              <button
                type="button"
                onClick={() => window.location.reload()}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  minHeight: 34,
                  background: "rgba(255,255,255,0.018)",
                  border: "0.5px solid rgba(94,234,212,0.4)",
                  color: accent2,
                  padding: "8px 11px",
                  cursor: "pointer",
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  fontFamily: "JetBrains Mono, Courier New",
                  fontWeight: 800
                }}
              >
                <RefreshCw size={13} strokeWidth={2} />
                REFRESH
              </button>
            </div>
          </div>

          <div style={{ padding: "22px 30px", flex: 1 }} className="fade-in fade-in-2">
            {shellError && <Banner kind="error" text={shellError} onClose={() => setShellError("")} />}
            {toast && <Banner kind="ok" text={toast} onClose={() => setToast("")} />}
            <Outlet />
          </div>

          <div className="ticker-wrap">
            <div className="ticker-track">
              {[...tickerTape, ...tickerTape].map((item, index) => (
                <span key={`${item}-${index}`} className="ticker-item">{item}</span>
              ))}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}

function CaseCapitalMark({ size = 34, compact = false }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        position: "relative",
        border: `1px solid ${compact ? "rgba(200,168,75,0.28)" : "rgba(200,168,75,0.42)"}`,
        background: "linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(5,5,9,0.35) 100%)",
        boxShadow: "0 0 16px rgba(200,168,75,0.12), inset 0 0 12px rgba(200,168,75,0.05)",
        overflow: "hidden",
        flexShrink: 0,
        display: "grid",
        placeItems: "center"
      }}
    >
      <img
        src={caseCapitalLogo}
        alt="Case Capital"
        style={{
          width: compact ? `${Math.round(size * 0.88)}px` : `${Math.round(size * 0.9)}px`,
          height: compact ? `${Math.round(size * 0.88)}px` : `${Math.round(size * 0.9)}px`,
          objectFit: "contain",
          filter: compact ? "drop-shadow(0 0 8px rgba(200,168,75,0.18))" : "drop-shadow(0 0 12px rgba(200,168,75,0.22))"
        }}
      />
    </div>
  );
}

function MicroLabel({ text, color = muted }) {
  return (
    <div style={{ fontSize: 8, color, letterSpacing: "0.22em", marginBottom: 8, fontWeight: 700 }}>
      {text}
    </div>
  );
}

function TopTag({ label, value, color }) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "5px 8px",
        border: "0.5px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.02)"
      }}
    >
      <span style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>{label}</span>
      <span style={{ color, fontSize: 9, letterSpacing: "0.16em", fontWeight: 700 }}>{value}</span>
    </div>
  );
}

function formatQuoteValue(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toFixed(value >= 10 ? 2 : 4);
}

function formatCompactNumber(value, { currency = false, maximumFractionDigits = 1 } = {}) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "N/A";
  }

  const abs = Math.abs(value);
  if (abs < 1000) {
    if (currency) {
      return `$${Math.round(value)}`;
    }
    if (Number.isInteger(value)) {
      return String(value);
    }
    return value.toFixed(1);
  }

  const formatted = new Intl.NumberFormat("en-US", {
    notation: "compact",
    compactDisplay: "short",
    maximumFractionDigits
  }).format(value);

  return currency ? `$${formatted}` : formatted;
}

function formatDisplayMetric(value) {
  if (typeof value === "number") {
    return formatCompactNumber(value);
  }
  return value ?? "N/A";
}

function CacheSyncBar({ status, warmStatus, fallbackTotal = 0 }) {
  const total = Math.max(status?.total_companies || fallbackTotal || 0, 0);
  const cached = Math.max(status?.reports_cached || 0, 0);
  const pending = Math.max(status?.pending_companies ?? total - cached, 0);
  const progress = total > 0 ? Math.min(100, Math.max(0, (cached / total) * 100)) : 0;
  const syncing = Boolean((status && pending > 0) || warmStatus?.running);
  const action = status?.last_action || warmStatus?.last_action || "cache standing by";
  const candidateText = warmStatus?.active_candidates
    ? `BUY BOARD ${warmStatus.active_candidates}`
    : "BUY BOARD WARMING";

  return (
    <div
      style={{
        border: hairline,
        background: "rgba(255,255,255,0.018)",
        overflow: "hidden",
        position: "relative"
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          width: `${progress}%`,
          background: syncing
            ? "linear-gradient(90deg, rgba(94,234,212,0.28) 0%, rgba(200,168,75,0.48) 100%)"
            : "linear-gradient(90deg, rgba(74,222,128,0.2) 0%, rgba(94,234,212,0.34) 100%)",
          boxShadow: syncing ? "0 0 18px rgba(200,168,75,0.16)" : "0 0 12px rgba(74,222,128,0.14)",
          transition: "width 0.6s ease"
        }}
      />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "8px 12px",
          fontSize: 10,
          letterSpacing: "0.12em",
          color: labelLight,
          flexWrap: "wrap"
        }}
      >
        <span style={{ color: syncing ? accent : "#4ade80", fontWeight: 800 }}>
          {syncing ? "CACHE SYNC" : "CACHE READY"}
        </span>
        <span className="num" style={{ color: "#e5e7eb" }}>
          {formatCompactNumber(cached)} / {formatCompactNumber(total)}
        </span>
        <span style={{ color: dim }}>|</span>
        <span>{formatCompactNumber(pending)} PENDING</span>
        <span style={{ color: dim }}>|</span>
        <span>{candidateText}</span>
        <span style={{ color: dim }}>|</span>
        <span style={{ color: muted, minWidth: 220 }}>{action.toUpperCase()}</span>
      </div>
    </div>
  );
}

function FilingTape({ items }) {
  const tapeItems = items.length ? items : ["NEW SEC FILINGS // STANDBY"];

  return (
    <div className="ticker-wrap ticker-wrap-top">
      <div className="ticker-track ticker-track-fast">
        {[...tapeItems, ...tapeItems].map((item, index) => (
          <span key={`${item}-${index}`} className="ticker-item ticker-item-filing">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function DataQualityBar({ stats, reportStatus }) {
  const companyCount = Math.max(stats.total_companies || 0, 1);
  const reportsCached = Math.max(stats.companies_with_reports || reportStatus?.reports_cached || 0, 0);
  const rawCoverageCount = Math.max(stats.companies_with_raw_facts || 0, 0);
  const canonicalCoverageCount = Math.max(stats.companies_with_canonical_facts || 0, 0);
  const statementCoverageCount = Math.max(stats.companies_with_statement_snapshots || 0, 0);
  const researchCoverageCount = Math.max(stats.companies_with_research_records || 0, 0);

  const rawPct = Math.min(100, (rawCoverageCount / companyCount) * 100);
  const canonicalPct = Math.min(100, (canonicalCoverageCount / companyCount) * 100);
  const reportPct = Math.min(100, (reportsCached / companyCount) * 100);
  const statementPct = Math.min(100, (statementCoverageCount / companyCount) * 100);
  const researchPct = Math.min(100, (researchCoverageCount / companyCount) * 100);
  const totalScore = Math.round((rawPct * 0.15) + (canonicalPct * 0.3) + (reportPct * 0.25) + (statementPct * 0.15) + (researchPct * 0.15));

  const bands = [
    { label: "RAW", value: rawPct, color: accent2 },
    { label: "CANONICAL", value: canonicalPct, color: "#a78bfa" },
    { label: "REPORTS", value: reportPct, color: "#5eead4" },
    { label: "STATEMENTS", value: statementPct, color: "#f97316" },
    { label: "RESEARCH", value: researchPct, color: "#fb7185" }
  ];

  return (
    <div
      style={{
        border: hairline,
        background: "rgba(255,255,255,0.018)",
        padding: "10px 12px",
        display: "grid",
        gap: 10
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <span style={{ color: accent2, fontSize: 10, letterSpacing: "0.16em", fontWeight: 800 }}>
          DATA COVERAGE
        </span>
        <span className="num" style={{ color: "#e5e7eb", fontSize: 16, fontWeight: 800 }}>
          {totalScore}%
        </span>
        <span style={{ color: dim }}>|</span>
        <span style={{ color: muted, fontSize: 10 }}>
          RAW CO {formatCompactNumber(rawCoverageCount)} | CAN CO {formatCompactNumber(canonicalCoverageCount)} | STM CO {formatCompactNumber(statementCoverageCount)} | RPT CO {formatCompactNumber(reportsCached)}
        </span>
      </div>

      <div style={{ display: "grid", gap: 6 }}>
        {bands.map((band) => (
          <div key={band.label} style={{ display: "grid", gridTemplateColumns: "92px 1fr 44px", gap: 8, alignItems: "center" }}>
            <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>{band.label}</div>
            <div style={{ height: 6, border: hairline, background: "rgba(255,255,255,0.02)", position: "relative", overflow: "hidden" }}>
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  width: `${band.value}%`,
                  background: `linear-gradient(90deg, ${band.color}99 0%, ${band.color} 100%)`,
                  boxShadow: `0 0 8px ${band.color}55`
                }}
              />
            </div>
            <div className="num" style={{ color: band.color, fontSize: 9, textAlign: "right", fontWeight: 700 }}>
              {band.value.toFixed(0)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DataTransferBar({ stats }) {
  const totalCompanies = Math.max(stats?.total_companies || 0, 1);
  const filingsCoverage = Math.max(stats?.companies_with_filings || 0, 0);
  const rawCoverage = Math.max(stats?.companies_with_raw_facts || 0, 0);
  const canonicalCoverage = Math.max(stats?.companies_with_canonical_facts || 0, 0);
  const reportCoverage = Math.max(stats?.companies_with_reports || 0, 0);

  const filingPct = Math.min(100, (filingsCoverage / totalCompanies) * 100);
  const rawPct = Math.min(100, (rawCoverage / totalCompanies) * 100);
  const canonicalPct = Math.min(100, (canonicalCoverage / totalCompanies) * 100);
  const reportPct = Math.min(100, (reportCoverage / totalCompanies) * 100);
  const overallPct = Math.round(
    (filingPct * 0.22) +
    (rawPct * 0.38) +
    (canonicalPct * 0.2) +
    (reportPct * 0.2)
  );

  let stageLabel = "SEEDING UNIVERSE";
  let stageColor = "#d0b15a";
  if (filingsCoverage > 0) {
    stageLabel = "INGESTING FILINGS";
    stageColor = "#60a5fa";
  }
  if (rawCoverage > 0) {
    stageLabel = "LANDING RAW FACTS";
    stageColor = accent2;
  }
  if (canonicalCoverage > 0) {
    stageLabel = "CANONICALIZING";
    stageColor = "#a78bfa";
  }
  if (reportCoverage > 0) {
    stageLabel = "BUILDING REPORTS";
    stageColor = "#4ade80";
  }
  if (reportCoverage >= totalCompanies) {
    stageLabel = "TRANSFER COMPLETE";
    stageColor = "#4ade80";
  }

  const phases = [
    { label: "FILINGS", count: filingsCoverage, pct: filingPct, color: "#60a5fa" },
    { label: "RAW", count: rawCoverage, pct: rawPct, color: accent2 },
    { label: "CANONICAL", count: canonicalCoverage, pct: canonicalPct, color: "#a78bfa" },
    { label: "REPORTS", count: reportCoverage, pct: reportPct, color: "#4ade80" }
  ];

  return (
    <div
      style={{
        border: hairline,
        background: "rgba(255,255,255,0.018)",
        overflow: "hidden",
        position: "relative"
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          width: `${overallPct}%`,
          background: `linear-gradient(90deg, ${stageColor}33 0%, ${stageColor}aa 100%)`,
          boxShadow: `0 0 22px ${stageColor}33`,
          transition: "width 0.7s ease"
        }}
      />
      <div
        style={{
          position: "relative",
          zIndex: 1,
          display: "grid",
          gap: 10,
          padding: "10px 12px"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <span style={{ color: stageColor, fontSize: 10, letterSpacing: "0.16em", fontWeight: 800 }}>
            DATA TRANSFER
          </span>
          <span className="num" style={{ color: "#e5e7eb", fontSize: 16, fontWeight: 800 }}>
            {overallPct}%
          </span>
          <span style={{ color: dim }}>|</span>
          <span style={{ color: "#e5e7eb", fontSize: 10, letterSpacing: "0.12em" }}>
            {stageLabel}
          </span>
          <span style={{ color: dim }}>|</span>
          <span style={{ color: muted, fontSize: 10 }}>
            {formatCompactNumber(reportCoverage)} / {formatCompactNumber(totalCompanies)} CO FULLY REPORT-READY
          </span>
        </div>

        <div style={{ display: "grid", gap: 6 }}>
          {phases.map((phase) => (
            <div key={phase.label} style={{ display: "grid", gridTemplateColumns: "92px 1fr 96px 44px", gap: 8, alignItems: "center" }}>
              <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>{phase.label}</div>
              <div style={{ height: 6, border: hairline, background: "rgba(255,255,255,0.02)", position: "relative", overflow: "hidden" }}>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: `${phase.pct}%`,
                    background: `linear-gradient(90deg, ${phase.color}88 0%, ${phase.color} 100%)`,
                    boxShadow: `0 0 8px ${phase.color}55`
                  }}
                />
              </div>
              <div className="num" style={{ color: muted, fontSize: 9, textAlign: "right" }}>
                {formatCompactNumber(phase.count)} CO
              </div>
              <div className="num" style={{ color: phase.color, fontSize: 9, textAlign: "right", fontWeight: 700 }}>
                {phase.pct.toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function WorkerTickerBar({ reportStatus, workerCompanies, companiesPerMinute }) {
  const queueTotal = Math.max(reportStatus?.total_companies || 0, 0);
  const queueBuilt = Math.max(reportStatus?.reports_cached || 0, 0);
  const queueProgress = queueTotal > 0 ? Math.min(100, (queueBuilt / queueTotal) * 100) : 0;
  const workers = (reportStatus?.worker_states || []).length
    ? reportStatus.worker_states
    : [{ worker_id: 1, ticker: null, status: "idle", last_action: reportStatus?.last_action || "idle", last_completed_ticker: reportStatus?.last_processed_ticker || null }];
  const targetWorkerCount = Math.max(workers.length, 8);
  const workerLanes = Array.from({ length: targetWorkerCount }, (_, index) => workers[index] || {
    worker_id: index + 1,
    ticker: null,
    status: "standby",
    last_action: reportStatus?.pending_companies ? "standby" : "queue drained",
    last_completed_ticker: null
  });
  const activeWorkers = workers.filter((worker) => worker.status === "processing");
  const loopLive = Boolean(reportStatus?.running) || activeWorkers.length > 0;
  const heartbeatAge = formatAgeCompact(reportStatus?.last_cycle_at);
  const activeTickers = activeWorkers
    .map((worker) => worker.ticker || worker.last_completed_ticker || "")
    .filter(Boolean)
    .join(", ");

  return (
    <div
      style={{
        border: hairline,
        background: "rgba(255,255,255,0.018)",
        overflow: "hidden",
        position: "relative"
      }}
    >
      <div
        style={{
          position: "relative",
          zIndex: 1,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "8px 12px",
          fontSize: 10,
          letterSpacing: "0.12em",
          color: labelLight,
          flexWrap: "wrap"
        }}
      >
        <span style={{ color: queueProgress >= 100 ? "#4ade80" : "#60a5fa", fontWeight: 800 }}>
          {queueProgress >= 100 ? "SWARM IDLE" : "REPORT SWARM"}
        </span>
        <span className="num" style={{ color: "#e5e7eb" }}>
          {targetWorkerCount}
        </span>
        <span style={{ color: dim }}>|</span>
        <span style={{ color: loopLive ? "#4ade80" : "#f87171" }}>
          {loopLive ? "LOOP LIVE" : "LOOP IDLE"}
        </span>
        <span style={{ color: dim }}>|</span>
        <span style={{ color: muted }}>
          HB {heartbeatAge}
        </span>
        <span style={{ color: dim }}>|</span>
        <span style={{ color: accent2 }}>ACTIVE SWARM</span>
        {activeTickers ? (
          <>
            <span style={{ color: dim }}>|</span>
            <span style={{ color: "#e5e7eb" }}>{activeTickers}</span>
          </>
        ) : null}
        <span style={{ color: dim }}>|</span>
        <span className="num" style={{ color: "#93c5fd" }}>
          {activeWorkers.length}/{targetWorkerCount} ACTIVE
        </span>
        <span style={{ color: dim }}>|</span>
        <span className="num" style={{ color: "#fca5a5" }}>
          {companiesPerMinute !== null ? `${companiesPerMinute.toFixed(1)} CO/MIN` : "RATE N/A"}
        </span>
        <span style={{ color: dim }}>|</span>
        <span style={{ color: muted, minWidth: 280 }}>
          REPORTS {formatCompactNumber(queueBuilt)} / {formatCompactNumber(queueTotal)} // PENDING {formatCompactNumber(reportStatus?.pending_companies || 0)}
        </span>
      </div>
      <div
        style={{
          position: "relative",
          zIndex: 1,
          display: "grid",
          gap: 8,
          padding: "0 12px 10px"
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 8
          }}
        >
        {workerLanes.map((worker) => {
          const workerTicker = worker.ticker || worker.last_completed_ticker || "";
          const workerCompany = workerTicker ? workerCompanies[workerTicker] : null;
          const stageLabel = workerCompany?.coverage_status?.toUpperCase() || (worker.status || "idle").toUpperCase();
          let progress = 4;
          if (workerCompany?.filings_count > 0) progress = 24;
          if (workerCompany?.raw_facts_count > 0) progress = 48;
          if (workerCompany?.canonical_facts_count > 0) progress = 72;
          if (workerCompany?.statement_snapshots_count > 0) progress = 88;
          if (worker.status === "complete") progress = 100;
          if ((reportStatus?.pending_companies || 0) === 0 && !workerTicker) progress = 100;
          const lineColor = progress >= 100 ? "#4ade80" : worker.status === "processing" ? "#60a5fa" : "#d0b15a";
          const label = workerTicker
            ? `WORKER ${worker.worker_id} // ${workerTicker} // ${stageLabel}`
            : reportStatus?.pending_companies
              ? `WORKER ${worker.worker_id} // STANDBY`
              : `WORKER ${worker.worker_id} // QUEUE DRAINED`;
          const detail = workerCompany
            ? `FIL ${formatCompactNumber(workerCompany.filings_count)} | RAW ${formatCompactNumber(workerCompany.raw_facts_count)} | CAN ${formatCompactNumber(workerCompany.canonical_facts_count)} | STM ${formatCompactNumber(workerCompany.statement_snapshots_count)}`
            : (worker.last_action || reportStatus?.last_action || "IDLE").toUpperCase();
          return (
          <div
            key={worker.worker_id}
            style={{
              display: "grid",
              gap: 6,
              padding: "8px 10px",
              border: hairline,
              background: "rgba(255,255,255,0.014)"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>{label}</div>
              <div className="num" style={{ color: lineColor, fontSize: 9, textAlign: "right" }}>
                {progress.toFixed(0)}%
              </div>
            </div>
            <div style={{ height: 5, border: hairline, background: "rgba(255,255,255,0.02)", position: "relative", overflow: "hidden" }}>
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  width: `${progress}%`,
                  background: `linear-gradient(90deg, ${lineColor}55 0%, ${lineColor} 100%)`,
                  boxShadow: `0 0 10px ${lineColor}55`,
                  transition: "width 0.7s ease"
                }}
              />
            </div>
            <div style={{ color: muted, fontSize: 8, letterSpacing: "0.12em" }}>{detail}</div>
          </div>
          );
        })}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "178px 1fr 44px", gap: 8, alignItems: "center", marginTop: 2 }}>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>QUEUE DRAIN</div>
          <div style={{ height: 5, border: hairline, background: "rgba(255,255,255,0.02)", position: "relative", overflow: "hidden" }}>
            <div
              style={{
                position: "absolute",
                inset: 0,
                width: `${queueProgress}%`,
                background: "linear-gradient(90deg, rgba(208,177,90,0.35) 0%, rgba(208,177,90,1) 100%)",
                boxShadow: "0 0 10px rgba(208,177,90,0.35)",
                transition: "width 0.7s ease"
              }}
            />
          </div>
          <div className="num" style={{ color: "#d0b15a", fontSize: 9, textAlign: "right" }}>
            {queueProgress.toFixed(0)}%
          </div>
        </div>
      </div>
    </div>
  );
}

function CommandCenterPage() {
  const { dashboard, selectedTicker, shellError, setShellError } = useTerminal();
  const [reportStatus, setReportStatus] = useState(null);
  const [cacheStatus, setCacheStatus] = useState(null);
  const [workerCompanies, setWorkerCompanies] = useState({});
  const rateSamplesRef = useRef([]);
  const lastRateKeyRef = useRef(null);
  const completionCounterRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    const loadStatus = async () => {
      const [reportResult, cacheResult] = await Promise.allSettled([
        api.reportMachineStatus(),
        api.cacheStatus()
      ]);
      if (cancelled) {
        return;
      }
      if (reportResult.status === "fulfilled") {
        const nextStatus = reportResult.value;
        const now = Date.now();
        const samples = rateSamplesRef.current;
        const last = samples[samples.length - 1];
        const restarted = last && last.startedAt !== nextStatus.started_at;
        const rewound = last && (nextStatus.reports_cached || 0) < last.reportsCached;
        const completionKey = nextStatus.last_processed_ticker && nextStatus.last_cycle_at
          ? `${nextStatus.last_processed_ticker}:${nextStatus.last_cycle_at}`
          : null;
        if (restarted || rewound) {
          completionCounterRef.current = 0;
          lastRateKeyRef.current = completionKey;
        }
        const reportDelta = Math.max(0, (nextStatus.reports_cached || 0) - (last?.reportsCached || 0));
        const tickerAdvanced = Boolean(
          completionKey &&
          lastRateKeyRef.current &&
          completionKey !== lastRateKeyRef.current
        );
        const completionDelta = reportDelta > 0 ? reportDelta : (tickerAdvanced ? 1 : 0);
        completionCounterRef.current += completionDelta;
        lastRateKeyRef.current = completionKey;
        const nextSamples = restarted || rewound
          ? []
          : samples.filter((sample) => now - sample.ts <= 10 * 60 * 1000);
        nextSamples.push({
          ts: now,
          reportsCached: nextStatus.reports_cached || 0,
          completionCount: completionCounterRef.current,
          startedAt: nextStatus.started_at || null,
        });
        rateSamplesRef.current = nextSamples;
        setReportStatus(nextStatus);
      }
      if (cacheResult.status === "fulfilled") {
        setCacheStatus(cacheResult.value);
      }
      if (reportResult.status === "rejected" && cacheResult.status === "rejected") {
        setCacheStatus((current) => current);
      }
    };

    loadStatus();
    const timer = setInterval(loadStatus, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tickers = Array.from(
      new Set(
        (reportStatus?.worker_states || [])
          .map((worker) => worker?.ticker || worker?.last_completed_ticker || "")
          .filter(Boolean)
      )
    );

    if (tickers.length === 0) {
      setWorkerCompanies({});
      return undefined;
    }

    Promise.allSettled(tickers.map((ticker) => api.company(ticker)))
      .then((results) => {
        if (!cancelled) {
          const next = {};
          results.forEach((result, index) => {
            if (result.status === "fulfilled") {
              next[tickers[index]] = result.value;
            }
          });
          setWorkerCompanies(next);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWorkerCompanies({});
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reportStatus?.worker_states, reportStatus?.last_action, reportStatus?.last_processed_ticker]);

  const companiesPerMinute = useMemo(() => {
    const samples = rateSamplesRef.current;
    if (samples.length < 2) {
      return null;
    }
    const first = samples[0];
    const last = samples[samples.length - 1];
    const reportsDelta = (last.completionCount || 0) - (first.completionCount || 0);
    const msDelta = last.ts - first.ts;
    if (reportsDelta < 0 || msDelta <= 0) {
      return null;
    }
    return reportsDelta * (60000 / msDelta);
  }, [reportStatus]);

  if (!dashboard) {
    return (
      <div style={{ display: "grid", gap: 18 }}>
        {shellError && <Banner kind="error" text={shellError} onClose={() => setShellError("")} />}
        <Card title="COMMAND CENTER" accentColor={accent}>
          <Empty text="BOOTING ACCOUNTANT COMMAND CENTER..." />
        </Card>
      </div>
    );
  }

  const stats = dashboard.stats;
  const rawFactsReady = (stats.total_raw_facts || 0) > 0 || (stats.companies_with_raw_facts || 0) === 0;
  const canonicalFactsReady = (stats.total_canonical_facts || 0) > 0 || (stats.companies_with_canonical_facts || 0) === 0;
  const topCoverage = dashboard.coverage.slice(0, 6);
  const selectedCoverage = dashboard.coverage.find((item) => item.ticker === selectedTicker);

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <CacheSyncBar
        status={reportStatus}
        warmStatus={cacheStatus}
        fallbackTotal={stats.total_companies}
      />

      <DataTransferBar stats={stats} />

      <WorkerTickerBar
        reportStatus={reportStatus}
        workerCompanies={workerCompanies}
        companiesPerMinute={companiesPerMinute}
      />

      <DataQualityBar
        stats={stats}
        reportStatus={reportStatus}
      />

      <Card title="COMMAND OVERVIEW" accentColor={accent}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0 }}>
          <Stat label="COMPANIES" value={stats.total_companies} sub="Tracked issuers in local coverage" color={accent} accentBar />
          <Stat label="FILINGS" value={stats.total_filings} sub="Source SEC filings landed" color="#60a5fa" />
          <Stat
            label="RAW FACTS"
            value={rawFactsReady ? stats.total_raw_facts : `${formatCompactNumber(stats.companies_with_raw_facts || 0)} CO`}
            sub={rawFactsReady ? "CompanyFacts observations loaded" : "Background total sync pending; company coverage is live"}
            color={accent2}
            isText={!rawFactsReady}
          />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0, borderTop: hairline }}>
          <Stat
            label="CANONICAL FACTS"
            value={canonicalFactsReady ? stats.total_canonical_facts : `${formatCompactNumber(stats.companies_with_canonical_facts || 0)} CO`}
            sub={canonicalFactsReady ? "Mapped internal concepts" : "Background total sync pending; company coverage is live"}
            color="#a78bfa"
            isText={!canonicalFactsReady}
          />
          <Stat label="STATEMENTS" value={stats.total_statement_snapshots} sub="Statement snapshots assembled" color="#f97316" />
          <Stat label="RESEARCH RECORDS" value={stats.total_research_records} sub="Analyst layer artifacts" color="#e879f9" />
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18 }}>
        <Card title="MISSION STACK" accentColor={accent2}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            <MissionTile
              label="SOURCE OF TRUTH"
              value="SEC"
              color={accent}
              detail="This terminal stays ledger-first: filings, XBRL facts, canonical mappings, then research."
            />
            <MissionTile
              label="CURRENT FOCUS"
              value={selectedTicker || "PICK"}
              color={accent2}
              detail="Use the left rail to drive every page from one selected coverage name."
            />
            <MissionTile
              label="ACCOUNTING POSTURE"
              value={selectedCoverage?.coverage_status?.toUpperCase() || "BOOT"}
              color="#4ade80"
              detail="Coverage status reflects how far a company has progressed through the ingest pipeline."
            />
          </div>
        </Card>

        <Card title="INTEL TAPE" accentColor="#60a5fa">
          <IntelBlock
            icon={Activity}
            title="RECENT FILINGS"
            body={`${dashboard.recent_filings.length} newest filing events are staged for operator review.`}
          />
          <IntelBlock
            icon={Database}
            title="PIPELINE BACKLOG"
            body={dashboard.backlog[0]}
          />
          <IntelBlock
            icon={ShieldCheck}
            title="CONTROL RULE"
            body="No market-data assumptions. This build stays accounting-first until external APIs are explicitly wired."
          />
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 18 }}>
        <Card title="TOP COVERAGE" accentColor="#4ade80">
          {topCoverage.length === 0 ? (
            <Empty text="NO COMPANIES PRESENT IN LOCAL COVERAGE." />
          ) : (
            topCoverage.map((item) => (
              <div key={item.ticker} style={{ padding: "10px 0", borderBottom: hairline }}>
                <div style={{ display: "grid", gridTemplateColumns: "90px 1fr 120px", gap: 10 }}>
                  <span style={{ color: accent, fontWeight: 700 }}>{item.ticker}</span>
                  <span style={{ color: labelLight }}>{item.name}</span>
                    <span style={{ color: "#4ade80", textAlign: "right", fontSize: 10 }}>{item.coverage_status}</span>
                </div>
                <div style={{ marginTop: 6, color: muted, fontSize: 10 }}>
                  FIL {formatCompactNumber(item.filings_count)} | RAW {formatCompactNumber(item.raw_facts_count)} | CAN {formatCompactNumber(item.canonical_facts_count)} | STM {formatCompactNumber(item.statement_snapshots_count)}
                </div>
              </div>
            ))
          )}
        </Card>

        <Card title="LATEST FEED" accentColor="#60a5fa">
          {dashboard.recent_filings.length === 0 ? (
            <Empty text="NO FILING EVENTS HAVE BEEN INGESTED YET." />
          ) : (
            dashboard.recent_filings.map((item) => (
              <div key={`${item.ticker}-${item.accession_number}`} style={{ padding: "10px 0", borderBottom: hairline }}>
                <div style={{ display: "grid", gridTemplateColumns: "70px 1fr 64px", gap: 10 }}>
                  <span style={{ color: "#60a5fa", fontWeight: 700 }}>{item.ticker}</span>
                  <span style={{ color: labelLight }}>{item.company_name}</span>
                  <span style={{ color: accent, textAlign: "right" }}>{item.form_type}</span>
                </div>
                <div style={{ marginTop: 6, color: muted, fontSize: 10 }}>
                  {item.filing_date} | {item.accession_number}
                </div>
              </div>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}

function CoveragePage() {
  const { companies, selectedTicker, setShellError, setToast, refreshDashboard, refreshCompanies } = useTerminal();
  const [running, setRunning] = useState("");
  const [universeName, setUniverseName] = useState("RUSSELL 2000 / NASDAQ / S&P 500");
  const [tickerBlob, setTickerBlob] = useState("");
  const pastedTickerCount = useMemo(
    () => tickerBlob.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean).length,
    [tickerBlob]
  );

  const runAction = async (key, action) => {
    if (!selectedTicker) {
      setShellError("Select a ticker from the left rail first.");
      return;
    }
    setRunning(key);
    try {
      const result = await action(selectedTicker);
      setToast(result.message);
      await refreshDashboard();
      await refreshCompanies();
    } catch (error) {
      setShellError(error.message);
    } finally {
      setRunning("");
    }
  };

  const importUniverse = async () => {
    if (!tickerBlob.trim()) {
      setShellError("Paste a ticker list before importing coverage.");
      return;
    }
    setRunning("coverage-import");
    try {
      const result = await api.importCoverage({ universeName, tickerBlob });
      const unresolved = result.unresolved.length ? ` | unresolved ${result.unresolved.length}` : "";
      const invalid = result.invalid.length ? ` | invalid ${result.invalid.length}` : "";
      setToast(`IMPORT ${result.imported} NEW | ${result.existing} EXISTING${unresolved}${invalid}`);
      setTickerBlob("");
      await refreshDashboard();
      await refreshCompanies();
    } catch (error) {
      setShellError(error.message);
    } finally {
      setRunning("");
    }
  };

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Card title="COVERAGE UNIVERSE INTAKE" accentColor={accent2}>
        <PageSectionHeader
          title="UNIVERSE BUILD CONSOLE"
          description="Paste or stage ticker sets before import. The registry below is the operator-facing intake queue for filings, facts, canonical mapping, and report construction."
          chips={[
            { label: "SEEDED", value: formatCompactNumber(companies.length), color: accent2 },
            { label: "SELECTED", value: selectedTicker || "NONE", color: selectedTicker ? accent : muted },
            { label: "PASTED", value: formatCompactNumber(pastedTickerCount), color: "#4ade80" }
          ]}
        />
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 12 }}>
            <FilterInput value={universeName} onChange={setUniverseName} label="UNIVERSE LABEL" />
            <div style={{ border: hairline, background: "#050509", padding: 10 }}>
              <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em", marginBottom: 8 }}>
                PASTE COMMA, SPACE, OR NEWLINE-DELIMITED TICKERS
              </div>
              <textarea
                value={tickerBlob}
                onChange={(event) => setTickerBlob(event.target.value)}
                placeholder="AAPL, MSFT, AMZN, GOOGL..."
                style={{
                  width: "100%",
                  minHeight: 120,
                  resize: "vertical",
                  border: 0,
                  outline: 0,
                  background: "transparent",
                  color: "#e5e7eb",
                  fontFamily: "JetBrains Mono, Courier New, monospace",
                  fontSize: 11,
                  lineHeight: 1.5
                }}
              />
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <div style={{ color: muted, fontSize: 10, letterSpacing: "0.12em" }}>
              Use this for full universe loads after you paste Russell 2000, Nasdaq, or S&P 500 ticker lists. Input accepts comma, space, or newline delimiters.
            </div>
            <button
              type="button"
              disabled={!!running}
              onClick={importUniverse}
              style={{
                background: running === "coverage-import" ? "rgba(94,234,212,0.12)" : "transparent",
                border: `0.5px solid ${accent2}`,
                color: accent2,
                fontSize: 10,
                padding: "8px 14px",
                cursor: running ? "wait" : "pointer",
                letterSpacing: "0.12em",
                fontFamily: "JetBrains Mono"
              }}
            >
              {running === "coverage-import" ? "IMPORTING..." : "IMPORT COVERAGE"}
            </button>
          </div>
        </div>
      </Card>

      <Card title="COVERAGE REGISTRY" accentColor="#4ade80">
        <PageSectionHeader
          title="REGISTRY TABLE"
          description="Sortable registry view of seeded companies and their ingest depth. Use the left rail for selection and this table for broad queue inspection."
          chips={[
            { label: "COMPANIES", value: formatCompactNumber(companies.length), color: "#4ade80" },
            { label: "REPORT-READY", value: formatCompactNumber(companies.filter((company) => company.coverage_status === "reports-ready").length), color: "#60a5fa" }
          ]}
        />
        <DataTable
          columns={["TICKER", "STATUS", "FILINGS", "FACTS", "CANONICAL", "SNAPSHOTS"]}
          rows={companies.map((company) => [
            company.ticker,
            company.coverage_status,
            company.filings_count,
            company.raw_facts_count,
            company.canonical_facts_count,
            company.statement_snapshots_count
          ])}
        />
      </Card>

      <Card title={`BUILD ${selectedTicker || "SELECTION"}`} accentColor={accent}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
          <ActionPanel
            title="INGEST FILINGS"
            body="Pull SEC submissions metadata and source documents into the local ledger."
            button={running === "filings" ? "RUNNING..." : "RUN"}
            disabled={!!running}
            onClick={() => runAction("filings", api.ingestFilings)}
          />
          <ActionPanel
            title="INGEST COMPANYFACTS"
            body="Pull raw XBRL facts from SEC CompanyFacts and link them to filing accessions."
            button={running === "facts" ? "RUNNING..." : "RUN"}
            disabled={!!running}
            onClick={() => runAction("facts", api.ingestCompanyFacts)}
          />
          <ActionPanel
            title="NORMALIZE CANONICAL"
            body="Map raw concepts into the Case Capital canonical taxonomy for downstream research."
            button={running === "canonical" ? "RUNNING..." : "RUN"}
            disabled={!!running}
            onClick={() => runAction("canonical", api.normalize)}
          />
        </div>
      </Card>
    </div>
  );
}

function FilingsPage() {
  const { selectedTicker, setShellError } = useTerminal();
  const [filings, setFilings] = useState([]);
  const [formFilter, setFormFilter] = useState("all");

  useEffect(() => {
    if (!selectedTicker) {
      setFilings([]);
      return;
    }
    api.filings(selectedTicker)
      .then(setFilings)
      .catch((error) => setShellError(error.message));
  }, [selectedTicker, setShellError]);
  const visibleFilings = useMemo(() => {
    if (formFilter === "all") {
      return filings;
    }
    return filings.filter((filing) => filing.form_type === formFilter);
  }, [filings, formFilter]);
  const forms = useMemo(() => ["all", ...Array.from(new Set(filings.map((filing) => filing.form_type).filter(Boolean)))], [filings]);

  return (
    <Card title={`FILING LEDGER ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#60a5fa">
      <PageSectionHeader
        title="SEC FILING LEDGER"
        description="Source filing events for the selected issuer. Filter by form type and jump directly to the SEC archive when a filing needs manual review."
        chips={[
          { label: "TICKER", value: selectedTicker || "NONE", color: selectedTicker ? accent : muted },
          { label: "ROWS", value: formatCompactNumber(visibleFilings.length), color: "#60a5fa" }
        ]}
        actions={
          <MiniSelect
            label="FORM"
            value={formFilter}
            onChange={setFormFilter}
            options={forms.map((form) => ({ value: form, label: form.toUpperCase() }))}
          />
        }
      />
      {visibleFilings.length === 0 ? (
        <Empty text="NO FILINGS IN VIEW. SEED A COMPANY FROM COVERAGE OPS." />
      ) : (
        visibleFilings.map((filing) => (
          <div key={filing.id} style={{ padding: "10px 0", borderBottom: hairline }}>
            <div style={{ display: "grid", gridTemplateColumns: "140px 1fr 120px", gap: 10 }}>
              <span style={{ color: accent, fontWeight: 700 }}>{filing.form_type}</span>
              <span style={{ color: labelLight }}>{filing.accession_number}</span>
              <span style={{ color: dim, textAlign: "right", fontSize: 10 }}>{filing.filing_date}</span>
            </div>
            <div style={{ marginTop: 6, fontSize: 10, color: muted }}>
              ACCEPTED {filing.accepted_at || "N/A"} | REPORT {filing.report_date || "N/A"} | {filing.primary_document || "NO PRIMARY DOC"}
            </div>
            {filing.source_url && (
              <a href={filing.source_url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa", fontSize: 10, marginTop: 6, display: "inline-block" }}>
                OPEN SEC ARCHIVE
              </a>
            )}
          </div>
        ))
      )}
    </Card>
  );
}

function FactsLabPage() {
  const { selectedTicker, setShellError } = useTerminal();
  const [facts, setFacts] = useState([]);
  const [canonicalFacts, setCanonicalFacts] = useState([]);
  const [concept, setConcept] = useState("");
  const [taxonomy, setTaxonomy] = useState("");
  const [factsMode, setFactsMode] = useState("raw");

  useEffect(() => {
    if (!selectedTicker) {
      setFacts([]);
      setCanonicalFacts([]);
      return;
    }
    Promise.all([
      api.facts(selectedTicker, { concept, taxonomy, limit: 25 }),
      api.canonicalFacts(selectedTicker, { limit: 25 })
    ])
      .then(([rawData, canonicalData]) => {
        setFacts(rawData);
        setCanonicalFacts(canonicalData);
      })
      .catch((error) => setShellError(error.message));
  }, [selectedTicker, concept, taxonomy, setShellError]);
  const topConcepts = useMemo(() => {
    const counts = new Map();
    facts.forEach((fact) => {
      const key = fact.concept || "UNKNOWN";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()]
      .sort((left, right) => right[1] - left[1])
      .slice(0, 6);
  }, [facts]);
  const confidenceBands = useMemo(() => {
    const bands = { high: 0, medium: 0, low: 0 };
    canonicalFacts.forEach((fact) => {
      const value = Number(fact.mapping_confidence || 0);
      if (value >= 0.9) bands.high += 1;
      else if (value >= 0.7) bands.medium += 1;
      else bands.low += 1;
    });
    return bands;
  }, [canonicalFacts]);

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Card title="FACT FILTERS" accentColor="#f59e0b">
        <PageSectionHeader
          title="FACT EXPLORER"
          description="Use raw concept and taxonomy filters to narrow SEC fact payloads, then switch between raw and mapped views."
          chips={[
            { label: "RAW", value: formatCompactNumber(facts.length), color: "#f59e0b" },
            { label: "CANONICAL", value: formatCompactNumber(canonicalFacts.length), color: "#a78bfa" }
          ]}
          actions={
            <div className="toolbar-cluster">
              {[
                { id: "raw", label: "RAW FACTS" },
                { id: "mapped", label: "MAPPED FACTS" }
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`chip-button ${factsMode === item.id ? "is-active" : ""}`}
                  onClick={() => setFactsMode(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          }
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <FilterInput value={concept} onChange={setConcept} label="RAW CONCEPT" />
          <FilterInput value={taxonomy} onChange={setTaxonomy} label="TAXONOMY" />
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <Card title="FACT SIGNALS" accentColor="#f59e0b">
          <PageSectionHeader
            title="RAW CONCEPT DENSITY"
            description="Most frequent raw concepts in the current filtered result set."
          />
          {topConcepts.length === 0 ? <Empty text="NO RAW FACTS RETURNED FOR THIS FILTER." /> : (
            <MetricBarList
              items={topConcepts.map(([label, value]) => ({ label, value, color: "#f59e0b" }))}
            />
          )}
        </Card>

        <Card title="MAPPING QUALITY" accentColor="#a78bfa">
          <PageSectionHeader
            title="CONFIDENCE BANDS"
            description="Quick read on canonical mapping confidence for the returned mapped facts."
          />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            <MiniMetric k="HIGH" v={confidenceBands.high} color="#4ade80" />
            <MiniMetric k="MED" v={confidenceBands.medium} color="#f59e0b" />
            <MiniMetric k="LOW" v={confidenceBands.low} color="#f87171" />
          </div>
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: factsMode === "raw" ? "1.3fr 0.7fr" : "0.7fr 1.3fr", gap: 18 }}>
        <Card title={`RAW FACTS ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#f59e0b">
          <DataTable
            columns={["CONCEPT", "TAXONOMY", "PERIOD", "VALUE", "FORM"]}
            rows={facts.map((fact) => [
              fact.concept,
              fact.taxonomy || "N/A",
              fact.period_end || fact.instant_date || "N/A",
              fact.value_numeric || fact.value_text || "N/A",
              fact.form || "N/A"
            ])}
          />
        </Card>

        <Card title={`CANONICAL FACTS ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#a78bfa">
          <DataTable
            columns={["CANONICAL", "RAW SOURCE", "PERIOD", "VALUE", "CONFIDENCE"]}
            rows={canonicalFacts.map((fact) => [
              fact.canonical_concept_code,
              `${fact.raw_taxonomy || "N/A"}:${fact.raw_concept || "N/A"}`,
              fact.period_end || "N/A",
              fact.value_numeric || fact.value || "N/A",
              fact.mapping_confidence
            ])}
          />
        </Card>
      </div>
    </div>
  );
}

function CanonicalPage() {
  const { selectedTicker, setShellError } = useTerminal();
  const [taxonomyRows, setTaxonomyRows] = useState([]);
  const [canonicalFacts, setCanonicalFacts] = useState([]);
  const [taxonomyQuery, setTaxonomyQuery] = useState("");

  useEffect(() => {
    Promise.all([
      api.taxonomy(),
      selectedTicker ? api.canonicalFacts(selectedTicker, { limit: 20 }) : Promise.resolve([])
    ])
      .then(([taxonomyData, factsData]) => {
        setTaxonomyRows(taxonomyData);
        setCanonicalFacts(factsData);
      })
      .catch((error) => setShellError(error.message));
  }, [selectedTicker, setShellError]);
  const visibleTaxonomyRows = useMemo(() => {
    const query = taxonomyQuery.trim().toLowerCase();
    if (!query) {
      return taxonomyRows;
    }
    return taxonomyRows.filter((row) =>
      [row.code, row.label, row.category, row.unit_hint].some((value) =>
        String(value || "").toLowerCase().includes(query)
      )
    );
  }, [taxonomyRows, taxonomyQuery]);
  const mappedConfidenceBands = useMemo(() => {
    const bands = { strong: 0, watch: 0, weak: 0 };
    canonicalFacts.forEach((fact) => {
      const score = Number(fact.mapping_confidence || 0);
      if (score >= 0.9) bands.strong += 1;
      else if (score >= 0.7) bands.watch += 1;
      else bands.weak += 1;
    });
    return bands;
  }, [canonicalFacts]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
      <Card title="CANONICAL REGISTRY" accentColor="#a78bfa">
        <PageSectionHeader
          title="REGISTRY SEARCH"
          description="Search canonical codes, labels, categories, and unit hints before checking mapped output for the active company."
          chips={[
            { label: "MATCHES", value: formatCompactNumber(visibleTaxonomyRows.length), color: "#a78bfa" }
          ]}
          actions={<FilterInput value={taxonomyQuery} onChange={setTaxonomyQuery} label="SEARCH REGISTRY" />}
        />
        <DataTable
          columns={["CODE", "LABEL", "CATEGORY", "UNIT", "VERSION"]}
          rows={visibleTaxonomyRows.slice(0, 40).map((row) => [
            row.code,
            row.label,
            row.category || "N/A",
            row.unit_hint || "N/A",
            row.version
          ])}
        />
      </Card>

      <Card title={`MAPPED OUTPUT ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#e879f9">
        <PageSectionHeader
          title="MAPPED OUTPUT QA"
          description="Mapped concept output for the active issuer, with confidence severity visible in one place."
          chips={[
            { label: "STRONG", value: formatCompactNumber(mappedConfidenceBands.strong), color: "#4ade80" },
            { label: "WATCH", value: formatCompactNumber(mappedConfidenceBands.watch), color: "#f59e0b" },
            { label: "WEAK", value: formatCompactNumber(mappedConfidenceBands.weak), color: "#f87171" }
          ]}
        />
        {canonicalFacts.length === 0 ? (
          <Empty text="NO CANONICAL FACTS AVAILABLE FOR THE SELECTED COMPANY." />
        ) : (
          canonicalFacts.map((fact) => (
            <div key={fact.id} style={{ padding: "10px 0", borderBottom: hairline }}>
              <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 80px", gap: 10 }}>
                <span style={{ color: accent, fontWeight: 700 }}>{fact.canonical_concept_code}</span>
                <span style={{ color: labelLight }}>{fact.raw_taxonomy || "N/A"}:{fact.raw_concept || "N/A"}</span>
                <span style={{ color: "#e879f9", textAlign: "right", fontSize: 10 }}>{fact.mapping_confidence}</span>
              </div>
              <div style={{ marginTop: 6, color: muted, fontSize: 10 }}>
                {fact.period_end || "N/A"} | {fact.value_numeric || fact.value || "N/A"}
              </div>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}

function TimeMachinePage() {
  const { selectedTicker, setShellError } = useTerminal();
  const [asOfDate, setAsOfDate] = useState("2025-12-31");
  const [snapshot, setSnapshot] = useState(null);
  const [compareDate, setCompareDate] = useState("2024-12-31");
  const [compareSnapshot, setCompareSnapshot] = useState(null);
  const datePresets = ["2026-06-30", "2025-12-31", "2024-12-31", "2023-12-31"];

  useEffect(() => {
    if (!selectedTicker || !asOfDate) {
      setSnapshot(null);
      return;
    }
    api.timeMachine(selectedTicker, asOfDate)
      .then(setSnapshot)
      .catch((error) => setShellError(error.message));
  }, [selectedTicker, asOfDate, setShellError]);
  useEffect(() => {
    if (!selectedTicker || !compareDate) {
      setCompareSnapshot(null);
      return;
    }
    api.timeMachine(selectedTicker, compareDate)
      .then(setCompareSnapshot)
      .catch((error) => setShellError(error.message));
  }, [selectedTicker, compareDate, setShellError]);
  const snapshotDelta = useMemo(() => {
    if (!snapshot || !compareSnapshot) {
      return null;
    }
    return {
      raw: (snapshot.raw_fact_coverage_pct || 0) - (compareSnapshot.raw_fact_coverage_pct || 0),
      completeness: (snapshot.statement_completeness_score || 0) - (compareSnapshot.statement_completeness_score || 0),
      annual: (snapshot.available_annual_filings?.length || 0) - (compareSnapshot.available_annual_filings?.length || 0),
      warnings: (snapshot.warnings?.length || 0) - (compareSnapshot.warnings?.length || 0),
    };
  }, [compareSnapshot, snapshot]);

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Card title="HISTORICAL DATE SELECTOR" accentColor="#f97316">
        <PageSectionHeader
          title="POINT-IN-TIME SNAPSHOT"
          description="Jump between predefined dates or enter a custom date to inspect available filings, data completeness, and warning conditions."
          chips={[
            { label: "TICKER", value: selectedTicker || "NONE", color: selectedTicker ? accent : muted },
            { label: "AS OF", value: asOfDate, color: "#f97316" }
          ]}
        />
        <input
          type="date"
          value={asOfDate}
          onChange={(event) => setAsOfDate(event.target.value)}
          style={{
            width: 220,
            background: "#050509",
            border: hairline,
            color: "#e5e7eb",
            padding: "8px 10px"
          }}
        />
        <div className="toolbar-cluster" style={{ marginTop: 12 }}>
          {datePresets.map((preset) => (
            <button
              key={preset}
              type="button"
              className={`chip-button ${asOfDate === preset ? "is-active" : ""}`}
              onClick={() => setAsOfDate(preset)}
            >
              {preset}
            </button>
          ))}
        </div>
        <label style={{ display: "grid", gap: 8, marginTop: 14, width: 220 }}>
          <span style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>COMPARE DATE</span>
          <input
            type="date"
            value={compareDate}
            onChange={(event) => setCompareDate(event.target.value)}
            style={{
              background: "#050509",
              border: hairline,
              color: "#e5e7eb",
              padding: "8px 10px"
            }}
          />
        </label>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <Card title={`SNAPSHOT ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#f97316">
          {!snapshot ? (
            <Empty text="NO SNAPSHOT LOADED." />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
              <MiniMetric k="10-KS" v={snapshot.available_annual_filings.length} color={accent} />
              <MiniMetric k="10-QS" v={snapshot.available_quarterly_filings.length} color={accent2} />
              <MiniMetric k="AMENDMENTS" v={snapshot.available_amendments.length} color="#f87171" />
              <MiniMetric k="RAW FACT COVERAGE" v={`${snapshot.raw_fact_coverage_pct.toFixed(1)}%`} color="#ffffff" />
              <MiniMetric k="STATEMENT COMPLETENESS" v={`${snapshot.statement_completeness_score.toFixed(1)}%`} color="#fb923c" />
              <MiniMetric k="VALUATION INPUTS" v={snapshot.valuation_inputs_available ? "READY" : "NO"} color={snapshot.valuation_inputs_available ? "#4ade80" : "#f87171"} />
            </div>
          )}
        </Card>

        <Card title="WARNING TAPE" accentColor="#f87171">
          {!snapshot ? (
            <Empty text="RUN A SNAPSHOT FIRST." />
          ) : snapshot.warnings.length === 0 ? (
            <Empty text="NO WARNINGS RETURNED." />
          ) : (
            snapshot.warnings.map((warning) => (
              <div key={warning} style={{ padding: "8px 0", borderBottom: hairline, color: labelLight, fontSize: 11 }}>
                {warning}
              </div>
            ))
          )}
        </Card>
      </div>

      <Card title="COMPARE DELTA" accentColor="#fb923c">
        <PageSectionHeader
          title="DATE-OVER-DATE COMPARISON"
          description="Quick comparison between the primary snapshot date and the selected compare date."
          chips={[
            { label: "PRIMARY", value: asOfDate, color: "#f97316" },
            { label: "COMPARE", value: compareDate, color: "#60a5fa" }
          ]}
        />
        {!snapshotDelta ? (
          <Empty text="LOAD BOTH SNAPSHOTS TO SEE DATE-OVER-DATE DELTAS." />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            <MiniMetric k="RAW DELTA" v={formatPctSigned(snapshotDelta.raw)} color={snapshotDelta.raw >= 0 ? "#4ade80" : "#f87171"} />
            <MiniMetric k="COMPLETE DELTA" v={formatPctSigned(snapshotDelta.completeness)} color={snapshotDelta.completeness >= 0 ? "#4ade80" : "#f87171"} />
            <MiniMetric k="10-K/10-Q DELTA" v={snapshotDelta.annual >= 0 ? `+${snapshotDelta.annual}` : String(snapshotDelta.annual)} color={snapshotDelta.annual >= 0 ? "#4ade80" : "#f87171"} />
            <MiniMetric k="WARNING DELTA" v={snapshotDelta.warnings >= 0 ? `+${snapshotDelta.warnings}` : String(snapshotDelta.warnings)} color={snapshotDelta.warnings <= 0 ? "#4ade80" : "#f87171"} />
          </div>
        )}
      </Card>
    </div>
  );
}

function ResearchPage() {
  const { selectedTicker, setShellError } = useTerminal();
  const [research, setResearch] = useState([]);
  const [statements, setStatements] = useState([]);

  useEffect(() => {
    if (!selectedTicker) {
      setResearch([]);
      setStatements([]);
      return;
    }
    Promise.all([api.research(selectedTicker), api.statements(selectedTicker)])
      .then(([researchData, statementData]) => {
        setResearch(researchData);
        setStatements(statementData);
      })
      .catch((error) => setShellError(error.message));
  }, [selectedTicker, setShellError]);
  const qualityTrend = useMemo(
    () =>
      research
        .map((item) => ({ label: item.as_of_date, value: Number(item.accounting_quality_score || 0), color: "#e879f9" }))
        .filter((item) => item.value > 0)
        .slice()
        .reverse()
        .slice(0, 8),
    [research]
  );
  const completenessTrend = useMemo(
    () =>
      statements
        .map((item) => ({ label: `${item.statement_type}-${item.fiscal_year}`, value: Number(item.completeness || 0), color: "#5eead4" }))
        .filter((item) => item.value > 0)
        .slice()
        .reverse()
        .slice(0, 8),
    [statements]
  );

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <Card title="RESEARCH TREND" accentColor="#e879f9">
          <PageSectionHeader
            title="QUALITY TREND"
            description="Recent accounting-quality history from archived research records."
          />
          {qualityTrend.length === 0 ? <Empty text="NO QUALITY HISTORY TO PLOT." /> : <MetricBarList items={qualityTrend} asPercent />}
        </Card>

        <Card title="SNAPSHOT TREND" accentColor="#5eead4">
          <PageSectionHeader
            title="COMPLETENESS TREND"
            description="Recent statement snapshot completeness history."
          />
          {completenessTrend.length === 0 ? <Empty text="NO SNAPSHOT HISTORY TO PLOT." /> : <MetricBarList items={completenessTrend} asPercent />}
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
      <Card title={`RESEARCH RECORDS ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#e879f9">
        <PageSectionHeader
          title="RESEARCH HISTORY"
          description="Classification and quality records for the selected name. Use this page to compare archived research calls against statement-builder outputs."
          chips={[
            { label: "RECORDS", value: formatCompactNumber(research.length), color: "#e879f9" }
          ]}
        />
        <DataTable
          columns={["DATE", "CLASSIFICATION", "QUALITY", "ROIC", "MOS"]}
          rows={research.map((item) => [
            item.as_of_date,
            item.classification,
            item.accounting_quality_score ?? "N/A",
            item.roic_pct ?? "N/A",
            item.margin_of_safety_pct ?? "N/A"
          ])}
        />
      </Card>

      <Card title={`STATEMENT SNAPSHOTS ${selectedTicker ? `| ${selectedTicker}` : ""}`} accentColor="#5eead4">
        <PageSectionHeader
          title="STATEMENT SNAPSHOT LOG"
          description="Builder outputs by statement type and fiscal period, including quality state and completeness."
          chips={[
            { label: "SNAPSHOTS", value: formatCompactNumber(statements.length), color: "#5eead4" }
          ]}
        />
        <DataTable
          columns={["TYPE", "FY", "QTR", "QUALITY", "COMPLETE", "BUILDER"]}
          rows={statements.map((item) => [
            item.statement_type,
            item.fiscal_year,
            item.fiscal_quarter ?? "-",
            item.quality_status,
            item.completeness ?? "N/A",
            item.builder_version
          ])}
        />
      </Card>
      </div>
    </div>
  );
}

function ReportsPage() {
  const { setShellError } = useTerminal();
  const [reports, setReports] = useState([]);
  const [machine, setMachine] = useState(null);
  const [running, setRunning] = useState(false);
  const [reportSort, setReportSort] = useState("bullish");
  const [reportFilter, setReportFilter] = useState("all");

  const load = useCallback(async () => {
    try {
      const [reportData, machineData] = await Promise.all([
        api.reports(),
        api.reportMachineStatus()
      ]);
      setReports(reportData);
      setMachine(machineData);
    } catch (error) {
      setShellError(error.message);
    }
  }, [setShellError]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  const nudgeMachine = async () => {
    setRunning(true);
    try {
      const data = await api.runReportMachineOnce();
      setMachine(data);
      await load();
    } catch (error) {
      setShellError(error.message);
    } finally {
      setRunning(false);
    }
  };
  const visibleReports = useMemo(() => {
    const filtered = reports.filter((report) => {
      if (reportFilter === "all") return true;
      if (reportFilter === "bullish") return report.stance?.includes("BULLISH");
      if (reportFilter === "degraded") return !report.current_price || report.key_stats?.canonical_facts_count === 0;
      return true;
    });
    const sorted = [...filtered];
    if (reportSort === "quality") {
      sorted.sort((left, right) => (right.key_stats?.accounting_quality_score || 0) - (left.key_stats?.accounting_quality_score || 0));
    } else if (reportSort === "updated") {
      sorted.sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
    } else {
      sorted.sort((left, right) => (right.bullish_score || 0) - (left.bullish_score || 0));
    }
    return sorted;
  }, [reportFilter, reportSort, reports]);

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Card title="MACHINE STATUS" accentColor="#fb7185">
        <PageSectionHeader
          title="REPORT MACHINE"
          description="Runner state, queue coverage, and manual trigger controls for the cached report book."
          chips={[
            { label: "RUNNER", value: machine?.running ? "LIVE" : "IDLE", color: machine?.running ? "#4ade80" : "#f87171" },
            { label: "REPORTS", value: formatCompactNumber(machine?.reports_cached ?? 0), color: "#fb7185" }
          ]}
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
          <MiniMetric k="RUNNER" v={machine?.running ? "LIVE" : "IDLE"} color={machine?.running ? "#4ade80" : "#f87171"} />
          <MiniMetric k="COMPANIES" v={machine?.total_companies ?? 0} color={accent} />
          <MiniMetric k="REPORTS" v={machine?.reports_cached ?? 0} color={accent2} />
          <MiniMetric k="LAST" v={machine?.last_processed_ticker || "N/A"} color="#fb7185" />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <TopTag label="UNIVERSES" value={Object.entries(machine?.universe_counts || {}).map(([key, value]) => `${key}:${formatCompactNumber(value)}`).join(" | ") || "LOADING"} color={labelLight} />
          <TopTag label="LAST ACTION" value={machine?.last_action || "BOOT"} color={accent2} />
          <button
            type="button"
            onClick={nudgeMachine}
            disabled={running}
            style={{
              background: running ? "rgba(251,113,133,0.12)" : "transparent",
              border: "0.5px solid #fb7185",
              color: "#fb7185",
              fontSize: 10,
              padding: "8px 14px",
              cursor: running ? "wait" : "pointer",
              letterSpacing: "0.12em",
              fontFamily: "JetBrains Mono"
            }}
          >
            {running ? "RUNNING..." : "RUN NOW"}
          </button>
        </div>
      </Card>

      <Card title="RANKED REPORT CACHE" accentColor="#fb7185">
        <PageSectionHeader
          title="RANKED BOOK"
          description="Filter and sort cached report output by stance, quality, or freshness. Degraded rows are names still missing price or canonical support."
          actions={
            <>
              <MiniSelect
                label="SORT"
                value={reportSort}
                onChange={setReportSort}
                options={[
                  { value: "bullish", label: "BULLISH" },
                  { value: "quality", label: "QUALITY" },
                  { value: "updated", label: "UPDATED" }
                ]}
              />
              <MiniSelect
                label="FILTER"
                value={reportFilter}
                onChange={setReportFilter}
                options={[
                  { value: "all", label: "ALL" },
                  { value: "bullish", label: "BULLISH" },
                  { value: "degraded", label: "DEGRADED" }
                ]}
              />
            </>
          }
        />
        {visibleReports.length === 0 ? (
          <Empty text="NO CACHED REPORTS YET. THE MACHINE IS STILL BUILDING THE BOOK." />
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {visibleReports.map((report, index) => (
              <div key={report.ticker} style={{ border: hairline, background: "#050509", padding: 12 }}>
                <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 120px 120px", gap: 10, alignItems: "start" }}>
                  <div>
                    <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em", marginBottom: 4 }}>#{index + 1}</div>
                    <div style={{ color: accent, fontSize: 18, fontWeight: 800 }}>{report.ticker}</div>
                    <div style={{ color: muted, fontSize: 10, marginTop: 4 }}>{report.company_name}</div>
                  </div>
                  <div style={{ color: labelLight, fontSize: 11, lineHeight: 1.5 }}>{report.highlights[0] || report.report_markdown}</div>
                  <div>
                    <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>STANCE</div>
                    <div style={{ color: "#fb7185", fontSize: 12, fontWeight: 700, marginTop: 6 }}>{report.stance}</div>
                    <div style={{ color: muted, fontSize: 10, marginTop: 8 }}>DQ {report.data_quality_tier || "N/A"}</div>
                  </div>
                  <div>
                    <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>SCORES</div>
                    <div style={{ color: "#4ade80", fontSize: 11, marginTop: 6 }}>BULL {report.bullish_score.toFixed(1)}</div>
                    <div style={{ color: "#f87171", fontSize: 11, marginTop: 4 }}>BEAR {report.bearish_score.toFixed(1)}</div>
                    <div style={{ color: accent2, fontSize: 11, marginTop: 4 }}>NET {report.composite_score.toFixed(1)}</div>
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginTop: 12 }}>
                  <MiniMetric k="FILINGS" v={report.key_stats.filings_count ?? "N/A"} color={accent} />
                  <MiniMetric k="RAW FACTS" v={report.key_stats.raw_facts_count ?? "N/A"} color={accent2} />
                  <MiniMetric k="CANONICAL" v={report.key_stats.canonical_facts_count ?? "N/A"} color="#a78bfa" />
                  <MiniMetric k="REV GROWTH" v={formatMetricPct(report.key_stats.revenue_growth_pct)} color="#60a5fa" />
                  <MiniMetric k="OWNER E" v={formatMetricNum(report.key_stats.owner_earnings)} color="#f59e0b" />
                  <MiniMetric k="QUALITY" v={formatMetricNum(report.key_stats.accounting_quality_score)} color="#fb7185" />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function BuyBoardPage() {
  const { setShellError } = useTerminal();
  const [board, setBoard] = useState([]);
  const [futureBoard, setFutureBoard] = useState([]);
  const [status, setStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [mode, setMode] = useState("board");
  const [expandedTicker, setExpandedTicker] = useState("");
  const [candidateSort, setCandidateSort] = useState("upside");
  const [sectorFilter, setSectorFilter] = useState("all");

  const load = useCallback(async () => {
    try {
      const [boardData, futureData, statusData] = await Promise.all([
        api.buyBoard(),
        api.futureBoard(),
        api.buyBoardStatus()
      ]);
      setBoard(boardData);
      setFutureBoard(futureData);
      setStatus(statusData);
    } catch (error) {
      setShellError(error.message);
    }
  }, [setShellError]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  const refreshPrices = async () => {
    setRefreshing(true);
    try {
      await api.refreshBuyBoard();
      await load();
    } catch (error) {
      setShellError(error.message);
    } finally {
      setRefreshing(false);
    }
  };
  const activeRows = mode === "board" ? board : futureBoard;
  const sectorOptions = useMemo(
    () => ["all", ...Array.from(new Set(activeRows.map((item) => item.sector || item.accounting_basis?.sector).filter(Boolean)))],
    [activeRows]
  );
  const visibleCandidates = useMemo(() => {
    const filtered = activeRows.filter((candidate) => {
      if (sectorFilter === "all") {
        return true;
      }
      return (candidate.sector || candidate.accounting_basis?.sector) === sectorFilter;
    });
    const sorted = [...filtered];
    if (candidateSort === "score") {
      sorted.sort((left, right) => (right.source_report_score || 0) - (left.source_report_score || 0));
    } else if (candidateSort === "valuation") {
      sorted.sort((left, right) => (right.current_cc_valuation || 0) - (left.current_cc_valuation || 0));
    } else {
      sorted.sort((left, right) => (right.upside_pct || -Infinity) - (left.upside_pct || -Infinity));
    }
    return sorted;
  }, [activeRows, candidateSort, sectorFilter]);

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Card title="BUY BOARD STATUS" accentColor="#4ade80">
        <PageSectionHeader
          title="PRICE REFRESH SCHEDULE"
          description="Candidate prices, valuations, and profile cards update from the research market layer. This panel stays separate from the report loop."
          chips={[
            { label: "BOARD", value: formatCompactNumber(board.length), color: "#4ade80" },
            { label: "FUTURE", value: formatCompactNumber(futureBoard.length), color: "#93c5fd" }
          ]}
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
          <MiniMetric k="RUNNER" v={status?.running ? "LIVE" : "IDLE"} color={status?.running ? "#4ade80" : "#f87171"} />
          <MiniMetric k="CANDIDATES" v={status?.candidate_count ?? 0} color={accent} />
          <MiniMetric k="LAST REFRESH" v={status?.last_refresh_count ?? 0} color={accent2} />
          <MiniMetric k="SUCCESS" v={status?.last_success_count ?? 0} color="#60a5fa" />
          <MiniMetric k="NEXT" v={formatTimestampCompact(status?.next_refresh_at)} color="#4ade80" />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <TopTag label="SCHEDULE" value="09:30 ET / 16:00 ET" color="#4ade80" />
          <TopTag label="LAST ACTION" value={status?.last_action || "BOOT"} color={accent2} />
          <TopTag label="ERROR" value={status?.last_error || "NONE"} color={status?.last_error ? "#f87171" : labelLight} />
          <button
            type="button"
            onClick={refreshPrices}
            disabled={refreshing}
            style={{
              background: refreshing ? "rgba(74,222,128,0.12)" : "transparent",
              border: "0.5px solid #4ade80",
              color: "#4ade80",
              fontSize: 10,
              padding: "8px 14px",
              cursor: refreshing ? "wait" : "pointer",
              letterSpacing: "0.12em",
              fontFamily: "JetBrains Mono"
            }}
          >
            {refreshing ? "REFRESHING..." : "REFRESH PRICES"}
          </button>
        </div>
      </Card>

      <Card title="TRADE CANDIDATE BOARD" accentColor="#4ade80">
        <PageSectionHeader
          title="CANDIDATE LIST"
          description="Ranked candidate list with expandable profile rows and dedicated ticker profile pages."
          actions={
            <>
              <MiniSelect
                label="SORT"
                value={candidateSort}
                onChange={setCandidateSort}
                options={[
                  { value: "upside", label: "UPSIDE" },
                  { value: "score", label: "REPORT SCORE" },
                  { value: "valuation", label: "CC VALUE" }
                ]}
              />
              <MiniSelect
                label="SECTOR"
                value={sectorFilter}
                onChange={setSectorFilter}
                options={sectorOptions.map((option) => ({ value: option, label: option === "all" ? "ALL" : option }))}
              />
            </>
          }
        />
        <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
          {[
            { id: "board", label: `BUY BOARD ${board.length}` },
            { id: "future", label: `FUTURE ${futureBoard.length}` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setMode(tab.id)}
              style={{
                background: mode === tab.id ? "rgba(94,234,212,0.12)" : "transparent",
                border: `0.5px solid ${mode === tab.id ? "#5eead4" : "rgba(255,255,255,0.12)"}`,
                color: mode === tab.id ? "#5eead4" : muted,
                fontSize: 10,
                padding: "8px 12px",
                letterSpacing: "0.14em",
                fontFamily: "JetBrains Mono",
                cursor: "pointer",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {mode === "board" && visibleCandidates.length === 0 ? (
          <Empty text="NO ACTIVE BUY BOARD CANDIDATES YET. CANDIDATES APPEAR AFTER A REPORT QUALIFIES AND CANONICAL COVERAGE IS LIVE." />
        ) : mode === "future" && visibleCandidates.length === 0 ? (
          <Empty text="NO FUTURE UPSIDE CANDIDATES YET. NAMES APPEAR HERE WHEN THE ACCOUNTANT FORECAST STACK FLAGS OUTPERFORMANCE VS EXPECTATIONS." />
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {visibleCandidates.map((candidate, index) => (
              <CollapsibleTickerRow
                key={`${mode}-${candidate.ticker}`}
                candidate={candidate}
                rank={index + 1}
                futureMode={mode === "future"}
                expanded={expandedTicker === `${mode}-${candidate.ticker}`}
                onToggle={() =>
                  setExpandedTicker((current) =>
                    current === `${mode}-${candidate.ticker}` ? "" : `${mode}-${candidate.ticker}`
                  )
                }
              />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function CollapsibleTickerRow({ candidate, rank, futureMode = false, expanded = false, onToggle }) {
  const basis = candidate.accounting_basis || {};
  return (
    <div style={{ border: `0.5px solid ${expanded ? (futureMode ? "#93c5fd88" : "#4ade8088") : "rgba(255,255,255,0.08)"}`, background: expanded ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.2)", minWidth: 0 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "110px minmax(0, 1.2fr) repeat(3, minmax(72px, 0.55fr)) 92px 86px",
          gap: 10,
          alignItems: "center",
          padding: "10px 12px"
        }}
      >
        <div>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em", marginBottom: 4 }}>#{rank}</div>
          <button
            type="button"
            onClick={onToggle}
            style={{
              background: "transparent",
              border: 0,
              padding: 0,
              textAlign: "left",
              cursor: "pointer",
              color: futureMode ? "#93c5fd" : "#4ade80",
              fontSize: 20,
              fontWeight: 900,
              letterSpacing: "0.08em",
              fontFamily: "JetBrains Mono"
            }}
          >
            {candidate.ticker}
          </button>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: muted, fontSize: 11, lineHeight: 1.35, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{candidate.company_name}</div>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em", marginTop: 4 }}>
            {futureMode ? "FUTURE PROFILE" : "BUY BOARD PROFILE"}
          </div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>CC VALUE</div>
          <div style={{ color: "#4ade80", fontSize: 12, fontWeight: 700, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{formatMoney(candidate.current_cc_valuation)}</div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>UPSIDE</div>
          <div style={{ color: candidate.upside_pct >= 0 ? "#4ade80" : "#f87171", fontSize: 12, fontWeight: 700, marginTop: 4 }}>{formatPctSigned(candidate.upside_pct)}</div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>REPORT</div>
          <div style={{ color: "#fb7185", fontSize: 12, fontWeight: 700, marginTop: 4 }}>{formatMetricNum(candidate.source_report_score || candidate.composite_score)}</div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>SECTOR</div>
          <div style={{ color: futureMode ? "#93c5fd" : "#5eead4", fontSize: 11, fontWeight: 700, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {candidate.sector || basis.sector || "Unclassified"}
          </div>
        </div>
        <Link
          to={`/buy-board/${candidate.ticker}`}
          style={{
            border: `0.5px solid ${futureMode ? "#93c5fd" : "#4ade80"}`,
            color: futureMode ? "#93c5fd" : "#4ade80",
            padding: "6px 10px",
            fontSize: 10,
            letterSpacing: "0.12em",
            textDecoration: "none",
            textAlign: "center"
          }}
        >
          OPEN
        </Link>
      </div>

      {expanded && (
        <div style={{ borderTop: hairline, padding: 12, display: "grid", gap: 12 }}>
          <div style={{ color: labelLight, fontSize: 11, lineHeight: 1.55 }}>{candidate.synopsis}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 8 }}>
            <MiniMetric k="REV NY" v={formatMetricPct(basis.revenue_forecast_next_year_pct)} color={futureMode ? "#93c5fd" : "#4ade80"} />
            <MiniMetric k="FCST CONF" v={formatMetricPct(basis.forecast_confidence_pct)} color="#5eead4" />
            <MiniMetric k="SURPRISE" v={formatMetricNum(basis.surprise_score)} color="#f59e0b" />
            <MiniMetric k="EPS FCST" v={formatMetricNum(basis.eps_forecast)} color="#93c5fd" />
            <MiniMetric k="CANONICAL" v={formatInt(basis.canonical_facts_count)} color="#a78bfa" />
            <MiniMetric k="OWNER E" v={formatMoney(basis.owner_earnings)} color={accent} />
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {(candidate.why_buy || []).slice(0, 3).map((reason) => (
              <div key={reason} style={{ color: labelLight, fontSize: 11, lineHeight: 1.5, borderTop: hairline, paddingTop: 8 }}>
                {reason}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BuyBoardTickerProfilePage() {
  const { ticker } = useParams();
  const { setShellError } = useTerminal();
  const [board, setBoard] = useState([]);
  const [futureBoard, setFutureBoard] = useState([]);

  const load = useCallback(async () => {
    try {
      const [boardData, futureData] = await Promise.all([api.buyBoard(), api.futureBoard()]);
      setBoard(boardData);
      setFutureBoard(futureData);
    } catch (error) {
      setShellError(error.message);
    }
  }, [setShellError]);

  useEffect(() => {
    load();
  }, [load]);

  const candidate = [...board, ...futureBoard].find((item) => item.ticker === ticker);
  const futureMode = futureBoard.some((item) => item.ticker === ticker);

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Card title={`TICKER PROFILE // ${ticker || "N/A"}`} accentColor={futureMode ? "#93c5fd" : "#4ade80"}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
          <div style={{ color: muted, fontSize: 10, letterSpacing: "0.12em" }}>
            FULL ACCOUNTANT PROFILE PAGE
          </div>
          <Link to="/buy-board" style={{ border: `0.5px solid ${accent}`, color: accent, padding: "7px 12px", textDecoration: "none", fontSize: 10, letterSpacing: "0.12em" }}>
            BACK TO BOARD
          </Link>
        </div>
        {!candidate ? <Empty text="TICKER PROFILE NOT FOUND IN THE ACTIVE BUY BOARD OR FUTURE BOARD." /> : <BuyBoardProfileDetail candidate={candidate} futureMode={futureMode} />}
      </Card>
    </div>
  );
}

function BuyBoardProfileDetail({ candidate, futureMode = false }) {
  const card = candidate.battle_card || {};
  const basis = candidate.accounting_basis || {};
  const scenario = card.scenario_matrix || {};
  const forecastPack = card.forecast_pack || {};
  const [tab, setTab] = useState("thesis");
  return (
    <div style={{ marginTop: 2, border: `0.5px solid ${accent}55`, background: "rgba(0,0,0,0.28)", padding: 16, minWidth: 0 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18, alignItems: "start", borderBottom: hairline, paddingBottom: 14, marginBottom: 14 }}>
        <div>
          <div style={{ color: dim, fontSize: 9, letterSpacing: "0.18em", fontWeight: 800, marginBottom: 8 }}>{futureMode ? "FUTURE UPSIDE CARD" : "BUY BOARD BATTLE CARD"}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div style={{ color: futureMode ? "#93c5fd" : "#4ade80", fontSize: 28, fontWeight: 900, letterSpacing: "0.08em" }}>{candidate.ticker}</div>
            <TopTag label="PROFILE" value={basis.designation_profile || card.designation_profile || "N/A"} color={futureMode ? "#93c5fd" : "#5eead4"} />
          </div>
          <div style={{ color: muted, fontSize: 12, lineHeight: 1.35, overflowWrap: "anywhere" }}>{candidate.company_name}</div>
          <div style={{ color: labelLight, fontSize: 12, lineHeight: 1.6, marginTop: 12 }}>{candidate.synopsis}</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 8 }}>
          <BoardMetric label="FIRST PX" value={formatMoney(candidate.first_price)} color={labelLight} />
          <BoardMetric label="CURRENT PX" value={formatMoney(candidate.current_price)} color="#60a5fa" />
          <BoardMetric label="CC VALUE" value={formatMoney(candidate.current_cc_valuation)} color="#4ade80" />
          <BoardMetric label="UPSIDE" value={formatPctSigned(candidate.upside_pct)} color={candidate.upside_pct >= 0 ? "#4ade80" : "#f87171"} />
        </div>
      </div>

      <div className="toolbar-cluster" style={{ marginBottom: 16 }}>
        {[
          { id: "thesis", label: "THESIS" },
          { id: "basis", label: "ACCOUNTING BASIS" },
          { id: "forecast", label: "FORECAST STACK" },
          { id: "risk", label: "RISKS" }
        ].map((item) => (
          <button
            key={item.id}
            type="button"
            className={`chip-button ${tab === item.id ? "is-active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "thesis" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14, minWidth: 0 }}>
            <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// WHY THE ACCOUNTANT BOUGHT</div>
            <div style={{ display: "grid", gap: 10 }}>
              {(candidate.why_buy || []).map((reason) => (
                <div key={reason} style={{ color: labelLight, fontSize: 11, lineHeight: 1.55, borderTop: hairline, paddingTop: 10 }}>
                  {reason}
                </div>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginTop: 14 }}>
              <MiniMetric k="FIRST VAL" v={formatMoney(candidate.first_cc_valuation)} color={accent} />
              <MiniMetric k="CURRENT VAL" v={formatMoney(candidate.current_cc_valuation)} color="#4ade80" />
              <MiniMetric k="CC GROWTH FCST" v={formatMetricPct(candidate.cc_valuation_growth_forecast_pct)} color="#f59e0b" />
              <MiniMetric k="EPS" v={formatMetricNum(basis.eps)} color="#60a5fa" />
              <MiniMetric k="CC EPS FORECAST" v={formatMetricNum(basis.eps_forecast)} color="#93c5fd" />
              <MiniMetric k="REPORT SCORE" v={formatMetricNum(candidate.source_report_score)} color="#fb7185" />
            </div>
          </div>

          <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14, minWidth: 0 }}>
            <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// PROFILE SNAPSHOT</div>
            <BoardLine k="SECTOR" v={candidate.sector || basis.sector || "Unclassified"} />
            <BoardLine k="SOURCE REPORT" v={formatTimestampCompact(candidate.source_report_date)} />
            <BoardLine k="FIRST PRICE DATE" v={formatTimestampCompact(candidate.first_price_at)} />
            <BoardLine k="CURRENT PRICE DATE" v={formatTimestampCompact(candidate.current_price_at)} />
            <BoardLine k="FIRST VAL DATE" v={formatTimestampCompact(candidate.first_valuation_at)} />
            <BoardLine k="CURRENT VAL DATE" v={formatTimestampCompact(candidate.current_valuation_at)} />
          </div>
        </div>
      ) : null}

      {tab === "basis" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14, minWidth: 0 }}>
            <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// ACCOUNTING BASIS</div>
            <BoardLine k="PROFILE" v={basis.designation_profile || "N/A"} />
            <BoardLine k="STANCE" v={basis.stance || "-"} />
            <BoardLine k="CANONICAL FACTS" v={formatInt(basis.canonical_facts_count)} />
            <BoardLine k="REV GROWTH" v={formatMetricPct(basis.revenue_growth_pct)} />
            <BoardLine k="REV FCST NQ" v={formatMetricPct(basis.revenue_forecast_next_quarter_pct)} />
            <BoardLine k="REV FCST NY" v={formatMetricPct(basis.revenue_forecast_next_year_pct)} />
            <BoardLine k="MARGIN FCST" v={formatMetricPct(basis.margin_forecast_pct)} />
            <BoardLine k="OWNER E" v={formatMoney(basis.owner_earnings)} />
            <BoardLine k="OWNER E FCST" v={formatMoney(basis.owner_earnings_forecast)} />
            <BoardLine k="NET INCOME" v={formatMoney(basis.net_income)} />
            <BoardLine k="DILUTION FCST" v={formatMetricPct(basis.dilution_growth_pct)} />
            <BoardLine k="FCST CONF" v={formatMetricPct(basis.forecast_confidence_pct)} />
            <BoardLine k="SURPRISE SCORE" v={formatMetricNum(basis.surprise_score)} />
            <BoardLine k="ACCOUNTING Q" v={formatMetricNum(basis.accounting_quality_score)} />
            <BoardLine k="PRICE SOURCE" v={candidate.last_price_source || "PENDING"} />
            <BoardLine k="LAST REFRESH" v={formatTimestampCompact(candidate.last_price_refresh_at)} />
            <BoardLine k="DATA QUALITY" v={candidate.current_market_data_quality || "N/A"} />
          </div>

          <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14 }}>
            <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// SCENARIO MATRIX</div>
            <BoardLine k="BEAR" v={formatMoney(scenario.bear || basis.scenario_bear_value)} />
            <BoardLine k="BASE" v={formatMoney(scenario.base || basis.scenario_base_value)} />
            <BoardLine k="BULL" v={formatMoney(scenario.bull || basis.scenario_bull_value)} />
            <BoardLine k="UPSIDE" v={formatPctSigned(candidate.upside_pct)} />
          </div>
        </div>
      ) : null}

      {tab === "forecast" ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginTop: 16 }}>
            <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 12 }}>
              <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>SCENARIO BEAR</div>
              <div className="num" style={{ color: "#fca5a5", fontSize: 20, fontWeight: 800, marginTop: 6 }}>{formatMoney(scenario.bear || basis.scenario_bear_value)}</div>
            </div>
            <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 12 }}>
              <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>SCENARIO BASE</div>
              <div className="num" style={{ color: "#e5e7eb", fontSize: 20, fontWeight: 800, marginTop: 6 }}>{formatMoney(scenario.base || basis.scenario_base_value)}</div>
            </div>
            <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 12 }}>
              <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em" }}>SCENARIO BULL</div>
              <div className="num" style={{ color: "#4ade80", fontSize: 20, fontWeight: 800, marginTop: 6 }}>{formatMoney(scenario.bull || basis.scenario_bull_value)}</div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16, marginTop: 16 }}>
            <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14 }}>
              <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// DESIGNATED PROFILE CARD</div>
              <BoardLine k="PROFILE" v={basis.designation_profile || card.designation_profile || "N/A"} />
              <BoardLine k="SURPRISE UP" v={formatMetricPct(basis.surprise_upside_pct || forecastPack.surprise_upside_pct)} />
              <BoardLine k="REV FCST" v={formatMetricPct(basis.revenue_forecast_next_year_pct || forecastPack.revenue_forecast_next_year_pct)} />
              <BoardLine k="EPS FCST" v={formatMetricNum(basis.eps_forecast || forecastPack.eps_forecast)} />
            </div>
            <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14 }}>
              <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// FORECAST STACK</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(92px, 1fr))", gap: 8 }}>
                <MiniMetric k="FCST CONF" v={formatMetricPct(forecastPack.forecast_confidence_pct || basis.forecast_confidence_pct)} color="#5eead4" />
                <MiniMetric k="REV NQ" v={formatMetricPct(forecastPack.revenue_forecast_next_quarter_pct || basis.revenue_forecast_next_quarter_pct)} color="#60a5fa" />
                <MiniMetric k="REV NY" v={formatMetricPct(forecastPack.revenue_forecast_next_year_pct || basis.revenue_forecast_next_year_pct)} color={futureMode ? "#93c5fd" : "#4ade80"} />
                <MiniMetric k="MARGIN" v={formatMetricPct(forecastPack.margin_forecast_pct || basis.margin_forecast_pct)} color="#f59e0b" />
                <MiniMetric k="SURPRISE" v={formatMetricNum(forecastPack.surprise_score || basis.surprise_score)} color="#fb7185" />
              </div>
            </div>
          </div>
        </>
      ) : null}

      {tab === "risk" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16, marginTop: 16 }}>
          <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14 }}>
            <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// BULL CASE</div>
            {(card.bull_case || []).map((item) => (
              <div key={item} style={{ color: labelLight, fontSize: 11, lineHeight: 1.55, borderTop: hairline, paddingTop: 10 }}>
                {item}
              </div>
            ))}
          </div>
          <div style={{ border: hairline, background: "rgba(255,255,255,0.018)", padding: 14 }}>
            <div style={{ color: labelLight, fontSize: 11, letterSpacing: "0.14em", marginBottom: 10, fontWeight: 700 }}>// RISK FLAGS</div>
            {(card.risk_flags || []).map((item) => (
              <div key={item} style={{ color: "#fca5a5", fontSize: 11, lineHeight: 1.55, borderTop: hairline, paddingTop: 10 }}>
                {item}
              </div>
            ))}
            {candidate.last_price_error && (
              <div style={{ color: "#fca5a5", fontSize: 11, lineHeight: 1.55, borderTop: hairline, paddingTop: 10 }}>
                IBKR refresh issue: {candidate.last_price_error}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Card({ title, children, accentColor = accent }) {
  return (
    <div className="corner-brackets fade-in" style={{ background: `linear-gradient(180deg, ${cardBg} 0%, ${pageBg} 200%)`, border: hairline, position: "relative" }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: `linear-gradient(90deg, ${accentColor} 0%, ${accentColor}33 30%, transparent 100%)` }} />
      <div style={{ padding: "16px 22px 18px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, paddingBottom: 10, borderBottom: hairline }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: accentColor, fontSize: 9 }}>{">"}</span>
            <span style={{ fontSize: 10, color: labelLight, letterSpacing: "0.18em", fontWeight: 600 }}>{title}</span>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

function PageSectionHeader({ title, description, chips = [], actions = null }) {
  return (
    <div className="section-toolbar">
      <div style={{ minWidth: 0 }}>
        <div style={{ color: dim, fontSize: 8, letterSpacing: "0.16em", marginBottom: 6 }}>{title}</div>
        <div style={{ color: labelLight, fontSize: 11, lineHeight: 1.5, maxWidth: 760 }}>{description}</div>
        {chips.length > 0 ? (
          <div className="toolbar-cluster" style={{ marginTop: 10 }}>
            {chips.map((chip) => (
              <TopTag key={`${chip.label}-${chip.value}`} label={chip.label} value={chip.value} color={chip.color || labelLight} />
            ))}
          </div>
        ) : null}
      </div>
      {actions ? <div className="toolbar-cluster">{actions}</div> : null}
    </div>
  );
}

function Stat({ label, value, sub, color, accentBar = false, isText = false }) {
  const displayValue = isText ? value : formatDisplayMetric(value);
  return (
    <div className="row-hover" style={{ padding: "18px 20px", borderRight: hairline, position: "relative", background: accentBar ? "linear-gradient(90deg, rgba(200,168,75,0.05) 0%, transparent 100%)" : "transparent" }}>
      {accentBar && <div style={{ position: "absolute", left: 0, top: 14, bottom: 14, width: 2, background: accent, boxShadow: `0 0 6px ${accent}80` }} />}
      <div style={{ fontSize: 9, color: muted, letterSpacing: "0.18em", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: dim, fontSize: 8 }}>{">"}</span>
        {label}
      </div>
      <div className="num" style={{ fontSize: isText ? 22 : 26, fontWeight: 600, color, marginTop: 8, fontFamily: "JetBrains Mono, Courier New", letterSpacing: "0.02em" }}>
        {displayValue}
      </div>
      <div style={{ fontSize: 9, color: muted, marginTop: 5, letterSpacing: "0.12em" }}>{sub}</div>
    </div>
  );
}

function MissionTile({ label, value, color, detail }) {
  return (
    <div style={{ border: hairline, background: "rgba(255,255,255,0.015)", padding: 12 }}>
      <div style={{ color: dim, fontSize: 9, letterSpacing: "0.16em" }}>{label}</div>
      <div style={{ color, fontSize: 22, fontWeight: 800, marginTop: 8, letterSpacing: "0.08em" }}>{value}</div>
      <div style={{ color: muted, fontSize: 10, marginTop: 6, lineHeight: 1.4 }}>{detail}</div>
    </div>
  );
}

function MiniMetric({ k, v, color = labelLight }) {
  const displayValue = typeof v === "number" ? formatDisplayMetric(v) : v;
  return (
    <div style={{ border: hairline, padding: "10px 12px", background: pageBg }}>
      <div style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>{k}</div>
      <div style={{ color, fontSize: 14, marginTop: 6, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{displayValue}</div>
    </div>
  );
}

function MetricBarList({ items, asPercent = false }) {
  const maxValue = Math.max(...items.map((item) => Number(item.value || 0)), 1);
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {items.map((item) => {
        const rawValue = Number(item.value || 0);
        const width = Math.max(6, (rawValue / maxValue) * 100);
        return (
          <div key={`${item.label}-${item.value}`} style={{ display: "grid", gridTemplateColumns: "140px 1fr 70px", gap: 10, alignItems: "center" }}>
            <div style={{ color: labelLight, fontSize: 10, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.label}</div>
            <div style={{ height: 8, border: hairline, background: "rgba(255,255,255,0.02)", position: "relative", overflow: "hidden" }}>
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  width: `${width}%`,
                  background: `linear-gradient(90deg, ${item.color || accent2}99 0%, ${item.color || accent2} 100%)`,
                  boxShadow: `0 0 8px ${(item.color || accent2)}55`
                }}
              />
            </div>
            <div className="num" style={{ color: item.color || accent2, textAlign: "right", fontSize: 10 }}>
              {asPercent ? `${rawValue.toFixed(1)}%` : formatCompactNumber(rawValue)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function IntelBlock({ icon: Icon, title, body }) {
  return (
    <div style={{ padding: "8px 0", borderBottom: hairline }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: accent2, fontSize: 10, letterSpacing: "0.12em", fontWeight: 700 }}>
        <Icon size={13} />
        {title}
      </div>
      <div style={{ marginTop: 6, color: labelLight, fontSize: 11, lineHeight: 1.5 }}>{body}</div>
    </div>
  );
}

function ActionPanel({ title, body, button, disabled, onClick }) {
  return (
    <div style={{ border: hairline, background: "#050509", padding: 12 }}>
      <div style={{ color: accent, fontSize: 10, letterSpacing: "0.12em", fontWeight: 700 }}>{title}</div>
      <div style={{ color: labelLight, fontSize: 11, lineHeight: 1.5, marginTop: 8, minHeight: 66 }}>{body}</div>
      <button
        type="button"
        disabled={disabled}
        onClick={onClick}
        style={{
          marginTop: 10,
          background: disabled ? "rgba(200,168,75,0.1)" : "transparent",
          border: `0.5px solid ${accent}`,
          color: accent,
          fontSize: 10,
          padding: "8px 14px",
          cursor: disabled ? "wait" : "pointer",
          letterSpacing: "0.12em",
          fontFamily: "JetBrains Mono"
        }}
      >
        {button}
      </button>
    </div>
  );
}

function DataTable({ columns, rows }) {
  if (rows.length === 0) {
    return <Empty text="NO ROWS AVAILABLE." />;
  }

  return (
    <div className="table-scroll">
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} style={{ textAlign: "left", padding: "8px 0", borderBottom: hairline, color: dim, fontSize: 8, letterSpacing: "0.14em", fontWeight: 700 }}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${index}-${row[0]}`} style={{ borderBottom: hairline }}>
              {row.map((cell, cellIndex) => (
                <td key={`${index}-${cellIndex}`} style={{ padding: "8px 0", color: labelLight, fontSize: 10 }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FilterInput({ value, onChange, label }) {
  return (
    <label style={{ display: "grid", gap: 8 }}>
      <span style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        style={{
          background: "#050509",
          border: hairline,
          color: "#e5e7eb",
          padding: "8px 10px"
        }}
      />
    </label>
  );
}

function StatusRow({ label, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 8px", color: labelLight, letterSpacing: "0.1em" }}>
      <span className="dot pulse-dot" style={{ background: color, boxShadow: `0 0 6px ${color}66` }} />
      <span style={{ flex: 1 }}>{label}</span>
      <span style={{ color: muted, fontSize: 8 }}>OK</span>
    </div>
  );
}

function Banner({ kind, text, onClose }) {
  return (
    <div style={{ marginBottom: 12, padding: "10px 12px", border: `0.5px solid ${kind === "error" ? "#f87171" : "#4ade80"}`, color: kind === "error" ? "#fecaca" : "#bbf7d0", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, background: kind === "error" ? "#3b080810" : "#052e1a10" }}>
      <span style={{ fontSize: 10, letterSpacing: "0.08em" }}>{text}</span>
      <button type="button" onClick={onClose} style={{ background: "transparent", border: 0, color: "inherit", cursor: "pointer", fontFamily: "JetBrains Mono", fontSize: 10 }}>CLOSE</button>
    </div>
  );
}

function Empty({ text }) {
  return <div style={{ color: muted, padding: 18, fontSize: 11 }}>{text}</div>;
}

function SkeletonList({ rows = 4, compact = false }) {
  return (
    <div style={{ display: "grid", gap: compact ? 6 : 10 }}>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="skeleton-line"
          style={{
            height: compact ? 34 : 54,
            border: hairline,
            background: "rgba(255,255,255,0.02)"
          }}
        />
      ))}
    </div>
  );
}

function MiniSelect({ label, value, onChange, options }) {
  return (
    <label style={{ display: "grid", gap: 6 }}>
      <span style={{ color: dim, fontSize: 8, letterSpacing: "0.14em" }}>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        style={{
          background: "#050509",
          border: hairline,
          color: "#e5e7eb",
          padding: "7px 8px",
          fontSize: 10,
          letterSpacing: "0.08em",
          fontFamily: "JetBrains Mono, Courier New, monospace"
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function BoardMetric({ label, value, color }) {
  return (
    <div style={{ border: hairline, background: "#020407cc", padding: "10px 11px", display: "grid", gap: 6, color: dim, fontSize: 9, letterSpacing: "0.12em" }}>
      <span>{label}</span>
      <strong style={{ color, fontSize: 18 }}>{value ?? "-"}</strong>
    </div>
  );
}

function BoardLine({ k, v }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, borderTop: hairline, paddingTop: 10, marginTop: 10, color: labelLight, fontSize: 11 }}>
      <span style={{ color: dim, letterSpacing: "0.12em" }}>{k}</span>
      <span style={{ textAlign: "right" }}>{v ?? "-"}</span>
    </div>
  );
}

function formatMetricPct(value) {
  return typeof value === "number" ? `${formatCompactNumber(value)}%` : "N/A";
}

function formatMetricNum(value) {
  return typeof value === "number"
    ? Math.abs(value) >= 1000
      ? formatCompactNumber(value)
      : value.toFixed(1)
    : "N/A";
}

function formatMoney(value) {
  return typeof value === "number" ? formatCompactNumber(value, { currency: true }) : "N/A";
}

function formatInt(value) {
  return typeof value === "number" ? formatCompactNumber(Math.round(value)) : value ?? "N/A";
}

function formatPctSigned(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "N/A";
  }
  return `${value >= 0 ? "+" : ""}${formatCompactNumber(value)}%`;
}

function formatTimestampCompact(value) {
  if (!value) {
    return "N/A";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const yyyy = parsed.getFullYear();
  const mm = String(parsed.getMonth() + 1).padStart(2, "0");
  const dd = String(parsed.getDate()).padStart(2, "0");
  const hh = String(parsed.getHours()).padStart(2, "0");
  const min = String(parsed.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

function formatAgeCompact(value) {
  if (!value) {
    return "N/A";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const deltaMs = Math.max(0, Date.now() - parsed.getTime());
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) {
    return `${seconds}s AGO`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}M AGO`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}H AGO`;
  }
  const days = Math.floor(hours / 24);
  return `${days}D AGO`;
}

export default App;
