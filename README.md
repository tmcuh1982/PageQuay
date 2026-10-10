# PageQuay (PQ)

Passerelle Web privée et auto-hébergée : un projet possède son propre profil Chromium persistant, ses onglets, ses clés API et ses contenus temporaires. API FastAPI REST + WebSocket et administration HTML/CSS/JavaScript locaux, sans build frontend, Docker ni abonnement.

**Version 0.1 — MVP fonctionnel, recette partielle.** Consulter [le rapport de tests](docs/testing/REPORT.md) pour distinguer les vérifications exécutées et les limites. Les sources initiales sont conservées dans `docs/definition/`. L'état de travail et les choix sont dans `memory.md` et `decisions.md`.

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
| [OpenAPI](docs/openapi.json) | Contrat API exporté |

Au 10 octobre 2026, le MVP et sa documentation sont publiés sur [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), branche `main`. Le dossier de développement suit cette branche ; les données et captures locales sont exclues du dépôt public. Le statut détaillé et la procédure de synchronisation sont dans les documents ci-dessus.

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

Le script installe les dépendances et Chromium ; `uv.lock` conserve les versions exactes des dépendances Python. Dans l'environnement de développement, cette installation a déjà été vérifiée. L'initialisation de l'administrateur reste à effectuer par chaque opérateur. La commande `pq serve` applique les migrations SQL au démarrage, lie **uniquement `127.0.0.1`**, utilise un seul processus et désactive les access logs. Ctrl-C arrête proprement le service et conserve les profils.

Sans uv, le script utilise un venv et `pip install -e '.[dev]'` ; cette voie respecte les bornes du pyproject, mais pas les versions exactes du lockfile.

Pour placer les données dans le projet pendant le développement :

```sh
export PQ_DATA_DIR="$PWD/.data"
.venv/bin/pq init-admin
./scripts/start.sh
```

Ne changez pas de dossier de données entre l'initialisation et le démarrage. `.env` est lu à la racine du projet ; `.env.example` décrit la configuration sans secrets. Le chemin par défaut est `~/Library/Application Support/PageQuay/` avec SQLite, `profiles/`, `artifacts/` et `logs/` séparés. Aucun profil Chrome personnel n'est réutilisé.

## Utilisation

1. Créer `universrobot` et `projet-b` dans **Projets / Profils**.
2. Démarrer leurs navigateurs : deux contextes persistants indépendants peuvent rester ouverts ensemble. Le mode visible est le défaut ; une session macOS graphique ouverte est nécessaire.
3. Créer une clé dans **Clés API**, choisir projet, droits et expiration. Copier le secret affiché une seule fois. Les droits initiaux sont `search:read` et `content:read` ; la navigation et les actions nécessitent `browser:interact`, les listes `browser:read`, les captures `screenshot:read`.
4. Utiliser **Recherche** ou **Sessions / Onglets** pour tester manuellement. Les opérations longues créent un job ; son état et son résultat apparaissent dans la console.
5. En cas de challenge, intervenir dans la fenêtre Chromium sur le Mac puis confirmer **Reprendre**. L'onglet reste ouvert ; aucune résolution automatique.

La révocation interrompt les jobs de la clé et ferme ses WebSockets lors de la revalidation suivante (au plus une seconde). La rotation crée un nouveau secret et révoque immédiatement l'ancien. Une clé API n'ouvre jamais la console administrateur.

## API v1

Toutes les routes de cette table utilisent `Authorization: Bearer <clé>` et contrôlent l'appartenance du projet et de la ressource. Un job se lit seulement avec son droit d'origine ; son contrôle est réservé à la clé qui l'a créé ou à l'administrateur.

| Méthode / chemin sous `/v1/projects/{slug}` | Droit | Résultat |
| --- | --- | --- |
| POST `/search` | `search:read` | 202, job de recherche |
| POST `/tabs` | `browser:interact` | 202, job d'ouverture/navigation |
| GET `/tabs`, GET `/tabs/{id}` | `browser:read` | Liste / état |
| DELETE `/tabs/{id}` | `browser:interact` | Fermeture, conflit si opération active |
| POST `/tabs/{id}/navigate` | `browser:interact` | 202, job |
| POST `/tabs/{id}/actions` | `browser:interact` | 202, job |
| GET `/tabs/{id}/content?format=text\|html\|links\|metadata\|structured` | `content:read` | 202, job et artefact temporaire |
| GET `/tabs/{id}/screenshot` | `screenshot:read` | 202, capture PNG du viewport |
| GET `/artifacts/{id}` | Droit associé à l'artefact | Téléchargement protégé |
| GET `/jobs/{id}` | Droit du job | État, résultat ou erreur |
| POST `/jobs/{id}/cancel`, `/resume` | Droit du job + clé d'origine | Annulation / reprise |
| POST `/ws-ticket` | Clé du projet | Ticket à usage unique, 30 s |
| WS `/events` | Ticket dans le **premier message** | Événements filtrés et commandes bornées |

`GET /health/live` et `/health/ready` ne renvoient que l'état minimal. `/docs` et `/openapi.json` sont désactivés par défaut ; `PQ_DEVELOPMENT=true` les active sur le transport local. Un schéma exporté est disponible dans `docs/openapi.json`.

Actions : `click`, `fill`, `select`, `scroll`, `wait_for_selector`, `wait_for_navigation`. Cette dernière attend l'état de chargement de la navigation courante ; pour un clic qui navigue, le clic Playwright attend lui-même sa navigation. Au plus 20 actions, sélecteurs et valeurs bornés, délais par action limités. Aucun `eval`, CDP, shell, upload ou chemin de fichier fourni par le client.

`format=structured` renvoie un JSON versionné à partir du **DOM rendu** : blocs ordonnés, listes imbriquées, tableaux HTML/ARIA, liens, images, contrôles/formulaires, métadonnées/JSON-LD et documents des iframes. Les Shadow DOM ouverts et leurs slots sont parcourus. `include_dom=true` ajoute un arbre DOM filtré avec IDs de nœuds ; cette option est réservée au format `structured`. Les valeurs des input/textarea, scripts, styles et contenus cachés sont exclus. Pour les applications qui chargent des éléments plus tard, utiliser d'abord les actions `wait_for_selector`/scroll/click nécessaires, puis extraire à nouveau. Voir [le contrat et les limites](docs/EXTRACTION.md), [l'exemple JSON](docs/testing/structured-complex-compact.json) et [l'exemple avec arbre](docs/testing/structured-complex.json).

Erreurs structurées `{"error":{"code":"…","message":"…","request_id":"…"}}`. Codes : `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_INPUT`, `NOT_FOUND`, `RATE_LIMITED`, `NAVIGATION_BLOCKED`, `TIMEOUT`, `BROWSER_CRASHED`, `CHALLENGE_REQUIRED`, `CONFLICT`, `INTERNAL_ERROR`, `UPSTREAM_CHANGED`, `UPSTREAM_UNAVAILABLE`. Les erreurs asynchrones apparaissent dans le job. Les états sont `queued`, `running`, `waiting_for_human`, `completed`, `failed`, `cancelled`. Un redémarrage de service marque les jobs interrompus comme échoués ; aucune action n'est rejouée automatiquement.

Exemple curl (clé saisie sans l'inscrire dans l'historique) :

```sh
read -s PQ_API_KEY
export PQ_API_KEY
curl --fail-with-body http://127.0.0.1:8765/v1/projects/universrobot/search \
  -H "Authorization: Bearer $PQ_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"robotique agricole","engine":"duckduckgo","limit":5}'
unset PQ_API_KEY
```

Les exemples Python et WebSocket sont dans `examples/`. Ne jamais transmettre de clé dans une URL. Le ticket WebSocket est envoyé en JSON `{"ticket":"…"}` sous cinq secondes ; la connexion dure au plus dix minutes et supporte ping/pong, navigation, actions, reprise et annulation avec les mêmes contrôles que REST.

## Recherche et rétention

DuckDuckGo, Brave Search et Google disposent d'adaptateurs séparés testés sur fixtures. `auto` essaie DuckDuckGo, puis Brave puis Google si nécessaire ; `merge` fusionne les résultats et conserve leur provenance. Six recherches par moteur/projet/minute, résultats plafonnés, pas de solveur CAPTCHA, spoofing ni rotation d'identité. Les mises en page peuvent changer. Les publicités explicitement identifiables sont filtrées ; le type des autres résultats reste `uncertain`. Le paramètre locale influence Google ; aucune fiabilité régionale n'est prétendue pour les autres moteurs.

| Opération / durée | Effet |
| --- | --- |
| TTL du contenu (60 min par défaut) | Expire les artefacts et efface les résultats de jobs, sans toucher aux cookies |
| Rétention des artefacts (24 h max par défaut) | S'applique avec le TTL le plus court ; quota disque par projet |
| Inactivité navigateur (30 min) | Ferme après drainage des jobs, conserve le profil |
| Soft restart (désactivé par défaut) | Ferme puis relance le même répertoire, différé pendant les jobs |
| Hard reset manuel | Intention serveur éphémère + deux confirmations ; efface uniquement ce profil |
| Audit (30 jours) | Purge le journal et l'historique ancien des jobs |

La maintenance passe toutes les 30 secondes. La consultation d'un artefact vérifie son expiration immédiatement. **Purger contenus** efface tous les contenus temporaires du projet, sans fermer le navigateur. Aucun reset destructeur automatique ni snapshot de session dans ce MVP. La durée de validité des cookies distants reste décidée par les sites.

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
