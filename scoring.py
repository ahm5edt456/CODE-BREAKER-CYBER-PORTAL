"""Per-challenge reward for active solving time."""
import math

BASE_POINTS=100
NO_HINT_BONUS=25
MAX_SPEED_BONUS=100

def speed_bonus(seconds):
    if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<0:
        raise ValueError('Solve time must be a finite non-negative number.')
    return max(0,MAX_SPEED_BONUS-math.floor(seconds*2))
