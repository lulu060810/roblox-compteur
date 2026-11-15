#!/bin/bash
# Montage final : images rendues + bloom + grain + textes + son -> MP4 H.264 1080x1920 30 i/s
set -e
S=${1:?dossier de travail}; OUT=${2:?fichier mp4}
ffmpeg -y -loglevel error -stats \
  -framerate 30 -i "$S/frames/f_%04d.png" \
  -framerate 30 -i "$S/overlay/o_%04d.png" \
  -i "$S/audio.wav" \
  -filter_complex "\
[0:v]format=gbrp,tpad=stop_mode=add:stop_duration=4:color=black,split[a][b];\
[b]colorlevels=rimin=0.45:gimin=0.45:bimin=0.45,gblur=sigma=28,split[g1][g2];\
[g2]gblur=sigma=90[g3];[g1][g3]blend=all_mode=addition:all_opacity=0.7[glow];\
[a][glow]blend=all_mode=screen:all_opacity=0.55,noise=alls=7:allf=t+u,format=rgba[base];\
[base][1:v]overlay=format=auto,trim=duration=18,format=yuv420p[v];\
[2:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[au]" \
  -map "[v]" -map "[au]" -c:v libx264 -preset slow -crf 16 -profile:v high -pix_fmt yuv420p \
  -r 30 -g 60 -c:a aac -b:a 192k -t 18 -movflags +faststart "$OUT"
