[English](lyrics.md) | [Français](lyrics.fr.md) — retour au [README](../README.fr.md)

# Paroles

## Ce qu'affiche la page

Les paroles de vos tags s'affichent dès le début du morceau, et une recherche web part quand même pour chaque morceau : c'est ainsi qu'un texte simple passe en karaoké.

![Ce qu'affiche la page selon vos tags et la recherche web](diagrams/lyrics-display.fr.png)

Chaque version trouvée reste accessible d'un appui sur la ligne de provenance sous les paroles, qui permet aussi de les masquer pour le morceau. Le bouton de relance refait la recherche sans passer par le cache du serveur.

## Comment la recherche web choisit une version

Les fournisseurs sont interrogés dans l'ordre de `LYRICS_PROVIDERS` ([Configuration](configuration.fr.md)). Une version synchronisée ne compte que si sa durée correspond à celle du morceau à 3 secondes près : un LRC fait pour une version live ou longue défilerait sur la mauvaise chronologie.

![Comment la recherche web choisit une version](diagrams/lyrics-search.fr.png)

Genius n'a que du texte simple : il est sauté dès qu'un texte est gardé. Un résultat trouvé est mis en cache 24 heures, une absence 1 heure. Pour savoir pourquoi un morceau est resté sans paroles, lisez sa recherche dans les [logs](logs.fr.md).
