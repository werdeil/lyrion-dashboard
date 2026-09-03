[English](docker.md) | [Français](docker.fr.md) — retour au [README](../README.fr.md)

# Docker

Le dashboard est publié sous forme d'image conteneur sur le GitHub Container Registry : `ghcr.io/werdeil/lyrion-dashboard`. L'installer ne demande aucun clone de ce dépôt — un `docker-compose.yml`, un `.env` rempli, et `docker compose up -d`.

## Tags d'image

| Tag | Pointe vers | Reconstruit |
|---|---|---|
| `latest` | la release la plus récente | à chaque release, plus une fois par semaine pour les correctifs du base image |
| `X.Y` | le dernier patch de cette mineure (ex: `0.2`) | à chaque release de cette série |
| `X.Y.Z` | cette release exacte (ex: `0.2.6`) | jamais — le digest est immuable |

Les images sont construites pour `linux/amd64` et `linux/arm64` : un Raspberry Pi ou un NAS ARM tire le même tag qu'un PC. Épinglez `X.Y.Z` pour un déploiement qui ne bouge que sur votre décision ; `latest` récupère en plus la reconstruction hebdomadaire qui fait entrer les correctifs de sécurité Debian dans l'image.

## Mise à jour

```bash
docker compose pull
docker compose up -d
```

## Construire depuis les sources

Copiez le modèle d'override pour que Compose construise ce dépôt au lieu de tirer l'image :

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
docker compose up -d --build
```

Le modèle monte aussi les sources en lecture seule et met `DEV=1`, de sorte que les modifications de templates et de CSS apparaissent à un simple rafraîchissement — c'est la configuration de développement. Retirez ces lignes si vous voulez seulement une image construite localement.

## Personnalisation locale de Compose

`docker-compose.override.yml` est l'endroit prévu pour les changements locaux — un service auxiliaire, un volume supplémentaire, un autre port — pour qu'un `git pull` n'entre jamais en conflit avec eux. Compose le charge automatiquement par-dessus `docker-compose.yml`, et `.gitignore` le tient hors du dépôt.

## Droits sur les fichiers

Le conteneur tourne sous l'uid 1000, pas root. Si les fichiers `library.db` et `persist.db` de Lyrion ne sont pas lisibles par tous, le dashboard démarre mais écrit dans ses logs qu'il ne peut pas les ouvrir ; lancez-le alors sous l'utilisateur qui les possède :

```yaml
services:
  lyrion-dashboard:
    user: "0:0"
```
