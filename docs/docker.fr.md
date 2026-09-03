[English](docker.md) | [Français](docker.fr.md) — retour au [README](../README.fr.md)

# Docker

Le dashboard est publié sous forme d'image conteneur sur le GitHub Container Registry : `ghcr.io/werdeil/lyrion-dashboard`. L'installer ne demande aucun clone de ce dépôt — un seul `docker-compose.yml` portant l'URL de votre Lyrion et son répertoire de données, et `docker compose up -d`.

Ce fichier compose vous appartient une fois téléchargé : changez le port, les volumes, la politique de redémarrage, intégrez le service à une pile plus large. Rien n'a besoin de rester synchronisé avec ce dépôt.

## Tags d'image

| Tag | Pointe vers | Reconstruit |
|---|---|---|
| `latest` | la release la plus récente | à chaque release |
| `X.Y` | le dernier patch de cette mineure (ex: `0.2`) | à chaque release de cette série |
| `X.Y.Z` | cette release exacte (ex: `0.2.6`) | jamais — le digest est immuable |
| `dev` | la branche `master` | à chaque merge — du code non publié, dans aucune release |

Les images sont construites pour `linux/amd64` et `linux/arm64` : un Raspberry Pi ou un NAS ARM tire le même tag qu'un PC. Épinglez `X.Y.Z` pour un déploiement qui ne bouge que sur votre décision ; `latest` suit les releases. Aucun tag publié n'est jamais reconstruit : un correctif de sécurité du base image Debian vous parvient donc avec la release suivante, et non sous le tag que vous faites déjà tourner.

`dev` sert à essayer un correctif avant sa publication ou à reproduire un bug sur le code courant. Il est instable par définition — n'y pointez pas un dashboard dont vous dépendez.

## Mise à jour

```bash
docker compose pull
docker compose up -d
```

## Construire depuis les sources

`docker-compose.yml` contient un `build: .` commenté. Décommentez-le dans un clone de ce dépôt et Compose construit l'image localement au lieu de la tirer :

```bash
docker compose up -d --build
```

Pour développer, lancer l'application directement avec `DEV=1` recharge les templates et les fichiers statiques à un simple rafraîchissement — une image construite ne le peut pas, puisqu'elle embarque sa propre copie des sources.

## Droits sur les fichiers

Le conteneur tourne sous l'uid 1000, pas root. Si les fichiers de Lyrion sous le répertoire que vous montez sur `/lyrion` ne lui sont pas lisibles, le dashboard démarre mais écrit dans ses logs qu'il ne peut pas ouvrir les bases ; lancez-le alors sous l'utilisateur qui les possède :

```yaml
services:
  lyrion-dashboard:
    user: "0:0"
```
