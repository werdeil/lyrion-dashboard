[English](endpoints.md) | [Français](endpoints.fr.md) — retour au [README](../README.fr.md)

# Endpoints

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Dashboard principal (now playing + stats) |
| GET | `/health` | Vérification de l'état du service |
| GET | `/stats.json` | Statistiques de la bibliothèque (JSON) |
| GET | `/now-playing.json` | État live de la piste du lecteur en cours de lecture, détecté automatiquement (JSON) |
| GET | `/cover/{coverid}.jpg` | Relaie une pochette depuis Lyrion, en same-origin |
| GET | `/cover/remote.jpg` | Relaie la pochette de la piste distante/streamée en cours de lecture |
| GET | `/mosaic-covers.json` | Ids de pochettes pour la mosaïque de l'état vide, les plus récemment écoutés d'abord (JSON) |
| GET | `/recent-covers.json` | Ids de pochettes des albums récemment écoutés, du plus récent au plus ancien (JSON) |
| GET | `/lyrics.json` | Récupère les paroles d'une piste sur le web, à la demande |
| GET | `/files/{path}` | Sert un fichier depuis le répertoire custom data |

Les endpoints JSON ne sont pas traduits : ils renvoient des valeurs brutes, que la page met en forme.

## Widget Homepage

`/stats.json` renvoie du JSON brut, il se branche donc directement sur un widget [`customapi`](https://gethomepage.dev/widgets/services/customapi/) de [Homepage](https://gethomepage.dev) pour afficher les statistiques de la bibliothèque sur votre tableau de bord :

```yaml
- Lyrion Dashboard:
    href: http://lyrion-dashboard:1111
    widget:
      type: customapi
      url: http://lyrion-dashboard:1111/stats.json
      mappings:
        - field: albums_total
          label: Albums
        - field: songs_total
          label: Morceaux
        - field: velocity_30d
          label: Écoutés (30 j)
```

N'importe quelle clé du JSON fonctionne comme `field` — ouvrez `/stats.json` dans un navigateur pour choisir celles qui vous intéressent.
