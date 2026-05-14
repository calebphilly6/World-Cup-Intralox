from __future__ import annotations


def american_to_decimal(american_odds: str | int | float | None) -> float | None:
    if american_odds is None or str(american_odds).strip() == "":
        return None
    value = float(str(american_odds).replace("+", "").strip())
    if value > 0:
        return 1 + (value / 100)
    if value < 0:
        return 1 + (100 / abs(value))
    return None


def decimal_to_implied_probability(decimal_odds: float | int | None) -> float | None:
    if decimal_odds is None:
        return None
    value = float(decimal_odds)
    if value <= 1:
        return None
    return 1 / value


def american_to_implied_probability(american_odds: str | int | float | None) -> float | None:
    return decimal_to_implied_probability(american_to_decimal(american_odds))
