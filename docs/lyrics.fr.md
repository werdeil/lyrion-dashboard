[English](lyrics.md) | [Français](lyrics.fr.md) — retour au [README](../README.fr.md)

# Paroles

## Ce qu'affiche la page

Les paroles de vos tags s'affichent dès le début du morceau, et une recherche web part quand même pour chaque morceau : c'est ainsi qu'un texte simple passe en karaoké.

```mermaid
flowchart TD
    A([Un morceau commence]) --> B{Paroles dans vos tags ?}
    B -- oui --> C[Affichées tout de suite]
    B -- non --> D["Recherche…"]
    C --> E[Recherche web]
    D --> E
    E -- version synchronisée --> F[Le karaoké prend la place]
    E -- texte simple seulement --> G[Le texte de vos tags s'il existe, sinon celui du web]
    E -- rien --> H["Le texte de vos tags s'il existe, sinon « Aucune parole trouvée »"]
```

Chaque version trouvée reste accessible d'un appui sur la ligne de provenance sous les paroles, qui permet aussi de les masquer pour le morceau. Le bouton de relance refait la recherche sans passer par le cache du serveur.

## Comment la recherche web choisit une version

Les fournisseurs sont interrogés dans l'ordre de `LYRICS_PROVIDERS` ([Configuration](configuration.fr.md)). Une version synchronisée ne compte que si sa durée correspond à celle du morceau à 3 secondes près : un LRC fait pour une version live ou longue défilerait sur la mauvaise chronologie.

```mermaid
flowchart TD
    A([Fournisseur suivant : LRCLIB, Musixmatch, Genius]) --> B{Paroles synchronisées de cette durée ?}
    B -- oui --> C[Karaoké, la recherche s'arrête]
    B -- non --> D[Son texte simple est gardé si c'est le premier trouvé]
    D --> E{Reste un fournisseur ?}
    E -- oui --> A
    E -- non --> F[Le premier texte simple trouvé, ou rien]
```

Genius n'a que du texte simple : il est sauté dès qu'un texte est gardé. Un résultat trouvé est mis en cache 24 heures, une absence 1 heure. Pour savoir pourquoi un morceau est resté sans paroles, lisez sa recherche dans les [logs](logs.fr.md).
