# DrawTemp 5.5 — R23.A : intégrité, distribution et preuves de release

> **Périmètre : tranche R23.A uniquement.** Cette intégration n'est ni une
> certification R23 complète ni une autorisation de publier un produit signé.

## Pourquoi continuer R15 au lieu de refaire l'export

R15 construit déjà un Player Qt/PyInstaller et une enveloppe de contenu avec
SHA-256. R17.8 effectue un smoke de ce Player sur un runner distinct. R23.A
conserve les schémas du Core, du GameProject et des sauvegardes historiques.
Elle durcit le **contrat de redistribution** et attache les preuves de build
au SHA réellement testé par la CI.

## Contrat R23.A : fail-closed

- Un `manifest.json` externe doit être un **fichier régulier**, limité à
  8 Mio, sans clé JSON dupliquée. Les chemins déjà déclarés continuent à
  bénéficier des vérifications de parcours et des empreintes R15.
- Après export, **aucun lien symbolique (même interne)** et aucun fichier
  spécial n'est accepté dans un bundle Player : le déplacement du répertoire
  ne peut pas modifier la cible d'un lien. Les liens *internes* d'un runtime
  PyInstaller d'entrée restent autorisés, mais sont matérialisés par la copie
  avant la publication.
- Le manifest doit référencer `game/<nom>.json` **et**
  `game/<nom>.game.json`, ainsi qu'un `Player/DrawTempPlayer[.exe]` indexé.
  Ceci empêche un package qui omet le GameProject de paraître intègre.
- Une sortie existante, y compris un lien symbolique cassé, n'est **jamais**
  écrasée. Le staging et la publication atomique R15 sont conservés.
- Les formats de manifest R15 schema 1 déjà valides restent lisibles.

## Preuves automatisées (pas des signatures)

Pour chaque OS, la CI `drawtemp5-r15.yml` produit
`r23-native-<OS>/r23-native.json` en vérifiant **les vrais octets**
du manifest et de tous les fichiers indexés. Le rapport indique
`revision` (SHA complet), `platform`, `manifest_sha256`, nombre de
fichiers, avertissements de licences, et laisse explicitement
`smoke` / `clean_machine` / `signing` à `not-asserted`.

Une tâche d'agrégation distincte rejette :

- une preuve d'OS absente ou en doublon ;
- une preuve issue d'un SHA différent ;
- un digest malformé ou un dossier incomplet ;
- toute revendication externe non attestée (signature, machine propre).

Les trois matrices d'intégrité conformes donnent un fichier
`r23-release-ledger.json`, contenant les 12 gates R23 et la décision
**`NO-GO`**. Les gates R23.2 et R23.11 sont `partial`, pas `pass`.
Le fichier n'est **pas un certificat de droits**, un rapport GPU réel, ni
une preuve d'installation native finale.

## Exécution locale

```bash
python -m unittest tests_standalone.test_drawtemp5_r15 tests_standalone.test_drawtemp5_r23a tests_standalone.test_drawtemp5_r23_evidence -v

# Après export natif R15 sur un runner Windows/Linux/macOS
python scripts/r23_release_gate.py native \
  --bundle export/Jeanne \
  --platform Linux \
  --revision $(git rev-parse HEAD) \
  --report r23-native.json

# Après collecte des trois rapports, un par sous-répertoire
python scripts/r23_release_gate.py aggregate \
  --directory r23-evidence \
  --revision $(git rev-parse HEAD) \
  --report r23-release-ledger.json
```

La mesure, la certification et la signature finale doivent être faites sur
les **véritables artefacts**. Un faux runtime de test ne certifie rien.

## Poursuite : R23.A puis R23.B

| ID | Couverture de cette PR | Éléments restant à prouver |
| --- | --- | --- |
| R23.1 | Aucun installateur ajouté | Packaging Windows/macOS/Linux, install/uninstall clean VM, signatures |
| R23.2 | Intégrité bundle et contrat GameProject renforcés | Install et exécution offline sur PC propre |
| R23.3 | Sauvegardes historiques inchangées | Corruption, sauvegarde/récupération et migrations réelles |
| R23.4 | Manifests ambigus, symlinks et fichiers spéciaux bloqués | ZIP bombs, imports ressources externes, fuzz malveillant |
| R23.5 | Aucun budget GPU déduit du CI | Mesures sur GPU physique, scénarios et percentiles |
| R23.6 | Aucune endurance revendiquée | Sessions longues et crash injection |
| R23.7 | Aucun test a11y revendiqué | Audit clavier, lisibilité, contrastes et remapping |
| R23.8 | Aucun playtest externe revendiqué | Tests créateurs/joueurs et retests |
| R23.9 | Guide et commandes fournis | Tutoriels utilisateur complets |
| R23.10 | Avertissements licences remontés sans les blanchir | Preuves légales/attributions approuvées |
| R23.11 | Matrice intégrité OS et SHA commun | Reproductibilité, signatures, provenance des installateurs |
| R23.12 | Registre fail-closed NO-GO généré | Go/no-go indépendant après preuves et décisions signées |

**Règle de fusion :** une CI verte signifie seulement que les contrats
automatisables de cette tranche ont été vérifiés, pas que la release 5.5 est
certifiée. Ne pas forcer `certified=true` à partir de smokes offscreen.
