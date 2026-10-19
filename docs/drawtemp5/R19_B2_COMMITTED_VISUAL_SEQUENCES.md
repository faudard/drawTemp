# R19.B2 — Synchronisation des poses R7 et des événements R12

**Statut : implémentation candidate, non approuvée artistiquement.**
Cette tranche se base sur R19.B1 (#309), elle-même dépendante de R19.A (#301).
Elle ne modifie ni le moteur CT, ni les événements, ni les sauvegardes, ni le replay.

## Contrat

- Le journal R1/R12 reste l'unique source d'événements : AnimationDirector produit des clips bornés et invalidés par serial à chaque action, chargement ou transition.
- Le Player consomme les clips dans l'ordre réel des événements. Une attaque n'entraîne une pose d'impact que si un événement de dégâts existe dans le journal. Miss, heal et interruption continuent à être rendus comme effets, sans inventer d'action supplémentaire.
- Le nouveau sélecteur headless partagé visual_clip_frames.clip_art_frame lit les ressources R7 via CharacterPack.sample. Il utilise la tenue effective issue de R8 (avec prévisualisation explicite), le vrai facing de l'acteur et le chrono visuel normalisé.
- Les actions disponibles : move → walk, attack → attack, cast → magic, impact → hit, et block lorsqu'il est explicitement demandé par une source de présentation. Aucune course automatique inventée depuis un simple move.
- Pour les projets sans pack R7, l'existant R4 PresentationAssets continue à rendre move / attack / hit ; les actions absentes n'inventent pas de sprites.
- Aucun miroir fictif : le changement de direction dépend du delta source/target ou du facing courant, notamment pour hit et cast sur place.
- Studio et Player utilisent le même RendererController.visualClipFrame; le TacticalBoard QML fait seulement avancer la phase visuelle et masque le sprite statique quand le remplacement est réellement affiché.

## Éviter les doubles personnages

Le TacticalBoard expose un seul acteur de substitution temporaire, jamais une seconde unité de simulation. La liste concealedActorIds est désormais liée à la visibilité de cette substitution au lieu d'être écrite par différentes branches impératives. Sans pose disponible pour cast/impact/block, l'acteur canonique reste visible.

Le système R12 existant est conservé : chargement, nouvelle scène, action annulée ou serial différent interrompent les animations en cours. Une animation qui finit restitue la visibilité du personnage sans créer de nouveau tick tactique.

## Vérifications

~~~sh
python -m unittest tests_standalone.test_drawtemp5_r19b2_visual_clips -v
python -m unittest tests_standalone.test_drawtemp5_r12_animation -v
# PySide6 + Pillow requis pour le test Qt ; sur Linux :
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r19b2_qt -v
~~~

Les tests couvrent le sens de déplacement, les attaques, l'impact, la magie, le retour au rendu canonique, la compatibilité R4, les durées R7 et la pureté du journal. La CI peut vérifier la mécanique du renderer en offscreen, pas l'esthétique ou le GPU réel.

## Limites

- Les nouvelles poses R19.B1 sont encore des prototypes dérivés, pas des dessins originaux approuvés frame par frame.
- run, victory et death possèdent un pack candidat mais ne sont pas déclenchés artificiellement par un événement absent ; le rendu dead/idle existant continue à fonctionner.
- Les assets de production et les droits de distribution restent soumis aux gates INT-03 et R15 : aucun résultat de ce lot n'accorde une licence.
- Pas de certification de FPS ni de goldens approuvés. Revue sur Windows/Linux/macOS, GPU réel, DPR 1x/2x et profils de scène R19.D à réaliser.

**Prochain lot R19.B3 :** production du bestiaire à quatre directions vérifiées et revue des huit rôles (loup, bandit, archer, lancier, chevalier, soigneur, officier, boss) sans vue unique déguisée en quatre directions.
