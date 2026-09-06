[English](configuration.md) | [Français](configuration.fr.md) — retour au [README](../README.fr.md)

# Configuration

Toute la configuration vient de variables d'environnement, lues une fois au démarrage. Sous Docker, elles sont posées dans `docker-compose.yml` lui-même ; en exécution depuis les sources, elles viennent de `.env`, comme décrit sur la page [Développement](development.fr.md).

| Variable | Description | Défaut |
|---|---|---|
| `LYRION_HOST` | URL du serveur Lyrion (ex: `https://lyrion.local:9000`) | -- |
| `LYRION_DATA_DIR` | Répertoire de données de Lyrion, celui qui contient ses sous-répertoires `prefs/` et `cache/` | `/lyrion` dans l'image |
| `PLAY_COUNTS_SOURCE` | Origine des compteurs d'écoute : `auto` (Alternative Play Count s'il est installé, sinon les compteurs de Lyrion) ou `lyrion` (toujours ceux de Lyrion) | `auto` |
| `CUSTOM_DATA_DIR` | Répertoire des fichiers générés | `/opt/scripts/custom_data` |
| `LYRICS_PROVIDERS` | Fournisseurs de paroles web, essayés dans l'ordre (`lrclib`, `musixmatch`, `genius`) | `lrclib,musixmatch,genius` |
| `MUSIXMATCH_TOKEN` | Jeton Musixmatch fixe (sinon récupéré automatiquement) | -- |
| `LRCLIB_TIMEOUT` | Délai d'expiration des requêtes LRCLIB, en secondes | `15` |
| `LYRICS_VERIFY_DURATION_TOLERANCE` | Écart max (secondes) toléré par `--verify` dans `embed_lyrics.py` | `3` |
| `TZ` | Fuseau horaire utilisé pour aligner les fenêtres d'écoutes récentes sur minuit local (ex: `Europe/Paris`) | `UTC` |
| `LOG_LEVEL` | Verbosité des logs applicatifs (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` (`DEBUG` si `DEV=1`) |
| `DEV` | Mettre à `1` pour recharger les templates à la volée et désactiver le cache statique (développement) | -- |

Ce que chaque `LOG_LEVEL` écrit réellement est sur la page [Logs](logs.fr.md).

## Où vivent les bases de données

Le dashboard lit deux fichiers SQLite que Lyrion garde côte à côte sous un même répertoire de données : `cache/library.db` (la bibliothèque musicale) et `prefs/persist.db` (notes et historique d'écoute). Ce répertoire est `/config` pour l'image Docker de Lyrion et `/var/lib/squeezeboxserver` pour le paquet Debian. Sous Docker, montez-le en lecture seule sur `/lyrion`, où l'image le cherche ; sinon, `LYRION_DATA_DIR` le nomme directement.

Lyrion permet de déplacer son cache (vers un SSD, un volume plus grand). Sous Docker, remontez-le à sa place dans `docker-compose.yml` et rien d'autre ne change :

```yaml
- /mnt/ssd/cache:/lyrion/cache:ro
```

Sans Docker il n'y a pas de montage pour le faire : nommez alors le vrai chemin dans `DB_DIR` — ou dans `DB_PERSIST_DIR` pour un répertoire de prefs déplacé. Chacune ne remplace que le chemin qu'elle nomme, et une installation standard n'a besoin d'aucune des deux.

Mise à jour depuis un `.env` qui ne définissait que `DB_DIR` et `DB_PERSIST_DIR` : nommez plutôt leur parent — monté sur `/lyrion` sous Docker, ou nommé dans `LYRION_DATA_DIR` sinon.

Les tags d'image et la mise à jour sont sur la page [Docker](docker.fr.md).
