# Lyrion Custom Data

Application web Flask pour [Lyrion Music Server](https://github.com/LMS-Community/slimserver) (anciennement Logitech Media Server / Squeezebox Server).

## Fonctionnalites

- **Now Playing** -- Détecte automatiquement le lecteur en cours de lecture et affiche sa piste (pochette, titre, artiste, album) et ses paroles, rafraîchi via l'API JSON-RPC de Lyrion.
- **Statistiques de la bibliotheque** -- Albums, artistes, morceaux joués/non joués, genres, notes, paroles, velocite d'ecoute sur 30 jours.
- **Serveur de fichiers** -- Sert les fichiers depuis un repertoire configurable.

## Structure du projet

```
├── app.py                 # Point d'entrée Flask (factory)
├── config.py              # Configuration centralisée (env vars)
├── requirements.txt       # Dépendances Python
├── docker-compose.yml     # Déploiement via Docker
├── .env.example           # Modèle de configuration
├── routes/
│   ├── nowplaying.py      # Routes : /  et  /now-playing.json
│   └── custom.py          # Routes : /files/<path>
├── services/
│   ├── lyrion.py          # Client JSON-RPC Lyrion
│   └── database.py        # Accès SQLite (paroles, stats)
└── templates/
    └── nowplaying.html    # Dashboard principal
```

## Pre-requis

- Python 3.12+
- Un serveur Lyrion Music Server accessible
- Le plugin [Alternative Play Count](https://github.com/AF-1/lms-alternativeplaycount) installé sur Lyrion

## Installation

### Avec Docker (recommandé)

```bash
cp .env.example .env
# Editer .env avec vos valeurs
docker compose up -d
```

### Personnalisation locale Docker Compose

Pour ajouter des services ou des options locales sans polluer les changements Git, copiez le modèle d'override :

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Editer docker-compose.override.yml selon vos besoins
docker compose up -d
```

Docker Compose charge automatiquement `docker-compose.override.yml` en complément du fichier principal.

### Sans Docker

```bash
pip install -r requirements.txt
cp .env.example .env
# Editer .env avec vos valeurs
source .env
python app.py
```

L'application est accessible sur `http://localhost:1111`.

## Configuration

| Variable | Description | Défaut |
|---|---|---|
| `LYRION_HOST` | URL du serveur Lyrion (ex: `https://lyrion.local:9000`) | -- |
| `DB_PATH` | Chemin absolu vers la base SQLite de Lyrion | -- |
| `DB_PERSIST_PATH` | Chemin absolu vers la base persistante de Lyrion | -- |
| `SECRET_KEY` | Clé secrete Flask | `supersecretkey` |
| `CUSTOM_DATA_DIR` | Répertoire des fichiers generes | `/opt/scripts/custom_data` |
| `HOST` | Adresse d'écoute | `0.0.0.0` |
| `PORT` | Port d'écoute | `1111` |

## Endpoints

| Methode | Route | Description |
|---|---|---|
| GET | `/` | Dashboard principal (now playing + stats) |
| GET | `/now-playing.json` | État live de la piste du lecteur en cours de lecture, détecté automatiquement (JSON) |
| GET | `/files/<path>` | Sert un fichier depuis le répertoire custom data |

## Scripts

### Intégrer les paroles dans les fichiers (`scripts/embed_lyrics.py`)

Parcourt un dossier (ou des fichiers), récupère les paroles auprès des fournisseurs web et les écrit dans le tag *lyrics* de chaque morceau. Lyrion n'est jamais sollicité : lancez le script quand vous voulez, Lyrion prendra les changements au prochain scan. La configuration (`.env`) est lue automatiquement.

```bash
python scripts/embed_lyrics.py /chemin/vers/musique [options]
# Les jokers shell fonctionnent, même entre guillemets :
python scripts/embed_lyrics.py "/chemin/vers/musique/A*" /chemin/vers/musique/B*
```

| Option | Description |
|---|---|
| `--force` | Réécrit le tag même si des paroles sont déjà présentes. |
| `--clear` | Efface le tag existant quand rien n'est trouvé en ligne, pour refléter ce que proposent les fournisseurs. Traite aussi les fichiers déjà taggés (donc une requête web par fichier) ; combinable avec `--force`. |
| `--dry-run` | Affiche ce qui serait fait, sans rien écrire. |
| `--delay 0.5` | Délai (secondes) entre deux requêtes web (défaut : 0.5). |
| `--verbose` | Journalise chaque fichier, y compris ceux ignorés. |
| `--newer-than MARQUEUR` | Ne traite que les fichiers modifiés depuis le dernier `mtime` du fichier `MARQUEUR`, puis horodate `MARQUEUR` à l'heure de départ de la passe. Marqueur absent : toute la bibliothèque est traitée (première passe). Ignoré en `--dry-run`. |

Pour un cron quotidien qui ne re-tague que les ajouts/modifications, appelez directement le Python du venv (pas besoin d'activer l'environnement) avec `--newer-than` :

```cron
0 4 * * * cd /chemin/vers/custom_data && \
  .venv/bin/python scripts/embed_lyrics.py /chemin/vers/musique \
  --newer-than var/embed_lyrics_last_run >> /tmp/embed_lyrics.log 2>&1
```

> Limite : un fichier copié en conservant son `mtime` (`rsync -a`, `cp -p`) ne sera pas détecté comme modifié.
