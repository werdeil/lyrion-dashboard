[English](configuration.md) | [Français](configuration.fr.md) — retour au [README](../README.fr.md)

# Configuration

Toute la configuration vient de variables d'environnement, lues une fois au démarrage. `.env.example` sert de modèle : copiez-le en `.env`, remplissez-le, et Docker Compose (ou `source .env`) le passe à l'application.

| Variable | Description | Défaut |
|---|---|---|
| `LYRION_HOST` | URL du serveur Lyrion (ex: `https://lyrion.local:9000`) | -- |
| `LYRION_DATA_DIR` | Répertoire de données de Lyrion, celui qui contient ses sous-répertoires `prefs/` et `cache/` | -- |
| `DB_DIR` | Répertoire contenant `library.db` de Lyrion, si son cache est hors de `LYRION_DATA_DIR` | `LYRION_DATA_DIR/cache` |
| `DB_PERSIST_DIR` | Répertoire contenant `persist.db` de Lyrion, si ses prefs sont hors de `LYRION_DATA_DIR` | `LYRION_DATA_DIR/prefs` |
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

Le dashboard lit deux fichiers SQLite que Lyrion garde côte à côte sous un même répertoire de données : `cache/library.db` (la bibliothèque musicale) et `prefs/persist.db` (notes et historique d'écoute). Ce répertoire est `/config` pour l'image Docker et `/var/lib/squeezeboxserver` pour le paquet Debian — pointez `LYRION_DATA_DIR` dessus et les deux fichiers sont trouvés, et Compose le monte en lecture seule en une ligne.

Lyrion permet de déplacer son cache (vers un SSD, un volume plus grand). Si c'est votre cas, mettez le vrai chemin dans `DB_DIR` — ou dans `DB_PERSIST_DIR` pour un répertoire de prefs déplacé ; chacune ne remplace que le chemin qu'elle nomme. Le conteneur doit aussi pouvoir l'atteindre : ajoutez-lui un montage en lecture seule dans `docker-compose.override.yml`.

Mise à jour depuis un `.env` qui ne définissait que `DB_DIR` et `DB_PERSIST_DIR` : Compose monte désormais `LYRION_DATA_DIR` et refuse de démarrer sans lui, il faut donc l'ajouter — en général le parent des deux répertoires que vous aviez déjà.

## Personnalisation locale de Docker Compose

Pour ajouter des services ou des options locales sans polluer les changements Git, copiez le modèle d'override :

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Éditer docker-compose.override.yml selon vos besoins
docker compose up -d
```

Docker Compose charge automatiquement `docker-compose.override.yml` par-dessus le fichier principal.
