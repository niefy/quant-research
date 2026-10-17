"""ValidationProfile v1 contracts.

Thresholds are configuration, not code. Every gate has a typed section so a
profile can be reviewed and hashed before a research run starts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from quant.contracts.factor import ContractModel


class G1ICThresholds(ContractModel):
    rank_ic_mean_min: float = 0.02
    icir_min: float = 0.40
    ic_win_rate_min: float = 0.52
    t_stat_min: float = 2.0
    min_periods: int = Field(default=365, ge=1)
    subperiod_positive_ratio_min: float = 0.60


class G2QuantileThresholds(ContractModel):
    n_quantiles: int = Field(default=5, ge=2)
    monotonicity_min: float = 0.70
    long_short_t_stat_min: float = 2.0
    turnover_max: float = 1.0


class G3RobustnessThresholds(ContractModel):
    plateau_coverage_min: float = 0.60
    plateau_tolerance: float = 0.20
    regime_positive_min: int = Field(default=2, ge=1)
    permutation_p_max: float = 0.05
    permutation_b: int = Field(default=1000, ge=1)
    bootstrap_b: int = Field(default=2000, ge=1)
    cost_multipliers: list[float] = Field(default_factory=lambda: [1.0, 2.0, 3.0])


class G4RedundancyThresholds(ContractModel):
    max_abs_corr: float = 0.50
    residual_rank_ic_min: float = 0.01
    residual_t_stat_min: float = 2.0
    duplicate_corr: float = 0.80


class G5GroupThresholds(ContractModel):
    fdr_q: float = 0.10
    pbo_max: float = 0.30
    cscv_splits: int = Field(default=10, ge=2)
    dsr_p_max: float = 0.05


class G6StrategyThresholds(ContractModel):
    cpcv_groups: int = Field(default=6, ge=2)
    cpcv_test_groups: int = Field(default=2, ge=1)
    purge: Literal["label_horizon"] = "label_horizon"
    embargo_pct: float = 0.01
    oos_sharpe_min: float = 0.5
    dsr_p_max: float = 0.05
    max_drawdown_p95: float = 0.40
    ruin_probability_max: float = 0.05


class G7HoldoutThresholds(ContractModel):
    min_rank_ic: float = 0.0
    min_sharpe: float = 0.0
    dsr_p_max: float = 0.10
    degradation_tolerance: float = 0.50


class Thresholds(ContractModel):
    g1_ic: G1ICThresholds = Field(default_factory=G1ICThresholds)
    g2_quantile: G2QuantileThresholds = Field(default_factory=G2QuantileThresholds)
    g3_robustness: G3RobustnessThresholds = Field(default_factory=G3RobustnessThresholds)
    g4_redundancy: G4RedundancyThresholds = Field(default_factory=G4RedundancyThresholds)
    g5_group: G5GroupThresholds = Field(default_factory=G5GroupThresholds)
    g6_strategy: G6StrategyThresholds = Field(default_factory=G6StrategyThresholds)
    g7_holdout: G7HoldoutThresholds = Field(default_factory=G7HoldoutThresholds)


class ProfileMetadata(ContractModel):
    id: str = Field(min_length=1)
    market: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    scope: Literal["cross_sectional", "time_series"]
    version: int = Field(default=1, ge=1)


class ValidationProfileDocument(ContractModel):
    api_version: Literal["quant/v1"] = Field(alias="apiVersion")
    kind: Literal["ValidationProfile"]
    metadata: ProfileMetadata
    thresholds: Thresholds = Field(default_factory=Thresholds)
