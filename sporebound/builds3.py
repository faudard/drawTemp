"""Talent trees, specialization budgets and build previews (2.7.3).

Jobs keep their existing XP model; earned JP is job_xp // 50, and purchases
are tracked separately. Existing saves with no talents keep the same builds.
"""
from __future__ import annotations

from .model import require

STATS = {"max_hp", "max_mp", "attack", "magic", "defense", "magic_defense",
         "speed", "move", "weapon_power"}


def validate_talent_trees(content):
    for job_id, job in content.jobs.items():
        talents = job.get("talents", {})
        require(isinstance(talents, dict), f"{job_id}: talents must be an object")
        for tid, spec in talents.items():
            require(isinstance(tid, str) and tid and isinstance(spec, dict),
                    f"{job_id}: invalid talent")
            require(set(spec) <= {"jp", "requires", "exclusive", "bonuses", "skills"},
                    f"{job_id}.{tid}: unsupported talent property")
            require(type(spec.get("jp", 1)) is int and 1 <= spec.get("jp", 1) <= 20,
                    f"{job_id}.{tid}: invalid JP cost")
            requires = spec.get("requires", [])
            require(isinstance(requires, list) and all(isinstance(dep, str) for dep in requires)
                    and len(set(requires)) == len(requires)
                    and tid not in requires and all(dep in talents for dep in requires),
                    f"{job_id}.{tid}: invalid prerequisites")
            require(isinstance(spec.get("exclusive", ""), str), "Invalid talent specialization")
            bonuses = spec.get("bonuses", {})
            require(isinstance(bonuses, dict) and set(bonuses) <= STATS
                    and all(type(value) is int and 0 <= value <= 100
                            for value in bonuses.values()),
                    f"{job_id}.{tid}: invalid bonuses")
            skills = spec.get("skills", [])
            require(isinstance(skills, list) and all(isinstance(sid, str) for sid in skills)
                    and len(set(skills)) == len(skills)
                    and all(skill_id in content.skills for skill_id in skills),
                    f"{job_id}.{tid}: unknown skill")
        visited, visiting = set(), set()

        def visit(tid):
            require(tid not in visiting, f"{job_id}: cyclic talent prerequisites")
            if tid in visited:
                return
            visiting.add(tid)
            for prerequisite in talents[tid].get("requires", []):
                visit(prerequisite)
            visiting.remove(tid)
            visited.add(tid)

        for tid in sorted(talents):
            visit(tid)


def available_jp(hero, job_id):
    return max(0, hero.job_xp.get(job_id, 0) // 50 -
               hero.spent_jp.get(job_id, 0))


def talent_catalog(content, hero, job_id):
    require(job_id in content.jobs, "Unknown job")
    talents = content.jobs[job_id].get("talents", {})
    owned = hero.learned_talents.get(job_id, [])
    points = available_jp(hero, job_id)
    rows = []
    for tid, spec in sorted(talents.items()):
        requires = spec.get("requires", [])
        group = spec.get("exclusive", "")
        excluded = bool(group and any(talents[other].get("exclusive") == group
                                      for other in owned if other != tid))
        rows.append({"id": tid, "owned": tid in owned, "jp": spec.get("jp", 1),
                     "available": tid not in owned and not excluded
                     and all(dep in owned for dep in requires)
                     and points >= spec.get("jp", 1), "exclusive": excluded})
    return {"job": job_id, "available_jp": points, "talents": rows}


def learn_talent(content, hero, job_id, talent_id):
    """Fail before mutation; caller owns persistence and transaction boundary."""
    require(job_id in content.jobs, "Unknown job")
    talents = content.jobs[job_id].get("talents", {})
    require(talent_id in talents, "Unknown talent")
    validate_talent_trees(content)
    row = next(r for r in talent_catalog(content, hero, job_id)["talents"]
               if r["id"] == talent_id)
    require(row["available"], "Talent locked, already learned or insufficient JP")
    cost = talents[talent_id].get("jp", 1)
    hero.learned_talents.setdefault(job_id, []).append(talent_id)
    hero.spent_jp[job_id] = hero.spent_jp.get(job_id, 0) + cost


def apply_talents(content, hero, unit):
    for job_id, learned in sorted(hero.learned_talents.items()):
        require(job_id in content.jobs, "Unknown learned talent job")
        specs = content.jobs[job_id].get("talents", {})
        for tid in learned:
            require(tid in specs, "Unknown learned talent")
            spec = specs[tid]
            for key, value in spec.get("bonuses", {}).items():
                setattr(unit, key, getattr(unit, key) + value)
            for sid in spec.get("skills", []):
                if sid not in unit.skills:
                    unit.skills.append(sid)


def validate_hero_build(content, hero):
    require(isinstance(hero.spent_jp, dict) and
            all(type(n) is int and n >= 0 for n in hero.spent_jp.values()),
            "Invalid spent JP")
    require(isinstance(hero.learned_talents, dict) and
            all(isinstance(v, list) and all(isinstance(t, str) for t in v)
                and len(v) == len(set(v)) for v in hero.learned_talents.values()), "Invalid learned talents")
    for job_id, learned in hero.learned_talents.items():
        require(job_id in content.jobs, "Unknown learned talent job")
        talents = content.jobs[job_id].get("talents", {})
        require(all(tid in talents for tid in learned), "Unknown learned talent")
        require(all(set(talents[tid].get("requires", [])) <= set(learned)
                    for tid in learned), "Missing talent prerequisite")
        groups = [talents[tid].get("exclusive") for tid in learned
                  if talents[tid].get("exclusive")]
        require(len(groups) == len(set(groups)), "Conflicting specialization")
        require(sum(talents[tid].get("jp", 1) for tid in learned)
                == hero.spent_jp.get(job_id, 0), "Inconsistent JP spending")
    for job_id, spent in hero.spent_jp.items():
        require(job_id in content.jobs and spent <= hero.job_xp.get(job_id, 0) // 50,
                "Talent JP exceeds earned JP")
        require(job_id in hero.learned_talents or spent == 0,
                "Missing learned talents")
