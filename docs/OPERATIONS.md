# Exploitation macOS et accès privé

[Français](OPERATIONS.md) | [English](OPERATIONS.en.md)

## Démarrage et diagnostic

Dans la racine du dépôt : `./scripts/start.sh`. Arrêt foreground : Ctrl-C. `./scripts/doctor.sh` vérifie l'environnement, le navigateur installé, le schéma, l'administrateur et l'état Serve si la CLI Tailscale existe. Cette commande crée le dossier de données et applique les migrations si nécessaire ; elle ne lance aucun navigateur.

Mode visible : une session utilisateur macOS graphique doit rester ouverte. Un LaunchDaemon système ne remplace pas cette session. La disponibilité dépend du sommeil du Mac, de son réseau et de sa session ; régler l'énergie dans Réglages système selon le besoin. PageQuay ne modifie pas `pmset`. Une session distante déjà autorisée peut servir aux interventions humaines ; aucun accès distant n'est installé par PQ.

## Fenêtres minimisées

La console locale propose **Minimiser** et **Restaurer** dans Projets / Profils et Sessions / Onglets pour les navigateurs visibles déjà démarrés. La navigation distante et l’extraction continuent dans une fenêtre minimisée ; ouvrir un nouvel onglet conserve cet état. Une capture restaure brièvement la fenêtre pour permettre le rendu macOS, puis la minimise à nouveau, y compris en cas d’échec de la capture.

Dans Paramètres, **Démarrer les fenêtres minimisées** ajoute `browser_start_minimized: true` aux valeurs globales. Enregistrer puis redémarrer les navigateurs pour appliquer cette option de lancement. Une surcharge JSON par projet peut activer ou désactiver le réglage. L’option est désactivée par défaut et ignorée en mode `headless`. Pour une vérification humaine, restaurer la fenêtre avant d’intervenir.

## LaunchAgent utilisateur

Le fichier `scripts/local.pagequay.gateway.plist.example` doit être adapté : chemins absolus du dépôt et du dossier de données, sans `~` ni variables shell. Le dossier `logs/` doit exister, avec permissions 0700, et les sorties 0600. Vérifier le fichier avec `plutil -lint`. Copier le résultat vers `~/Library/LaunchAgents/local.pagequay.gateway.plist`, puis :

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.pagequay.gateway.plist"
launchctl print "gui/$(id -u)/local.pagequay.gateway"
curl --fail http://127.0.0.1:8765/health/live
```

Décharger : `./scripts/stop.sh`, qui utilise `launchctl bootout`. Le fichier reste présent ; le supprimer seulement si vous souhaitez empêcher le chargement aux connexions futures. Recharger avec `bootstrap` pour repartir. Ne pas faire tourner en parallèle une instance foreground et celle du LaunchAgent utilisant les mêmes profils.

Le mode Aqua est spécifié dans le plist. Le démarrage après reboot reste à vérifier sur la machine cible. Si macOS refuse la lecture du dépôt sous `Documents`, utiliser une copie d’exécution hors de ce dossier et un environnement Python dont les imports ne pointent pas vers `Documents`.

Sur le Mac mini de cette session, le LaunchAgent utilisateur a été installé explicitement. Il lance `~/Library/Application Support/PageQuayService/.venv/bin/python -m pagequay.cli serve`, avec le dossier de travail `PageQuayService`, `RunAtLoad` et `KeepAlive`. Les sources d’exécution et `.env` sont copiées depuis le dépôt ; toute mise à jour doit donc être déployée aussi dans cette copie avant de relancer le service. Les données restent dans `~/Library/Application Support/PageQuay`, distinctes du runtime. Aucun mot de passe administrateur n’est créé par cette installation.

## Administration locale et Tailscale Serve HTTPS

Installer et connecter Tailscale selon ses [instructions officielles](https://tailscale.com/docs/features/tailscale-serve). Activer HTTPS pour le tailnet si nécessaire. Avant Serve, limiter dans les ACL/grants Tailscale qui peut joindre ce Mac et son port HTTPS. `Serve` rend le service accessible dans le tailnet ; `Funnel` l'exposerait publiquement et ne doit pas être activé pour PQ.

La CLI ouvre deux sockets loopback dans le même processus : `127.0.0.1:8765` pour la console locale et `127.0.0.1:8766` pour l’API. `PQ_PORT` et `PQ_API_PORT` permettent de choisir deux ports distincts. Le port API accepte uniquement `/v1/`, `/health/live`, `/health/ready` et le contrat client `/openapi.json` ; la console, son login, ses mutations et ses assets sont refusés, même avec un cookie admin ou un Host localhost. Le contrôle utilise le port de destination réel, sans faire confiance aux en-têtes du client.

Configurer `.env` avec le hostname **exact** du Mac :

```dotenv
PQ_ALLOWED_HOSTS=["127.0.0.1","localhost","mac-mini.votre-tailnet.ts.net"]
PQ_ALLOWED_ORIGINS=["http://127.0.0.1:8765","http://localhost:8765"]
PQ_SECURE_COOKIES=false
PQ_PORT=8765
PQ_API_PORT=8766
```

Redémarrer PQ puis lancer explicitement :

```sh
tailscale serve --bg http://127.0.0.1:8766
tailscale serve status
tailscale funnel status
```

Contrôles à effectuer : état Serve indique HTTPS/tailnet-only ; Funnel n'a aucune route active ; la destination est `127.0.0.1:8766` ; un appareil autorisé du tailnet atteint `/health/ready` et les routes API avec sa clé, tandis que `/admin`, `/admin/login` et les mutations admin renvoient 404 ; un appareil refusé par ACL ne l'atteint pas ; depuis un appareil hors tailnet le service est inaccessible. Aucun NAT, UPnP ou port routeur à ouvrir. `tailscale serve reset` retire les routes Serve de cette machine : examiner l'état auparavant si elle héberge d'autres services.

Ouvrir la console **sur le Mac** à `http://127.0.0.1:8765/admin`. Les cookies HTTP locaux utilisent `PQ_SECURE_COOKIES=false` ; l’authentification API distante reste par Bearer sur HTTPS et n’utilise pas ces cookies. Ne jamais configurer Serve, Funnel ou un autre proxy vers le port admin 8765. Aucun en-tête `X-Forwarded-For`/`Proto` d'un client n'accorde un accès privilégié. La procédure et les ACL restent **non validées en réseau réel** tant que la recette de la machine cible n'a pas été exécutée.

### Port API local depuis la console

Dans **Paramètres → Accès local**, choisir le **Port API local** entre 1024 et 65535, puis **Enregistrer le port local**. Tailscale n’est pas requis. Le port doit être différent du port administrateur enregistré et disponible sur `127.0.0.1` ; la console refuse un conflit avec un autre service. La disponibilité est vérifiée à l’enregistrement, sans réserver le port : si un autre processus le prend ensuite, le démarrage échoue.

Le port actif reste inchangé jusqu’au redémarrage du service PageQuay ; la page affiche le port enregistré et un message de redémarrage requis. En lancement manuel, arrêter avec Ctrl-C puis relancer `./scripts/start.sh`. Avec le LaunchAgent, utiliser la procédure d’arrêt/redémarrage décrite plus haut. Les clients locaux doivent ensuite utiliser `http://127.0.0.1:PORT`. L’API reste liée uniquement au loopback et l’administration reste refusée sur ce port. Enregistrer à nouveau le port actif annule un changement en attente.

Le réglage est conservé dans `local-api.json` (0600), dans `PQ_DATA_DIR`, et prend priorité sur `PQ_API_PORT` au démarrage, y compris pour `pq doctor`. Pour revenir à la configuration `.env`, arrêter le service, retirer ce fichier du dossier de données puis redémarrer. Avant le premier lancement, ou si le port API actuel empêche le démarrage, définir `PQ_API_PORT` dans `.env` (et retirer une éventuelle surcharge `local-api.json`). Le port de la console se règle aussi dans **Port administrateur** ; `PQ_PORT` sert de valeur initiale. Les origines loopback existantes sont adaptées au port administrateur enregistré.

Si Tailscale Serve est déjà utilisé, adapter aussi sa destination loopback au nouveau port ; le réglage local ne modifie aucune route Serve. Les ports locaux et HTTPS externes ont des fonctions distinctes.

## Port HTTPS externe depuis la console

Dans **Paramètres → Accès externe**, le champ **Port HTTPS externe** configure le port HTTPS vu par les clients, de 1 à 65535 (443 par défaut). La console lit le port et l’adresse actifs dans Tailscale, sans confondre ce port avec la destination loopback `PQ_API_PORT`. **Appliquer le port HTTPS** crée la nouvelle route privée vers le port API, vérifie sa configuration, retire l’ancienne route PageQuay, puis confirme l’état final. Aucun redémarrage de PageQuay ni des navigateurs n’est nécessaire. `--bg` conserve la configuration Serve après redémarrage de Tailscale.

**Choix recommandé pour un port alternatif : 8443**, facile à retenir pour HTTPS. L’adresse cliente devient alors `https://mac-mini.votre-tailnet.ts.net:8443`. **8080 reste possible en HTTPS**, par exemple `https://mac-mini.votre-tailnet.ts.net:8080`, même s’il évoque généralement HTTP par convention : le protocole est déterminé par la [configuration HTTPS de Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve), pas par le numéro du port. Choisir un port disponible et autorisé par les règles d’accès du tailnet. Ce choix est global à PageQuay, indépendant des projets ; le port actif change uniquement après application dans la console.

Prérequis : CLI Tailscale accessible au processus PageQuay, connexion au tailnet, Serve/HTTPS préalablement activé et hostname exact dans `PQ_ALLOWED_HOSTS`. Si Tailscale n’est pas disponible, les autres paramètres restent utilisables et un message explique le blocage. Le formulaire exige une session admin locale et CSRF ; il est inaccessible depuis le port API et les clés clientes.

Le LaunchAgent macOS utilise un `PATH` minimal. PageQuay cherche aussi le lanceur `tailscale` dans `/usr/local/bin` et `/opt/homebrew/bin` avant le binaire de l’application. Sur la machine vérifiée, ce lanceur est nécessaire : le binaire appelé directement depuis cet environnement renvoie une erreur de démarrage au lieu du JSON attendu, ce qui désactive le bouton avec « État Tailscale illisible ».

Après changement, mettre à jour l’URL des clients, par exemple `https://mac-mini.votre-tailnet.ts.net:8443`, et les ACL/grants du tailnet pour le port choisi. La console ne modifie pas les règles d’accès. Le port 443 n’apparaît pas dans l’URL. Le backend API reste sur son port loopback actuel et l’administration reste locale.

Un port utilisé par un autre service, une route partagée avec d’autres chemins, Serve en mode temporaire ou Funnel sur le port concerné sont refusés avant modification. La commande ne réinitialise jamais toute la configuration Serve. En cas d’échec, elle tente de restaurer l’ancienne route et de retirer la nouvelle ; si cette récupération échoue, elle signale un changement incomplet et demande de vérifier `tailscale serve status`. Le réglage repose sur les commandes officielles [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve).

## Sauvegarde / restauration

1. Drainer ou annuler les jobs. Arrêter PQ (Ctrl-C ou bootout) ; vérifier que ses fenêtres Chromium sont fermées.
2. Copier **tout le dossier de données** vers un emplacement privé, incluant SQLite, WAL/SHM éventuels, profils et artefacts. Sous macOS, `ditto` conserve les permissions. La configuration `.env` est à conserver séparément dans un emplacement privé.
3. Protéger la copie comme un secret, jamais dans le dépôt ni une archive publique. Ne pas copier un profil pendant que Chrome l'utilise.
4. Pour restaurer, arrêter PQ et sauvegarder d'abord les données actuelles. Restaurer la copie vers un dossier privé, vérifier propriétaire/0700 et fichiers sensibles/0600, puis pointer `PQ_DATA_DIR` dessus et redémarrer.
5. Vérifier login, liste des projets et état des sessions. Les sites peuvent invalider des cookies restaurés ; PQ n'en garantit pas la validité.

Les verrous flock peuvent rester sous forme de fichiers après copie : ils n'ont pas de verrou noyau actif après arrêt. Les jobs interrompus ne sont pas rejoués au redémarrage. Ne pas effacer les fichiers `Singleton*` d'un profil tant qu'un processus Chromium l'utilise.

## Logs et dépannage

- Les logs d'audit en base sont purgés automatiquement ; les fichiers stdout/stderr du LaunchAgent nécessitent une rotation opérateur. Après arrêt du service, archiver ou supprimer les anciens logs privés selon la rétention choisie, puis reprendre. Aucune commande périodique destructive n'est installée.
- `BROWSER_CRASHED` au lancement : vérifier `playwright install chromium`, session GUI, version Playwright/Chromium et droits des dossiers. Le sandbox reste activé.
- `CONFLICT` : profil utilisé ailleurs ou jobs actifs ; attendre le drainage, jamais effacer un verrou/profil pour forcer une instance concurrente.
- `NAVIGATION_BLOCKED` : schéma, port, DNS, adresse privée ou listes de domaines interdits. Une page publique peut charger des sous-ressources bloquées ; c'est attendu.
- `UPSTREAM_CHANGED` / `UPSTREAM_UNAVAILABLE` : mise en page de moteur, erreur réseau ou page non reconnue. Le diagnostic en direct est séparé des fixtures ; ne pas ajouter de contournement anti-bot.
- `waiting_for_human` : intervenir sur le Mac puis reprendre ou annuler. Le budget humain est limité ; la détection est imparfaite.
- `RATE_LIMITED` : lire `error.details.scope/cause`, attendre `Retry-After` ou `retry_at` s’ils sont connus ; une capacité pleine n’a pas de délai prévisible. Le quota moteur de 6 tentatives/60 s est partagé par projet et moteur. Pour reprendre une continuation échouée, utiliser un nouveau `Idempotency-Key` si `can_resume_continuation=true`. Espacer les appels et le polling ; utiliser les événements WS pour réduire la fréquence. Par défaut, 60 requêtes par clé/minute, polling compris.
- État de listener : `lsof -nP -iTCP:8765 -sTCP:LISTEN` doit indiquer loopback uniquement. Chaque navigateur ouvre aussi un port CDP explicite non nul sur `127.0.0.1`, choisi à son lancement ; il n’est ni publié par Tailscale Serve ni exposé par l’API. Vérifier le listener du processus navigateur avec `lsof -nP -a -p <PID_NAVIGATEUR> -iTCP -sTCP:LISTEN`. Ne jamais publier ce port. Voir [transport navigateur](BROWSER_TRANSPORT.md).


## Budgets de ressources

Les réglages suivants se définissent dans `.env` et prennent effet au redémarrage :

| Réglage | Défaut | Plage |
| --- | ---: | ---: |
| `PQ_AUDIT_QUEUE_SIZE` | 512 événements | 16–4096 |
| `PQ_AUDIT_EVENTS_PER_MINUTE` | 2400 | 60–10000 |
| `PQ_AUDIT_EVENTS_PER_PROJECT_MINUTE` | 600 | 30–5000 |
| `PQ_AUDIT_MAX_ROWS` | 20000 | 100–100000 |
| `PQ_AUDIT_MAX_BYTES` | 64000000 octets | 1000000–256000000 |

Le détail est admis selon ces budgets ; les événements les plus anciens sont purgés lorsqu’un plafond est dépassé, même avant la rétention en jours. Les opérations admin, clés, projets, profils et réglages disposent d’une réserve distincte : 64 événements en file, 5000 lignes et 16000000 octets. Chaque détail JSON est limité à 65536 octets. La collecte réseau retient au plus 128 requêtes par onglet et lance au plus 32 tâches de mesure simultanées dans le service.

Les écritures sont regroupées environ toutes les 250 ms. La console attend leur visibilité hors de la boucle serveur, avec un délai maximal de 5 s ; en cas de panne du writer, elle peut montrer un état antérieur. L’alerte Audit indique les omissions et erreurs depuis le dernier démarrage ainsi que le nombre persistant de lignes purgées pour capacité. Une file pleine peut également omettre un événement administratif ; la réserve n’est pas une garantie de journal exhaustif.

Les histogrammes conservent séparément les totaux des réponses API connues, y compris 401 et 429, dans 24 tranches UTC. Les erreurs d’écriture sont réessayées dans des buckets bornés. Au-delà des capacités (512 dimensions en attente, 8192 persistées), les dimensions projet/clé sont regroupées sans réduire le total par endpoint ; ce regroupement est signalé. Les routes normalisées sont également bornées. Les compteurs en attente peuvent être perdus lors d’un arrêt brutal ou d’une panne persistante au shutdown. Au premier démarrage de la migration 006, les événements API disponibles des dernières 24 heures sont repris une seule fois avant la purge ; aucun détail déjà supprimé n’est reconstruit.

Les limites d’octets mesurent le contenu logique retenu, pas le fichier SQLite, ses index ou le WAL. Les pages libérées sont réutilisées ; le fichier peut rester à sa taille maximale historique. Une réduction physique exige une maintenance SQLite à l’arrêt après sauvegarde, distincte de cette purge.

Les titres de page sont limités à 512 caractères (`title_truncated`), le challenge à un échantillon de 20000 caractères, liens/métadonnées à des collections et chaînes plafonnées. `PQ_MAX_CONTENT_BYTES` (2000000 par défaut) limite HTML/texte transférés, enveloppes structurées et résultats/erreurs de jobs. Une lecture trop volumineuse échoue en 413 ; les frames devenues indisponibles sont signalées dans le résultat structuré. Les résultats historiques trop volumineux sont retirés à l’ouverture avec statut d’échec explicite. La mémoire du renderer et du driver n’est pas une ressource plafonnée par ces réglages.

### Port de la console administrateur

Dans **Paramètres → Accès local**, régler **Port administrateur** et **Port API local**, puis enregistrer et redémarrer le service. Les deux ports doivent être distincts et disponibles. Le port administrateur sert à `/admin/` et au login ; le port API sert aux clients Bearer. Les origines locales autorisées sont adaptées au nouveau port administrateur au démarrage. Les réglages persistants de `local-api.json` prennent priorité sur `PQ_PORT` et `PQ_API_PORT`. Exemple pour cette installation : console `http://127.0.0.1:8767/admin/`, API `http://127.0.0.1:8787`. Mettre à jour les clients et, si utilisé, la destination de Tailscale Serve.
