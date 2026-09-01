"""UI translations (FR/EN).

Language is picked per-request from the browser's Accept-Language header,
falling back to English. The whole dict for the chosen language is handed to
the template (and serialised to JS) so every visible string has a single
source of truth here.
"""

SUPPORTED = ("fr", "en")
DEFAULT_LANG = "en"

TRANSLATIONS = {
    "fr": {
        # Now playing
        "empty_state": "Aucune lecture en cours",
        "no_lyrics_library": "Aucune parole dans la bibliothèque",
        "lyrics_search": "Recherche automatique de paroles sur le web (synchro si disponible)",
        "lyrics_sync_toggle": "Activer/Désactiver la synchronisation des paroles",
        "searching": "Recherche…",
        "lyrics_synced_hint": "Paroles synchronisées (karaoké)",
        "retry_lyrics": "Relancer la recherche de paroles sur le web",
        "no_lyrics_found": "Aucune parole trouvée, ni dans la bibliothèque ni sur le web",
        "lyrics_unavailable": "Recherche impossible : services de paroles injoignables",
        "lyrics_throttled": "Recherche relancée trop tôt, réessayez dans quelques secondes",
        "resume_scroll": "Reprendre le défilement auto",
        "open_lyrion": "Ouvrir dans Lyrion",
        "lyrion_logo_alt": "Logo Lyrion",
        "choose_player": "Choisir le lecteur affiché",
        "app_menu": "Menu de l'application",
        "cover_alt": "Pochette",
        "cover_zoom": "Agrandir la pochette",
        "source_prefix": "Source :",
        "source_library": "Bibliothèque",
        # Stats
        "stats_title": "Statistiques",
        "history": "Historique",
        "tracks": "Morceaux",
        "albums": "Albums",
        "album_artists": "Artistes d'album",
        "track_artists": "Tous les artistes",
        "library": "Bibliothèque",
        "total": "Total",
        "fully_played": "Écoutés complètement",
        "partially_played": "Partiellement écoutés",
        "never_played": "Jamais écoutés",
        "played": "Écoutés",
        "unplayed": "Jamais écoutés",
        "played_last_30d": "30 derniers jours",
        "played_last_year": "12 derniers mois",
        "total_plays": "Écoutes cumulées",
        "total_skips": "Sauts cumulés",
        "genres": "Genres",
        "rated_songs": "Morceaux notés",
        "with_lyrics": "Avec paroles",
    },
    "en": {
        # Now playing
        "empty_state": "Nothing playing",
        "no_lyrics_library": "No lyrics in the library",
        "lyrics_search": "Automatically search the web for lyrics (synced when available)",
        "lyrics_sync_toggle": "Toggle lyrics synchronization",
        "searching": "Searching…",
        "lyrics_synced_hint": "Time-synced lyrics (karaoke)",
        "retry_lyrics": "Retry the web lyrics search",
        "no_lyrics_found": "No lyrics found, neither in the library nor on the web",
        "lyrics_unavailable": "Search failed: the lyrics services are unreachable",
        "lyrics_throttled": "Retried too soon, try again in a few seconds",
        "resume_scroll": "Resume auto-scroll",
        "open_lyrion": "Open in Lyrion",
        "lyrion_logo_alt": "Lyrion logo",
        "choose_player": "Choose the player shown",
        "app_menu": "App menu",
        "cover_alt": "Cover",
        "cover_zoom": "Enlarge the cover",
        "source_prefix": "Source:",
        "source_library": "Library",
        # Stats
        "stats_title": "Statistics",
        "history": "History",
        "tracks": "Tracks",
        "albums": "Albums",
        "album_artists": "Album artists",
        "track_artists": "All artists",
        "library": "Library",
        "total": "Total",
        "fully_played": "Fully played",
        "partially_played": "Partially played",
        "never_played": "Never played",
        "played": "Played",
        "unplayed": "Never played",
        "played_last_30d": "Last 30 days",
        "played_last_year": "Last 12 months",
        "total_plays": "Cumulative plays",
        "total_skips": "Cumulative skips",
        "genres": "Genres",
        "rated_songs": "Rated songs",
        "with_lyrics": "With lyrics",
    },
}


def pick_lang(accept_languages):
    """Best supported language from a Werkzeug Accept-Language, defaulting to EN."""
    return accept_languages.best_match(SUPPORTED) or DEFAULT_LANG
