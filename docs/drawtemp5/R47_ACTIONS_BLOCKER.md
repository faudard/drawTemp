# Incident et récupération CI R47 (2026-10-19)

## État vérifié (SHA de la PR #384)

Les workflows GitHub Actions R47.A, R47.B, R47.C échouent au démarrage avec 0 job selon l'API GitHub. Des workflows d'autres lots et branches présentent exactement ce symptôme ; leur résultat ne dit **rien** sur la réussite ou l'échec des tests Python.

Le 19 octobre 2026, GitHub Status a déclaré un incident GitHub Actions/Pages/Webhooks de **15:49 à 16:56 UTC**, résolu ; certaines exécutions sans job observées sur DrawTemp ont encore lieu après 16:56. **L'incident historique ne démontre donc pas que la panne persistante du dépôt a la même cause.**

- Statut officiel : https://www.githubstatus.com/
- Derniers runs observés : https://github.com/faudard/drawTemp/actions
- Dernière PR R47 : https://github.com/faudard/drawTemp/pull/384

## Vérifications à effectuer avec les droits propriétaire GitHub

1. Ouvrir **Settings → Billing and licensing → Usage / Budgets** (selon l'interface du compte). Examiner crédits/minutes Actions et blocages budgétaires ; ne pas supposer un blocage de facturation sans la donnée du compte.
2. Ouvrir **Settings → Actions → General** du dépôt et vérifier que les workflows GitHub Actions sont autorisés et que les règles de l'organisation n'interdisent pas les runners/actions.
3. Ouvrir un run sans job et ses annotations de démarrage ; si l'interface fournit un diagnostic sur budget/permissions/incident, le conserver.
4. Corriger **la cause exacte**, puis relancer uniquement les trois workflows R47 depuis leur action « Re-run jobs / Re-run all jobs » ou un push ciblé après corrections. Vérifier le SHA exécuté.
5. Examiner les trois matrices Linux/Windows/macOS et archiver les logs ; ne certifier aucun gate sur un run sans job.

## Limiter le fanout

Les trois workflows R47 ont désormais une `concurrency` par PR/branche avec `cancel-in-progress`. Cela évite d'empiler plusieurs versions **d'un même workflow R47** ; cela ne résout ni un problème de budget ni l'exécution de centaines d'autres workflows du dépôt sans filtres de chemins. La révision des autres workflows exige un chantier CI global distinct.

## Validation technique locale / post-déblocage

~~~bash
python -m pip install .
python -m unittest tests_standalone.test_drawtemp_r47a_modding tests_standalone.test_drawtemp_r47c_two_games -v
python -m drawtemp.sdk.migration --verify-baseline docs/drawtemp5/reference-baseline.json
python -m pip install ".[qt6]"
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r47b_qt -v
~~~

Sur Windows PowerShell : `$env:QT_QPA_PLATFORM='offscreen'` avant l'appel Python.

Le **gate R47 reste NO-GO** sans les résultats de tests vrais, tests onscreen, runtime Player natif, essais clean machine et droit de redistribution des assets vérifié.
