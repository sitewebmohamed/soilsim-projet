"""Agronomic and scoring constants for SoilSim.

Pure constants only per AGENTS.md.
Every non-crop constant has a citation or is flagged as an ASSUMPTION.
"""

from typing import Dict

# Available water tiers (mm/year) by farmer irrigation access level.
# This is the irrigation water the farmer can supply per year on top of rain.
# ASSUMPTION: rough regional irrigation access tiers (low/rainfed supplemental, medium, high).
AVAILABLE_WATER_MM: Dict[str, float] = {
    "low": 100.0,
    "medium": 300.0,
    "high": 600.0,
}

# Shortfall range (mm) over which a slot's water score falls from the
# within-budget floor to 0 once its water deficit exceeds the budget.
# ASSUMPTION: a shortfall of 300 mm beyond the budget scores 0.
WATER_UNMET_RANGE_MM: float = 300.0

# Water score of a slot whose deficit exactly equals the budget.
# Slots that need less water score between this floor and 100, so saving water
# is rewarded; slots that need more score below it.
# ASSUMPTION: 50 on the 0-100 scale.
WATER_WITHIN_BUDGET_FLOOR: float = 50.0

# LEGACY: linear revenue reference used before T5c. No longer used by income_score
# (it saturated at 100 for any plan containing irrigated potato). Kept so old
# imports do not break.
INCOME_REF_MAD_PER_HA: float = 20000.0

# Revenue scale (MAD/ha/year) of the logarithmic income score. Income score is
# 100 * ln(1 + revenue / scale) / ln(1 + highest main-crop revenue / scale),
# averaged over the three slots. The log gives diminishing returns, so very
# high-revenue irrigated crops do not hit 100 so easily.
# This is gross REVENUE (price x yield), NOT profit: costs are not included.
# ASSUMPTION: 5000 MAD/ha is roughly the revenue of a rainfed cereal.
INCOME_SCALE_MAD_PER_HA: float = 5000.0

# Water deficit threshold (mm) for flag/alert.
# ASSUMPTION: threshold signaling mild moisture stress requiring attention.
WATER_FLAG_MM: float = 30.0

# Reference root depth benchmark (cm).
# Source: FAO-56 Table 22 maximum rooting depth for deep-rooting cereals/taproots (150 cm).
ROOT_REF_CM: float = 150.0

# Maximum categorical score for crop residue retention (0 to 3 scale).
# Source: Qualitative residue rating scale from data/crops.csv.
RESIDUE_MAX: float = 3.0

# Maximum categorical score for forage value (0 to 3 scale).
# Source: Qualitative forage rating scale from data/crops.csv.
FORAGE_MAX: float = 3.0

# Penalty deducted from pest break score for each consecutive repeat of the same crop family.
# ASSUMPTION: 50 point deduction per consecutive family repeat on a 0-100 scale.
PEST_REPEAT_PENALTY: float = 50.0

# Minimum number of plans that must fit the water budget for the budget rule to
# apply. If fewer fit, the app falls back to the least water-demanding plans.
# ASSUMPTION: need at least a recommended plan and one alternative.
MIN_BUDGET_POOL: int = 2

# Size of the fallback pool (plans with the lowest peak-year water demand) used
# when almost no plan fits the water budget.
# ASSUMPTION: 100 plans gives enough variety to rank by the farmer's priorities.
LEAST_DEMANDING_POOL_SIZE: int = 100
