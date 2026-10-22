[English](scripts.md) | [Français](scripts.fr.md) — retour au [README](../README.fr.md)

# Scripts

`scripts/` regroupe l'outillage qui tourne en dehors de l'application web.

## Regénérer les captures d'écran (`scripts/generate_screenshots.py`)

Lance la vraie application avec les couches Lyrion/base de données mockées (piste factice en cours de lecture, paroles LRC synchronisées, pochettes générées, historique d'écoutes factice, statistiques fixes) et capture toutes les images de `docs/screenshots/` avec Chromium headless : le tableau de bord desktop dans les deux langues, la vue mobile responsive, l'application Android dans un cadre de téléphone, et la galerie de démo (pochette agrandie, paroles karaoké, pile des dernières écoutes, panneau de statistiques, mosaïque de l'état vide). Chaque capture utilise volontairement une pochette différente, pour montrer l'adaptation de la couleur d'accent à la pochette. Aucun serveur Lyrion, base de données ni accès réseau n'est nécessaire.

```bash
pip install -r requirements.txt playwright
playwright install chromium   # une seule fois, ou définir CHROMIUM_PATH
python scripts/generate_screenshots.py
```

Une capture est une entrée `Shot` dans la table `SHOTS` du script : le scénario à servir, le viewport et la langue, éventuellement du JS à exécuter d'abord (ouvrir la pochette agrandie) et un élément sur lequel recadrer.
