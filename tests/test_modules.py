import pytest
from app.utils.scoring import (
    calculate_jeonse_risk_score,
    score_to_grade,
    calculate_reliability_score,
)
from app.models.schemas import RiskGrade


class TestJeonseRiskScore:
    def test_all_safe_returns_zero(self):
        score = calculate_jeonse_risk_score()
        assert score == 0

    def test_high_jeonse_rate(self):
        score = calculate_jeonse_risk_score(jeonse_rate=85)
        assert score == 60

    def test_seizure_adds_30(self):
        score = calculate_jeonse_risk_score(has_seizure=True)
        assert score == 30

    def test_trust_adds_20(self):
        score = calculate_jeonse_risk_score(has_trust=True)
        assert score == 20

    def test_combined_risk(self):
        score = calculate_jeonse_risk_score(
            jeonse_rate=85,
            has_seizure=True,
            has_trust=True,
        )
        assert score == 100  # 60 + 30 + 20 = 110, capped at 100

    def test_suspicious_text(self):
        score = calculate_jeonse_risk_score(text_risk_level="suspicious")
        assert score == 20

    def test_low_price_deviation(self):
        score = calculate_jeonse_risk_score(price_deviation=-25)
        assert score == 30

    def test_moderate_mortgage(self):
        score = calculate_jeonse_risk_score(mortgage_ratio=30)
        assert score == 10


class TestScoreToGrade:
    @pytest.mark.parametrize(
        "score, expected",
        [
            (0, RiskGrade.SAFE),
            (20, RiskGrade.SAFE),
            (21, RiskGrade.CAUTION),
            (40, RiskGrade.CAUTION),
            (41, RiskGrade.WARNING),
            (60, RiskGrade.WARNING),
            (61, RiskGrade.DANGER),
            (100, RiskGrade.DANGER),
        ],
    )
    def test_grade_boundaries(self, score: float, expected: RiskGrade):
        assert score_to_grade(score) == expected


class TestReliabilityScore:
    def test_perfect_scores_no_jeonse(self):
        result = calculate_reliability_score(100, 100)
        assert result == 100.0

    def test_perfect_scores_with_safe_jeonse(self):
        result = calculate_reliability_score(100, 100, 0)
        assert result == 100.0

    def test_half_scores(self):
        result = calculate_reliability_score(50, 50)
        assert result == 50.0

    def test_clamped_to_zero(self):
        result = calculate_reliability_score(0, 0, 100)
        assert result == 0
