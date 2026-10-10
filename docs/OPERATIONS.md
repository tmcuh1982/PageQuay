# Exploitation macOS et accès privé

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
- État de listener : `lsof -nP -iTCP:8765 -sTCP:LISTEN` doit indiquer loopback uniquement. Aucun port CDP n'est configuré ; Playwright utilise son transport interne.
