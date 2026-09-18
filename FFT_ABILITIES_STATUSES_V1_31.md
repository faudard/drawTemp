# Sporebound V1.31 — FFT Abilities & Statuses

Mechanical-only pass built on V1.30.

## Ability slots
- Reaction: Counter / Opportunity / Intercept + Blade Grasp / Auto-Potion / MP Switch.
- Support: Attack UP, Magic Attack UP, Defense UP, Magic Defense UP, Concentrate, Short Charge.
- Movement: Move+1, Move+2, Ignore Height, Teleport, Move-MP Up.

## FFT statuses
Protect 32t, Shell 32t, Regen 36t, Silence (persistent), Sleep 60t, Stop 20t, Don't Move 24t, Don't Act 24t.
Sleep and Stop freeze CT. Don't Move / Don't Act pay the matching CT cost even though the command is sealed.

## Compatibility
Legacy reaction_type fields remain valid. New ability slots default to `none`, so existing content does not silently change build identity.

## Runtime notes
- The 3D battle runtime implements the full V1.31 movement set, including Teleport success rolls and Move-MP Up.
- Auto-Potion currently heals 25% MaxHP because Sporebound does not yet expose FFT-style consumable inventory selection; its Brave-based reaction timing is implemented.
- MP Switch follows the FFT damage-routing behavior: if it triggers while at least 1 MP remains, the hit is redirected to MP and HP damage becomes 0 even when the hit exceeds remaining MP.
- Concentrate removes normal physical equipment/class evasion but does not bypass Blade Grasp.
