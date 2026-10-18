# Montage vidéo « Boîte manuelle » (9:16)

- `edl.py` : timeline (clips source, transcription vérifiée, ancres mot par mot)
- `build.py` : cadrage/punch-ins, étalonnage, motion design, sous-titres, mixage, export H.264/AAC
- `synth_audio.py` : musique et SFX 100 % générés (libres de droits)
- `timeline.json` : timecodes source → sortie de chaque mot

Rendu : `python3 build.py source.mov dossier_travail final.mp4`
(dépendances : ffmpeg avec libx264, numpy, pillow, police Inter)
