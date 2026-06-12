# Airport Manager Simulator

**Airport Manager Simulator** est une simulation de gestion d'un petit aéroport en temps réel, développée en **Python avec Pygame**.

Le joueur observe et gère le parcours des passagers depuis leur arrivée dans l'aéroport jusqu'à leur embarquement dans l'avion. Le but est de faire embarquer un maximum de passagers avant le départ du vol, tout en évitant les retards et en optimisant le flux dans l'aéroport.

---

## Objectif du projet

Le projet a été conçu autour de trois notions principales :

- **Machines à états** : chaque passager suit un comportement défini par des états successifs.
- **Cartes de distance** : les déplacements sont guidés par des cartes de distance sur une grille.
- **Affichage temps réel avec Pygame** : la simulation est visible en direct dans une fenêtre graphique.

Le projet respecte donc une architecture simple, lisible et adaptée à un projet scolaire.

---

## Principe du jeu

Les passagers apparaissent à l'entrée de l'aéroport, passent par plusieurs étapes, puis embarquent dans l'avion.

Parcours principal d'un passager :

```text
ARRIVE
→ VA_ENREGISTREMENT
→ ATTEND_ENREGISTREMENT
→ VA_SECURITE
→ ATTEND_SECURITE
→ VA_PORTE
→ ATTEND_EMBARQUEMENT
→ VA_EMBARQUER
→ EMBARQUEMENT
→ TERMINE
```

Le passager doit donc :

1. arriver dans l'aéroport ;
2. aller au check-in ;
3. attendre et être servi au check-in ;
4. aller à la sécurité ;
5. attendre et être contrôlé ;
6. aller au lounge ;
7. attendre l'embarquement ;
8. embarquer dans l'avion.

---

## Fonctionnalités principales

### 1. Déplacement automatique

Les passagers se déplacent seuls grâce à des **cartes de distance**.

Le principe est simple :

- une carte de distance est générée vers une cible ;
- le passager regarde les cases autour de lui ;
- il choisit la case ayant la plus petite distance ;
- il avance progressivement vers son objectif.

Le projet n'utilise pas A*. Il reste volontairement sur un système simple de cartes de distance.

---

### 2. Machine à états des passagers

Chaque passager possède un état courant.

Exemples :

- `VA_ENREGISTREMENT` : le passager marche vers le check-in ;
- `ATTEND_ENREGISTREMENT` : il attend au check-in ;
- `VA_SECURITE` : il marche vers la sécurité ;
- `ATTEND_SECURITE` : il attend à la sécurité ;
- `ATTEND_EMBARQUEMENT` : il attend dans le lounge ;
- `EMBARQUEMENT` : il monte dans l'avion ;
- `TERMINE` : il a fini son parcours.

Les états de déplacement font bouger le passager.  
Les états d'attente le gardent fixe.

---

### 3. Check-in et sécurité avec plusieurs places

Le check-in et la sécurité peuvent gérer plusieurs passagers.

Dans la carte :

```text
C = check-in
X = sécurité
```

Chaque zone peut accueillir plusieurs passagers avec des positions visuelles différentes pour éviter qu'ils se superposent.

---

### 4. Lounge normal et lounge VIP

Les passagers vont ensuite dans le lounge.

Dans la carte :

```text
S = lounge normal
V = lounge VIP
```

Les passagers VIP sont affichés en violet et vont dans une zone dédiée.

---

### 5. Priorité VIP à l'embarquement

Quand l'embarquement commence :

1. les VIP embarquent en premier ;
2. ils avancent deux par deux ;
3. les passagers normaux restent bloqués au lounge ;
4. les passagers normaux commencent seulement quand tous les VIP sont dans l'avion.

---

### 6. Zone commerce dynamique

Le projet contient aussi une extension d'IA comportementale.

Si le check-in ou la sécurité est saturé, un passager peut aller temporairement au commerce.

Dans la carte :

```text
B = boutique / commerce
K = café, si utilisé
```

États ajoutés :

```text
VA_COMMERCE
ATTEND_COMMERCE
RETOUR_CHECKIN
RETOUR_SECURITE
```

Comportement :

- si le check-in est saturé, le passager peut aller au commerce ;
- il attend quelques secondes ;
- il revient ensuite au check-in ;
- même principe pour la sécurité ;
- si le départ approche, il ne va plus au commerce et reprend le parcours principal.

---

### 7. Système de score

Le score récompense maintenant la progression du passager dans l'aéroport.

Barème :

```text
Check-in terminé              +5 points
Sécurité terminée             +8 points
Arrivée au lounge             +5 points
Passager normal embarqué      +30 points
VIP embarqué                  +45 points
Passager normal raté          -10 points
VIP raté                      -20 points
```

Bonus final :

```text
100% des passagers embarqués  +200 points
80% ou plus                   +100 points
60% ou plus                   +50 points
```

Ce système évite les scores trop négatifs et récompense mieux la bonne gestion du flux.

---

## Légende de la carte

```text
M = mur
W = entrée / spawn des passagers
C = check-in
X = sécurité
S = lounge normal
V = lounge VIP
B = commerce / boutique
K = café, si présent
G = porte d'embarquement
A = avion
```

---

## Installation

### 1. Cloner ou télécharger le projet

Téléchargez le dossier du projet puis placez-vous dans le dossier principal :

```bash
cd Airport-Manager-Simulator-main
```

### 2. Créer un environnement virtuel, optionnel mais recommandé

```bash
python -m venv .venv
```

Activation sous Windows :

```bash
.venv\Scripts\activate
```

Activation sous macOS / Linux :

```bash
source .venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## Lancer le jeu

Depuis le dossier du projet :

```bash
python main.py
```

---

## Contrôles

```text
Espace  = pause / reprise
Échap   = quitter
Croix   = fermer la fenêtre
```

---

## Structure du projet

```text
Airport-Manager-Simulator-main/
│
├── main.py              # Point d'entrée du jeu et carte principale
├── game_engine.py       # Logique principale, états, score, embarquement
├── entities.py          # Passagers, avion, zones de service
├── map_manager.py       # Carte, parsing, cartes de distance
├── ui.py                # Affichage Pygame
├── events.py            # Bus d'événements simple
├── requirements.txt     # Dépendances Python
└── README.md            # Documentation du projet
```

---

## Déroulement d'une partie

1. Les passagers apparaissent à l'entrée.
2. Ils sont dirigés vers les check-ins.
3. Ils attendent et sont servis.
4. Ils vont à la sécurité.
5. Ils attendent et passent le contrôle.
6. Si une zone est saturée, certains peuvent faire un détour par le commerce.
7. Ils rejoignent ensuite le lounge.
8. Quand l'avion ouvre l'embarquement, les VIP passent d'abord.
9. Les passagers normaux embarquent ensuite.
10. À la fin, le score est calculé avec les passagers embarqués, ratés et le bonus final.

---

## Points techniques importants

### Machines à états

Le comportement des passagers est contrôlé par une FSM.  
Cela permet d'avoir un parcours clair et contrôlé.

### Cartes de distance

Les déplacements utilisent des cartes de distance précalculées ou générées vers une cible.  
Le passager suit toujours la case voisine ayant la meilleure distance.

### Gestion des files

Les zones comme le check-in et la sécurité possèdent des slots.  
Un passager peut réserver un slot, s'y déplacer, puis démarrer son service uniquement lorsqu'il arrive réellement.

### Priorité VIP

La priorité VIP est gérée au moment de l'embarquement.  
Les passagers normaux ne peuvent pas embarquer tant qu'il reste un VIP non terminé.

---

## Améliorations possibles

Quelques idées d'amélioration :

- ajouter des jauges de patience visibles ;
- ajouter plus de types de passagers ;
- ajouter des événements aléatoires ;
- permettre au joueur de construire ou déplacer les zones ;
- ajouter des niveaux de difficulté ;
- améliorer l'interface graphique ;
- ajouter un menu de lancement.

---

## Résumé

Airport Manager Simulator est une simulation simple mais complète qui montre :

- une machine à états ;
- du pathfinding par cartes de distance ;
- une simulation temps réel avec Pygame ;
- une gestion de files ;
- une priorité VIP ;
- une IA comportementale dynamique avec commerce ;
- un système de score progressif.
