[English](configuration.md) | [Français](configuration.fr.md) — retour au [README](../README.fr.md)

# Configuration

Toute la configuration vient de variables d'environnement, lues une fois au démarrage. `.env.example` sert de modèle : copiez-le en `.env`, remplissez-le, et Docker Compose (ou `source .env`) le passe à l'application.

| Variable | Description | Défaut |
|---|---|---|
| `LYRION_HOST` | URL du serveur Lyrion (ex: `https://lyrion.local:9000`) | -- |
| `DB_DIR` | Répertoire contenant `library.db` de Lyrion | -- |
| `DB_PERSIST_DIR` | Répertoire contenant `persist.db` de Lyrion | -- |
| `CUSTOM_DATA_DIR` | Répertoire des fichiers générés | `/opt/scripts/custom_data` |
| `LYRICS_PROVIDERS` | Fournisseurs de paroles web, essayés dans l'ordre (`lrclib`, `musixmatch`, `genius`) | `lrclib,musixmatch,genius` |
| `MUSIXMATCH_TOKEN` | Jeton Musixmatch fixe (sinon récupéré automatiquement) | -- |
| `LRCLIB_TIMEOUT` | Délai d'expiration des requêtes LRCLIB, en secondes | `15` |
| `LYRICS_VERIFY_DURATION_TOLERANCE` | Écart max (secondes) toléré par `--verify` dans `embed_lyrics.py` | `3` |
| `TZ` | Fuseau horaire utilisé pour aligner les fenêtres d'écoutes récentes sur minuit local (ex: `Europe/Paris`) | `UTC` |
| `LOG_LEVEL` | Verbosité des logs applicatifs (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` (`DEBUG` si `DEV=1`) |
| `DEV` | Mettre à `1` pour recharger les templates à la volée et désactiver le cache statique (développement) | -- |

Ce que chaque `LOG_LEVEL` écrit réellement est sur la page [Logs](logs.fr.md).

## Personnalisation locale de Docker Compose

Pour ajouter des services ou des options locales sans polluer les changements Git, copiez le modèle d'override :

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Éditer docker-compose.override.yml selon vos besoins
docker compose up -d
```

Docker Compose charge automatiquement `docker-compose.override.yml` par-dessus le fichier principal.
