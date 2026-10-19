# R44.C — La route des cinq vallées

**Candidat vertical slice headless, non certifié 8.4.** Le code n'est pas une preuve de Player natif GPU ni de clean-machine.

## Contenu

- Cinq scènes/régions liées : **hameau → vergers → lagune → crête → sanctuaire**, chacune avec une relique persistante. Les portes de l'étape suivante dépendent du flag activé en interagissant avec la relique locale.
- Quatre retours explicites, sans téléportation implicite ni second registre de progression.
- Biomes, thèmes d'exploration et conversions top-down/isométriques définis par le `WorldGraph` R44.A/B.
- `GameSession.route_world_interact("relic")` valide qu'il s'agit d'une interaction existante, non-sortie et atteignable dans la scène active. Elle délègue à `route_interact` puis inscrit exactement un booléen dans les `Campaign.story_flags` et ne distribue aucun bonus/reward parallèle. Toute erreur laisse la progression inchangée.
- `GameSession.route_transition` et `SceneRouter` restent seuls responsables de la navigation. Le coût R44 n'a toujours aucun effet temporel.
- La sauvegarde v1 existante stocke déjà les flags, la scène active et l'historique de routes; aucune migration ou nouvel encodage de save.

## Reproduire

```bash
python -m examples.r44_five_valleys --smoke
python -m examples.r44_five_valleys --output /tmp/r44-five-valleys
python -m drawtemp.export.cli check --content /tmp/r44-five-valleys/five_valleys.json --require-licenses
python -m unittest tests_standalone.test_r44c_five_valleys
```

L'émetteur refuse de remplacer un dossier existant. Le projet généré n'inclut aucun asset physique : la vérification de licence stricte concerne donc un registre vide, **et ne qualifie pas l'illustration du jeu**.

## Gate R44 restant

- [ ] Vérifier les tests headless, anciens replays/saves et Qt onscreen sur CI active.
- [ ] Adapter **la vraie interface Player** aux scènes R25/R44 (interaction, navigation, scène active), puis recharger une partie dans le Player natif.
- [ ] Qualifier cinq régions graphiquement avec sprites/FX licites, picking et viewport réellement partagé.
- [ ] Exporter et réexécuter sur trois OS propres, budget de chargement mesuré et QA clavier/GPU.
- [ ] Vérifier les contre-exemples de portes/clés en jouabilité, pas seulement la connectivité du graphe.

La démo fournit la preuve **au niveau GameSession** et un pair Content/GameProject utilisable pour le futur Player; le Player Qt existant ne prend pas encore en charge la totalité de ce parcours. R44.C n'est donc pas livré intégralement.
