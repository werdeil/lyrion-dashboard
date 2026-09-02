[English](logs.md) | [Français](logs.fr.md) — back to the [README](../README.md)

# Logs

Everything the app has to say goes to the container's standard output:

```bash
docker logs -f lyrion-dashboard
```

At start-up it reports the version, the resolved `LYRION_HOST`, the provider order and whether `library.db` / `persist.db` were actually found — the first thing to check when the page stays empty.

At `INFO` (the default), a track that ends up without lyrics tells its whole story: the library lookup, then each provider, then the verdict.

```
track 12345: no lyrics in the library
lyrics: lrclib has no match (312 ms)
lyrics: musixmatch unreachable after 5003 ms (Read timed out)
lyrics: genius has no match (486 ms)
lyrics: 'Hocus Pocus' by 'Focus' -> none (synced=False, plain=False) in 5801 ms
```

A healthy search is a single line, `lyrics: 'Space Debris' by 'Deep Purple' -> lrclib (synced=True, plain=True) in 412 ms`. `source` tells the outcomes apart: a provider name (found), `none` (searched, nothing matched), `rejected` (a candidate came back but was another recording), `unavailable` (no provider answered — the search is not cached and will be retried). Also at `INFO`: a result served from the cache instead of a new search, a search refused by the rate limit or the refresh cooldown, and a stats recompute with its duration.

Set `LOG_LEVEL=DEBUG` and restart the container to also get each provider's HTTP detail, the lookups that succeeded, the player enumeration and every Lyrion JSON-RPC call with its duration. It is verbose — the now-playing poll runs every 2s — so use it while reproducing a problem, then set it back.
