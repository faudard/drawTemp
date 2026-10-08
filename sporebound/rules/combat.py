"""Pure combat calculations shared by forecasts and effect execution."""
from . import statuses
from ..model import Unit, Skill, Effect, distance

def hit_chance(battle, caster: Unit, target: Unit, skill: Skill) -> float:
    if target.team == caster.team and skill.target in {"ally", "self", "downed"}:
        return 1.0
    chance = skill.accuracy / 100
    d = distance(caster.pos, target.pos)
    if skill.optimal_range and d > skill.optimal_range and skill.falloff_per_tile:
        chance *= max(0, 100 - (d - skill.optimal_range) * skill.falloff_per_tile) / 100
    if skill.id == "attack" and caster.weapon == "ranged" and battle.engaged_by(caster):
        chance *= 0.65
    if target.cast or battle.status_blocks(target, "evasion"):
        return chance
    if skill.magical:
        return chance * (1 - target.magic_evade / 100)
    if caster.support != "concentrate":
        dx, dy = caster.pos[0] - target.pos[0], caster.pos[1] - target.pos[1]
        dot = dx * target.facing[0] + dy * target.facing[1]
        layers = [target.accessory_evade]
        if dot >= 0:
            layers += [target.shield_evade, target.weapon_evade]
        if dot > 0:
            layers += [target.class_evade]
        for evade in layers:
            chance *= 1 - evade / 100
    return battle.rules.reactions.get(target.reaction).evade(battle, target, chance)

def damage(battle, caster: Unit, target: Unit, skill: Skill, effect: Effect) -> int:
    if skill.id == "attack":
        power = caster.attack
        if caster.weapon == "focus":
            power = caster.magic
        elif caster.weapon == "ranged":
            power = (caster.attack + caster.speed) // 2
        elif caster.weapon == "unarmed":
            return battle._mitigate(caster, target, skill, effect, caster.attack * caster.attack * caster.brave // 100)
        raw = power * caster.weapon_power
    elif skill.magical:
        raw = effect.power * caster.magic * caster.faith * target.faith // 10000
    else:
        raw = caster.attack * effect.power
    return battle._mitigate(caster, target, skill, effect, raw)

def _mitigate(battle, caster, target, skill, effect, raw):
    support = "magic_attack_up" if skill.magical else "attack_up"
    defense = "magic_defense_up" if skill.magical else "defense_up"
    if caster.support == support:
        raw = raw * 4 // 3
    if target.support == defense:
        raw = raw * 2 // 3
    raw = statuses.mitigate(battle, target, skill, raw)
    if target.cast and not skill.magical:
        raw = raw * 3 // 2
    raw = max(0, raw - (target.magic_defense if skill.magical else target.defense))
    return max(0, raw * (100 - target.resistances.get(effect.element, 0)) // 100)

