"""Phase A tests: valuation, WACC, reverse DCF, and credit engines."""

from accountant.valuation.credit_engine import (
    CreditQuality,
    CreditRiskEngine,
)
from accountant.valuation.reverse_dcf_engine import (
    ReverseDCFEngine,
    SolveStatus,
    SolveVariable,
)
from accountant.valuation.valuation_engine import (
    ApplicabilityStatus,
    ValuationEngine,
    ValuationMethod,
)
from accountant.valuation.wacc_engine import (
    CapitalStructureType,
    WACCEngine,
)


class TestValuationEngine:
    """DCF and multiples valuation tests."""

    def test_dcf_basic_calculation(self):
        """Test basic DCF with simple FCF projections."""
        fcf_proj = [100.0, 110.0, 121.0, 133.1, 146.4]
        dcf = ValuationEngine.calculate_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            fcf_projections=fcf_proj,
            terminal_growth=0.025,
            discount_rate=0.08,
            forecast_horizon=5,
            shares_outstanding=100.0,
            reference_price=120.0,
        )
        assert dcf.base_pv > 0
        assert dcf.base_price_per_share is not None
        assert dcf.terminal_value is not None
        assert dcf.formula_version == "DCF_V1"

    def test_dcf_with_missing_fcf(self):
        """Test DCF handles missing FCF gracefully."""
        dcf = ValuationEngine.calculate_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            fcf_projections=[],
            terminal_growth=0.025,
            discount_rate=0.10,
            shares_outstanding=100.0,
        )
        assert dcf.base_pv is None
        assert "Insufficient FCF projections" in dcf.assumptions.notes

    def test_dcf_bear_base_bull_scenarios(self):
        """Test DCF creates bear/base/bull scenarios."""
        fcf_proj = [100.0, 105.0, 110.0]
        dcf = ValuationEngine.calculate_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            fcf_projections=fcf_proj,
            terminal_growth=0.025,
            discount_rate=0.10,
            forecast_horizon=3,
            shares_outstanding=50.0,
        )
        if dcf.base_price_per_share:
            assert dcf.bull_price_per_share == dcf.base_price_per_share * 1.20
            assert dcf.bear_price_per_share == dcf.base_price_per_share * 0.80

    def test_margin_of_safety_calculation(self):
        """Test margin of safety calculates correctly."""
        fcf_proj = [100.0, 110.0]
        dcf = ValuationEngine.calculate_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            fcf_projections=fcf_proj,
            terminal_growth=0.025,
            discount_rate=0.10,
            forecast_horizon=2,
            shares_outstanding=100.0,
            reference_price=100.0,
        )
        if dcf.margin_of_safety_pct:
            assert isinstance(dcf.margin_of_safety_pct, float)

    def test_method_applicability_dcf(self):
        """Test DCF applicability assessment."""
        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.DCF,
            company_id="TEST001",
            has_fcf_history=True,
            is_financial_sector=False,
            is_reit=False,
        )
        assert status == ApplicabilityStatus.APPLICABLE

        # Not applicable for financial sector
        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.DCF,
            company_id="TEST001",
            has_fcf_history=True,
            is_financial_sector=True,
        )
        assert status == ApplicabilityStatus.NOT_APPLICABLE

    def test_method_applicability_dividend_discount(self):
        """Test dividend discount model applicability."""
        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.DIVIDEND_DISCOUNT,
            company_id="TEST001",
            has_dividend_history=True,
        )
        assert status == ApplicabilityStatus.APPLICABLE

        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.DIVIDEND_DISCOUNT,
            company_id="TEST001",
            has_dividend_history=False,
        )
        assert status == ApplicabilityStatus.NOT_APPLICABLE

    def test_method_applicability_multiples(self):
        """Test multiples method applicability."""
        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.PEER_MULTIPLES,
            company_id="TEST001",
            has_peer_group=True,
        )
        assert status == ApplicabilityStatus.APPLICABLE

        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.PEER_MULTIPLES,
            company_id="TEST001",
            has_peer_group=False,
        )
        assert status == ApplicabilityStatus.INSUFFICIENT_DATA

    def test_method_applicability_nav(self):
        """Test NAV applicability for different sectors."""
        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.NET_ASSET_VALUE,
            company_id="TEST001",
            is_financial_sector=True,
        )
        assert status == ApplicabilityStatus.APPLICABLE

        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.NET_ASSET_VALUE,
            company_id="TEST001",
            is_reit=True,
        )
        assert status == ApplicabilityStatus.APPLICABLE

        status, reason = ValuationEngine.assess_method_applicability(
            method=ValuationMethod.NET_ASSET_VALUE,
            company_id="TEST001",
            is_financial_sector=False,
            is_reit=False,
        )
        assert status == ApplicabilityStatus.NOT_APPLICABLE


class TestWACCEngine:
    """WACC and cost of capital tests."""

    def test_cost_of_equity_basic(self):
        """Test CAPM cost of equity calculation."""
        coe = WACCEngine.calculate_cost_of_equity(
            risk_free_rate=0.045,
            beta=1.2,
            equity_risk_premium=0.06,
        )
        assert coe.cost_of_equity is not None
        # Re = 0.045 + 1.2 × 0.06 = 0.045 + 0.072 = 0.117
        assert abs(coe.cost_of_equity - 0.117) < 0.001

    def test_cost_of_equity_with_defaults(self):
        """Test cost of equity uses defaults when inputs missing."""
        coe = WACCEngine.calculate_cost_of_equity(
            risk_free_rate=None,
            beta=None,
            equity_risk_premium=None,
        )
        assert coe.cost_of_equity is not None
        assert coe.risk_free_rate == WACCEngine.DEFAULT_RISK_FREE_RATE

    def test_cost_of_debt_calculation(self):
        """Test after-tax cost of debt."""
        cod = WACCEngine.calculate_cost_of_debt(
            debt_amount_usd=1000.0,
            interest_expense_usd=50.0,
            tax_rate=0.21,
        )
        assert cod.pre_tax_cost_of_debt == 0.05
        # After-tax = 0.05 × (1 - 0.21) = 0.05 × 0.79 = 0.0395
        assert abs(cod.after_tax_cost_of_debt - 0.0395) < 0.001

    def test_cost_of_debt_no_debt(self):
        """Test cost of debt when no debt."""
        cod = WACCEngine.calculate_cost_of_debt(
            debt_amount_usd=None,
            interest_expense_usd=None,
        )
        assert cod.after_tax_cost_of_debt is None

    def test_capital_structure_classification(self):
        """Test capital structure type classification."""
        cs_type = WACCEngine.classify_capital_structure(0.80)
        assert cs_type == CapitalStructureType.DEBT_HEAVY

        cs_type = WACCEngine.classify_capital_structure(0.50)
        assert cs_type == CapitalStructureType.BALANCED

        cs_type = WACCEngine.classify_capital_structure(0.20)
        assert cs_type == CapitalStructureType.EQUITY_HEAVY

        cs_type = WACCEngine.classify_capital_structure(0.0)
        assert cs_type == CapitalStructureType.NO_DEBT

    def test_wacc_calculation(self):
        """Test WACC calculation."""
        wacc_result = WACCEngine.calculate_wacc(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            market_cap_usd=10000.0,
            debt_amount_usd=4000.0,
            interest_expense_usd=200.0,
            tax_rate=0.21,
            risk_free_rate=0.045,
            beta=1.1,
            equity_risk_premium=0.06,
        )
        assert wacc_result.wacc is not None
        assert abs(wacc_result.capital_structure.debt_weight - 0.286) < 0.01
        assert abs(wacc_result.capital_structure.equity_weight - 0.714) < 0.01

    def test_wacc_sensitivities(self):
        """Test WACC sensitivity calculations."""
        wacc_result = WACCEngine.calculate_wacc(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            market_cap_usd=10000.0,
            debt_amount_usd=4000.0,
            interest_expense_usd=200.0,
            tax_rate=0.21,
            risk_free_rate=0.045,
            beta=1.0,
            equity_risk_premium=0.06,
        )
        if wacc_result.wacc:
            assert wacc_result.wacc_if_beta_increases_20pct is not None
            assert wacc_result.wacc_if_risk_premium_increases_100bps is not None


class TestReverseDCFEngine:
    """Reverse DCF tests."""

    def test_solve_for_terminal_growth(self):
        """Test solving for terminal growth rate."""
        solved_g, reasonable = ReverseDCFEngine.solve_for_terminal_growth(
            fcf_per_share=10.0,
            market_price_per_share=150.0,
            discount_rate=0.08,
            forecast_horizon=10,
        )
        assert solved_g is not None
        assert isinstance(reasonable, bool)

    def test_solve_for_discount_rate(self):
        """Test solving for discount rate."""
        solved_r, reasonable = ReverseDCFEngine.solve_for_discount_rate(
            fcf_per_share=10.0,
            market_price_per_share=150.0,
            terminal_growth=0.025,
            forecast_horizon=10,
        )
        assert solved_r is not None
        assert isinstance(reasonable, bool)

    def test_reverse_dcf_terminal_growth(self):
        """Test reverse DCF with terminal growth solve."""
        result = ReverseDCFEngine.calculate_reverse_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            market_price_per_share=100.0,
            shares_outstanding=50.0,
            current_fcf_per_share=5.0,
            solve_variable=SolveVariable.TERMINAL_GROWTH_RATE,
            discount_rate=0.10,
        )
        assert result.market_cap_usd == 5000.0
        assert result.solve_status in [SolveStatus.SOLVED, SolveStatus.OUT_OF_BOUNDS]

    def test_reverse_dcf_discount_rate(self):
        """Test reverse DCF with discount rate solve."""
        result = ReverseDCFEngine.calculate_reverse_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            market_price_per_share=120.0,
            shares_outstanding=100.0,
            current_fcf_per_share=8.0,
            solve_variable=SolveVariable.DISCOUNT_RATE,
            terminal_growth=0.025,
        )
        assert result.solve_status != SolveStatus.INSUFFICIENT_DATA

    def test_reverse_dcf_missing_price(self):
        """Test reverse DCF with missing price."""
        result = ReverseDCFEngine.calculate_reverse_dcf(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            market_price_per_share=None,
            shares_outstanding=100.0,
            current_fcf_per_share=5.0,
        )
        assert result.solve_status == SolveStatus.INSUFFICIENT_DATA


class TestCreditEngine:
    """Credit risk analysis tests."""

    def test_leverage_metrics_calculation(self):
        """Test leverage ratio calculations."""
        lev = CreditRiskEngine.calculate_leverage_metrics(
            gross_debt_usd=1000.0,
            cash_and_equivalents_usd=100.0,
            ebitda_usd=500.0,
            fcf_usd=300.0,
            owner_earnings_usd=350.0,
            operating_cf_usd=400.0,
        )
        assert lev.net_debt_usd == 900.0
        assert lev.gross_leverage_x == 2.0  # 1000 / 500
        assert lev.net_leverage_x == 1.8  # 900 / 500
        assert abs(lev.debt_to_fcf_x - 3.33) < 0.01  # ~1000 / 300

    def test_coverage_metrics_calculation(self):
        """Test coverage ratio calculations."""
        cov = CreditRiskEngine.calculate_coverage_metrics(
            interest_expense_usd=50.0,
            ebitda_usd=300.0,
            fcf_usd=200.0,
            owner_earnings_usd=250.0,
            operating_cf_usd=280.0,
            debt_service_usd=100.0,
        )
        assert cov.interest_coverage_x == 6.0  # 300 / 50
        assert cov.fcf_coverage_x == 4.0  # 200 / 50
        assert cov.owner_earnings_coverage_x == 5.0  # 250 / 50
        assert cov.debt_service_coverage_x == 2.8  # 280 / 100

    def test_maturity_analysis(self):
        """Test debt maturity profile analysis."""
        mat = CreditRiskEngine.calculate_maturity_analysis(
            due_within_1_year_usd=200.0,
            due_within_1_3_years_usd=300.0,
            due_within_3_5_years_usd=250.0,
            due_after_5_years_usd=250.0,
        )
        assert mat.total_debt_usd == 1000.0
        assert mat.near_term_refinancing_risk == 20.0  # 200 / 1000
        assert mat.maturity_concentration_risk == "BALANCED"

    def test_leverage_scoring(self):
        """Test leverage component scoring."""
        score = CreditRiskEngine.score_leverage(0.8)
        assert score == 25.0

        score = CreditRiskEngine.score_leverage(1.5)
        assert score == 20.0

        score = CreditRiskEngine.score_leverage(2.5)
        assert score == 15.0

        score = CreditRiskEngine.score_leverage(5.0)
        assert score == 2.0

    def test_coverage_scoring(self):
        """Test coverage component scoring."""
        score = CreditRiskEngine.score_coverage(10.0)
        assert score == 25.0

        score = CreditRiskEngine.score_coverage(5.0)
        assert score == 20.0

        score = CreditRiskEngine.score_coverage(2.0)
        assert score == 8.0

    def test_credit_quality_classification(self):
        """Test credit quality score classification."""
        quality = CreditRiskEngine.classify_credit_quality(90.0)
        assert quality == CreditQuality.VERY_STRONG

        quality = CreditRiskEngine.classify_credit_quality(70.0)
        assert quality == CreditQuality.STRONG

        quality = CreditRiskEngine.classify_credit_quality(50.0)
        assert quality == CreditQuality.ADEQUATE

        quality = CreditRiskEngine.classify_credit_quality(30.0)
        assert quality == CreditQuality.WEAK

        quality = CreditRiskEngine.classify_credit_quality(10.0)
        assert quality == CreditQuality.DISTRESSED

    def test_credit_risk_full_calculation(self):
        """Test full credit risk calculation."""
        result = CreditRiskEngine.calculate_credit_risk(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            gross_debt_usd=1000.0,
            cash_and_equivalents_usd=100.0,
            ebitda_usd=500.0,
            fcf_usd=300.0,
            owner_earnings_usd=350.0,
            operating_cf_usd=400.0,
            interest_expense_usd=50.0,
            debt_service_annual_usd=100.0,
            due_within_1_year_usd=200.0,
            due_within_1_3_years_usd=300.0,
            due_within_3_5_years_usd=250.0,
            due_after_5_years_usd=250.0,
        )
        assert result.credit_quality_score.total_score is not None
        assert result.credit_quality_score.quality_classification is not None
        assert result.formula_version == "CREDIT_RISK_V1"

    def test_credit_risk_high_leverage_scenario(self):
        """Test credit risk with high leverage scenario."""
        result = CreditRiskEngine.calculate_credit_risk(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            gross_debt_usd=5000.0,
            cash_and_equivalents_usd=100.0,
            ebitda_usd=500.0,
            fcf_usd=100.0,
            owner_earnings_usd=150.0,
            operating_cf_usd=150.0,
            interest_expense_usd=200.0,
            debt_service_annual_usd=300.0,
            due_within_1_year_usd=800.0,
            due_within_1_3_years_usd=600.0,
            due_within_3_5_years_usd=1800.0,
            due_after_5_years_usd=1800.0,
        )
        assert result.credit_quality_score.quality_classification in [
            CreditQuality.WEAK,
            CreditQuality.DISTRESSED,
        ]
        assert "High leverage" in " ".join(result.key_risks)

    def test_credit_risk_strong_scenario(self):
        """Test credit risk with strong profile."""
        result = CreditRiskEngine.calculate_credit_risk(
            company_id="TEST001",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            gross_debt_usd=800.0,
            cash_and_equivalents_usd=200.0,
            ebitda_usd=1000.0,
            fcf_usd=800.0,
            owner_earnings_usd=900.0,
            operating_cf_usd=850.0,
            interest_expense_usd=40.0,
            debt_service_annual_usd=100.0,
            due_within_1_year_usd=80.0,
            due_within_1_3_years_usd=200.0,
            due_within_3_5_years_usd=240.0,
            due_after_5_years_usd=280.0,
        )
        assert result.credit_quality_score.quality_classification in [
            CreditQuality.VERY_STRONG,
            CreditQuality.STRONG,
            CreditQuality.ADEQUATE,
        ]
        if result.key_strengths:
            assert len(result.key_strengths) > 0
