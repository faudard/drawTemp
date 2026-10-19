# DrawTemp 5.5 — R23.F : répétition Release Candidate (RC0)

> **Dossier de préqualification, pas validation commerciale.**
> La candidate technique `5.5.0-rc0` n'est ni un tag GitHub, ni une
> release stable, ni un installateur certifié. Le résultat est toujours
> `NO-GO` / `tag_allowed=false` tant que les validations R23 restent ouvertes.

## Conditions d'entrée

La PR R23.F est empilée après R23.A (#297), R23.B (#312),
R23.C (#326), R23.D (#338) et R23.E (#345).
La compatibilité de l'export natif R15 avec le contrôle structuré des
droits R17.E a été conservée lors de la résolution du conflit sur R23.A.

Le code prend la révision Git complète (**même SHA pour toutes les preuves**),
et ne combine pas un inventaire de licences sur un commit avec un
installateur ou un test de jeu sur un autre.

## Parcours réel Studio → GameProject → export → Player → reprise

`scripts/r23f_acceptance.py` réutilise la même API d'authoring que le
Studio et le scénario R17.D (événement interactif, porte, levier,
dialogue, cinématique et ressource sonore) :

1. Construire un projet de référence avec les éditeurs Studio existants.
2. Enregistrer les **vrais Content/GameProject** par la transaction à
   deux documents, puis les rouvrir et contrôler leur contenu.
3. Exporter par le **vrai exporteur R15** avec preflight et inventaire.
4. Copier l'export dans un répertoire indépendant, supprimer le répertoire
   auteur et faire vérifier le bundle sur son nouvel emplacement.
5. Démarrer le **vrai PlayerController** sur les seuls Content et
   GameProject exportés ; jouer le premier dialogue, débuter la mission et
   activer le levier/porte dans le moteur tactique.
6. Sauvegarder puis rouvrir dans un **nouveau contrôleur** et vérifier
   l'identité des états de bataille sans réécrire la sauvegarde.
7. Modifier un document exporté et confirmer le rejet du bundle par
   `verify_bundle`.

Ce parcours est **headless mais emploie les véritables APIs du projet**.
Pour l'export lui-même, un **faux exécutable PyInstaller** est utilisé :
cette suite **ne prétend pas exécuter un Player natif**, un Studio graphique
ou les installateurs système. Les parcours natifs sont contrôlés
séparément dans R23.D ; le rendu Qt offscreen et la machine physique
restent des contrôles distincts.

```bash
python -m scripts.r23f_acceptance \
  --revision "$(git rev-parse HEAD)" \
  --platform Linux \
  --output r23f-journey.json
```

Un rapport JSON décrit les étapes effectivement terminées,
un SHA-256 du manifeste R15, le temps mesuré et les limites
`runtime=synthetic-native-stub`,
`native_gui_qa=not-asserted`, `signed=false`.

## Assemblage des preuves

Le workflow R15 propose deux jobs supplémentaires :

- `r23f-authoring-player` : exécute la réception technique sous
  Linux, Windows et macOS, sans falsifier des preuves humaines.
- `r23f-candidate` : attend les trois parcours et le dossier
  R23.E issu du **même workflow/commit**, rejette tout OS manquant
  ou provenance divergente, puis archive
  `r23f-rc0-NO-GO.json`.

```bash
python scripts/r23f_release_candidate.py \
  --revision "$(git rev-parse HEAD)" \
  --journey-directory r23f-evidence \
  --r23e r23f-upstream/r23e-release-dossier.json \
  --output r23f-rc0-NO-GO.json
```

Le registre R23.B relève d'un **autre workflow GitHub Actions** :
son absence ne vaut pas succès. Si un dossier
`r23b-assessment.json` correspondant **au même SHA** a été recueilli
par un responsable, il peut être introduit explicitement par
`--r23b`; le statut d'endurance demeure `partial`.

## Matrice R23 au stade RC0

| Axe | Présent en RC0 | Bloque encore GO |
|---|---|---|
| R23.1–2 | Installateurs natifs R23.D + parcours export R23.F sur même SHA | Vrai OS vierge, GUI et installation hors ligne validée |
| R23.3 | Sauvegarde/reprise et égalité d'état entre deux contrôleurs | Matrice exhaustive des migrations et corruption/recovery |
| R23.4 | Validation des manifests et tentative de falsification rejetée | Corpus d'imports adversariaux et fuzz |
| R23.5 | Smoke headless / Qt logiciel existant | FPS/CPU/GPU/VRAM sur matériel ciblé |
| R23.6 | Contrôle de persistance R23.B, si joint | Plusieurs heures d'endurance réelle et budgets |
| R23.7–8 | Réglages Player et infrastructure playtests | Audit lecteur d'écran/clavier, testeurs et retests humains |
| R23.9 | Contrat de parcours de référence reproductible | Validation de tutoriels et documentation par un créateur externe |
| R23.10 | Inventaire R23.E des ressources et déclarations | Preuves des droits et attributions validées juridiquement |
| R23.11 | Empreintes et convergence du SHA | Signature/notarisation, provenance éditeur |
| R23.12 | Dossier RC0 avec explicitement douze gates | Approbation et décision de publication humaines |

**Règle ferme :** aucune commande de R23.F ne crée un tag, n'émet une
GitHub Release, n'envoie un paquet à un utilisateur ou ne déclare la
5.5 certifiée. Pour la publication, les responsables doivent refaire
la revue sur un candidat gelé et signer un dossier **hors de ce workflow**.

## Tests et fusion

```bash
python -m unittest tests_standalone.test_drawtemp5_r23f -v
python -m unittest tests_standalone.test_r17d_studio_player_roundtrip -v
python -m unittest tests_standalone.test_drawtemp5_r23a -v
python -m unittest tests_standalone.test_r17_asset_rights -v
```

Ordre de fusion : **#297 → #312 → #326 → #338 → #345 → R23.F**.
Toute fusion doit être précédée de la correction des conflits et du
passage de la CI du commit final. Une PR fusionnable n'implique pas
une CI verte ni la certification de la release.
