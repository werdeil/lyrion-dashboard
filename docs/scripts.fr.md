[English](scripts.md) | [Français](scripts.fr.md) — retour au [README](../README.fr.md)

# Scripts

Les scripts de `scripts/` tournent en dehors de l'application web, avec les seules dépendances de `requirements-cli.txt`. Ils écrivent directement dans les fichiers audio ; Lyrion n'est jamais sollicité et prend les changements à son prochain scan.

## Intégrer les paroles dans les fichiers (`scripts/embed_lyrics.py`)

Parcourt un dossier (ou des fichiers), récupère les paroles auprès des fournisseurs web et les écrit dans le tag *lyrics* de chaque morceau. La configuration (`.env`) est lue automatiquement.

```bash
python scripts/embed_lyrics.py /chemin/vers/musique [options]
# Les jokers shell fonctionnent, même entre guillemets :
python scripts/embed_lyrics.py "/chemin/vers/musique/A*" /chemin/vers/musique/B*
```

| Option | Description |
|---|---|
| <code>&#8209;&#8209;force</code> | Réécrit le tag même si des paroles sont déjà présentes. |
| <code>&#8209;&#8209;clear</code> | Efface le tag existant quand rien n'est trouvé en ligne, pour refléter ce que proposent les fournisseurs. Traite aussi les fichiers déjà taggés (donc une requête web par fichier) ; combinable avec `--force`. |
| <code>&#8209;&#8209;no&#8209;verify</code> | Accepte les paroles d'un fournisseur même quand son titre/artiste/durée ne correspondent pas au fichier. Désactivé par défaut : les tags étant écrits définitivement, un mauvais résultat est pire que l'absence de paroles. |
| <code>&#8209;&#8209;dry&#8209;run</code> | Affiche ce qui serait fait, sans rien écrire. |
| <code>&#8209;&#8209;delay&nbsp;0.5</code> | Délai (secondes) entre deux requêtes web (défaut : 0.5). |
| <code>&#8209;&#8209;verbose</code> | Journalise chaque fichier, y compris ceux ignorés. |

### Cron : ne re-taguer que les fichiers modifiés (`scripts/embed_lyrics_cron.sh`)

Wrapper destiné au cron : il ne passe à `embed_lyrics.py` que les fichiers dont le `ctime` a changé depuis la dernière passe réussie (`find -cnewer`), via un fichier marqueur.

```bash
scripts/embed_lyrics_cron.sh /chemin/vers/musique [MARQUEUR] [-- OPTIONS]
```

- `MARQUEUR` : fichier d'horodatage (défaut : `state/embed_lyrics.last_run` à la racine du repo). Absent → toute la bibliothèque est traitée (première passe).
- Le marqueur est horodaté au **début** de la passe et n'avance qu'**en cas de succès** : un échec ne fait pas avancer la fenêtre, et un fichier modifié pendant la passe est repris au prochain run. `--dry-run` ne fait pas avancer le marqueur.
- Tout ce qui suit `--` est transmis tel quel à `embed_lyrics.py` (ex. `-- --clear --delay 1`).

```cron
30 3 * * * /chemin/vers/custom_data/scripts/embed_lyrics_cron.sh \
  /chemin/vers/musique >> /tmp/embed_lyrics.log 2>&1
```

> Le `ctime` (et non le `mtime`) est utilisé volontairement : il capte aussi les ré-écritures de tags en place et les fichiers copiés en conservant leur `mtime` (`rsync -a`, `cp -p`).

## Intégrer les pochettes dans les fichiers (`scripts/embed_covers.py`)

Parcourt les dossiers d'albums et écrit le fichier de pochette de chaque dossier dans le tag *artwork* de ses morceaux, partout où ce fichier est plus net que ce que portent déjà les tags. Lyrion affiche la pochette embarquée et ignore totalement `folder.jpg` : un album avec une pochette de 1500 px sur le disque et une de 300 px dans ses tags continue donc d'afficher la petite tant que ce script n'est pas passé.

```bash
python scripts/embed_covers.py /chemin/vers/musique [options]
# Les jokers shell fonctionnent, même entre guillemets :
python scripts/embed_covers.py "/chemin/vers/musique/A*" /chemin/vers/musique/B*
```

| Option | Description |
|---|---|
| <code>&#8209;&#8209;name&nbsp;folder.jpg</code> | Nom du fichier de pochette cherché dans chaque dossier d'album (défaut : `folder.jpg`), casse indifférente. |
| <code>&#8209;&#8209;dry&#8209;run</code> | Affiche quels albums seraient re-tagués, sans rien écrire. |
| <code>&#8209;&#8209;verbose</code> | Journalise chaque album, y compris ceux ignorés. |

Les pochettes sont comparées sur leur **petit côté**, celui qui décide de la netteté à l'écran : seul un fichier plus grand est intégré, et un album dont les tags ne portent aucune pochette est toujours complété. L'image est stockée telle quelle, jamais ré-encodée. L'intégration réécrit chaque morceau de l'album, aussi la passe indique-t-elle de combien grossissent les fichiers audio — une pochette de 2 Mo sur un album de douze titres ajoute 24 Mo, qu'il faudra ensuite resynchroniser et sauvegarder.

### Cron : ne re-vérifier que les dossiers modifiés (`scripts/embed_covers_cron.sh`)

Même mécanisme de marqueur que le wrapper des paroles, à ceci près que l'unité est le dossier d'album : `find -cnewer` liste les fichiers dont le `ctime` a changé, et ce sont leurs dossiers qui sont passés à `embed_covers.py`. Un `folder.jpg` remplacé met donc son album dans la file au même titre qu'un nouveau morceau.

```bash
scripts/embed_covers_cron.sh /chemin/vers/musique [MARQUEUR] [-- OPTIONS]
```

- `MARQUEUR` : fichier d'horodatage (défaut : `state/embed_covers.last_run` à la racine du repo). Absent → toute la bibliothèque est traitée (première passe).
- Mêmes règles que ci-dessus : horodaté au **début** de la passe, avancé uniquement **en cas de succès**, laissé en place par `--dry-run`.
- Tout ce qui suit `--` est transmis tel quel à `embed_covers.py` (ex. `-- --name cover.jpg`).

```cron
0 5 * * * /chemin/vers/repo/scripts/embed_covers_cron.sh \
  /chemin/vers/musique >> /tmp/embed_covers.log 2>&1
```

> Intégrer une pochette modifie le `ctime` de chaque morceau : l'album reparaît donc à la passe suivante, qui trouve alors les tags déjà corrects et passe son chemin.

## Regénérer les captures d'écran (`scripts/generate_screenshots.py`)

Lance la vraie application avec les couches Lyrion/base de données mockées (piste factice en cours de lecture, paroles LRC synchronisées, pochettes générées, historique d'écoutes factice, statistiques fixes) et capture toutes les images de `docs/screenshots/` avec Chromium headless : le tableau de bord desktop dans les deux langues, la vue mobile responsive, l'application Android dans un cadre de téléphone, et la galerie de démo (pochette agrandie, paroles karaoké, pile des dernières écoutes, panneau de statistiques, mosaïque de l'état vide). Chaque capture utilise volontairement une pochette différente, pour montrer l'adaptation de la couleur d'accent à la pochette. Aucun serveur Lyrion, base de données ni accès réseau n'est nécessaire.

```bash
pip install -r requirements.txt playwright
playwright install chromium   # une seule fois, ou définir CHROMIUM_PATH
python scripts/generate_screenshots.py
```

Une capture est une entrée `Shot` dans la table `SHOTS` du script : le scénario à servir, le viewport et la langue, éventuellement du JS à exécuter d'abord (ouvrir la pochette agrandie) et un élément sur lequel recadrer.
