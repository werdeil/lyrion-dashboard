# Audit sécurité & performance — Lyrion Dashboard

Date : 2026-07-09 · Périmètre : backend Flask (`app.py`, `routes/`, `services/`),
front (`static/nowplaying.js`, templates), app Android (`android/`), Docker et CI.
Aucune modification de code n'accompagne cet audit ; chaque constat inclut une
recommandation.

Contexte pris en compte : l'application est conçue pour un LAN domestique
(dashboard en lecture seule sur la base Lyrion). Les sévérités sont évaluées
dans ce contexte — elles montent d'un cran si l'instance est exposée au-delà du
réseau local.

## Suivi

| Point | Statut | Référence |
|---|---|---|
| S1 | **Risque accepté** (2026-07-09) — voir la note dans la section | `# nosec` documentés |
| S3 | **Corrigé** — validation du `coverid` + tests | `4f39be2` |
| S4 | **Corrigé** — cache LRU borné, purge à l'écriture, champs limités + tests | `7315f56` |
| S11 | **Corrigé** — pip-audit + bandit en CI, Dependabot | `07bfe81` |
| P1 | **Corrigé (minimal)** — `--threads 8`, worker unique conservé ; budget/semaphore optionnels | `71db928` |
| P2 | **Corrigé** — cache TTL 60 s single-flight sur `get_stats()` + tests | voir section |
| Autres | À traiter | — |

---

## 1. Sécurité

### S1 — Vérification TLS désactivée vers Lyrion (élevée)

`services/lyrion.py:5` désactive globalement les avertissements urllib3, et
toutes les requêtes vers `LYRION_HOST` passent `verify=False`
(`services/lyrion.py:13`, `:35`, `:37`). Tout trafic vers Lyrion (état des
players, covers) est donc vulnérable à une interception/altération
(machine-in-the-middle) dès que `LYRION_HOST` est en HTTPS.

**Recommandation :** rendre la vérification configurable
(`LYRION_VERIFY_SSL`, défaut activé) et ne désactiver qu'explicitement pour un
certificat auto-signé ; idéalement accepter un chemin de CA
(`REQUESTS_CA_BUNDLE`/paramètre `verify=<ca.pem>`). Supprimer le
`urllib3.disable_warnings()` global (il masque aussi d'autres avertissements du
process).

**Décision (2026-07-09) : risque accepté.** Dans le déploiement réel,
`LYRION_HOST` est en HTTP (la découverte LMS ne propose que du HTTP), donc
`verify=False` est inerte : il n'y a pas de certificat à vérifier sur ce canal.
Activer la vérification par défaut ne protégerait rien aujourd'hui et
casserait les installations HTTPS auto-signées à la mise à jour. Le choix est
documenté dans le code par les marqueurs `# nosec B501` (services/lyrion.py).
À réévaluer si `LYRION_HOST` passe un jour en HTTPS : la bonne approche sera
alors l'option CA (`verify=<ca.pem>`), pas un booléen.

### S2 — Aucune authentification, écoute sur 0.0.0.0 (élevée si exposé)

Aucune route n'est protégée et le serveur écoute par défaut sur toutes les
interfaces (`config.py:18`, `docker-compose.yml` publie `1111:1111`). Quiconque
joint le port peut : lire les statistiques de la bibliothèque, voir ce qui joue,
déclencher des recherches de paroles sortantes (`/lyrics.json`), télécharger
tout le contenu de `CUSTOM_DATA_DIR` (`/files/`), et récupérer n'importe quelle
cover via le proxy.

**Recommandation :** documenter clairement que l'app ne doit jamais être exposée
telle quelle (reverse proxy avec auth si accès distant), et/ou proposer un
token/basic-auth optionnel. À minima, permettre de binder sur une interface
précise via `HOST`.

### S3 — `coverid` non validé : le proxy cover peut atteindre d'autres URL du serveur Lyrion (moyenne)

`routes/nowplaying.py:37` accepte n'importe quelle chaîne comme `coverid`, qui
est interpolée telle quelle dans l'URL amont
(`services/lyrion.py:35` : `f"{host}/music/{coverid}/{name}"`). Un `coverid`
valant `..` produit `/music/../cover.jpg`, et selon la version de
Werkzeug/du client HTTP un `%2F` encodé peut permettre d'injecter des segments
de chemin complets — le proxy devient alors un accès same-origin à d'autres
endpoints du serveur Lyrion (pages d'admin/paramètres), avec mise en cache
navigateur 24 h (`Cache-Control: public, max-age=86400`).

**Recommandation :** valider le format avant l'appel amont — les coverids LMS
sont alphanumériques (id numérique ou hash hexadécimal). Par exemple rejeter en
404 tout `coverid` ne matchant pas `^[0-9a-fA-F]+$` (ou utiliser un converter
Flask `<int:...>`/regex dans la route).

### S4 — Cache de paroles en mémoire non borné, alimenté par des entrées client (moyenne)

`services/lyrics.py:52` : `_cache` est un dict sans limite de taille ni purge
périodique (les entrées expirées ne sont supprimées que si leur clé est relue,
`services/lyrics.py:56-63`). La clé de cache contient `artist`/`title` fournis
librement par le client (`routes/nowplaying.py:101-117`,
`services/lyrics.py:408`). Un client (ou un script) peut donc faire croître la
mémoire du process indéfiniment en variant les paramètres — déni de service par
épuisement mémoire, d'autant que gunicorn ne tourne qu'avec un seul worker.

**Recommandation :** borner le cache (LRU avec taille max, ou purge des entrées
expirées à chaque écriture + plafond d'entrées, p. ex. 1000). Limiter aussi la
longueur acceptée pour `artist`/`title`/`album`.

### S5 — `/lyrics.json` : relais non limité vers des services tiers (moyenne)

Chaque appel peut déclencher jusqu'à 3 fournisseurs externes (LRCLIB,
Musixmatch, Genius) avec des chaînes arbitraires, et `refresh=1` court-circuite
le cache (`routes/nowplaying.py:115`). Un client peut faire marteler ces API par
votre IP (risque de bannissement, consommation de bande passante).

**Recommandation :** rate-limiter l'endpoint (p. ex. quelques requêtes/minute
par IP, et un plafond global), et n'accepter `refresh=1` qu'avec parcimonie
(cooldown par piste).

### S6 — `/files/` sert tout type de fichier same-origin (basse)

`routes/custom.py:6-11` : `send_from_directory` protège bien contre la
traversée de chemin, mais tout fichier déposé dans `CUSTOM_DATA_DIR` (monté en
écriture dans `docker-compose.yml:32`) est servi sur l'origine du dashboard. Un
HTML/SVG malveillant qui y atterrit devient un XSS stocké sur l'origine (qui a
accès aux endpoints du dashboard).

**Recommandation :** ajouter sur ces réponses `X-Content-Type-Options: nosniff`
et `Content-Disposition: attachment` (ou au minimum `Content-Security-Policy:
sandbox`), ou restreindre les extensions servies à une liste blanche.

### S7 — `SECRET_KEY` par défaut (basse)

`config.py:5` retombe sur `"supersecretkey"` et `docker-compose.yml:15` propage
le même défaut. Aucune session/cookie signé n'est utilisé aujourd'hui, mais le
jour où une fonctionnalité en dépendra, elle sera forgeable silencieusement.

**Recommandation :** supprimer le défaut (générer une valeur aléatoire au
démarrage si absente, ou refuser de démarrer hors mode DEV), et retirer le
fallback du compose.

### S8 — En-têtes de sécurité HTTP absents (basse)

Aucune réponse ne porte `X-Content-Type-Options`, `X-Frame-Options`/
`frame-ancestors` ni de CSP. Le front insère par ailleurs des valeurs via
`innerHTML` (`static/nowplaying.js:912`) — aujourd'hui uniquement des nombres
issus de la base, donc pas exploitable en l'état, mais c'est un piège pour les
évolutions futures.

**Recommandation :** ajouter un `after_request` global posant `nosniff`,
`X-Frame-Options: SAMEORIGIN` et une CSP simple (`default-src 'self'` convient
presque : les scripts sont locaux, les images same-origin). Remplacer le
`innerHTML` de `renderStats` par des nœuds texte.

### S9 — Pas de limite de taille sur les contenus proxifiés (basse)

`fetch_cover`/`fetch_remote_cover` (`services/lyrion.py:35`, `:47`) chargent la
réponse entière en mémoire sans plafond. Une cover anormalement grosse (ou un
serveur amont malveillant/compromis) peut consommer beaucoup de RAM par requête.

**Recommandation :** `stream=True` + lecture plafonnée (p. ex. 10 Mo), et
vérifier que le `Content-Type` amont est bien `image/*` avant de le relayer.

### S10 — App Android : durcissements possibles (basse)

- `android:usesCleartextTraffic="true"` et préfixe `http://` par défaut
  (`AndroidManifest.xml:14`, `MainActivity.kt:112`) : assumé pour un LAN, mais
  tout le trafic (et le bridge JS `LyrionApp`) est alors altérable par un
  attaquant du réseau. Préférer une `network_security_config` limitant le
  cleartext aux domaines locaux configurés.
- `MainActivity.kt:196-204` : l'`Intent.parseUri` issu du contenu web ajoute
  bien `CATEGORY_BROWSABLE`, mais un intent explicite (avec `component=`)
  ignore les catégories. Ajouter `intent.component = null` et
  `intent.selector = null` avant `startActivity`.
- `android:allowBackup="true"` : l'URL du serveur part dans les sauvegardes ;
  acceptable, mais à désactiver si l'on veut être strict.

### S11 — Chaîne d'approvisionnement / CI (basse)

Les dépendances sont bien épinglées (`requirements.txt`), mais rien ne détecte
les CVE : pas de `pip-audit`/Dependabot, pas d'analyse statique sécurité
(`bandit`) dans `python-ci.yml`. Le `pip install` au démarrage du conteneur
(`docker-compose.yml:8`) télécharge aussi les paquets à chaque redémarrage, ce
qui élargit la fenêtre d'attaque réseau au runtime.

**Recommandation :** ajouter `pip-audit` (ou Dependabot) et `bandit -r .` à la
CI ; construire une vraie image Docker (voir P8).

---

## 2. Performance

### P1 — Famine de threads : 1 worker × 4 threads face à des requêtes longues (élevée)

`docker-compose.yml:8` lance gunicorn avec `-w 1 --threads 4`. Or une recherche
de paroles peut durer très longtemps : LRCLIB a un budget de 15 s **par appel**
et peut en enchaîner jusqu'à 3 (`get` + 2 `search`, `services/lyrics.py:109-136`),
puis Musixmatch (~11 s) puis Genius (~12 s) — plus d'une minute au pire, par
requête. Quatre recherches simultanées suffisent à occuper les 4 threads : le
dashboard entier ne répond plus (les polls `/now-playing.json` de tous les
clients échouent).

**Recommandation :** au choix (cumulables) —
- augmenter workers/threads (la base est en lecture seule, plusieurs workers
  sont sûrs ; seuls les caches in-process se dupliquent, ce qui est acceptable) ;
- imposer un budget global à `fetch_lyrics` (p. ex. 20 s toutes sources
  confondues) ;
- limiter le nombre de recherches web concurrentes (semaphore) pour préserver
  des threads pour les polls.

**Décision (2026-07-09) : corrigé en version minimale** — `--threads 4` →
`--threads 8`, en gardant un seul worker. Le worker unique est volontaire :
les caches in-process (paroles, futur cache stats) restent partagés entre
toutes les requêtes, hypothèse sur laquelle `services/lyrics.py` est
explicitement construit ; le travail étant presque entièrement I/O-bound, les
threads suffisent à doubler la capacité. Le scénario de saturation demande
plusieurs requêtes lentes simultanées — rare avec 1-3 clients ; le budget de
temps global et le semaphore sont rétrogradés en durcissements optionnels, à
reconsidérer seulement si un gel se produit en pratique.

### P2 — `get_stats()` : 4 agrégations lourdes, aucune mise en cache (élevée)

`services/database.py:92-256` scanne `tracks` × `alternativeplaycount` ×
`contributor_track` quatre fois. C'est exécuté à **chaque chargement de page**
(`routes/nowplaying.py:18`) et par **chaque client** toutes les 60 s
(`/stats.json`, `static/nowplaying.js:947`). Sur une grosse bibliothèque cela
peut prendre plusieurs centaines de ms de CPU/I-O par appel, multiplié par le
nombre de clients ouverts en permanence (l'app Android garde l'écran allumé).

**Recommandation :** cacher le résultat côté serveur avec un TTL (60 s suffit —
la base ne change qu'au fil des écoutes/scans), même mécanisme que le cache de
paroles. Gain immédiat : une seule exécution par minute quel que soit le nombre
de clients.

**Décision (2026-07-09) : corrigé.** `get_stats()` sert une copie cachée
pendant `STATS_TTL` (60 s), avec un verrou single-flight (deux clients
simultanés sur un cache expiré ne déclenchent qu'un seul recalcul). Effet le
plus visible : l'ouverture de la page ne paie plus les 4 agrégations avant le
premier rendu, sauf au pire une fois par minute.

### P3 — `/now-playing.json` : 1+N requêtes HTTP séquentielles vers Lyrion par poll (moyenne)

`get_active_now_playing()` (`services/lyrion.py:112-134`) fait `players` puis un
`status` **par player**, séquentiellement, à chaque poll de chaque client
(toutes les 5 s, `static/nowplaying.js:946`). Avec 4 players et 3 clients :
15 requêtes HTTP vers Lyrion toutes les 5 s. Chaque requête recrée en plus une
connexion TCP/TLS complète car aucun `requests.Session` n'est réutilisé.

**Recommandation :**
- utiliser un `requests.Session` module-level (keep-alive : supprime le
  handshake TCP/TLS répété — d'autant plus coûteux que TLS est en jeu) ;
- mutualiser entre clients avec un mini-cache TTL de 1-2 s sur le résultat de
  `get_active_now_playing()` ;
- optionnel : interroger d'abord le dernier player vu en train de jouer (dans
  la majorité des polls c'est encore lui), avant de re-énumérer.

### P4 — Les paroles complètes repartent à chaque poll de 5 s (moyenne)

`routes/nowplaying.py:29-34` joint `get_track_lyrics()` (requête SQLite +
connexion neuve) et le texte intégral des paroles à **chaque** réponse
`/now-playing.json`, même quand la piste n'a pas changé — plusieurs Ko répétés
toutes les 5 s par client, alors que le front ne s'en sert qu'au changement de
piste (`static/nowplaying.js:669-696`).

**Recommandation :** laisser le client passer la clé de piste courante
(`?known=<track_id>`) et n'inclure `lyrics` que si elle diffère ; ou déplacer la
lecture des paroles locales dans un endpoint séparé appelé au changement de
piste seulement.

### P5 — Connexion SQLite recréée à chaque requête (basse)

`services/database.py:7-23` ouvre `library.db`, fait un `ATTACH` de
`persist.db` et repose 3 PRAGMA (dont un mmap de 256 Mo) à chaque appel — et
`/now-playing.json` le fait toutes les 5 s par client via `get_track_lyrics`.
Le coût unitaire est modeste mais purement du gaspillage répété.

**Recommandation :** réutiliser une connexion par thread
(`threading.local()`), en gardant le mode read-only actuel ; ou au minimum ne
pas rouvrir la base pour `get_track_lyrics` quand `track_id` n'a pas changé
(couplé à P4).

### P6 — Proxy covers : pas de cache serveur, cover principale en pleine résolution (basse)

Chaque affichage de la mosaïque re-télécharge les vignettes depuis Lyrion pour
chaque client (le `Cache-Control` de `routes/nowplaying.py:51` n'aide que le
navigateur qui a déjà vu la cover). La cover du morceau en cours est par
ailleurs demandée en pleine résolution (`static/nowplaying.js:674` : pas de
`?size=`), ce qui peut représenter plusieurs Mo par piste pour un affichage
≤ 600 px.

**Recommandation :** demander une taille bornée pour la cover principale
(p. ex. `?size=512`, le canvas d'extraction de couleur n'a pas besoin de plus)
et ajouter un petit cache serveur (dict LRU borné ou en-tête `ETag` relayé).

### P7 — Front : re-scan DOM du karaoké toutes les 250 ms (basse)

`syncLyrics()` refait `querySelectorAll('.lrc-line')` et réécrit les classes de
**toutes** les lignes 4×/s (`static/nowplaying.js:382-411`, `:954-956`), plus le
repaint à chaque tick de progression. Pour des paroles longues (centaines de
lignes) cela se sent sur mobile.

**Recommandation :** mémoriser la NodeList à la construction (`setLyrics`) et
l'index actif précédent, et ne toucher que les 2-4 lignes dont l'état change.

### P8 — `pip install` à chaque démarrage du conteneur (basse)

`docker-compose.yml:7-8` installe les dépendances au lancement : démarrage lent,
dépendance au réseau/PyPI à chaque redémarrage (`restart: unless-stopped` peut
boucler hors-ligne), et surface supply-chain au runtime (cf. S11).

**Recommandation :** ajouter un `Dockerfile` (image construite avec les
dépendances) et pointer le compose dessus ; le mode dev peut garder le montage
du code.

### P9 — Polls front sans garde de chevauchement (info)

`poll()` est déclenché toutes les 5 s sans vérifier qu'un appel est déjà en vol
(`static/nowplaying.js:890-904`, `:946`) : si le serveur ralentit (cf. P1), les
requêtes s'empilent et aggravent la congestion.

**Recommandation :** un booléen `inFlight` (ou `AbortController` sur le poll
précédent) suffit.

---

## 3. Points positifs relevés

- SQL systématiquement paramétré (`services/database.py`) — pas d'injection.
- Bases ouvertes en lecture seule (`mode=ro`) et montées `:ro` dans le compose.
- `send_from_directory` (et non un `open()` maison) pour `/files/` : la
  traversée de chemin est déjà couverte.
- `/cover/remote.jpg` résout l'URL côté serveur depuis Lyrion au lieu de la
  prendre du client — pas de proxy d'images ouvert (`routes/nowplaying.py:55-72`).
- `size` de `/cover/<id>.jpg` borné (16–512) et `limit` de
  `/mosaic-covers.json` borné (1–200).
- Timeouts posés sur tous les appels `requests` sortants.
- Le front n'utilise quasiment que `textContent` ; les données Lyrion (titres,
  artistes) ne passent pas par `innerHTML`.
- Dépendances épinglées, code monté en lecture seule dans le conteneur, healthcheck présent.
- WebView Android : navigation restreinte à l'origine du dashboard, liens
  externes délégués au système, bridge JS minimal (2 méthodes sans données).

## 4. Priorités suggérées

(mis à jour au fil des corrections — voir le tableau de suivi en tête)

1. ~~S1 (TLS)~~ risque accepté · ~~S3 (validation `coverid`)~~ ✅ · ~~S4
   (bornage du cache)~~ ✅ · ~~S11 (CI sécurité)~~ ✅ · ~~P1 (threads)~~ ✅ ·
   ~~P2 (cache stats)~~ ✅
2. **S5** (rate limit `/lyrics.json`) : protège vos accès aux API tierces.
3. Le reste (en-têtes HTTP, P3-P9, durcissements Android) au fil de l'eau.
