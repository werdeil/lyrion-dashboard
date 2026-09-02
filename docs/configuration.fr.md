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

## Personnalisation locale de Docker Compose

Pour ajouter des services ou des options locales sans polluer les changements Git, copiez le modèle d'override :

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Éditer docker-compose.override.yml selon vos besoins
docker compose up -d
```

Docker Compose charge automatiquement `docker-compose.override.yml` par-dessus le fichier principal.

## Logs

Tout ce que l'application a à dire part sur la sortie standard du conteneur :

```bash
docker logs -f lyrion-dashboard
```

Au démarrage, elle indique la version, le `LYRION_HOST` résolu, l'ordre des fournisseurs de paroles et si `library.db` / `persist.db` ont bien été trouvés — la première chose à vérifier quand la page reste vide.

En `INFO` (le défaut), une piste qui finit sans paroles raconte toute son histoire : la consultation de la bibliothèque, puis chaque fournisseur, puis le verdict.

```
track 12345: no lyrics in the library
lyrics: lrclib has no match (312 ms)
lyrics: musixmatch unreachable after 5003 ms (Read timed out)
lyrics: genius has no match (486 ms)
lyrics: 'Hocus Pocus' by 'Focus' -> none (synced=False, plain=False) in 5801 ms
```

Une recherche qui aboutit tient en une ligne, `lyrics: 'Space Debris' by 'Deep Purple' -> lrclib (synced=True, plain=True) in 412 ms`. `source` distingue les cas : un nom de fournisseur (trouvé), `none` (recherche faite, aucune correspondance), `rejected` (un candidat est revenu mais correspondait à un autre enregistrement), `unavailable` (aucun fournisseur n'a répondu — la recherche n'est pas mise en cache et sera réessayée). Également en `INFO` : un résultat servi depuis le cache au lieu d'une nouvelle recherche, une recherche refusée par le rate limit ou le cooldown de rafraîchissement, et un recalcul des statistiques avec sa durée.

Avec `LOG_LEVEL=DEBUG` (puis un redémarrage du conteneur), s'ajoutent le détail HTTP de chaque fournisseur, les consultations qui ont abouti, l'énumération des lecteurs et chaque appel JSON-RPC à Lyrion avec sa durée. C'est verbeux — le sondage now-playing tourne toutes les 2 s — donc à activer le temps de reproduire un problème, puis à remettre comme avant.
