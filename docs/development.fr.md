[English](development.md) | [Français](development.fr.md) — retour au [README](../README.fr.md)

# Développement

Trois façons de faire tourner autre chose que l'image publiée, de la plus légère à la plus proche de la production.

## Depuis les sources

La boucle dans laquelle écrire du code : sous `DEV=1`, les templates et les fichiers statiques sont relus à chaque requête, donc une modification HTML ou CSS apparaît à un simple rafraîchissement.

Deux réglages suffisent pour démarrer. Placez-les dans un `.env` à la racine du dépôt :

```
LYRION_HOST=https://lyrion.local:9000
LYRION_DATA_DIR=/var/lib/squeezeboxserver
```

puis, avec Python 3.12+ :

```bash
pip install -r requirements.txt
source .env
DEV=1 python app.py
```

L'application est accessible sur `http://localhost:1111`. C'est aussi la façon de faire tourner le dashboard sur une machine où l'on ne veut pas de Docker — sans le `DEV=1` dans ce cas.

C'est `.env` qui alimente l'application ici (`config.py` lit l'environnement une fois au démarrage), et `scripts/embed_lyrics.py` charge le même fichier via python-dotenv. Chaque variable est documentée sur la page [Configuration](configuration.fr.md).

## L'image `dev`

`ghcr.io/werdeil/lyrion-dashboard:dev` est reconstruite à chaque merge dans `master` : elle porte donc du code qui n'est dans aucune release. Servez-vous-en pour essayer un correctif avant sa publication ou reproduire un bug sur le code courant, puis repointez `image:` sur un tag de version — rien ne garantit que `dev` soit dans un état fonctionnel.

## Construire l'image depuis un clone

```bash
docker build -t lyrion-dashboard:local .
```

Pointez l'`image:` du fichier compose sur ce tag pour la lancer. C'est ainsi qu'on vérifie une modification du `Dockerfile` lui-même. C'est une mauvaise boucle pour le code applicatif : l'image embarque sa propre copie des sources, donc chaque modification demande une reconstruction.

## Vérifications

La suite de tests, les linters et les scanners de sécurité sont ceux que la CI exécute ; `CLAUDE.md` liste chaque commande et comment la reproduire.

```bash
python -m unittest discover
```
