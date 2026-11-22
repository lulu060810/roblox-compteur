# Teaser UNITED GAMES × NOKSO (10 s, 9:16, 4K 60 fps)

Vidéo finale : `united-games-x-nokso-teaser.mp4` (2160×3840, 60 fps, H.264 + AAC).

- `scene.html` — l'animation complète (canvas, déterministe : `render(t)` pour t ∈ [0, 10]).
  Ouvrir dans un navigateur pour un aperçu en boucle ; `?res=0.5` pour un aperçu léger, `?t=3.4` pour figer une image.
- `sound.py` — sound design procédural (basses, impacts, whooshes, risers, pulsations), synchronisé à l'image.
- `render.js` — rendu image par image avec Playwright → segments MP4 via ffmpeg.
- `assets/` — logos détourés (transparence) et piste audio.

Reconstruire :

```bash
python3 sound.py assets/sound.wav
node render.js out 4 2 60          # 4 workers, résolution x2 (4K), 60 fps
printf "file 'out/seg%d.mp4'\n" 0 1 2 3 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -i assets/sound.wav -c:v copy -c:a aac -b:a 320k -shortest united-games-x-nokso-teaser.mp4
```

Découpage : 0–2 s intro (lignes rouge/bleue, formes sur les basses) · 2–5 s révélation des logos + « × » ·
5–8 s orbites lumineuses + textes · 8–10 s écran final crédits + « BIENTÔT… » et impulsion finale.
