"""Timeline de montage (EDL) : clips source, transcription vérifiée, ancres temporelles.

Chaque mot : (texte, ancre_source_s | None, flags)
  flags : "K" = mot-clé (jaune), "B" = retour à un nouveau groupe de sous-titres après ce mot
Les ancres viennent du modèle zipformer FR (timestamps par mot) ; les mots sans ancre
sont interpolés au prorata de leur longueur.
"""

FPS = 30

CLIPS = [
    # --- COLD OPEN / HOOK : la question, sortie de son contexte puis rejouée plus loin
    dict(id="hook", src=(66.04, 67.95), zoom=1.16, cx=590, cy=760, push=0.02,
         words=[("Qu'est-ce", 66.10, ""), ("qui", 66.40, ""), ("se", None, ""), ("passe", 66.62, "B"),
                ("quand", 66.92, ""), ("tu", 67.04, ""), ("passes", 67.16, ""), ("pas", 67.36, "KB"),
                ("les", 67.52, ""), ("vitesses ?", 67.68, "K")],
         punch=[(67.36, 0.06)]),
    # --- 01 L'EMBRAYAGE
    dict(id="c1", src=(4.20, 9.96), zoom=1.00, cx=590, cy=780, push=0.012,
         words=[("Tu", 4.30, ""), ("as", 4.48, ""), ("un", 4.56, ""), ("embrayage", 4.72, "KB"),
                ("avec", None, ""), ("cette", None, ""), ("jambe-là.", 6.10, "B"),
                ("Là,", 6.86, ""), ("tu", 7.05, ""), ("accélères", 7.20, "KB"),
                ("et", 7.84, ""), ("tu", 8.00, ""), ("relèves", 8.16, "B"),
                ("le", 8.56, ""), ("pied", 8.72, "KB"), ("sur", 9.00, ""), ("l'embrayage.", 9.16, "K")],
         punch=[(8.72, 0.07)]),
    # --- 02 MANUELLE VS AUTO
    dict(id="c2", src=(34.90, 43.14), zoom=1.12, cx=590, cy=770, push=0.010,
         words=[("En", 34.98, ""), ("fait,", None, "B"), ("la", None, ""), ("différence,", None, "KB"),
                ("c'est", None, ""), ("que", None, ""), ("c'est", None, ""), ("toi", None, "KB"),
                ("qui", None, ""), ("es", None, ""), ("obligé", None, "B"),
                ("de", 37.16, ""), ("passer", 37.24, ""), ("les", 37.56, ""), ("vitesses", 37.76, "KB"),
                ("toi-même.", 38.20, "KB"), ("C'est", 38.75, ""), ("chiant.", 38.95, "B"),
                ("Par", 39.50, ""), ("rapport", 39.68, "B"), ("à", 40.00, ""), ("une", 40.10, ""),
                ("boîte", 40.25, ""), ("auto,", 40.45, "KB"),
                ("la", 41.00, ""), ("boîte", 41.16, ""), ("auto", 41.48, "B"),
                ("elle", 41.72, ""), ("gère", 41.85, ""), ("ta", 42.24, ""), ("voiture", 42.36, "B"),
                ("toute", 42.68, "K"), ("seule.", 42.85, "K")],
         punch=[(36.20, 0.06), (42.68, 0.07)]),
    # --- 03 LES VITESSES
    dict(id="c7", src=(59.25, 62.00), zoom=1.04, cx=590, cy=780, push=0.015,
         words=[("Là,", 59.32, ""), ("je", None, ""), ("suis", None, "B"), ("en", 60.24, ""),
                ("quelle", 60.40, ""), ("vitesse,", 60.60, "K"), ("là ?", 60.85, "B"),
                ("5.", 61.52, "K")],
         punch=[(61.52, 0.08)]),
    # --- RETOUR À LA QUESTION (même plan que le hook, cadrage différent)
    dict(id="q2", src=(66.04, 67.95), zoom=1.00, cx=590, cy=780, push=0.01,
         words=[("Qu'est-ce", 66.10, ""), ("qui", 66.40, ""), ("se", None, ""), ("passe", 66.62, "B"),
                ("quand", 66.92, ""), ("tu", 67.04, ""), ("passes", 67.16, ""), ("pas", 67.36, "KB"),
                ("les", 67.52, ""), ("vitesses ?", 67.68, "K")],
         punch=[]),
    dict(id="c8", src=(72.85, 74.15), zoom=1.15, cx=590, cy=760, push=0.02,
         words=[("Il", 72.95, ""), ("consomme", 73.12, "K"), ("plus", 73.60, "KB"),
                ("d'essence.", 73.72, "K")],
         punch=[(73.60, 0.06)]),
    # --- 04 LE RÉGIME MOTEUR
    dict(id="c9", src=(76.88, 84.70), zoom=1.02, cx=590, cy=780, push=0.010,
         words=[("C'est", 76.95, ""), ("pour", None, ""), ("ça", None, "B"), ("que", None, ""),
                ("le", None, ""), ("moteur", 78.16, "KB"), ("peut", 78.48, ""), ("être", None, ""),
                ("en", 78.92, "B"), ("sur-régime", 79.08, "KB"), ("ou", 79.80, ""), ("en", 80.00, "B"),
                ("sous-régime.", 80.08, "KB"),
                ("Sur-régime,", 81.32, "KB"), ("c'est", 81.96, ""), ("que", None, "B"),
                ("tu", 82.28, ""), ("lui", None, ""), ("en", None, ""), ("demandes", None, "B"),
                ("trop.", 82.85, "KB"),
                ("Sous-régime,", 83.24, "KB"), ("tu", 83.70, ""), ("lui", None, ""), ("en", None, ""),
                ("demandes", None, "B"), ("pas", 84.20, ""), ("assez.", 84.40, "K")],
         punch=[(79.08, 0.05), (82.85, 0.07), (84.40, 0.06)]),
    dict(id="c10", src=(85.00, 87.91), zoom=1.14, cx=590, cy=760, push=0.015,
         words=[("Et", 85.05, ""), ("dans", 85.32, ""), ("les", 85.48, ""), ("deux", 85.60, "K"),
                ("cas,", 85.80, "B"), ("il", 86.02, ""), ("consomme", 86.12, ""), ("trop.", 86.40, "KB"),
                ("Dans", 86.80, ""), ("les", None, ""), ("deux", None, ""), ("cas ?", None, "B"),
                ("Ouais.", 87.55, "")],
         punch=[(86.40, 0.07)]),
    # --- 05 À L'OREILLE
    dict(id="c11", src=(88.30, 91.43), zoom=1.03, cx=590, cy=780, push=0.012,
         words=[("Tu", 88.35, ""), ("as", 88.50, ""), ("l'habitude,", 88.68, "B"), ("à", 89.12, ""),
                ("l'oreille,", 89.20, "KB"), ("de", 89.64, ""), ("savoir", 89.76, "B"), ("quand", 90.12, ""),
                ("le", None, ""), ("moteur", 90.32, "B"), ("il", 90.56, ""), ("est", 90.68, ""),
                ("bien", 90.76, "KB"), ("ou", 90.96, ""), ("pas.", 91.10, "K")],
         punch=[(89.20, 0.05)]),
    # --- OUTRO
    dict(id="c12", src=(95.00, 96.80), zoom=1.13, cx=590, cy=760, push=0.02,
         words=[("Arrête-moi", 95.10, ""), ("ta", 96.00, ""), ("vidéo,", 96.08, "KB"),
                ("c'est", 96.45, ""), ("bon.", 96.60, "")],
         punch=[]),
]
