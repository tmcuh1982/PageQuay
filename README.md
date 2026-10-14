# PageQuay (PQ)

Passerelle Web privée et auto-hébergée : un projet possède son propre profil Chromium persistant, ses onglets, ses clés API et ses contenus temporaires. API FastAPI REST + WebSocket et administration HTML/CSS/JavaScript locaux, sans build frontend, Docker ni abonnement.

**Version 0.2 — recherche paginée, recette externe partielle.** Consulter [le rapport de tests](docs/testing/REPORT.md) pour distinguer les vérifications exécutées et les limites. Les sources initiales sont conservées dans `docs/definition/`. L'état de travail et les choix sont dans `memory.md` et `decisions.md`.

## Documentation et état du projet

| Document | Utilité |
| --- | --- |
| [État actuel](docs/STATUS.md) | Fonctionnalités livrées, tests effectués et étapes restant à valider |
| [Architecture](docs/ARCHITECTURE.md) | Composants, flux, profils et contrôle réseau |
| [Extraction JSON et DOM](docs/EXTRACTION.md) | Contrat structuré, exemples, bornes et limites des pages complexes |
| [Exploitation](docs/OPERATIONS.md) | macOS, LaunchAgent, accès Tailscale, sauvegarde et dépannage |
| [Publication GitHub](docs/PUBLISHING.md) | Synchronisation du dossier local et du dépôt public |
| [Sécurité](SECURITY.md) | Protections et limites du MVP |
| [Rapport de tests](docs/testing/REPORT.md) | Résultats observés et recettes non exécutées |
| [Mémoire](memory.md) / [Décisions](decisions.md) | Suivi du développement et choix techniques |
| [Recherche paginée](docs/SEARCH_API.md) | Continuations DuckDuckGo, quotas, idempotence et exemple ProjectX |
| [Navigation et portée](docs/NAVIGATION_SCOPE.md) | Redirections, attente Cloudflare, reprise humaine et refus scope_changed (0.2.2) |
| [Correctif iframe KUKA](docs/KUKA_FRAME_FIX.md) | Preuves réelles, régressions et version corrective 0.2.1 |
| [Acquisition exacte](docs/ACQUISITION.md) | Navigation attestée, URL stricte, robots, diagnostics iframe et client serveur |
| [OpenAPI](docs/openapi.json) | Contrat API client 0.2.2, également disponible via `/openapi.json` |

La [release 0.2.2](https://github.com/tmcuh1982/PageQuay/releases/tag/v0.2.2), ses paquets Python et leurs sommes SHA-256 sont publiés le 13 octobre 2026. Le MVP et sa documentation sont publiés sur [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), branche `main`. Le dossier de développement suit cette branche ; les données et captures locales sont exclues du dépôt public. Le statut détaillé et la procédure de synchronisation sont dans les documents ci-dessus.

## Installation macOS

Python 3.12–3.14 et [uv](https://docs.astral.sh/uv/) sont nécessaires pour la procédure verrouillée. Le développement initial utilise Python 3.14 sur Apple Silicon. Pour une nouvelle installation, dans un terminal :

```sh
git clone https://github.com/tmcuh1982/PageQuay.git
cd PageQuay
./scripts/install_macos.sh
.venv/bin/pq init-admin
./scripts/start.sh
```

Le programme demande un identifiant et un mot de passe d'au moins 14 caractères dans un terminal interactif. Aucun compte initial ou mot de passe par défaut. Ouvrir ensuite [la console locale](http://127.0.0.1:8765/admin).

Avec une copie déjà présente, commencer dans sa racine sans relancer `git clone`.

Le script installe les dépendances et Chromium ; `uv.lock` conserve les versions exactes des dépendances Python. Dans l'environnement de développement, cette installation a déjà été vérifiée. L'initialisation de l'administrateur reste à effectuer par chaque opérateur. La commande `pq serve` applique les migrations SQL au démarrage, lie **uniquement `127.0.0.1`** sur deux ports (8765 pour la console locale, 8766 pour l’API locale et un éventuel accès Tailscale), utilise un seul processus et désactive les access logs. Ctrl-C arrête proprement le service et conserve les profils.

Sans uv, le script utilise un venv et `pip install -e '.[dev]'` ; cette voie respecte les bornes du pyproject, mais pas les versions exactes du lockfile.

Pour placer les données dans le projet pendant le développement :

```sh
export PQ_DATA_DIR="$PWD/.data"
.venv/bin/pq init-admin
./scripts/start.sh
```

Ne changez pas de dossier de données entre l'initialisation et le démarrage. `.env` est lu à la racine du projet ; `.env.example` décrit la configuration sans secrets. Le chemin par défaut est `~/Library/Application Support/PageQuay/` avec SQLite, `profiles/`, `artifacts/` et `logs/` séparés. Aucun profil Chrome personnel n'est réutilisé.

Le navigateur utilise un port CDP explicite, non nul, lié à `127.0.0.1` et choisi à chaque lancement. Un relais local conserve le contexte persistant et toutes les protections Playwright (sandbox, proxy filtrant, interceptions, blocage des Service Workers et téléchargements). Le pipe interne de Playwright se termine au relais ; Chrome reçoit uniquement le port CDP. Ce port de contrôle local n’est pas publié par l’API et se ferme avec le navigateur.

Les connexions WebSocket des pages sont refusées par une règle de proxy native de Chrome : HTTP/HTTPS passent par le proxy filtrant, et la catégorie `socks=` (« autres proxys », utilisée par Chrome pour `ws://` et `wss://`) pointe vers un second port local qui refuse toute connexion sans résoudre de destination. Aucun repli direct n’est configuré. Ce contrôle couvre aussi les frames, fenêtres secondaires et workers ; l’objet JavaScript `WebSocket` reste natif. Le WebSocket de commande de l’API PageQuay reste disponible. Voir les [règles de proxy WebSocket de Chromium](https://chromium.googlesource.com/chromium/src/+/HEAD/net/docs/proxy.md#mapping-websockets-urls-to-a-proxy).

`PQ_BROWSER_CHANNEL=chrome` sélectionne Google Chrome installé sur macOS ; `chromium` (défaut) conserve le navigateur fourni par Playwright, dont le binaire peut se nommer « Google Chrome for Testing ».

Version 0.2.4 : [notes de release](docs/releases/0.2.4.md), [transport navigateur et recette Music Store](docs/BROWSER_TRANSPORT.md).

## Utilisation

1. Créer `projectx` et `projet-b` dans **Projets / Profils**.
2. Démarrer leurs navigateurs : deux contextes persistants indépendants peuvent rester ouverts ensemble. Le mode visible est le défaut ; une session macOS graphique ouverte est nécessaire.
3. Créer une clé dans **Clés API**, choisir projet, droits et expiration. Copier le secret affiché une seule fois. Les droits initiaux sont `search:read` et `content:read` ; la navigation et les actions nécessitent `browser:interact`, les listes `browser:read`, les captures `screenshot:read`.
4. Utiliser **Recherche** ou **Sessions / Onglets** pour tester manuellement. Les opérations longues créent un job ; son état et son résultat apparaissent dans la console.
5. En cas de challenge, intervenir dans la fenêtre Chromium sur le Mac puis confirmer **Reprendre**. L'onglet reste ouvert ; aucune résolution automatique.

Dans **Paramètres → Accès local**, définir le **Port API local** puis cliquer **Enregistrer le port local**. Ce réglage fonctionne sans Tailscale et permet de choisir un port libre quand un autre service tourne sur le même Mac. Les ports occupés et le port de la console sont refusés. Redémarrer le service pour activer le nouveau port, puis adapter les clients locaux ; le port actif et le changement en attente sont affichés séparément. Pour configurer le port avant le premier démarrage, utiliser `PQ_API_PORT` dans `.env`. Voir [le port API local](docs/OPERATIONS.md#port-api-local-depuis-la-console).

Dans **Paramètres → Accès externe**, définir le **Port HTTPS externe** puis cliquer **Appliquer le port HTTPS** pour changer le port utilisé par les clients Tailscale (443 par défaut). L’adresse active est affichée ; par exemple, le port 8443 donne `https://mac-mini.votre-tailnet.ts.net:8443`. Le changement est immédiat et persistant dans Serve. Mettre à jour les clients et les règles d’accès du tailnet. La destination API locale (`PQ_API_PORT`, 8766 par défaut) et le port de la console restent distincts. Tailscale connecté, Serve/HTTPS activé et hostname dans `PQ_ALLOWED_HOSTS` sont requis ; un port occupé, partagé ou publié via Funnel est refusé. Voir [l’exploitation réseau](docs/OPERATIONS.md#port-https-externe-depuis-la-console).

**Port alternatif recommandé : 8443**, facile à retenir pour un accès HTTPS. **8080 fonctionne aussi en HTTPS** si Serve est configuré ainsi, mais évoque généralement HTTP par convention. Le réglage est global, indépendant des projets ; cette recommandation ne modifie pas le port actif.

Dans **Projets / Profils** ou **Sessions / Onglets**, **Minimiser** réduit les fenêtres du navigateur du projet dans le Dock ; **Restaurer** les réaffiche. Les tâches distantes continuent pendant la minimisation. Une capture réaffiche brièvement la fenêtre pour permettre son rendu, puis la minimise à nouveau. Une fenêtre minimisée avec le bouton jaune macOS reste minimisée après l’ouverture d’un nouvel onglet distant. Dans **Paramètres**, cocher **Démarrer les fenêtres minimisées** puis enregistrer pour appliquer ce comportement au prochain démarrage ; `browser_start_minimized` peut aussi être surchargé par projet dans sa configuration JSON. Le mode sans interface (`headless`) n’a pas de fenêtre à minimiser. Pour un challenge, restaurer la fenêtre puis intervenir manuellement.

Dans **Créer une clé API**, « Requêtes / minute » limite les appels effectués avec cette clé sur 60 secondes : lancer une opération, suivre son job et télécharger son résultat comptent séparément. Le plafond effectif est le minimum entre la valeur de la clé et celle du projet, affichée dans le formulaire. Au dépassement, l’API renvoie 429. L’expiration est désactivée par défaut : cocher **Définir une date d’expiration** pour choisir une échéance ; décocher efface et désactive le champ. La liste affiche explicitement **Sans expiration** pour les clés concernées.

Dans la liste **Clés de vos projets**, **Modifier la sécurité** ouvre un formulaire prérempli : nom, autorisations, quota et expiration sont modifiables sans changer le secret ni le projet. Enregistrer applique les nouveaux réglages ; retirer un droit annule les jobs qui en dépendent. Une clé révoquée ne peut pas être modifiée. Une clé expirée peut recevoir une échéance future ou revenir à « Sans expiration ». **Annuler** conserve les réglages existants.

La révocation interrompt les jobs de la clé et ferme ses WebSockets lors de la revalidation suivante (au plus une seconde). La rotation crée un nouveau secret et révoque immédiatement l'ancien. Une clé API n'ouvre jamais la console administrateur.

## API v1

Toutes les routes de cette table utilisent `Authorization: Bearer <clé>` et contrôlent l'appartenance du projet et de la ressource. Un job se lit seulement avec son droit d'origine ; son contrôle est réservé à la clé qui l'a créé ou à l'administrateur.

| Méthode / chemin sous `/v1/projects/{slug}` | Droit | Résultat |
| --- | --- | --- |
| GET `/key-info` | Clé du projet, aucun scope supplémentaire | Droits, expiration et quota effectif de la clé appelante |
| POST `/search` | `search:read` | 202, job de recherche |
| POST `/tabs` | `browser:interact` | 202, job d'ouverture/navigation |
| GET `/tabs`, GET `/tabs/{id}` | `browser:read` | Liste / état |
| DELETE `/tabs/{id}` | `browser:interact` | Fermeture, conflit si opération active |
| POST `/tabs/{id}/navigate` | `browser:interact` | 202, job |
| POST `/tabs/{id}/actions` | `browser:interact` | 202, job |
| GET `/cookie-policy` | `browser:read` | Choix automatique du projet |
| PUT `/cookie-policy` | `browser:interact` | Enregistrement du choix automatique |
| GET `/tabs/{id}/content?format=text\|html\|links\|metadata\|structured` | `content:read` | 202, job et artefact temporaire |
| GET `/tabs/{id}/screenshot` | `screenshot:read` | 202, capture PNG du viewport |
| GET `/artifacts/{id}` | Droit associé à l'artefact | Téléchargement protégé |
| GET `/jobs/{id}` | Droit du job | État, résultat ou erreur |
| POST `/jobs/{id}/cancel`, `/resume` | Droit du job + clé d'origine | Annulation / reprise |
| POST `/ws-ticket` | Clé du projet | Ticket à usage unique, 30 s |
| WS `/events` | Ticket dans le **premier message** | Événements filtrés et commandes bornées |

`GET /health/live` et `/health/ready` ne renvoient que l'état minimal. Le contrat client `/openapi.json` est disponible sur le port API, y compris via HTTPS privé ; les routes admin en sont exclues. `/docs` reste réservé au transport admin en mode `PQ_DEVELOPMENT=true`. Le même contrat est exporté dans `docs/openapi.json`.

### Informations de la clé appelante

`GET /v1/projects/{slug}/key-info` permet à un client de découvrir ses propres réglages avec son Bearer habituel. Exemple local sur le port API :

```sh
curl --fail-with-body http://127.0.0.1:8766/v1/projects/projectx/key-info \
  -H "Authorization: Bearer $PQ_API_KEY"
```

Réponse illustrative après le premier appel avec une clé à 60 requêtes/minute :

```json
{
  "key_id": "identifiant-de-la-cle",
  "name": "Mon application",
  "prefix": "pq_exemple",
  "project": {"slug": "projectx", "name": "ProjectX"},
  "scopes": ["content:read", "search:read"],
  "expires_at": null,
  "rate_limit": {
    "configured_requests_per_minute": 60,
    "project_requests_per_minute": 60,
    "effective_requests_per_minute": 60,
    "window_seconds": 60,
    "remaining_requests": 59,
    "resets_at": 1800000060.0
  }
}
```

Le client doit utiliser `effective_requests_per_minute` : c’est le minimum entre quota de la clé et plafond du projet. `remaining_requests` tient compte de cet appel et de tous les autres appels REST acceptés avec la même clé, y compris le suivi des jobs et les téléchargements. La fenêtre fixe de 60 secondes commence au premier appel accepté ; `resets_at` est son échéance en secondes Unix UTC. Le solde décrit l’instant de la réponse, sans réserver de requêtes pour le client. L’appel renvoie 429 si le quota est déjà épuisé.

`expires_at` est une date en secondes Unix UTC ou `null` pour **sans expiration**. `scopes` contient les droits accordés, détaillés dans la table des routes. Les réglages modifiés depuis l’administration apparaissent au prochain appel ; une clé expirée/révoquée renvoie 401, une clé d’un autre projet ou un projet désactivé renvoie 403. Aucun secret ni hash n’est retourné. Les limites propres aux opérations (captures, moteurs de recherche) et aux messages WebSocket s’appliquent en plus de ce quota REST. Le client Python autonome [key_info.py](examples/key_info.py) utilise `PQ_URL`, `PQ_PROJECT` et `PQ_API_KEY`.

Actions : `click`, `fill`, `select`, `scroll`, `wait_for_selector`, `wait_for_navigation`, `validate_cookies`. `wait_for_navigation` attend l'état de chargement de la navigation courante ; pour un clic qui navigue, le clic Playwright attend lui-même sa navigation. Au plus 20 actions, sélecteurs et valeurs bornés, délais par action limités. Aucun `eval`, CDP, shell, upload ou chemin de fichier fourni par le client.

**Valider cookies** détecte une bannière de consentement et clique sur **Refuser** par défaut. Appel ponctuel REST (202, puis lecture du job), également disponible dans la commande WebSocket `actions` :

```http
POST /v1/projects/{slug}/tabs/{tab_id}/actions
Authorization: Bearer <clé>
Content-Type: application/json

{"actions":[{"type":"validate_cookies","value":"reject","timeout_ms":5000}]}
```

`value` accepte `reject` ou `accept` ; son omission signifie `reject`. Un `selector` facultatif désigne le **conteneur de la bannière**, dont le texte doit toujours concerner les cookies. Le bouton doit avoir un libellé exact reconnu pour le choix demandé ; le refus ne bascule jamais vers l'acceptation si le site ne propose pas de refus direct.

Pour répéter le choix lors des visites suivantes du projet, enregistrer une règle persistante :

```http
PUT /v1/projects/{slug}/cookie-policy
Authorization: Bearer <clé>
Content-Type: application/json

{"choice":"reject","timeout_ms":1500}
```

La règle est désactivée par défaut (`choice: null`). `choice: "accept"` active l'acceptation ; `choice: null` désactive les clics automatiques. Elle s'applique aux ouvertures et navigations REST/WebSocket, aux pages de recherche et à leur pagination native, ainsi qu'après les actions `click` et `wait_for_navigation`. Elle est commune aux clés du projet, conservée après redémarrage et relue à chaque opération. L'enregistrement ne clique pas immédiatement dans les onglets ouverts et ne réécrit pas les cookies existants. Les navigations manuelles hors API et les bannières apparaissant après le délai nécessitent l'action ponctuelle. Le budget automatique est borné par le temps restant de navigation ; `timeout_ms` accepte 100 à 10 000 ms.

Le résultat du job contient `cookie_consent` : objet pour une navigation automatique, liste avec `action_index` pour des actions (et `automatic: true` pour une application de la règle). Statuts : `clicked` (clic effectué, sans garantie que le site ait enregistré le consentement), `not_found`, `choice_unavailable`, `ambiguous`, `scan_limit`, `timeout`, `unavailable`. Une bannière absente ou non reconnue ne fait pas échouer la visite. Le choix et le statut sont aussi consignés dans l'audit `function.validate_cookies`.

Détection bornée à huit frames et 32 conteneurs/boutons par frame, incluant les iframes visibles et le Shadow DOM ouvert. Libellés courants français, anglais, allemand et polonais ; les CMP personnalisées et les parcours nécessitant plusieurs écrans de préférences ne sont pas garantis. Aucun clic si plusieurs boutons correspondent, si l'inventaire dépasse les bornes ou si le choix demandé manque. Les contrôles de challenge, d'autorisation et de réseau restent appliqués.

`format=structured` renvoie un JSON versionné à partir du **DOM rendu** : blocs ordonnés, listes imbriquées, tableaux HTML/ARIA, liens, images, contrôles/formulaires, métadonnées/JSON-LD et documents des iframes. Les Shadow DOM ouverts et leurs slots sont parcourus. `include_dom=true` ajoute un arbre DOM filtré avec IDs de nœuds ; cette option est réservée au format `structured`. Les valeurs des input/textarea, scripts, styles et contenus cachés sont exclus. Pour les applications qui chargent des éléments plus tard, utiliser d'abord les actions `wait_for_selector`/scroll/click nécessaires, puis extraire à nouveau. Voir [le contrat et les limites](docs/EXTRACTION.md), [l'exemple JSON](docs/testing/structured-complex-compact.json) et [l'exemple avec arbre](docs/testing/structured-complex.json).

Erreurs structurées `{"error":{"code":"…","message":"…","request_id":"…"}}`. Codes : `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_INPUT`, `NOT_FOUND`, `RATE_LIMITED`, `NAVIGATION_BLOCKED`, `TIMEOUT`, `BROWSER_CRASHED`, `CHALLENGE_REQUIRED`, `CONFLICT`, `INVALID_CURSOR`, `CURSOR_EXPIRED`, `CURSOR_USED`, `INTERNAL_ERROR`, `UPSTREAM_CHANGED`, `UPSTREAM_UNAVAILABLE`. Les erreurs asynchrones apparaissent dans le job. Les états sont `queued`, `running`, `waiting_for_human`, `completed`, `failed`, `cancelled`. Un redémarrage de service marque les jobs interrompus comme échoués ; aucune action n'est rejouée automatiquement.

Exemple curl (clé saisie sans l'inscrire dans l'historique) :

```sh
read -s PQ_API_KEY
export PQ_API_KEY
curl --fail-with-body http://127.0.0.1:8765/v1/projects/projectx/search \
  -H "Authorization: Bearer $PQ_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"robotique agricole","engine":"duckduckgo","limit":5}'
unset PQ_API_KEY
```

Les exemples Python et WebSocket sont dans `examples/`. Ne jamais transmettre de clé dans une URL. Le ticket WebSocket est envoyé en JSON `{"ticket":"…"}` sous cinq secondes ; la connexion dure au plus dix minutes et supporte ping/pong, navigation, actions, reprise et annulation avec les mêmes contrôles que REST.

## Recherche et rétention

DuckDuckGo, Brave Search et Google disposent d’adaptateurs séparés testés sur fixtures. `auto` autorise le repli/la fusion ; un moteur explicite ne bascule jamais vers un autre. DuckDuckGo accepte un `cursor` opaque pour rendre le reliquat d’une page puis suivre son formulaire natif « Next ». `limit` reste un maximum de résultats par job, plafonné à 10 par défaut ; pour autoriser 50, régler `search_max_results=50` dans le projet. Le résultat indique `next_cursor`, `has_more` (true/false/null), moteurs, quantités, rangs, URL exacte et motif d’arrêt. Les chaînes sont bornées à 10 pages / 200 résultats / 15 minutes par défaut. Les essais réels récents ont rencontré un CAPTCHA ; trois pages natives sont validées en simulation, pas encore sur DuckDuckGo réel.

Le quota **PageQuay** est de 6 tentatives de page par fenêtre fixe de 60 secondes pour chaque couple projet/moteur, partagé par les clés et l’admin ; il ne décrit pas un quota DuckDuckGo. Les reliquats stockés ne consomment pas de tentative moteur. Le quota REST par clé reste distinct et compte notamment le suivi des jobs. HTTP 429 fournit `Retry-After` lorsqu’il est connu ; les erreurs des jobs indiquent portée/cause/délai, reprise possible et résultats partiels. `Idempotency-Key` sur POST /search permet de retrouver la même opération pendant 24 heures, y compris après redémarrage. Les onglets internes sont fermés après succès, échec ou annulation.

Pour cibler l’actualité avec DuckDuckGo, ajouter `region` (par exemple `fr-fr`, `pl-pl`, `us-en` ou `wt-wt`) et `time_range` (`any`, `day`, `week`, `month`, `year`). La console **Recherche** propose les menus **Pays / région** et **Période** lorsque DuckDuckGo est sélectionné. Exemple : `{"query":"robot agriculture","engine":"duckduckgo","region":"fr-fr","time_range":"week"}`. Les filtres restent identiques dans les continuations ; une page récente peut néanmoins raconter un événement ancien. Les autres moteurs et `auto` refusent les filtres explicites.

Contrat et exemples : [SEARCH_API](docs/SEARCH_API.md), [OpenAPI](docs/openapi.json), [client Python serveur pour plusieurs requêtes](examples/search_duckduckgo.py). Le schéma client est également disponible sur `GET /openapi.json` via le port API/HTTPS privé. Les paramètres régionaux sont transmis à Google et DuckDuckGo sans garantie de classement. Les publicités explicitement identifiables restent filtrées, les autres types restent `uncertain`. Aucun solveur CAPTCHA, spoofing ni rotation d’identité.

| Opération / durée | Effet |
| --- | --- |
| TTL du contenu (60 min par défaut) | Expire les artefacts et efface les résultats de jobs, sans toucher aux cookies |
| Rétention des artefacts (24 h max par défaut) | S'applique avec le TTL le plus court ; quota disque par projet |
| Inactivité navigateur (30 min) | Ferme après drainage des jobs, conserve le profil |
| Soft restart (désactivé par défaut) | Ferme puis relance le même répertoire, différé pendant les jobs |
| Hard reset manuel | Intention serveur éphémère + deux confirmations ; efface uniquement ce profil |
| Audit (30 jours) | Purge le journal et l'historique ancien des jobs |

La maintenance passe toutes les 30 secondes. La consultation d'un artefact vérifie son expiration immédiatement. **Purger contenus** efface tous les contenus temporaires du projet, sans fermer le navigateur. Aucun reset destructeur automatique ni snapshot de session dans ce MVP. La durée de validité des cookies distants reste décidée par les sites.

La console **Audit** affiche les URL visitées, les ressources reçues avec leur taille en Ko, les fonctions appelées, les codes HTTP, les destinations de redirection et le temps d’exécution des fonctions, jobs et requêtes réseau en ms ou s. Les durées des jobs excluent la file d’attente et incluent l’attente humaine ; les lignes historiques sans mesure affichent « — ». Les clics de pagination reconnus et les formulaires natifs DuckDuckGo portent le libellé **next page** avec l’URL obtenue. Filtrer par projet, type, action, statut, dates avec heures ou job ; le menu Job propose les 200 opérations récentes et cliquer sur un job rassemble ses événements. La grille, le menu Job et les filtres affichent les dates dans le même fuseau local du navigateur ; le stockage et les paramètres de requête restent en UTC. Les boutons **last 10 min**, **last hour** et **Today** appliquent immédiatement une période, en conservant les autres filtres ; Today commence à minuit local. Les tailles correspondent au corps de réponse encodé mesuré par Playwright (1 Ko = 1 024 octets), hors en-têtes ; les mesures indisponibles sont signalées. Les paramètres d’URL et fragments sont conservés et affichés en clair, avec leur encodage d’origine ; les identifiants de connexion intégrés à l’URL sont retirés. Cet audit reste réservé à l’admin locale. Les anciennes valeurs enregistrées comme `[masque]` ne peuvent pas être reconstituées. Les anciens événements encore dans les limites de rétention restent disponibles sans détails rétroactifs.

L’audit est écrit par un worker dédié avec files, quotas et volume bornés. Une alerte indique les événements omis ou purgés et les erreurs d’écriture. Les histogrammes utilisent des compteurs séparés pour conserver les totaux API lorsque le détail est omis ; les dimensions projet/clé peuvent être regroupées si leur capacité est atteinte. Voir [les budgets de ressources](docs/OPERATIONS.md#budgets-de-ressources).

## Tests et développement

```sh
uv sync --frozen --extra dev
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
.venv/bin/pytest tests/test_browser.py tests/test_ui.py --browser --headed -q
.venv/bin/pytest tests/test_structured.py --browser --headed -q
.venv/bin/pytest tests/test_live_search.py --live -q -s
```

Les tests réels ouvrent des navigateurs de test et un serveur localhost. L'exception LAN est injectée uniquement dans leur dépendance réseau et n'est pas configurable dans le service de production. Sans `--browser`, les tests Chromium sont explicitement ignorés. `--live` est un diagnostic extérieur : les fichiers `docs/testing/duckduckgo-live.json` et `docs/testing/google-live.json` sont générés localement et exclus du dépôt public. Lire [le rapport versionné](docs/testing/REPORT.md) pour leurs résultats ; le succès d'un test de diagnostic ne signifie pas que le moteur a répondu avec des résultats.

Pour tester Google depuis un autre Mac une fois le service privé configuré, copier `examples/probe_google.py` sur ce Mac puis lancer `python3 probe_google.py --url https://HOSTNAME-PQ --project SLUG`. Le client utilise uniquement la bibliothèque standard ; il demande la clé de façon masquée (ou lit `PQ_API_KEY`). Scopes requis : `search:read`, `browser:interact`, `content:read`. Le rapport `pagequay-google-probe.json` identifie la machine cliente ; en cas de succès, le texte téléchargé est enregistré dans `pagequay-google-probe.txt`. Il s'arrête sur un challenge humain et sort avec code 1 si le parcours n'aboutit pas. HTTPS ou HTTP loopback via tunnel SSH uniquement ; ce client n'installe pas le service ni Tailscale Serve.

Pour une recette jetable depuis le MacBook Air, son alias SSH `macmini-codex` permet de lancer directement :

```sh
ssh macmini-codex 'cat Documents/Codex/PageQuay/examples/probe_via_ssh.py' | python3 - --human
```

Le dossier distant par défaut est `Documents/Codex/PageQuay`, relatif au home SSH ; utiliser `--remote-root /chemin/vers/PageQuay` et adapter le chemin du `cat` si nécessaire. Le mini doit avoir une session graphique ouverte et son port loopback 18766 disponible. Le client crée un tunnel loopback et une instance PQ temporaire avec profil/clé isolés, sans configuration admin ni Serve. Avec `--human`, intervenir manuellement dans Chromium sur le mini si Google demande un CAPTCHA, puis taper `reprendre` dans le Terminal de l'Air ; `annuler` termine le diagnostic. Le rapport est enregistré sur l'Air et recopié sur le mini dans `docs/testing/macbook-air-google.json`, avec `.txt` si le contenu a été téléchargé. Le tunnel et l'instance sont fermés à la fin ; durée maximale du service 15 minutes. Sans `--human`, le client rapporte le blocage immédiatement. La clé n'est affichée ni ajoutée aux arguments ; elle est transmise par SSH et l'environnement du sous-processus client. La commande distante demeure à exécuter ; le contrôle local de ce serveur est dans `docs/testing/ssh-probe-local.json`.

Ajouter `--format structured` à la commande Air pour récupérer `macbook-air-google.content.json` sur le mini ; ajouter aussi `--include-dom` pour l'arbre filtré. Les deux clients Python acceptent ces options. Le fichier de rapport demeure distinct du contenu téléchargé.

Structure : `src/pagequay/` contient `api`, `admin`, `auth`, `browser`, `profiles`, `search`, `retention`, `jobs`, `storage`, `settings`, `events`, `artifacts`, templates et assets. `src/pagequay/migrations/` contient les migrations SQL empaquetées ; `tests/` contient la recette reproductible. SQLite standard, sans ORM/Alembic : choix explicite dans `decisions.md`.

## Exploitation

Voir [macOS, LaunchAgent, Tailscale et sauvegardes](docs/OPERATIONS.md) et [la politique de sécurité](SECURITY.md). Les profils contiennent des secrets locaux ; ils ne sont pas chiffrés par l'application. Aucun réglage d'énergie, service launchd, ouverture de port, tunnel ou accès public n'est installé automatiquement.

Références : [Playwright et profils persistants](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context), [sandbox Chromium](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-option-chromium-sandbox), [WebSockets FastAPI](https://fastapi.tiangolo.com/advanced/websockets/), [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve).
