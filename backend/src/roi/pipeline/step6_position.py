POSITION_WEIGHTS = {1: 1.5, 2: 1.3, 3: 1.0, 4: 0.8, 5: 0.6}


def position_weight(position: float | None) -> float:
    if position is None:
        return 0.0
    rounded = max(1, min(5, round(position)))
    return POSITION_WEIGHTS[rounded]
