# Kit IA — Teaser GTA VI (Runway Gen-4 / Kling)

## Principe (important)
Les générateurs vidéo IA déforment le texte et les logos. Il faut donc :
1. Générer le mouvement sur l'image **sans textes** : `plate_sans_textes_sans_logo.png`.
2. Remettre les textes et le logo par-dessus au montage, à partir des PNG transparents de `layers/` : `title.png`, `logo_gta6.png`, `phrase.png` et `emoji.png`.
3. Ajouter la piste `sfx.wav` (effets sonores uniquement).

Réglages : image vers vidéo, format 9:16, 1080p, durée 5 s par plan (ou 10 s), mouvement modéré.

## Plan 1 (0–5 s) : découverte de Vice City
Image de départ : `plate_sans_textes_sans_logo.png`

```
Cinematic slow dolly-in toward the neon city skyline at sunset. The helicopter flies slowly
from left to right across the sky, main rotor and tail rotor spinning fast with motion blur.
The pink speedboat speeds to the right across the bay, cutting white foam and a spray wake,
waves spreading behind it. Palm leaves sway in a warm breeze. Clouds drift slowly.
City windows and neon signs flicker and twinkle, reflections shimmer on the water.
The two characters in the foreground stay still, only subtle breathing. Stylised
illustrated look, vibrant magenta/orange/purple palette, 2.5D parallax depth.
```

## Plan 2 (5–10 s) : mise en valeur du logo
Image de départ : la dernière image du plan 1 (ou la même plate).

```
Slow cinematic crane up and push-in toward the sky in the upper centre of the frame, where the
title logo will be placed. Sunset light rays and lens flare sweep across the sky. The helicopter
continues slowly to the right with its searchlight on. A jet plane with contrails crosses far
away. Gentle palm sway, shimmering water, twinkling city lights. Characters stay static.
```

## Plan 3 (10–15 s) : chute humoristique
```
Slow pull-back revealing the whole scene, very subtle camera drift, characters looking at the
camera, boat continues on the water, palms swaying, neon flicker. Calm, steady final shot.
```

## Prompt négatif (Kling) / à éviter
```
text, letters, logo, watermark, face distortion, morphing faces, extra fingers, warped body,
melting, flicker artifacts, camera shake, fast cuts, style change, photorealistic
```

## Montage final (après génération)
Mets les 3 clips bout à bout (`clip1.mp4`, `clip2.mp4`, `clip3.mp4`) puis superpose les textes avec FFmpeg :

```bash
ffmpeg -i clip1.mp4 -i clip2.mp4 -i clip3.mp4 \
  -loop 1 -i layers/title.png -loop 1 -i layers/logo_gta6.png \
  -loop 1 -i layers/phrase.png -loop 1 -i layers/emoji.png -i sfx.wav \
  -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0,scale=1080:1920,fps=60[bg]; \
   [3:v]scale=1080:1920,format=rgba,fade=in:st=5.5:d=0.6:alpha=1[t]; \
   [4:v]scale=1080:1920,format=rgba[l]; \
   [5:v]scale=1080:1920,format=rgba,fade=in:st=10:d=0.4:alpha=1[p]; \
   [6:v]scale=1080:1920,format=rgba,fade=in:st=11.1:d=0.3:alpha=1[e]; \
   [bg][l]overlay=shortest=1[a];[a][t]overlay[b];[b][p]overlay[c];[c][e]overlay,format=yuv420p[v]" \
  -map "[v]" -map 7:a -t 15 -c:v libx264 -crf 16 -preset slow -c:a aac -b:a 256k -movflags +faststart \
  GTA6_TIKTOK_TEASER_IA.mp4
```

Le logo reste alors net et identique à l'original, puisqu'il n'est jamais passé par l'IA.
