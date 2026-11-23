# Teaser Noël UNITED GAMES : storyboard et production

**Vidéo finale :** `out/united_games_teaser_noel.mp4`, 1080 × 1920 (9:16), 30 fps, 18 s, H.264, **sans piste audio**.
**Regénérer :** `python3 render_teaser.py` (aperçus : `python3 render_teaser.py --preview 2.2 14.8`).
Tous les effets (glace, fissures, éclats, neige, bonnet, textes) sont générés par le script à partir de `assets/reference.png` (décor) et `assets/logo.png` (logo officiel, non modifié).

| Temps | Scène | Ce qu'on voit |
|---|---|---|
| 0,0 – 1,95 s | 🧊 Glaçon | Bloc de glace plein écran (reflets bleutés, givre sur les bords, bulles). Impact central : les fissures se propagent en 3 « coups » avec secousse de caméra. Accroche dès la 1re image. |
| 1,95 – 3,2 s | 💥 Éclatement | Flash blanc-bleu, ~80 éclats projetés vers la caméra (rotation, agrandissement, gravité) et poussière de glace. Révélation du décor. |
| 3,2 – 7,0 s | 🎁 Cadeaux | Neige, guirlande dorée, cadeau rouge, logo **très flou**. Texte en pop décalé : **PLEIN DE / CADEAUX** (rouge, contour blanc) **/ POUR VOUS ! 🎁**. À 4,35 s, en petit dessous : *Normalement… ce n'est pas sûr ! 👀* (léger balancement). |
| 7,0 – 12,0 s | ❄️ Mystère | Lumière baissée, brume hivernale, zoom lent vers le logo, toujours flou. *Quelque chose se prépare…* (7,35 s), puis *Êtes-vous prêts ? 👀* (9,85 s) : apparition par mise au point et disparition en fondu. |
| 12,0 – 17,0 s | 🎄 Révélation | Guirlande qui s'allume en cascade, plus de neige, recul de la caméra. Le logo devient net (12,0 → 13,8 s) en gardant un halo. Le bonnet tombe sur le G avec des étincelles (13,1 s). **NOËL ARRIVE** (doré) / **CHEZ UNITED GAMES 🎄** (14 s), puis *Restez connectés… 🎁* (15,3 s). |
| 17,0 – 18,0 s | ⬛ Fin | Fondu au noir. |

Zones sûres TikTok : aucun texte au-dessus de y = 450 px ni sous y = 1 500 px, ce qui laisse libres les onglets du haut et la légende du bas.

---

## Option : prompts pour un outil de vidéo IA (Runway, Kling, Sora, Veo…)

Pour une version « photoréaliste » générée par IA, découpe-la en 3 plans, puis ajoute les textes et le logo net en post-production (CapCut / After Effects). Les IA vidéo déforment les logos et l'orthographe.

**Plan 1, 3 s (image de départ : texture de glace) :**
> Vertical 9:16 extreme close-up of a massive block of clear blue ice filling the entire frame, frost crystals on the edges, trapped air bubbles, cold blue reflections. Cracks suddenly spread from the center in fast bursts, then the ice explodes into shards flying toward the camera in slow motion, revealing warm golden Christmas lights in the darkness behind. Cinematic lighting, shallow depth of field, photorealistic, no text.

**Plan 2, 9 s (image de départ : `assets/reference.png`) :**
> Vertical 9:16, dark night Christmas scene, soft snowfall, golden string lights at the top, a red gift box with a gold ribbon resting in snow, a strongly blurred white logo in the background. Slow, smooth camera push-in toward the blurred logo, light winter mist drifting, bokeh twinkles. Mysterious, cinematic, photorealistic, no text, keep the logo blurred.

**Plan 3, 6 s :**
> Same scene, the string lights brighten one by one, snowfall gets denser, the camera slowly pulls back, the background logo gradually comes into focus. Festive and elegant, warm gold highlights, cinematic, no text. End with fade to black.

**Post-production :** incruster `assets/logo.png` net (mode « Écran » ou blanc avec alpha) pour la révélation, ajouter les textes ci-dessus aux timings du tableau et exporter **sans audio**.
