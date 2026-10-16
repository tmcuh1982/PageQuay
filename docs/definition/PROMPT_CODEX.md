# PROMPT CODEX — Home Browser Gateway (Mac mini)

[Français](PROMPT_CODEX.md) | [English](PROMPT_CODEX.en.md)

> **Consigne** : coller l'intégralité de ce fichier dans Codex, dans un dépôt vide. Les fichiers `SPEC_API.md` et `RECETTE.md` fournis dans ce ZIP détaillent le contrat et les tests de réception ; les lire avant de commencer.

## Mission

Tu es un ingénieur logiciel senior spécialisé en Python, FastAPI, Playwright, sécurité applicative et macOS. Crée une application **fonctionnelle**, locale, gratuite et auto-hébergeable, appelée **Home Browser Gateway** (HBG), destinée à tourner en continu sur un **Mac mini** connecté à une connexion Internet domestique.

**Objectif produit** : offrir à plusieurs projets logiciels un service de **recherche sur le Web et de navigation pilotable par API** en réutilisant des profils de navigateur **persistants et complètement séparés**, tout en proposant une **petite interface Web d'administration** pour gérer projets, profils, clés API, activité et politiques de rétention.

Exemples de clients : ProjectX, un agent de recherche, un outil d'extraction, un programme interne. Ils appellent HBG sur le réseau privé ; **la navigation externe réelle est exécutée par le Mac mini**, via sa propre connexion Internet. Le service ne doit dépendre d'aucun fournisseur SaaS payant, proxy résidentiel commercial ou clé API de moteur de recherche.

**À LIVRER** : le code source complet, tests automatisés, migrations SQLite, interface d'administration réellement utilisable, documentation d'installation macOS, scripts de démarrage/arrêt et un service `launchd` adapté au mode graphique (Chrome visible). Ne te limite pas à générer une architecture théorique ou des TODO.

## Priorités impératives

1. **Sécurité by design**, isolation par projet et contrôle d'accès effectif côté serveur (pas seulement dans l'interface).
2. **Un projet = un répertoire de profil navigateur persistant = un contexte Playwright persistant exclusif.** Plusieurs projets doivent pouvoir faire tourner **deux ou davantage d'instances Chrome/Chromium en parallèle**, sans partager cookies, localStorage, cache ou onglets. Interdire deux instances simultanées sur **le même répertoire utilisateur** ; verrouiller ce répertoire avec gestion des crashs.
3. **REST + WebSocket** : API REST pour les opérations courantes et tâches asynchrones ; WebSocket pour événements de progression et interactions autorisées en temps réel. **Ne jamais exposer CDP brut ni le port remote-debugging sur un réseau**. CDP n'est éventuellement utilisable qu'en interne.
4. **Moteur de recherche** gratuit via navigateur : adaptateurs Google, Brave Search et DuckDuckGo, un mode `auto`/multi-moteur, normalisation et déduplication, limites et gestion des erreurs/challenges. Pas d'API payante requise.
5. **Interface Web légère** (pas besoin de React) pour administrer projets/profils, clés API, onglets, sessions, paramètres, rétentions et audit.
6. **Rétention explicite et sûre** : distinguer l'expiration du cache des contenus, l'inactivité du navigateur, le redémarrage « soft » qui conserve la session et la remise à zéro « hard » qui efface cookies/session et nécessite une confirmation explicite. Le reset destructeur automatique est **désactivé par défaut**.
7. **Gratuit, simple et maintenable** : aucune télémétrie externe, aucun appel à un service payant, aucune dépendance à Docker pour exécuter Chrome avec une interface graphique sur macOS. Docker est une extension possible ultérieurement, mais non requis.

## Choix techniques souhaités

- **Backend** : Python récent stable compatible avec macOS Apple Silicon, FastAPI, Uvicorn, Pydantic, SQLAlchemy ou SQLModel, Alembic, SQLite en WAL, tâches `asyncio` correctement pilotées.
- **Navigateur** : Playwright pour Python et Chromium Playwright en premier choix ; option Chrome installé si compatible. Mode **headed** par défaut pour permettre une intervention humaine. Utiliser `launch_persistent_context(user_data_dir=...)` et ne jamais réutiliser le profil Chrome personnel de l'utilisateur. Un profil automatisé possède son propre dossier dédié.
- **Interface admin** : HTML rendu serveur (Jinja2) + HTMX ou JavaScript minimal, CSS local sans CDN, design propre, responsive ; pas de framework frontend lourd.
- **Sécurité** : mot de passe admin haché avec Argon2id ; sessions Web sécurisées ; tokens API générés cryptographiquement, stockés uniquement sous forme de **hash vérifiable** ; règles de périmètre et expiration ; protections explicites décrites ci-dessous.
- **Réseau** : backend lié à `127.0.0.1` par défaut. Fournir une procédure documentée pour exposer via **Tailscale Serve** aux appareils autorisés du tailnet, sans ouverture de port sur le routeur. Réseau privé et TLS en amont. Interdire par défaut l'accès public. Ne pas utiliser Funnel par défaut.
- **Organisation du dépôt** : modules séparés (`api`, `admin`, `auth`, `browser`, `profiles`, `search`, `retention`, `jobs`, `storage`, `settings`, `audit`, `tests`) ; architecture simple et testable.

N'ajoute pas de LLM, de broker distribué, de Redis, de Celery, de Kubernetes ou de services externes pour la première version.

## Modèle métier et fonctionnement

### Projet et profil

- Un **projet** : `id`, `slug` immuable et validé, nom d'affichage, statut, date création, configuration, politique d'accès réseau, quotas, dernière activité.
- Un projet correspond exactement à **un profil persistant**. Les dossiers doivent être générés à partir d'un ID opaque interne, jamais par concaténation de chaînes fournies par le client (prévention traversée de chemin).
- Chaque profil a son `user_data_dir`, ses cookies, son localStorage, son cache, ses onglets, son navigateur, ses tâches et sa propre file d'opérations.
- **Deux projets peuvent tourner en parallèle**. Les opérations concurrentes au sein d'un même onglet sont sérialisées pour éviter des races ; les onglets distincts peuvent être traités sans collisions.
- Une panne du navigateur d'un projet ne doit pas corrompre ni bloquer un autre projet. Détecter les crashs, nettoyer les verrous orphelins, reprendre sans effacer automatiquement l'état persistant.
- Permettre démarrage/arrêt/redémarrage explicites depuis l'interface. Démarrage à la demande possible ; ne pas lancer inutilement tous les navigateurs dès le boot.
- Tableau de bord montrant état par projet, nombre d'onglets, date dernière utilisation, éventuel challenge humain, erreurs et consommation approximative de ressources (si mesurable de façon fiable).

### Recherche Web

Implémenter des adaptateurs **Google, Brave Search, DuckDuckGo** en mode navigation Web normale (sans clé d'API commerciale) :

- Recherche simple par requête, langue, région si configurables de manière fiable, nombre de résultats plafonné et timeout.
- Mode `engine=auto` : stratégie configurable (`fallback` par défaut, `merge` optionnel). Ne pas lancer systématiquement trois recherches si l'une suffit.
- Normaliser : titre, URL canonique si disponible, extrait, rang, moteur source, horodatage d'extraction.
- Filtrer les liens publicitaires/sponsorisés **si identifiables avec fiabilité** ; sinon les marquer comme incertains, sans inventer le type de résultat.
- Fusion des doublons par URL normalisée raisonnablement, en gardant la provenance de chaque moteur.
- Retourner les résultats, ou un état d'erreur/`challenge_required` intelligible si l'interface du moteur change ou demande une vérification.
- Les sélecteurs HTML changent : isoler toute logique de parsing par adaptateur, prévoir fixtures et tests, ne jamais prétendre que tous les moteurs fonctionnent en permanence.
- **Ne pas développer de contournement anti-bot** : pas de solveur CAPTCHA, pas de fingerprint spoofing, pas de rotation d'identité, pas de technique destinée à neutraliser Cloudflare ou les limitations des moteurs. Respecter les conditions d'accès applicables, limites de fréquence et blocages. Rechercher les alternatives officielles ou les méthodes permises si nécessaire.

### Navigation et extraction

Pour chaque projet :

- Création / liste / fermeture d'onglets ; navigation vers URL HTTP/HTTPS autorisée ; retour d'ID d'onglet stable pendant la session.
- Actions élémentaires validées (`click`, `fill`, `select`, `scroll`, `wait_for_selector`, `wait_for_navigation`) autorisées **uniquement** aux clés dotées du droit `browser:interact`. Plafonner durée et nombre d'actions par tâche, jamais `eval` JavaScript arbitraire exposé au client.
- Extraction du **DOM rendu** après exécution JavaScript (HTML), texte visible, titre, URL effective, liens et métadonnées ; captures d'écran si autorisées. Aucun HTML de provenance externe ne doit être injecté dans le panneau admin sans échappement/sanitisation.
- Proposer une politique de chargement configurable (`domcontentloaded`, `load`, `networkidle` si nécessaire), timeout et taille maximale de réponse ; ne pas supposer que `networkidle` garantit une page prête.
- Renvoi des données éventuellement volumineuses sous forme d'artefacts éphémères propres au projet, accessibles seulement avec permission ; pas de base64 massif automatique dans toutes les réponses.
- Files d'attente bornées, nombre d'onglets maximum et nombre de navigateurs concurrents configurable. Pas de requêtes illimitées.
- Prévoir des erreurs JSON stables, y compris `TIMEOUT`, `RATE_LIMITED`, `BROWSER_CRASHED`, `NAVIGATION_BLOCKED`, `CHALLENGE_REQUIRED`, `NOT_FOUND`, `FORBIDDEN`.

### Vérifications humaines

- Détecter **sans chercher à contourner** les pages de vérification/captcha/challenge lorsque possible ; signaler `WAITING_FOR_HUMAN` avec capture protégée et URL, sans promettre une détection parfaite.
- **Ne jamais cliquer automatiquement sur « Je suis un humain »** et ne jamais externaliser la résolution à un service.
- Conserver l'onglet, la session et le profil ouverts le temps d'une intervention manuelle dans le navigateur graphique du Mac mini (ou via un outil d'accès distant déjà autorisé).
- Une fois l'utilisateur intervenu, permettre reprise automatique sur confirmation ou détection normale de retour à la page, avec limite de temps et mécanisme d'annulation.
- Aucune garantie qu'une vérification humaine ne sera plus jamais demandée.

## API REST et WebSocket

Implémenter la spécification de `SPEC_API.md` et exposer OpenAPI `/docs` **désactivé par défaut hors mode développement**, ou rendu accessible aux seuls administrateurs. Versionner sous `/v1/`.

Principes :

- Demandes courtes : HTTP synchrone raisonnable ; navigation/recherche/extraire lourd : réponse `202 Accepted` avec `job_id`, endpoint de polling et événements WebSocket.
- `project_id`/`slug` est résolu côté serveur ; **l'autorisation par projet et scope est testée sur chaque route, sur chaque job, sur chaque onglet et sur chaque message WS**.
- WebSocket authentifié avec **ticket éphémère à usage unique** délivré via REST authentifié (pas de clé API longue durée dans l'URL), origine contrôlée, durée limitée, limites de messages et taille, ping/pong, nettoyage à la déconnexion.
- Événements : `job.started`, `job.progress`, `job.completed`, `job.failed`, `browser.started`, `browser.stopped`, `browser.crashed`, `challenge.required`, `tab.navigated`, `tab.closed`.
- Pour les interactions WS, utiliser le même modèle d'autorisation/validation que REST ; jamais de commande CDP arbitraire ni de moteur « execute-code ».
- Fournir exemples `curl`, Python et JavaScript WebSocket **sans secrets en dur**.

## Sécurité — EXIGENCES NON NÉGOCIABLES

### Authentification / administration

- Initialisation administrateur avec une commande CLI explicite et interactive, qui exige de définir un mot de passe fort. Pas d'identifiants par défaut, pas d'utilisateur admin anonyme.
- Password hash Argon2id avec salage ; cookies de session HTTP-only, Secure sous HTTPS, SameSite strict ou lax selon flux, expiration/inactivité, régénération session après login, logout ; protection CSRF de toutes les mutations de l'interface ; anti-bruteforce login ; en-têtes HTTP CSP, X-Frame-Options ou frame-ancestors, nosniff et politique de cache adaptée.
- Restreindre l'interface admin au loopback/Tailscale ; ne jamais l'exposer publiquement automatiquement.
- Une clé API **ne donne jamais** accès à la gestion des clés ni à la console administrateur, même si sa portée comprend tous les projets.

### Clés API par projet

Créer une section Web dédiée **Clés API** :

- Créer une ou plusieurs clés par projet, avec nom/description, périmètre, date d'expiration facultative, limites de débit et statut.
- Droits : `search:read`, `browser:read`, `browser:interact`, `content:read`, `screenshot:read` (et seulement les droits justifiés). Par défaut `search:read` + `content:read` et restreint à **un seul projet**.
- Génération à forte entropie (CSPRNG), préfixe non secret pour l'identification, **affichage intégral une seule fois à la création** avec bouton copier. Ne jamais rendre le secret complet lors de la consultation ultérieure.
- Hash de clé dans SQLite (HMAC-SHA256 avec secret serveur protégé, ou SHA-256 robuste pour tokens uniformément aléatoires de forte entropie ; exposer le raisonnement technique dans la documentation). Comparaison en temps constant ; aucun plaintext de clé enregistré en DB, logs ou audit.
- Listing : préfixe, nom, projet, scopes, date création, dernière utilisation, expiration, révocation.
- Révoquer immédiatement, expirer, et faire tourner la clé sans fenêtre d'exposition non voulue. La révocation doit interrompre/refuser les nouvelles requêtes **et les connexions WS déjà ouvertes** après revalidation.
- Retour 401/403 cohérent, délais et quotas ; ne pas permettre l'énumération des clés par préfixe.
- Audit non sensible : identité de la clé par ID/préfixe, action, projet, date, résultat, IP de transport seulement si utile et configurable.

### Réseau et protections du navigateur

- Ne faire écouter FastAPI que sur `127.0.0.1` par défaut, y compris en production locale. Accès distant conseillé **via Tailscale Serve avec HTTPS et ACLs**, documenté et testé manuellement. Aucune redirection NAT/UPnP et aucune ouverture de port routeur.
- **SSRF / rebinding DNS / accès réseau local** : accepter seulement `http`/`https` avec analyse stricte des URL. Rejeter `file:`, `data:`, `javascript:`, `chrome:`, `about:`, schémas spéciaux, adresses loopback, link-local, privées, multicast, réservées, métadonnées cloud, réseau tailnet et résolution DNS vers ces adresses. Vérifier redirections et sous-requêtes/sous-ressources/iframes autant que possible ; ne pas supposer qu'une simple validation initiale suffit. Au besoin, ajouter une politique d'egress et documenter clairement les limites résiduelles du navigateur/OS. Exception LAN éventuelle réservée à l'admin, **désactivée par défaut**, domaines explicitement autorisés, jamais implicite.
- Éviter le `--no-sandbox` ; garder le sandbox du navigateur et ses mises à jour ; traiter pages distantes comme données non fiables (risque de prompt injection si transmises à un LLM externe).
- Limiter downloads, uploads, accès aux fichiers locaux, clipboard, géolocalisation, permissions de caméra/micro ; désactiver par défaut sauf autorisation admin par projet. Éviter toute fonctionnalité exposant arbitrairement le système de fichiers.
- Valider toute entrée client par Pydantic, quotas de taille, timeouts et plafonds globaux/par projet ; pas de commandes shell, d'évaluation JavaScript ou de chemins fournis par l'appelant.
- Faire respecter la séparation des dossiers (permissions `0700` répertoires, `0600` fichiers sensibles lorsque possible) et avertir que cookies/profils sont des secrets stockés localement. Ne pas promettre le chiffrement au repos si non implémenté réellement.
- Journaliser les erreurs sans jamais stocker Authorization, cookies, valeurs des formulaires, HTML sensible, screenshots ni mots de passe par défaut ; purger logs/artefacts selon politique.
- Tester les cas d'escalade inter-projets, contrôle d'accès et injection.

## Paramètres et politique de rétention (interface Web)

Créer une vue **Paramètres globaux** et une vue **Paramètres par projet**, avec héritage de paramètres et indication des valeurs effectives :

- `search_default_engine` (`duckduckgo`, `brave`, `google`, `auto`) ; `search_auto_strategy` (`fallback`, `merge`).
- `search_max_results`, `max_tabs_per_project`, `max_concurrent_browsers`, `max_concurrent_jobs`, `per_key_rate_limit`, `navigation_timeout_seconds`.
- `headless` (par défaut **false**), `browser_start_on_demand` (**true**), `browser_idle_timeout_minutes` (ex. **30**).
- `content_cache_ttl_minutes` (ex. **60**) : durée des réponses HTML/texte/artefacts d'extraction ; expiration = invalider/purger ces contenus **sans effacer cookies ni fermer le navigateur**.
- `session_snapshot_retention_days` : si snapshots sont réellement utilisés, durée max (sinon ne pas générer de snapshots inutiles).
- `soft_restart_after_hours` : redémarrage planifié du navigateur en préservant son `user_data_dir` (valeur désactivée par défaut, ou fenêtre explicite). Ne pas interrompre un travail en cours ; attendre le drain ou proposer reporter.
- `hard_profile_reset_after_days` : **désactivé par défaut**. Lorsque activé volontairement par l'admin, afficher très clairement que cookies, sessions, localStorage et cache de profil seront perdus, exiger confirmation, prévoir sauvegarde facultative et journal d'audit. Ne pas confondre TTL du contenu et TTL du profil.
- `audit_log_retention_days` (ex. 30), `artifact_retention_hours` (ex. 24).
- `allowed_domains`/`blocked_domains` facultatifs par projet, en appliquant le filtrage aussi après redirection.

Créer dans l'interface des boutons distincts :

1. **Purger contenus** : supprime uniquement les résultats cache/artefacts expirés (ou tous sur demande), préserve le navigateur et les authentifications.
2. **Fermer navigateur** : arrête proprement le processus tout en conservant le profil sur disque.
3. **Redémarrer navigateur** (*soft reset*) : ferme puis relance, conserve cookies/session si les sites les maintiennent valides.
4. **Réinitialiser le profil** (*hard reset*) : fermeture puis suppression des données navigateur du projet uniquement, avec double confirmation et contrôle admin. Ne jamais permettre ce reset via une clé API client.

Toutes les opérations doivent produire un statut/événement, être sans collision avec les tâches en cours et respecter l'isolation par projet. Une rétention de cache ne prétend pas contrôler la durée des cookies imposée par les sites.

## Interface Web : écrans à implémenter

Navigation simple et cohérente :

1. **Tableau de bord** — santé de l'application, service accessible localement/Tailscale, navigateurs actifs, jobs en cours, warnings, erreur récente, statut des challenges.
2. **Projets / Profils** — création, édition, activation, inspection état, onglets, profil persistant, redémarrage, purge cache, hard reset contrôlé ; au moins deux navigateurs en parallèle visibles au tableau.
3. **Clés API** — création avec scopes et expiration, secret visible une seule fois, copie, listing, rotation, révocation, historique dernière utilisation.
4. **Sessions / Onglets** — liste par projet, URL/titre, navigation de test, capture sécurisée, fermeture ; pas d'intégration iframe de sites distants non fiables.
5. **Recherche** — formulaire manuel permettant de choisir projet, moteur et requête, afficher résultats et ouvrir un résultat dans le profil ; état challenge clair.
6. **Paramètres** — paramètres globaux et par projet, TTL, concurrence, autorisations réseau, redémarrage, limites.
7. **Audit** — filtres simples par projet, période, action et statut, sans secrets.

L'interface doit être petite, lisible, adaptée au mobile et utilisable sans build complexe. Les actions destructrices ont confirmations et affichage des conséquences.

## Exploitation macOS

- Préparer un environnement `venv`, dépendances figées ou contraintes raisonnables, `playwright install chromium`, migrations auto au premier démarrage contrôlé.
- Produire `scripts/install_macos.sh`, `scripts/start.sh`, `scripts/stop.sh`, `scripts/doctor.sh` et un exemple `launchd` **LaunchAgent** utilisateur compatible avec un navigateur headed dans la session graphique. Ne pas prétendre qu'un LaunchDaemon sans session GUI peut ouvrir Chrome visible.
- Prévoir un chemin de données tel que `~/Library/Application Support/HomeBrowserGateway/` : sous-dossiers séparés SQLite/profiles/artifacts/logs avec permissions adaptées ; configuration globale à part.
- Documenter conditions nécessaires pour service disponible (session utilisateur macOS ouverte, Mac non endormi, énergie/réseau). Ne pas modifier agressivement les réglages `pmset` sans accord utilisateur.
- Fournir procédure `Tailscale Serve` (non automatique) : destination `127.0.0.1:<port>`, HTTPS/Tailnet et ACL ; expliquer comment vérifier que le service **n'est pas publiquement exposé**. Ne jamais rendre l'interface admin accessible sans authentification même dans le tailnet.
- Fournir sauvegarde et restauration manuelles sûres (arrêter browsers avant copie des profils, préserver permissions, pas de secrets dans archives publiques).
- Prévoir un `README.md`, `.env.example` **sans secrets réels**, `SECURITY.md`, un tableau des endpoints et des instructions de dépannage.

## Déroulement de réalisation

Travaille en **MVP solide**, puis extensions dans le même dépôt, en commits ou étapes logiques. N'attends pas de validation pour les décisions techniques non critiques ; documente toute hypothèse.

**Phase 1 — Socle sécurisé** : structure, DB/migrations, bootstrap admin, authentification UI, modèles projets, clés API hachées, scopes, tests d'accès.

**Phase 2 — Browser Manager** : profils persistants, deux contextes réellement parallèles, onglets, isolation, jobs et statuts, arrêts/restarts, rétention.

**Phase 3 — API + événements** : endpoints REST, auth API, WebSocket par ticket, actions de navigation/extraction/screenshots, budgets/timeouts.

**Phase 4 — Search** : adaptateurs moteurs, normalisation, `auto`, résultats ouverts par le browser propre au projet, gestion des challenges.

**Phase 5 — UI + macOS** : tableaux de bord et gestion intégrale, scripts launchd, Tailscale docs, audit, durcissement, tests.

Après chaque phase, exécute les tests pertinents et corrige les erreurs. Si un site tiers empêche un test en direct, fournir un test avec fixtures et indiquer explicitement la limitation ; **ne jamais simuler un succès réel non vérifié**.

## Critères d'acceptation obligatoires

Le résultat n'est **pas terminé** avant les tests reproductibles ci-dessous (voir `RECETTE.md`) :

- Installation locale à partir des instructions et démarrage sans abonnement.
- Admin initial créé sans mot de passe par défaut ; console inaccessible sans login.
- Création de `projectx` et `projet-b` ; les deux navigateurs actifs simultanément avec deux répertoires de profil distincts.
- Sessions/cookies d'un projet invisibles depuis l'autre sur un site local de test.
- Deux clés API différentes, chacune bornée à son projet. Un appel croisé est refusé (y compris job, onglet et WebSocket).
- Une clé révoquée/expirée est immédiatement inutilisable ; secret affiché une seule fois et absent de SQLite en clair.
- Naviguer, obtenir DOM rendu, texte, liens et capture via API, avec réponse et erreurs documentées.
- Recherche sur **au moins DuckDuckGo** démontrée en direct lorsque disponible ; Google/Brave implémentés proprement et testés avec fixtures, erreurs explicites si non disponibles.
- Une page de challenge simulée passe à `WAITING_FOR_HUMAN`, puis reprise sur signal, **sans résolution automatique**.
- Cache TTL expiré sans perte des cookies ; soft reset conserve profil ; hard reset efface uniquement le bon projet après double confirmation.
- Pas d'écoute réseau externe par défaut, pas de CDP public, requête visant `127.0.0.1` et une IP privée bloquée, test avec redirection vers une cible privée.
- Tests `pytest` (unitaires et intégration), sécurité minimale, linters/formatters, guide d'exploitation et rapports de tests exécutés.

**Conclusion attendue de Codex** : fournir le chemin des fichiers créés, commandes exactes d'installation/test/démarrage, liste de fonctions réellement vérifiées, tests exécutés et limites réelles. Ne pas promettre la résolution de Cloudflare, ni l'absence de blocage par les moteurs de recherche.
