# V1.29 — FFT Magic, Charging & Evasion

This pass continues the V1.28 CT loop toward Final Fantasy Tactics behavior.

## MP economy
- The serialized `focus` / `focus_cost` names remain for backward save/content compatibility.
- In battle UI they are now presented as **MP**.
- MP no longer regenerates by +1 every round.
- Explicit equipment/passive `focus_regen_bonus` still works as an MP-regen extension.
- Cooldowns remain disabled.

## Slow actions / Charging
- A slow action has a separate countdown (`cast_time_ticks`) while the caster's own CT keeps filling.
- A caster can therefore receive another Active Turn before the slow action resolves.
- Move and WAIT preserve the cast. Choosing another Action (Attack/skill) cancels it.
- Slow-action MP is checked and paid at resolution; a cancelled cast spends no MP.
- Ordinary damage does **not** cancel Charging; interruption is reserved for explicit mechanics.
- Enemy AI automatically WAITs when its AT arrives during a cast.
- While Charging, evasion is ignored and physical damage receives the FFT-style x3/2 vulnerability.

## Evasion
- Basic ATTACK starts from 100% before evade layers.
- Existing generic `evasion` is mapped to FFT-style physical class evade (C.Ev).
- Optional shield/accessory/weapon evade layers are available in both the unit data resource and `SporeUnitActor3D`.
- Front: class + shield + accessory + weapon evade.
- Side: shield + accessory + weapon evade.
- Back: accessory evade only.
- Accuracy-based magical skills use magical shield + accessory evade and ignore facing.
- Height/cover hit bonuses from the previous custom formula are disabled in the shared strict FFT calculation.

## Simultaneous Active Turns
- Speed only controls CT gain.
- If several units become ready on the same clocktick, the stable battle roster order breaks the tie instead of highest CT/Speed.

## Compatibility
No `.tres` property was renamed. Existing Sporebound content remains loadable.
