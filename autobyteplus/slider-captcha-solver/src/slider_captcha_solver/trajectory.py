"""Human-like drag trajectory generation. Pure function, no browser dependency.

The trajectory is what passes behavior-analysis scoring: sine
acceleration/deceleration (fast middle, slow ends), micro-jitter, and a
slight overshoot with pull-back. Monotonic ease-out drags get flagged.

Validated against ByteDance Turing's real risk engine (2026-10).
"""
import math
import random


def human_drag_trajectory(start_x, start_y, distance, rng=None):
    """Generate waypoints for a human-like drag.

    Args:
        start_x, start_y: drag start point in pixels.
        distance: intended drag distance in pixels (positive = right).
        rng: optional random.Random instance for reproducibility.

    Returns:
        List of steps. Each step is a tuple:
        - ("move", x, y, delay_ms): move pointer to (x, y), then wait.
        - ("down", delay_ms): press left button, then wait.
        - ("up", delay_ms): release left button, then wait.
    """
    r = rng or random
    overshoot = r.uniform(4, 9)
    target = distance + overshoot

    steps = r.randint(45, 75)
    raw = []
    for i in range(steps):
        t = i / steps
        v = math.sin(math.pi * t) ** 0.8  # fast middle, slow ends
        raw.append(v + r.uniform(0, 0.35))
    total = sum(raw)
    xs, acc = [], 0.0
    for v in raw:
        acc += target * v / total
        xs.append(acc)

    traj = [("move", start_x, start_y, r.uniform(150, 250))]
    traj.append(("down", r.randint(120, 260)))  # "grab" pause
    for x in xs:
        y = start_y + r.uniform(-2, 2)
        traj.append(("move", start_x + x, y, r.randint(8, 22)))
    for back in (overshoot * 0.6, overshoot * 0.3, 0):  # pull back
        y = start_y + r.uniform(-1.5, 1.5)
        traj.append(("move", start_x + distance + back, y,
                     r.randint(60, 140)))
    traj.append(("up", r.randint(150, 350)))
    return traj
