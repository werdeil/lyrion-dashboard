[English](docker.md) | [Français](docker.fr.md) — retour au [README](../README.fr.md)

# Docker

Le dashboard est publié sous forme d'image conteneur sur le GitHub Container Registry : `ghcr.io/werdeil/lyrion-dashboard`. L'installer ne demande aucun clone de ce dépôt — un seul `docker-compose.yml` portant l'URL de votre Lyrion et son répertoire de données, et `docker compose up -d`.

Ce fichier compose vous appartient une fois téléchargé : changez le port, les volumes, la politique de redémarrage, intégrez le service à une pile plus large. Rien n'a besoin de rester synchronisé avec ce dépôt.

## Tags d'image

| Tag | Pointe vers | Bouge quand |
|---|---|---|
| `latest` | la release stable la plus récente | une release est publiée |
| `X.Y` | le dernier patch de cette mineure (ex: `0.2`) | une release de cette série est publiée |
| `X.Y.Z` | cette release exacte (ex: `0.2.6`) | jamais — construite une fois, elle garde son digest |
| `dev` | la branche `master` | à chaque merge — du code non publié, voir [Développement](development.fr.md) |

Les images sont construites pour `linux/amd64` et `linux/arm64` : un Raspberry Pi ou un NAS ARM tire le même tag qu'un PC. Épinglez `X.Y.Z` pour un déploiement qui ne bouge que sur votre décision ; `latest` suit les releases. Aucun tag publié n'est jamais reconstruit : un correctif de sécurité du base image Debian vous parvient donc avec la release suivante, et non sous le tag que vous faites déjà tourner. Une release marquée comme pre-release ne publie que son tag `X.Y.Z` : `latest` et `X.Y` continuent de pointer sur la dernière stable.

## Mise à jour

```bash
docker compose pull
docker compose up -d
```

## Migrer depuis l'installation bind-montée

Avant cette image, le fichier compose lançait un `python:3.12-slim` nu sur un clone de ce dépôt et lisait ses réglages dans un `.env` posé à côté. Ni l'un ni l'autre ne servent désormais. Reprenez le fichier compose du [README](../README.fr.md), reportez-y votre `LYRION_HOST`, et montez sur `/lyrion` ce que `LYRION_DATA_DIR` désignait. Le clone peut disparaître ; ne gardez le `.env` que si vous faites tourner les [scripts](scripts.fr.md), qui le lisent toujours.

## Droits sur les fichiers

Le conteneur tourne sous l'uid 1000, pas root. Si les fichiers de Lyrion sous le répertoire que vous montez sur `/lyrion` ne lui sont pas lisibles, le dashboard démarre mais écrit dans ses logs qu'il ne peut pas ouvrir les bases ; lancez-le alors sous l'utilisateur qui les possède. `stat -c '%u:%g' /var/lib/squeezeboxserver` affiche le couple à utiliser :

```yaml
services:
  lyrion-dashboard:
    user: "999:999"
```

`user: "0:0"`, c'est root, qui lit tout : un recours de dernier ressort, pas la première chose à essayer.
