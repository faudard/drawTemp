# Jeanne — Acte I : Les Cendres (3.0.4)

## Jouer

```bash
python -m sporebound validate --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
python -m sporebound player --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json
python -m unittest tests_standalone.test_jeanne_acte1 -v
python -m unittest tests_standalone.test_jeanne_prologue -v
```

L'Acte I commence **après** le prologue jouable de Domrémy, dans le camp des réfugiés. La promesse de Jeanne mène directement à la scène de recrutement, sans saut de mission ni JSON manuel.

| Étape | Mode | Conséquences |
|---|---|---|
| Camp des réfugiés | Scène à choix | Étienne (écuyer) ou Agnès (hospitalière), équipement obtenu et équipé, confiance initiale |
| Route des fugitifs | Combat tactique | XP/JP, escorte narrative des rescapés, potions supplémentaires si villageois sauvés |
| Pont de la Brume | Combat tactique | Priorité familles ou reconnaissance ; confiance ou renseignement |
| Hospice | Défense tactique (survie) | Approvisionnement des blessés ou préservation des dossiers |
| Archives **ou** otages | Deux missions exclusives | Preuves sur Valcroix **ou** témoignages et soutien populaire |
| Vaucouleurs | Combat tactique | Audience avec Robert de Baudricourt, choix politique, drapeaux pour l'Acte II |

### Mécanismes persistants

- `recruit_hero`, `grant_item`, `equip_hero` sont des **effets narratifs typés et validés**. Les modifications de ressources et d'équipement sont atomiques dans une copie de `Campaign`.
- Le tag opt-in `recruit:<unit_id>` empêche d'insérer dans une bataille un compagnon non recruté ; les unités des autres campagnes ne sont pas affectées.
- XP et XP de métier suivent le `Campaign.finish` existant. L'équipement utilise les bonus de `Campaign.prepare`. L'interface Player affiche une synthèse équipe, niveaux, équipement et confiance.
- `trust_refugies`, `renseignement`, `evidence` et `acte1_choix` suivent les décisions. Un lien `battle_support` convertit certaines décisions en potion tactique réelle, reproductible.
- Les missions de branche ne se débloquent pas mutuellement. Les récompenses sont attribuées uniquement après une vraie victoire tactique, par le journal de combat existant ; un combat abandonné n'accorde rien.
- `acte1_complete`, `acte2_appui` et `acte2_route_ouverte` ouvrent le **point de raccord narratif** de l'Acte II. Aucune fausse mission de l'Acte II n'est débloquée.

### Limites et compatibilité

- L'Acte I utilise des cartes tactiques et des scènes dialoguées existantes, pas une carte libre permanente de la route.
- L'hospice repose sur l'objectif `survive`, et la mission otages sur la protection effective d'Anne pendant le combat ; le convoi de civils n'a pas d'IA hors combat dédiée.
- Le système de relation est encore une **confiance scénarisée** (flags + conséquences), et non un dialogue de camp illimité / romance autonome.
- Les projets existants sans recrutement ou ces effets ne changent pas. En revanche, la définition de l'histoire Jeanne a changé : le digest de StoryBook empêche d'ouvrir silencieusement des **anciens slots Jeanne** sans migration. Faire une nouvelle partie pour cette tranche ; conserver ses sauvegardes d'avant mise à jour.

### Suites (non livrées dans cette PR)

- **Acte II — Route d'Orléans et sacre** : consommer le drapeau `acte2_appui`, conversations, progression et nouveaux alliés.
- **Acte III — Siège de Valcroix** : connecter le scénario `SiegeCampaign` / `MultiFrontSession` déjà développé comme mission majeure de campagne, avec le graphe narratif stratégique et les preuves du bailli. Ne pas traiter la démo château comme déjà intégrée.
- **Acte IV — Captivité et révélations** puis **Acte V — Résolution**, avec fins conditionnelles.

## Tests

`test_jeanne_acte1` exerce recrutement, statistiques d'équipement, garde d'accès, missions, choix exclusifs, sauvegarde/reprise et clôture de l'Acte I. `test_jeanne_prologue` conserve la validation des deux routes de Domrémy. Les tests headless et la CI multi-OS doivent être verts avant fusion.
