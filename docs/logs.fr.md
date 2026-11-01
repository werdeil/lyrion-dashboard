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

Une recherche qui aboutit tient en une ligne, `lyrics: 'Space Debris' by 'Deep Purple' -> lrclib (synced=True, plain=True) in 412 ms`. `source` distingue les cas : un nom de fournisseur (trouvé), `none` (recherche faite, aucune correspondance), `rejected` (un candidat est revenu mais correspondait à un autre enregistrement), `unavailable` (aucun fournisseur n'a répondu). Une recherche pendant laquelle un fournisseur était injoignable n'est pas mise en cache, sauf si elle a trouvé des paroles synchronisées, et le signale par `lyrics: a provider was unreachable, … not cached` : elle sera refaite au prochain changement de morceau ou au prochain réessai. Également en `INFO` : un résultat servi depuis le cache au lieu d'une nouvelle recherche, une recherche refusée par le rate limit ou le cooldown de rafraîchissement, un recalcul des statistiques avec sa durée, et `musixmatch: 3 search results, none is 'Space Debris' by 'Muse' (247s) - first is 'Nu Ma Uita' by 'Elena' (199s)` quand la recherche Musixmatch n'a listé que d'autres morceaux ou d'autres enregistrements. Une durée que le fournisseur ou vos tags ne donnent pas s'affiche `(length unknown)`.

Deux lignes LRCLIB portent une URL, pour les morceaux qui méritent un examen. `lrclib: no record, catalogue search: https://lrclib.net/search/Focus%20Hocus%20Pocus` passe vos propres tags dans la page de recherche de LRCLIB : elle dit si le catalogue n'a vraiment rien, ou s'il orthographie l'artiste ou le titre autrement que votre bibliothèque. `lrclib: https://lrclib.net/tracks/22439347 is 419s, this track is 302s - its timings dropped` est l'autre cas fréquent — le bon morceau, mais une version live ou allongée dont le LRC défilerait sur la mauvaise timeline : ses mots sont gardés comme paroles simples, pas son karaoké. Cette recherche consultable ne filtre pas sur la durée comme le fait l'application, elle listera donc des enregistrements que l'application refuse ensuite : c'est l'écart entre les deux qui est le diagnostic, pas un bug.

`LOG_LEVEL=DEBUG` ajoute le détail HTTP de chaque fournisseur, les consultations qui ont abouti et l'énumération des lecteurs. Cette énumération se répète toutes les 2 s avec le sondage now-playing, elle n'est donc affichée que lorsque ce qu'elle trouve change : `players (63 ms): Salon=play:12345, Cuisine=stop` liste tous les lecteurs connus de Lyrion, avec l'identifiant de piste de ceux qui sont affichés, et `disconnected` pour un lecteur qui a décroché. À activer le temps de reproduire un problème, puis à remettre comme avant.

`LOG_LEVEL` est lu au démarrage, mais le niveau peut aussi être changé pendant que le conteneur tourne — sans redémarrage ni perte d'état, pratique quand le problème est en train de se produire :

```bash
curl -X POST 'http://lyrion-dashboard:1111/log-level?level=debug'
# {"default":"INFO","level":"DEBUG"}
curl http://lyrion-dashboard:1111/log-level   # le niveau actuel, et celui qu'un redémarrage rétablirait
curl -X POST 'http://lyrion-dashboard:1111/log-level?level=info'
```

Le changement vit dans le process en cours — un redémarrage revient à `LOG_LEVEL`, c'est ce que rapporte `default`. Comme le reste de l'application, cet endpoint ne demande aucune authentification : à garder sur le LAN.

## Musixmatch

Musixmatch a besoin du jeton de votre compte ([Configuration](configuration.fr.md#jeton-musixmatch)), et chacun de ses trois états a sa ligne :

- `musixmatch: skipped, MUSIXMATCH_TOKEN is not set …` — un `WARNING` écrit une fois par démarrage ; Musixmatch est écarté de toutes les recherches tant qu'aucun jeton n'est fourni.
- `lyrics: musixmatch unreachable after … (musixmatch refused the request (HTTP 401, status 401): MUSIXMATCH_TOKEN is likely expired or revoked …)` — le jeton a été refusé ; recopiez-en un neuf.
- `lyrics: musixmatch unreachable after … (musixmatch answered with its placeholder track 'NOKIA' by 'Drake' instead of searching …)` — Musixmatch répond à toute recherche par le même morceau bouche-trou quand il ne fait plus confiance à l'appelant ; c'est une panne, pas une absence de résultat, donc la recherche n'est pas mise en cache.

Les deux refus comptent comme une panne : la recherche est refaite au morceau suivant. Pour vérifier un jeton sans attendre, lancez une recherche dans le conteneur avec le client de l'application, qui signe la requête comme Musixmatch l'exige :

```bash
docker exec lyrion-dashboard python -c "from services.lyrics import _provider_musixmatch as m; print(m('Henri Salvador', 'Embrasse-la', None, None))"
```

Elle affiche les paroles trouvées (`{'lyrics': …, 'synced': '[00:…`), `None` quand Musixmatch n'a pas de correspondance, ou le refus ci-dessus sous forme d'erreur.
