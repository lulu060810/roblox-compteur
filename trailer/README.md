# MINE TO GET RICH — Trailer officiel (30 s, 16:9, 60 i/s)

Trailer monté **uniquement avec les vrais éléments du jeu** : les deux captures vidéo
Roblox Studio, les deux captures d'écran de la carte et l'image officielle du logo.
Aucune mécanique, aucun personnage, aucun texte n'a été ajouté.

## Fichiers

| Fichier | Rôle |
|---|---|
| `assets/footage/aerien.mov` | Rush : gros plan des minerais puis la caméra s'élève au-dessus de la mine |
| `assets/footage/sol.mov` | Rush : travelling au ras du sol vers les bâtiments de l'arène |
| `assets/vue_aerienne.png` | Capture : arène centrale vue du dessus |
| `assets/arene.png` | Capture : falaises bleues, arbres cubiques, nuages |
| `assets/logo.png` | Logo officiel — utilisé tel quel, jamais redessiné |
| `build_trailer.sh` | Montage complet (ffmpeg) |
| `render_finale.py` | Séquence suspense + apparition du logo (21,5 → 30 s) |
| `make_audio.py` | Bande-son temporaire générée (120 BPM, calée sur les coupes) |

## Générer la vidéo

```bash
./build_trailer.sh --preview   # 1280x720 30 i/s, ~40 s de calcul
./build_trailer.sh             # 3840x2160 60 i/s -> build/MINE_TO_GET_RICH_trailer_4K.mp4
MUSIC=musique.wav ./build_trailer.sh   # avec votre propre musique (30 s)
```

Dépendances : `ffmpeg`, `python3`, `Pillow`, `numpy`.

## Découpage (120 BPM : 1 temps = 0,5 s, chaque coupe tombe sur un temps)

| Temps | Plan | Source | Effets |
|---|---|---|---|
| 0 – 5 s | **Intro** : descente depuis le ciel et les nuages vers la carte | `aerien.mov` 2,6 → 7,4 s **à l'envers** | Ouverture au noir 1,4 s, vent |
| 5 – 11 s | **Découverte** : survol de la mine jusqu'aux bâtiments turquoise | `sol.mov` 0 → 9,6 s (×1,6) | Éclat cyan à la coupe, la musique démarre |
| 11 – 12,5 s | Vue aérienne de l'arène | `vue_aerienne.png` | Dézoom, éclat lumineux |
| 12,5 – 14 s | Travelling rapide au-dessus du sol | `sol.mov` 0 → 4,5 s (×3) | Éclat lumineux |
| 14 – 15,5 s | Rotation autour de l'arène centrale | `vue_aerienne.png` | Rotation + zoom |
| 15,5 – 17 s | Survol des falaises bleues | `arene.png` | Panoramique |
| 17 – 19 s | Gros plan sur les minerais lumineux | `aerien.mov` 0 → 2 s | Zoom avant lent |
| 19 – 21,5 s | **Suspense** : la caméra s'éloigne vite de la carte | `aerien.mov` 2,6 → 7,4 s (×1,9) | Fondu au noir, la musique se coupe net à 21,5 s |
| 21,5 – 23 s | Fond du jeu flouté et assombri, particules bleues qui convergent vers le centre | `arene.png` | Souffle inversé |
| 23 s | **Impact** | — | Flash cyan, onde de choc, tremblement de caméra, sub drop |
| 23 – 30 s | **Logo** : zoom 3D depuis la profondeur avec léger rebond puis stabilisation | `logo.png` | Halo cyan, cristaux bleus scintillants, pièces d'or qui tournent, 2 reflets lumineux sur l'image, poussière lumineuse |

Étalonnage commun : contraste +6 %, saturation +20 %, netteté, vignettage.
Le ViewCube de Studio (coin haut droit) est recadré hors champ.

## À savoir / pour aller plus loin

- **Résolution** : les rushes font 1442×836. La sortie est en 4K 60 i/s (mise à l'échelle
  Lanczos + netteté), mais pour une vraie finesse 4K, réenregistrez les rushes en plein
  écran à la plus haute résolution possible et relancez `./build_trailer.sh`.
- **Rushes Studio** : on voit encore par moments le curseur de la souris et les contours
  de sélection cyan sur certains arbres/nuages. Pour un rendu parfait : désélectionnez tout,
  masquez le curseur et l'interface (`Ctrl+Shift+F` dans Studio / mode caméra libre en jeu).
- **Océan / île vue de loin** : aucun rush ne montre l'eau turquoise ni l'île entière depuis
  les nuages, donc ce plan n'a pas été inventé. Enregistrez un survol avec la caméra libre
  (de très haut vers l'arène, puis un recul rapide) et remplacez `aerien.mov`.
- **Logo** : l'image fournie est carrée (personnage + titre + décor). Elle est affichée
  entière, sans modification. Avec un PNG détouré (fond transparent) du logo en haute
  définition, le halo épousera automatiquement la forme du logo.
- **Musique** : la bande-son incluse est une maquette générée par code. Pour la version
  publique, utilisez une musique épique sous licence (structure : intro calme 0–5 s, montée
  5–19 s à 120 BPM, coupure à 21,5 s, impact à 23 s) via `MUSIC=...`.
