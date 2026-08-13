"""Tests for Phase B: Bear Case, Capital Structure, Special Situations engines."""

from accountant.valuation import (
    BearCaseEngine,
    BearRiskFactor,
    CapitalStructureEngine,
    SpecialSituationsEngine,
    SpecialSituationType,
    ThesisBreaker,
)


class TestBearCaseEngine:
    """Test bear case analysis engine."""

    def test_thesis_breaker_negative_fcf(self):
        """Test detection of negative FCF thesis breaker."""
        breakers = BearCaseEngine.assess_thesis_breakers(
            fcf_current=-100,
            revenue_trend=[1000, 1100, 1200],
            net_leverage_x=2.0,
            fcf_coverage_x=2.5,
            customer_concentration_pct=0.30,
            capex_last_year=200,
            capex_prior_year=200,
            revenue_last_year=1200,
            revenue_prior_year=1100,
        )
        assert len(breakers) == 1
        assert breakers[0].breaker == ThesisBreaker.NEGATIVE_FCF
        assert breakers[0].severity == "CRITICAL"

    def test_thesis_breaker_declining_revenue(self):
        """Test detection of declining revenue thesis breaker."""
        breakers = BearCaseEngine.assess_thesis_breakers(
            fcf_current=100,
            revenue_trend=[1200, 1100, 1000],  # Declining
            net_leverage_x=2.0,
            fcf_coverage_x=2.5,
            customer_concentration_pct=0.30,
            capex_last_year=200,
            capex_prior_year=200,
            revenue_last_year=1000,
            revenue_prior_year=1100,
        )
        assert len(breakers) == 1
        assert breakers[0].breaker == ThesisBreaker.DECLINING_REVENUE

    def test_thesis_breaker_unsustainable_debt(self):
        """Test detection of unsustainable debt thesis breaker."""
        breakers = BearCaseEngine.assess_thesis_breakers(
            fcf_current=50,
            revenue_trend=[1000, 1100, 1200],
            net_leverage_x=4.5,  # >4.0x
            fcf_coverage_x=1.2,  # <1.5x
            customer_concentration_pct=0.30,
            capex_last_year=200,
            capex_prior_year=200,
            revenue_last_year=1200,
            revenue_prior_year=1100,
        )
        assert len(breakers) == 1
        assert breakers[0].breaker == ThesisBreaker.UNSUSTAINABLE_DEBT
        assert breakers[0].severity == "CRITICAL"

    def test_thesis_breaker_customer_concentration(self):
        """Test detection of customer concentration thesis breaker."""
        breakers = BearCaseEngine.assess_thesis_breakers(
            fcf_current=100,
            revenue_trend=[1000, 1100, 1200],
            net_leverage_x=2.0,
            fcf_coverage_x=2.5,
            customer_concentration_pct=0.55,  # >50%
            capex_last_year=200,
            capex_prior_year=200,
            revenue_last_year=1200,
            revenue_prior_year=1100,
        )
        assert len(breakers) == 1
        assert breakers[0].breaker == ThesisBreaker.CUSTOMER_CONCENTRATION

    def test_thesis_breaker_multiple_breakers(self):
        """Test detection of multiple thesis breakers."""
        breakers = BearCaseEngine.assess_thesis_breakers(
            fcf_current=-100,  # Negative FCF
            revenue_trend=[1200, 1100, 1000],  # Declining
            net_leverage_x=4.5,  # High leverage
            fcf_coverage_x=1.2,  # Low coverage
            customer_concentration_pct=0.55,  # High concentration
            capex_last_year=200,
            capex_prior_year=200,
            revenue_last_year=1000,
            revenue_prior_year=1100,
        )
        assert len(breakers) >= 3
        breaker_types = {b.breaker for b in breakers}
        assert ThesisBreaker.NEGATIVE_FCF in breaker_types
        assert ThesisBreaker.DECLINING_REVENUE in breaker_types

    def test_risk_factors_market_share_loss(self):
        """Test assessment of market share loss risk."""
        risks = BearCaseEngine.assess_risk_factors(
            current_market_share_pct=22,
            historical_market_share_pct=25,  # Lost 3%
            current_operating_margin_pct=20,
            historical_operating_margin_pct=20,
            current_pe_multiple=15,
            historical_pe_multiple=15,
            gross_revenue=1000,
            roe=0.15,
            debt_to_fcf_x=2.5,
            capex_intensity_pct=0.06,
            r_and_d_intensity_pct=0.08,
        )
        assert len(risks) > 0
        market_share_risks = [r for r in risks if r.risk_factor == BearRiskFactor.MARKET_SHARE_LOSS]
        assert len(market_share_risks) > 0
        assert market_share_risks[0].revenue_impact_pct < 0

    def test_risk_factors_margin_compression(self):
        """Test assessment of margin compression risk."""
        risks = BearCaseEngine.assess_risk_factors(
            current_market_share_pct=25,
            historical_market_share_pct=25,
            current_operating_margin_pct=18,
            historical_operating_margin_pct=20,  # Declined 200bps
            current_pe_multiple=15,
            historical_pe_multiple=15,
            gross_revenue=1000,
            roe=0.15,
            debt_to_fcf_x=2.5,
            capex_intensity_pct=0.06,
            r_and_d_intensity_pct=0.08,
        )
        margin_risks = [r for r in risks if r.risk_factor == BearRiskFactor.MARGIN_COMPRESSION]
        assert len(margin_risks) > 0
        assert margin_risks[0].margin_impact_bps < 0

    def test_bear_case_score_no_breakers(self):
        """Test bear case score with no thesis breakers."""
        result = BearCaseEngine.calculate_bear_case(
            company_id="AAPL",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            thesis_breakers=[],
            risk_factors=[],
            consensus_target_price=180,
            base_enterprise_value=2_500_000,
            shares_outstanding=15_600,
        )
        assert result.bear_case_score < 50
        assert not result.thesis_is_broken

    def test_bear_case_score_with_breakers(self):
        """Test bear case score with critical thesis breakers."""
        from accountant.valuation.bear_case_engine import ThesisBreakerFlag

        breaker = ThesisBreakerFlag(
            breaker=ThesisBreaker.NEGATIVE_FCF,
            description="FCF is negative",
            severity="CRITICAL",
            threshold_metric="FCF < $0",
            remediation="Improve profitability",
        )
        result = BearCaseEngine.calculate_bear_case(
            company_id="AAPL",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            thesis_breakers=[breaker],
            risk_factors=[],
            consensus_target_price=180,
            base_enterprise_value=2_500_000,
            shares_outstanding=15_600,
        )
        assert result.thesis_is_broken
        assert result.bear_case_score >= 70

    def test_bear_case_scenarios(self):
        """Test bear case scenario modeling."""
        result = BearCaseEngine.calculate_bear_case(
            company_id="AAPL",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            thesis_breakers=[],
            risk_factors=[],
            consensus_target_price=180,
            base_enterprise_value=2_500_000,
            shares_outstanding=15_600,
            current_stock_price=190,
        )
        assert result.recession_scenario is not None
        assert result.margin_compression_scenario is not None
        assert result.combined_downside_scenario is not None
        assert result.recession_scenario.revenue_impact_pct < 0
        assert result.margin_compression_scenario.ebitda_margin_bps < 0

    def test_bear_case_downside_assessment(self):
        """Test downside to consensus assessment."""
        result = BearCaseEngine.calculate_bear_case(
            company_id="AAPL",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            thesis_breakers=[],
            risk_factors=[],
            consensus_target_price=180,
            base_enterprise_value=2_500_000,
            shares_outstanding=15_600,
            current_stock_price=190,
        )
        assert result.downside_to_consensus_pct is not None
        assert result.downside_is_material or result.downside_to_consensus_pct > -15


class TestCapitalStructureEngine:
    """Test capital structure opportunity engine."""

    def test_excess_cash_analysis(self):
        """Test excess cash identification."""
        excess_analysis = CapitalStructureEngine.analyze_excess_cash(
            cash_and_equivalents_usd=10_000,
            annualized_opex_usd=10_000,
        )
        assert excess_analysis.total_cash_usd == 10_000
        assert excess_analysis.operating_cash_minimum_usd > 0
        assert excess_analysis.excess_cash_usd > 0

    def test_leverage_opportunity_underleveraged(self):
        """Test identification of underleveraged company."""
        lev_opp = CapitalStructureEngine.analyze_leverage_opportunity(
            current_net_leverage_x=0.5,
            ebitda_usd=500,
            sector="TECHNOLOGY",
        )
        assert lev_opp.leverage_headroom_x > 0.5
        assert lev_opp.borrowing_capacity_usd > 0
        assert lev_opp.recommendation == "BORROW"

    def test_leverage_opportunity_optimal(self):
        """Test identification of optimal leverage."""
        lev_opp = CapitalStructureEngine.analyze_leverage_opportunity(
            current_net_leverage_x=1.4,
            ebitda_usd=500,
            sector="TECHNOLOGY",
        )
        assert abs(lev_opp.leverage_headroom_x) < 0.2
        assert lev_opp.recommendation in ["HOLD", "BORROW"]

    def test_leverage_opportunity_overleveraged(self):
        """Test identification of overleveraged company."""
        lev_opp = CapitalStructureEngine.analyze_leverage_opportunity(
            current_net_leverage_x=4.0,
            ebitda_usd=500,
            sector="TECHNOLOGY",
        )
        assert lev_opp.leverage_headroom_x <= 0
        assert lev_opp.recommendation == "REDUCE"

    def test_buyback_opportunity_accretive(self):
        """Test accretive buyback opportunity."""
        buyback = CapitalStructureEngine.analyze_buyback_opportunity(
            current_stock_price=80,
            intrinsic_value_estimate=100,  # 20% undervalued
            shares_outstanding=100,
            annual_fcf=500,
            net_income=400,
        )
        assert buyback.discount_to_intrinsic_pct > 10
        assert buyback.buyback_is_accretive
        assert buyback.recommendation in ["AGGRESSIVE", "MODERATE"]

    def test_buyback_opportunity_not_accretive(self):
        """Test non-accretive buyback (overvalued stock)."""
        buyback = CapitalStructureEngine.analyze_buyback_opportunity(
            current_stock_price=130,
            intrinsic_value_estimate=100,  # 30% overvalued
            shares_outstanding=100,
            annual_fcf=500,
            net_income=400,
        )
        assert buyback.discount_to_intrinsic_pct < 0
        assert not buyback.buyback_is_accretive
        assert buyback.recommendation == "NONE"

    def test_dividend_analysis_sustainable(self):
        """Test sustainable dividend assessment."""
        dividend = CapitalStructureEngine.analyze_dividend(
            annual_dividend_usd=50,  # 10% of FCF
            annual_fcf=500,
            net_income=400,
            shares_outstanding=100,
        )
        assert dividend.current_dividend_per_share is not None
        assert dividend.fcf_coverage_of_dividend > 1
        assert dividend.recommendation in ["MAINTAIN", "EXPAND"]

    def test_dividend_analysis_unsustainable(self):
        """Test unsustainable dividend assessment."""
        dividend = CapitalStructureEngine.analyze_dividend(
            annual_dividend_usd=350,  # 70% of FCF
            annual_fcf=500,
            net_income=400,
            shares_outstanding=100,
        )
        assert dividend.fcf_coverage_of_dividend < 2
        assert dividend.recommendation == "REDUCE"

    def test_capital_structure_cash_rich(self):
        """Test classification of cash-rich company."""
        result = CapitalStructureEngine.calculate_capital_structure(
            company_id="AAPL",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            cash_usd=50_000,  # 25% of capital
            debt_usd=30_000,
            equity_market_cap_usd=150_000,
            ebitda_usd=100_000,
            fcf_annual_usd=80_000,
            net_income_usd=70_000,
            shares_outstanding=15_600,
            stock_price=160,
            intrinsic_value_estimate=150,
            sector="TECHNOLOGY",
        )
        from accountant.valuation.capital_structure_engine import CapStructureType

        assert result.current_cap_structure_type == CapStructureType.CASH_RICH
        assert result.has_excess_cash

    def test_capital_structure_underleveraged(self):
        """Test classification of underleveraged company."""
        result = CapitalStructureEngine.calculate_capital_structure(
            company_id="TECH",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            cash_usd=20_000,
            debt_usd=10_000,
            equity_market_cap_usd=150_000,
            ebitda_usd=100_000,
            fcf_annual_usd=80_000,
            net_income_usd=70_000,
            shares_outstanding=15_600,
            stock_price=160,
            intrinsic_value_estimate=150,
            sector="TECHNOLOGY",
        )

        assert result.can_borrow_more


class TestSpecialSituationsEngine:
    """Test special situations (M&A, spin-offs, restructurings) engine."""

    def test_acquisition_scenario_modeling(self):
        """Test M&A acquisition scenario modeling."""
        acq = SpecialSituationsEngine.model_acquisition(
            target_current_stock_price=100,
            shares_outstanding=100,
            enterprise_value_usd=10_000,
            strategic_buyer_exists=True,
            synergy_potential_usd=500,
        )
        assert acq.implied_acquisition_price > acq.target_current_price
        assert acq.control_premium_pct > 0
        assert acq.deal_likelihood_pct > 0

    def test_acquisition_regulatory_risk(self):
        """Test acquisition scenario with regulatory risk."""
        acq_no_risk = SpecialSituationsEngine.model_acquisition(
            target_current_stock_price=100,
            shares_outstanding=100,
            enterprise_value_usd=10_000,
            regulatory_risk=False,
        )
        acq_with_risk = SpecialSituationsEngine.model_acquisition(
            target_current_stock_price=100,
            shares_outstanding=100,
            enterprise_value_usd=10_000,
            regulatory_risk=True,
        )
        assert acq_with_risk.control_premium_pct < acq_no_risk.control_premium_pct
        assert acq_with_risk.deal_likelihood_pct < acq_no_risk.deal_likelihood_pct

    def test_tender_offer_scenario(self):
        """Test tender offer (take-private) modeling."""
        tender = SpecialSituationsEngine.model_tender_offer(
            current_stock_price=100,
            offer_price_per_share=130,
        )
        assert tender.arbitrage_spread_pct > 0
        assert tender.deal_certainty_pct > 0
        assert tender.expected_close_timeline_months > 0

    def test_spinoff_scenario(self):
        """Test spin-off value creation modeling."""
        spinoff = SpecialSituationsEngine.model_spinoff(
            parent_current_market_cap=10_000,
            parent_revenue=1_000,
            spinco_estimated_revenue=300,
        )
        assert spinoff.parent_implied_value > 0
        assert spinoff.spinco_implied_value > 0
        assert spinoff.combined_sum_of_parts > 0

    def test_restructuring_chapter_11(self):
        """Test Chapter 11 restructuring scenario."""
        reorg = SpecialSituationsEngine.model_restructuring(
            current_equity_value=100,
            total_debt=500,
            enterprise_value=600,
            restructuring_type="CHAPTER_11",
        )
        assert reorg.debt_recovery_pct < 100
        assert reorg.equity_recovery_pct < 50
        assert reorg.timeline_months >= 12

    def test_restructuring_out_of_court(self):
        """Test out-of-court restructuring scenario."""
        reorg_ch11 = SpecialSituationsEngine.model_restructuring(
            current_equity_value=100,
            total_debt=500,
            enterprise_value=600,
            restructuring_type="CHAPTER_11",
        )
        reorg_ooc = SpecialSituationsEngine.model_restructuring(
            current_equity_value=100,
            total_debt=500,
            enterprise_value=600,
            restructuring_type="OUT_OF_COURT",
        )
        # Out-of-court should have better recovery
        assert reorg_ooc.debt_recovery_pct > reorg_ch11.debt_recovery_pct
        assert reorg_ooc.equity_recovery_pct > reorg_ch11.equity_recovery_pct

    def test_special_situations_calculation_m_and_a(self):
        """Test comprehensive special situations analysis for M&A."""
        result = SpecialSituationsEngine.calculate_special_situations(
            company_id="TGT",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            situation_type=SpecialSituationType.M_AND_A_ACQUISITION,
            current_stock_price=100,
            base_case_price=95,
            bull_case_price=130,
            bear_case_price=85,
            event_probability_pct=60,
        )
        assert result.situation_type == SpecialSituationType.M_AND_A_ACQUISITION
        assert result.probability_pct == 60
        assert result.expected_value_price is not None
        assert result.expected_value_price > result.current_stock_price

    def test_special_situations_deal_risks(self):
        """Test deal risk identification."""
        result = SpecialSituationsEngine.calculate_special_situations(
            company_id="TGT",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            situation_type=SpecialSituationType.TENDER_OFFER,
            current_stock_price=100,
            base_case_price=95,
            event_probability_pct=40,
        )
        assert len(result.deal_risks) > 0
        assert any("Regulatory" in risk for risk in result.deal_risks)

    def test_special_situations_mispricing_upside(self):
        """Test upside mispricing detection."""
        result = SpecialSituationsEngine.calculate_special_situations(
            company_id="TGT",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            situation_type=SpecialSituationType.M_AND_A_ACQUISITION,
            current_stock_price=100,
            base_case_price=95,
            bull_case_price=140,
            event_probability_pct=70,
        )
        # Current price (100) < expected value (higher)
        assert result.current_price_vs_expected_value_pct < 0
        assert result.mispricing_opportunity == "UPSIDE"

    def test_special_situations_mispricing_downside(self):
        """Test downside mispricing detection."""
        result = SpecialSituationsEngine.calculate_special_situations(
            company_id="TGT",
            fiscal_year=2024,
            as_of_date="2024-12-31",
            situation_type=SpecialSituationType.M_AND_A_ACQUISITION,
            current_stock_price=100,
            base_case_price=95,
            bull_case_price=110,
            event_probability_pct=20,
        )
        # Current price (100) > expected value (lower)
        assert result.current_price_vs_expected_value_pct > 0
        assert result.mispricing_opportunity == "DOWNSIDE"
