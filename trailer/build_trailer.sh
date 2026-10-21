#!/usr/bin/env bash
# Monte le trailer MINE TO GET RICH (30 s, 16:9, 60 i/s) à partir des rushes du jeu.
#
#   ./build_trailer.sh            -> build/MINE_TO_GET_RICH_trailer_4K.mp4 (3840x2160)
#   ./build_trailer.sh --preview  -> build/MINE_TO_GET_RICH_trailer_preview.mp4 (1280x720, 30 i/s)
#   MUSIC=ma_musique.wav ./build_trailer.sh   -> remplace la bande-son générée
#
# Dépendances : ffmpeg, python3, Pillow, numpy.
set -euo pipefail
cd "$(dirname "$0")"

A=assets/footage/aerien.mov      # caméra qui s'élève au-dessus de la mine
B=assets/footage/sol.mov         # travelling au ras du sol vers l'arène
AERIAL=assets/vue_aerienne.png   # vue du dessus de l'arène
ARENA=assets/arene.png           # falaises bleues, arbres, nuages
LOGO=assets/logo.png             # image officielle, jamais modifiée

if [[ "${1:-}" == "--preview" ]]; then
  W=1280; H=720; FPS=30; PRESET=veryfast; CRF=20; FIN=--preview; OUT=build/MINE_TO_GET_RICH_trailer_preview.mp4
else
  W=3840; H=2160; FPS=60; PRESET=slow; CRF=14; FIN=; OUT=build/MINE_TO_GET_RICH_trailer_4K.mp4
fi
T=build/tmp
mkdir -p "$T"

ENC=(-an -c:v libx264 -preset "$PRESET" -crf "$CRF" -pix_fmt yuv420p -r "$FPS")
# Retire le ViewCube de Studio (coin haut droit), remplit le 16:9, étalonnage léger.
FOOT="crop=iw*0.92:ih*0.92:0:ih*0.08,scale=${W}:${H}:force_original_aspect_ratio=increase:flags=lanczos,crop=${W}:${H},setsar=1"
GRADE="eq=contrast=1.06:saturation=1.2:gamma=0.98,unsharp=5:5:0.6,vignette=PI/5"
FLASH="fade=t=in:st=0:d=0.12:color=0xCFF8FF"   # éclat lumineux bref sur les coupes rythmées

# footage <sortie> <source> <début> <fin> <durée finale> <filtres en plus> [filtres avant agrandissement]
footage() {
  local out=$1 src=$2 ss=$3 to=$4 dur=$5 extra=$6 pre=${7:-}
  local speed; speed=$(python3 -c "print(($to-$ss)/$dur)")
  ffmpeg -loglevel error -y -ss "$ss" -to "$to" -i "$src" \
    -vf "${pre}${FOOT},setpts=(PTS-STARTPTS)/${speed},fps=${FPS},trim=duration=${dur},${extra}${GRADE}" \
    "${ENC[@]}" "$T/$out.mp4"
}

# still <sortie> <image> <durée> <filtres de mouvement (z = progression 0->1)>
still() {
  local out=$1 img=$2 dur=$3 motion=$4
  ffmpeg -loglevel error -y -loop 1 -framerate "$FPS" -t "$dur" -i "$img" \
    -vf "scale=-2:$((H * 3 / 2)):flags=lanczos,${motion},setsar=1,${GRADE},${FLASH}" \
    "${ENC[@]}" "$T/$out.mp4"
}

echo "1/4 Plans du jeu"
# 0-5 s   INTRO : le plan aérien joué à l'envers -> descente depuis le ciel et les nuages.
footage s01 "$A" 2.6 7.4 5.0 "fade=t=in:st=0:d=1.4," "reverse,"
# 5-11 s  DÉCOUVERTE : travelling au-dessus de la mine jusqu'aux bâtiments de l'arène.
footage s02 "$B" 0.0 9.6 6.0 "fade=t=in:st=0:d=0.25:color=0xCFF8FF,"
# 11-19 s MONTÉE EN PUISSANCE : 5 plans calés sur les temps (120 BPM, 1 temps = 0,5 s).
#   vue aérienne de toute la carte (léger dézoom)
still s03 "$AERIAL" 1.5 "scale=w='iw*(1.25-0.15*t/1.5)':h=-2:eval=frame,crop=${W}:${H}"
#   travelling rapide au ras du sol
footage s04 "$B" 0.0 4.5 1.5 "${FLASH},"
#   rotation autour de l'arène centrale
still s05 "$AERIAL" 1.5 "scale=w='iw*1.35':h=-2,rotate=a='-0.18+0.24*t/1.5':ow=iw:oh=ih,crop=${W}:${H}"
#   survol des falaises bleues
still s06 "$ARENA" 1.5 "crop='iw*0.8':'ih*0.8':'iw*0.2*t/1.5':'ih*0.1',scale=${W}:-2:flags=bicubic,crop=${W}:${H}"
#   gros plan sur les minerais
footage s07 "$A" 0.0 2.0 2.0 "${FLASH},scale=w='${W}*(1+0.08*t/2)':h=-2:eval=frame,crop=${W}:${H},"
# 19-21,5 s SUSPENSE : la caméra s'éloigne vite de la carte, puis noir.
footage s08 "$A" 2.6 7.4 2.5 "fade=t=out:st=2.15:d=0.35,"

echo "2/4 Séquence logo (21,5-30 s)"
python3 render_finale.py --logo "$LOGO" --background "$ARENA" --out "$T/s09.mp4" $FIN

echo "3/4 Bande-son"
if [[ -n "${MUSIC:-}" ]]; then
  ffmpeg -loglevel error -y -i "$MUSIC" -t 30 -ar 48000 -ac 2 "$T/audio.wav"
else
  python3 make_audio.py "$T/audio.wav"
fi

echo "4/4 Assemblage"
: > "$T/list.txt"
for s in s01 s02 s03 s04 s05 s06 s07 s08 s09; do echo "file '$s.mp4'" >> "$T/list.txt"; done
ffmpeg -loglevel error -y -f concat -safe 0 -i "$T/list.txt" -i "$T/audio.wav" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -t 30 -movflags +faststart "$OUT"
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of compact "$OUT"
echo "OK -> $OUT"
