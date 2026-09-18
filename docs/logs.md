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

A healthy search is a single line, `lyrics: 'Space Debris' by 'Deep Purple' -> lrclib (synced=True, plain=True) in 412 ms`. `source` tells the outcomes apart: a provider name (found), `none` (searched, nothing matched), `rejected` (a candidate came back but was another recording), `unavailable` (no provider answered — the search is not cached and will be retried). Also at `INFO`: a result served from the cache instead of a new search, a search refused by the rate limit or the refresh cooldown, a stats recompute with its duration, and `musixmatch: matched 'Nu Ma Uita' by 'Elena' (199s), not 'Space Debris' by 'Muse' (247s) - dropped` when Musixmatch's fuzzy matcher answered with a different song.

Two LRCLIB lines carry a URL, for the tracks worth a closer look. `lrclib: no record, catalogue search: https://lrclib.net/search/Focus%20Hocus%20Pocus` runs your own tags through LRCLIB's search page: it says whether the catalogue really holds nothing, or whether it spells the artist or the title differently from your library. `lrclib: https://lrclib.net/tracks/22439347 is 419s, this track is 302s - its timings dropped` is the other frequent case — the right song, but a live or extended upload whose LRC would scroll against the wrong timeline, so its words are kept as plain lyrics and the karaoke is not. That browsable search does not filter on length the way the app does, so it will list records the app then refuses: the gap between the two is the diagnosis, not a bug.

`LOG_LEVEL=DEBUG` adds each provider's HTTP detail, the lookups that succeeded and the player enumeration. The enumeration repeats every 2s with the now-playing poll, so it only prints when what it finds changes: `players (63 ms): Salon=play:12345, Cuisine=stop` names every player Lyrion knows, with the track id of the ones shown, `disconnected` for a player that dropped off. Use it while reproducing a problem, then set it back.

`LOG_LEVEL` is read at start-up, but the level can also be switched while the container runs — no restart, no lost state, handy when the problem is already happening:

```bash
curl -X POST 'http://lyrion-dashboard:1111/log-level?level=debug'
# {"default":"INFO","level":"DEBUG"}
curl http://lyrion-dashboard:1111/log-level   # what it is now, and what a restart would restore
curl -X POST 'http://lyrion-dashboard:1111/log-level?level=info'
```

The change lives in the running process — a restart goes back to `LOG_LEVEL`, which is what `default` reports. Like the rest of the app it asks for no credentials, so keep it on the LAN.
