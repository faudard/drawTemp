"""R36.B2 software-capable, deterministic and bounded cosmetic particle/light plan.

Consumes R36.B1 detached FX snapshots, not simulation commands or hitboxes.
This is a *render plan*: no GPU shader, occlusion or per-pixel light solver.
"""
from __future__ import annotations

from hashlib import sha256
from math import isfinite

MAX_PARTICLES = 128
MAX_LIGHTS = 8
ALLOWED_FX = frozenset(("slash", "dust", "impact", "defeat", "guard", "spark"))
KINDS = {
    "slash": ("#ffe4a8", 4),
    "dust": ("#b6b1a2", 3),
    "impact": ("#ffb096", 5),
    "defeat": ("#b2b3da", 6),
    "guard": ("#b5d8f1", 2),
    "spark": ("#fbdd87", 4),
}
LIT_KINDS = frozenset(("slash", "impact", "guard", "spark"))


def _byte(value):
    return sha256(value.encode("utf-8")).digest()


def project_vfx(fx, *, reduced_motion=False, lights_enabled=True,
                density=2, ambient_alpha=0.08):
    """Pure stable QML-friendly particle/light descriptors.

    Effects already have committed start/expiry timestamps and positions.
    Density is capped; the result is independent of draw cadence and Python
    hash randomization. No per-frame RNG or resource allocation in Qt.
    """
    if type(fx) is not list or len(fx) > 96:
        raise ValueError("Invalid bounded committed FX snapshot")
    if (type(reduced_motion) is not bool or type(lights_enabled) is not bool or
            type(density) is not int or density not in (0, 1, 2, 3) or
            type(ambient_alpha) not in (int, float) or
            not isfinite(ambient_alpha) or not 0 <= ambient_alpha <= 0.25):
        raise ValueError("Invalid R36 visual quality profile")
    particles = []
    lights = []
    for row in fx:
        if (type(row) is not dict or
                set(row) != {"id", "kind", "actor", "x", "y", "alpha", "scale"} or
                type(row["id"]) is not str or len(row["id"]) > 128 or
                row["kind"] not in ALLOWED_FX or
                any(type(row[k]) not in (int, float) or not isfinite(row[k])
                    for k in ("x", "y", "alpha", "scale")) or
                not 0 <= row["alpha"] <= 1 or not 0 < row["scale"] <= 2):
            raise ValueError("Malformed committed cosmetic effect")
        if reduced_motion:
            continue
        color, count = KINDS[row["kind"]]
        for i in range(count * density):
            if len(particles) >= MAX_PARTICLES:
                break
            digest = _byte(row["id"] + ":" + str(i))
            angle_x = (digest[0] / 255 - .5) * 1.2
            angle_y = (digest[1] / 255 - .5) * 1.2
            progression = 1 - row["alpha"]
            particles.append({
                "id": row["id"] + ":" + str(i),
                "x": row["x"] + angle_x * progression,
                "y": row["y"] + angle_y * progression,
                "radius": 2 + digest[2] % 5,
                "color": color,
                "alpha": round(row["alpha"] * 0.7, 4),
            })
        if lights_enabled and row["kind"] in LIT_KINDS and len(lights) < MAX_LIGHTS:
            lights.append({
                "id": row["id"], "x": row["x"], "y": row["y"],
                "radius": 30 + 28 * row["scale"],
                "color": color,
                "alpha": round(row["alpha"] * .20, 4),
            })
    return {"ambient_alpha": float(ambient_alpha),
            "particles": particles, "lights": lights}
