# 3.7.11 — Isometric Map Builder: remplissage et pipettes

Ce jalon ajoute à l'éditeur Tk deux outils de composition accessibles dans le sélecteur **Outil** et dans la palette **Sol / Décor**.

## Construire une carte

1. Choisir **Sol** (herbe, pierre, eau, pont...) dans la palette ; le pinceau est activé.
2. Cliquer sur **Remplir sol** pour passer à l'outil **Remplissage**. Un clic remplace toute la composante connexe de cases possédant la même surface que la case visée, avec voisinage orthogonal N/E/S/O. Une case sur la diagonale n'appartient pas à cette région.
3. Cliquer sur **Pipette sol**, puis une case : le terrain de cette case devient le pinceau courant. L'outil repasse automatiquement en **Pinceau**.
4. **Pipette décor** choisit le décor de la case sous le curseur. Si cette case n'a pas de décor, le pinceau devient **Effacer décor**.
5. Ces outils fonctionnent en vue orthogonale ou **Vue isométrique 2.5D** ; le calcul utilise les coordonnées tactiques existantes.

La zone survolée par le remplissage est indiquée par un contour de case. Le remplissage ne déclenche pas de changement si la surface cible est déjà celle de la région.

## Contrats de compatibilité

- Aucun nouveau champ JSON. Les cartes et sauvegardes existantes ne sont pas migrées.
- La sélection d'une région lit les surfaces courantes, avec `grass` comme défaut des tuiles absentes du document sparse.
- Une opération de remplissage est **une seule transaction validée et annulable** ; elle utilise les règles existantes de `Document.paint_many`, y compris blocages eau/pont et interdiction d'une carte tactiquement invalide.
- La couche `feature`, les hauteurs et les métadonnées tactiques non concernées sont conservées. Une pipette ne modifie jamais la carte.
- Les règles tactiques, l'IA, les coordonnées, la sérialisation, le Player headless et les replays restent inchangés.
- Les changements JSON en attente doivent être appliqués/abandonnés avant une pipette ou un remplissage. Le mode combat interdit ces outils.

## Gates

```sh
python -m unittest discover -s tests_standalone -p test_map_fill_3711.py -v
python -m unittest discover -s tests_standalone -p test_iso_map_builder.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

Le smoke GUI doit vérifier le remplissage de deux cases contiguës, la conservation des cases voisines, la pipette de sol et de décor, le passage en vue iso et la sauvegarde. La CI multi-OS + distribution reste la gate finale.
