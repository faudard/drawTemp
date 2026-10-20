"""R63.C: deterministic, read-only survival balancing diagnostics.

The Studio forecast never changes authored data, GameSession, player inventory,
CT or RNG. The horizon is bounded and never assumes any unearned resources.
"""
from __future__ import annotations

from .model import require
from .survival import SurvivalRuntime


def balance_survival(spec, scenes, *, exploration=None, horizon=256):
    require(type(horizon) is int and 1 <= horizon <= 256,
            "R63 balance horizon must be an integer in 1..256")
    simulation = SurvivalRuntime(spec, scenes, exploration=exploration)
    initial = dict(simulation.needs)
    warning_tick = None
    exhausted_tick = None
    for tick in range(1, horizon + 1):
        simulation.advance(1)
        condition = simulation.condition()
        if warning_tick is None and condition["phase"] != "stable":
            warning_tick = tick
        if condition["phase"] == "incapacitated":
            exhausted_tick = tick
            break

    recipes = [
        {"id": row["id"], "energy_cost": row["energy_cost"],
         "input_types": len(row["inputs"]),
         "output_types": len(row["outputs"]),
         "available_at_start": (
             initial["energy"] >= row["energy_cost"]
             and initial["hunger"] > 0
             and initial["temperature"] > 0)}
        for row in sorted(spec["recipes"], key=lambda row: row["id"])
    ]
    hazards = [
        {"id": row["id"], "scene": row["scene"], "cold": row["cold"]}
        for row in spec["nodes"] if row["cold"] > 0
    ]
    return {
        "horizon": horizon,
        "warning_tick": warning_tick,
        "exhausted_tick": exhausted_tick,
        "initial_needs": initial,
        "forecast_needs": dict(simulation.needs),
        "recipes": recipes,
        "cold_hazards": hazards,
        "recoveries": [
            {"id": row["id"], "scene": row["scene"],
             "energy_restore": row["energy_restore"],
             "warmth": row["warmth"],
             "fuel": dict(row["fuel"])}
            for row in spec["shelters"]],
        "issues": [
            issue for issue, triggered in (
                ("less_than_two_recipes", len(recipes) < 2),
                ("no_environmental_hazard", not hazards),
                ("no_shelter", not spec["shelters"]),
                ("no_food", not spec["foods"]),
            ) if triggered
        ],
    }
