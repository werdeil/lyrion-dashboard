[English](logs.md) | [Français](logs.fr.md) — retour au [README](../README.fr.md)

# Logs

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
