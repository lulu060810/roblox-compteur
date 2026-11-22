# Teaser UNITED GAMES × NOKSO (19 s, 9:16, 4K 60 fps)

Vidéo finale : `united-games-x-nokso-teaser.mp4` (2160×3840, 60 fps, H.264 + AAC).

- `scene.html` — l'animation complète (canvas, déterministe : `render(t)` pour t ∈ [0, 19]).
  Ouvrir dans un navigateur pour un aperçu en boucle ; `?res=0.5` pour un aperçu léger, `?t=7.9` pour figer une image.
- `sound.py` — sound design procédural (basses, impacts, whooshes, risers, pulsations), synchronisé à l'image.
- `render.js` — rendu image par image avec Playwright → segments MP4 via ffmpeg.
- `assets/` — logos détourés (transparence) et piste audio.

Reconstruire :

```bash
python3 sound.py assets/sound.wav
node render.js out 4 2 60 19       # 4 workers, résolution x2 (4K), 60 fps, 19 s
printf "file 'out/seg%d.mp4'\n" 0 1 2 3 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -i assets/sound.wav -c:v copy -c:a aac -b:a 320k -shortest united-games-x-nokso-teaser.mp4
```

Découpage : 0–5 s intro (lignes lumineuses rouge/bleue, anneaux 3D sur les basses, flash) ·
5–8,5 s révélation des logos en 3D + impact du « × » · 8,5–14 s orbites lumineuses + textes ·
14–19 s écran final (crédits, « BIENTÔT… ») et impulsion finale.
