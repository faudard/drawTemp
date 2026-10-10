# Sporebound Tactics — Research Bibliography

This bibliography distinguishes theory/research, industry primary sources, and secondary mechanical documentation. It is intended to support design decisions rather than decorate them.

## Source hierarchy

When sources disagree, prefer:
1. peer-reviewed paper / academic book;
2. developer talk, postmortem or official interview;
3. official manual/documentation;
4. developer-authored project update;
5. high-quality reverse-engineered/community mechanics guide;
6. wiki/community discussion.

Community sources are useful for exact legacy mechanics but should not be treated as developer intent.

## A. Game design and systems

### Adams, Ernest; Dormans, Joris. *Game Mechanics: Advanced Game Design*. New Riders, 2012.
Use for emergence, system interaction, simulation, balancing, progression and the integration of mechanics with level design.
https://books.google.com/books/about/Game_Mechanics.html?id=moG9m2rGrTUC

Priority chapters for Sporebound:
- Emergence and Progression
- Complex Systems
- Simulating and Balancing Games
- Integrating Level Design and Mechanics
- Progression Mechanisms
- Meaningful Mechanics

### Schreiber, Ian; Romero, Brenda. *Game Balance*. CRC Press, 2021.
Use for numeric relationships, fairness, difficulty, economies and systematic balancing.
https://www.routledge.com/link/link/p/book/9781032034003

### Hunicke, Robin; LeBlanc, Marc; Zubek, Robert. "MDA: A Formal Approach to Game Design and Game Research." 2004.
Use to separate mechanics implemented by the engine from dynamics produced during play and the intended player experience.
https://www.researchgate.net/publication/228884866_MDA_A_Formal_Approach_to_Game_Design_and_Game_Research

## B. Procedural content and mixed-initiative authoring

### Shaker, Noor; Togelius, Julian; Nelson, Mark J. *Procedural Content Generation in Games*. Springer, 2016.
DOI: 10.1007/978-3-319-42716-4
https://www.pcgbook.com/

Priority chapters:
- Rules and mechanics
- Experience-driven PCG
- Mixed-initiative content creation
- Evaluating content generators

Relevance: even if Sporebound remains mostly handcrafted, the editor can become mixed-initiative: author -> validate -> simulate -> diagnose -> suggest -> author.

## C. Telemetry and analytics

### El-Nasr, Magy Seif; Drachen, Anders; Canossa, Alessandro (eds.). *Game Analytics: Maximizing the Value of Player Data*. Springer, 2013.
DOI: 10.1007/978-1-4471-4769-5
https://link.springer.com/book/10.1007/978-1-4471-4769-5

Use for defining telemetry, metrics, heatmaps, behavioral analysis and data-driven balancing.

## D. Game AI

### Rabin, Steve (ed.). *Game AI Pro* series and Online Edition.
The site legally hosts individual chapters.
https://www.gameaipro.com/

Priority readings:
- David "Rez" Graham, "An Introduction to Utility Theory"
- Kevin Dill, "Dual-Utility Reasoning"
- Matthew Jack, "Tactical Position Selection: An Architecture and Query Language"
- Dave Mark, "Modular Tactical Influence Maps"
- Matthias Siemonsmeier, "Gearing the Tactics Genre: Simultaneous AI Actions in Gears Tactics"
- Automated AI Testing (Online Edition 2021)

### Browne, Cameron B. et al. "A Survey of Monte Carlo Tree Search Methods." IEEE TCIAIG 4(1), 2012, pp. 1–43.
DOI: 10.1109/TCIAIG.2012.2186810
https://research.monash.edu/en/publications/a-survey-of-monte-carlo-tree-search-methods/

Use as a reference for later search-based AI evaluation, not as an assumption that MCTS is the right production architecture.

## E. Primary tactical-RPG / tactics sources

### Nintendo — Triangle Strategy developer interview
Useful for elevation, placement, knockback, traps and giving characters tactical identity through map structure.
https://www.nintendo.com/en-ca/whatsnew/get-insight-and-tips-for-triangle-strategy-from-the-devs-themselves/

### Nintendo — Triangle Strategy tactical guidance
Useful as evidence for player-facing presentation of height, rear attacks, follow-ups and terrain interactions.
https://www.nintendo.com/en-gb/News/2022/March/Ten-tactical-tips-for-TRIANGLE-STRATEGY--2181496.html

### Nintendo / Intelligent Systems — Fire Emblem Engage, Ask the Developer Vol. 8 Part 3
Key source for the design tension between spectacular mobility and preserving stage tactics.
https://www.nintendo.com/us/whatsnew/ask-the-developer-vol-8-fire-emblem-engage-part-3/

### Subset Games — Into the Breach, Road to the IGF
Key source for telegraphed intent, reduced randomness, readable failure and displacement-focused weapon design.
https://www.gamedeveloper.com/game-platforms/road-to-the-igf-subset-games-i-into-the-breach-i-

### Matthew Davis / Subset Games — Into the Breach Design Postmortem, GDC 2019
Key source for iteration, cuts, RNG and balancing decisions.
https://www.gdcvault.com/play/1026333/-Into-the-Breach-Design

### Ubisoft — Mario + Rabbids Sparks of Hope, Layered Battles, GDC 2023
Key source for topography/navigation/cover/zoning layers, spawn rules, objectives, enemy archetypes and encounter intention.
https://news.ubisoft.com/en-gb/article/3NxX4lLLU7pkebcFDaoOen/gdc-2023-how-mario-rabbids-sparks-of-hope-improved-procedural-generation-with-layered-battles

### Square Enix — Tactics Ogre: Reborn overview
Useful for class/equipment/magic combination and unit-level progression.
https://amp.square-enix-games.com/en_US/news/tactics-ogre-reborn-preview

### 6 Eyes Studio — Fell Seal project update
Developer-authored description of class active/passive/counter structure and gradual unlocks.
https://fellseal.backerkit.com/hosted_preorders/project_updates?page=9

## F. Secondary/reverse-engineered mechanics sources

### Final Fantasy Tactics Battle Mechanics Handbook
A long-running community reverse-engineering reference. Use for factual legacy mechanics, not authorial intent.
https://www.neoseeker.com/finalfantasytactics/faqs/26855-final-fantasy-tactics-battle-mechanics.html

It documents:
- CT >= 100 activation;
- CT gain from Speed;
- Move+Act / single action / Wait CT costs;
- slow actions;
- reactions.

## Research backlog

Next bibliography expansions should cover:
- progression/jobs and respec design;
- tactical level-design theory;
- difficulty without hidden AI bonuses;
- UI/UX for probabilistic tactical games;
- campaign pacing and roster attachment;
- automated balancing/search;
- accessible presentation of complex tactical information.


## G. Team tactics, reactions and relationship systems

### Firaxis / 2K — XCOM 2: War of the Chosen manual and Soldier Bonds
Primary source for pair progression translated into tactical benefits. The manual documents Teamwork, Spotter, Stand By Me, Advanced Teamwork and Dual Strike, while the expansion documentation frames bonds as relationships that develop through joint deployment.

https://assets.2k.com/1a6ngf98576c/6LIsXornIgRpO5WnGoU1oS/d99b534548498ac045f80e5888d2c3f3/XCOM2_WOTC_ONLINE_MANUAL_SHEET_ENG.pdf
https://newsroom.2k.com/news/xcomr-2-war-of-the-chosen-expansion-available-now

### Firaxis — "Breathing More Layers into XCOM 2: War of the Chosen"
Useful production lesson: establish a small working core for a new strategic/tactical system, then add complexity after iteration and playtesting.

https://xcom.com/news/breathing-more-layers-and-life-into-xcom-2-war-of-the-chosen/amp

### Chrono Trigger — 1995 developer interviews
Primary historical interview describing Double/Triple Techs as coordinated character actions developed to make characters visibly work together.

https://shmuplations.com/chronotrigger2/

### Craig Stern — "12 ways to improve turn-based RPG combat systems"
Secondary design essay describing counterattacks, opportunity attacks and reaction fire as delayed attacks that increase the tactical value of action reserves, movement and positioning.

https://www.gamedeveloper.com/design/12-ways-to-improve-turn-based-rpg-combat-systems
