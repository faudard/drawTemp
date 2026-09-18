# Sporebound V1.30 — FFT Core Combat

Cette passe poursuit la convergence vers Final Fantasy Tactics sans changer les assets.

## Ajouts
- Brave/Faith par unité.
- Zodiac + sexe, compatibilité Neutral/Good/Bad/Best/Worst.
- Réactions répétables, proc = Brave (les réactions Sporebound legacy restent disponibles).
- Weapon Power et formules d'attaque par famille : mêlée/lance PA×WP, distance proche arc `(PA+Speed)/2×WP`, focus MA×WP, mains nues Brave/PA.
- Les attaques de base n'ajoutent plus de dégâts artificiels pour dos/flanc/hauteur/couvert ; l'orientation agit via l'évasion.
- Magie stat-scalée : Q × MA × Faith lanceur × Faith cible, avec compatibilité zodiacale.
- Haste/Slow modifient le gain CT (+50% / ×0,5) sans modifier la Speed utilisée par les formules d'armes.
- Durées de statuts en clockticks ; Poison = 1/8 HP max en fin d'AT.

## Compatibilité Sporebound
Les DEF, résistances et quelques réactions custom (Opportunity/Intercept) sont encore conservées pour ne pas casser le contenu. Elles pourront être retirées/transformées dans la prochaine passe FFT stricte.
