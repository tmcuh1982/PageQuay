# Mémoire de travail — PageQuay (PQ)

## 16 octobre 2026 — Commit de release 1.1.1 demandé

Utilisateur : audit en lecture seule puis correction approuvée, recette UBTECH réelle approuvée, puis demande de commit de release local. Acquisition sans Base64 interne par second GET Chromium contrôlé, reprise explicite du même job, décodeur jetable, nettoyage et diagnostics renforcés. Client refuse les services sans marqueur de transport et ne rejoue pas de POST incertain. Recette du 16 octobre réussie : JPEG 1080 × 1530, 689381 octets, empreinte concordante, GET authentifié 200, anonyme 401, autre projet 403, nettoyage confirmé ; premier essai interrompu par le polling trop fréquent du script (429), puis nouvelle recette après annulation confirmée. Preuves dans docs/testing/DOWNLOAD_IMAGE_REPORT.md. Sources testées avant version : 307 passed/104 skipped, Chromium ciblé 98 passed. Release locale 1.1.1, versions alignées, dépendances inchangées. Après version : 307 passed/104 skipped, 12,43 s ; Ruff/format, contrat, lock offline et diff conformes. Pas de push, tag, paquets publiés ou installation autorisés par cette demande ; aucun service installé, donnée réelle, profil, clé, droit, pause/horaire ou fichier UniversRobot modifié. Les limites mémoire sous macOS reposent sur octets/blocs/pixels, pas sur un plafond RSS OS.

## 14 octobre 2026 — Publication v1 demandée

La demande de publier 0.2.4 a été remplacée avant toute mutation distante par « fais une v1 en release ». Préparer v1.0.0 depuis le commit local 31dd4ec (343 tests réussis/4 ignorés) : métadonnées et contrat à 1.0.0, notes dédiées, code navigateur inchangé. Compte GitHub tmcuh1982 et droit ADMIN sur tmcuh1982/PageQuay public vérifiés ; origin/main reste sur la release précédente. Construire wheel/sdist/SHA256SUMS depuis le commit Git, publier main puis tag annoté v1.0.0 et release stable, vérifier références et fichiers retéléchargés. Aucun déploiement ou redémarrage du service demandé.

## 14 octobre 2026 — Transport CDP, WebSockets natifs et commit 0.2.4

État courant : relais `cdp_launch.py` du pipe Playwright vers le port CDP explicite loopback du navigateur enfant ; proxy natif à deux listeners pour HTTP/HTTPS publics et refus ws/wss avant DNS. Initialisation persistante et gardes conservées, `route_web_socket` retiré. Comparaisons suggérant l’effet de cette instrumentation sur Music Store, sans preuve générale des décisions Cloudflare. Tests Chrome/Chromium couvrant constructeur natif, frames/popups/workers, aucun handshake amont et absence de repli direct.

Correctif runtime et dépendance déployés dans PageQuayService avec sauvegarde, readiness et conservation de la configuration/permissions. Service toujours sur Chromium, métadonnées 0.2.2. Chrome local puis Chromium : recherche test et Yamaha P-45 en HTTP200. Nouveau profil vierge Chromium laissé ouvert ; Shure SM58 puis cinq recherches/fiches différentes réussies dans le même processus et onglet, sans défi détecté. Premier clic Fender expiré ; cinq fiches ouvertes ensuite via les liens observés par navigation API. Session laissée sur Roland FP-10, délai d’inactivité inchangé. Les profils précédents restent en sauvegarde privée ; aucun secret/rapport brut versionné.

Demande actuelle : documentation puis commit de release local 0.2.4. Versions paquet/module/OpenAPI/test/lock alignées ; notes et sécurité mises à jour. Aucun nouveau déploiement, fermeture de la fenêtre, tag ou publication GitHub pour cette demande. Contrôles finaux : suite complète avec navigateurs 343 passed/4 skipped en 95,71 s ; warning Starlette existant. Ruff check/format ciblés, lock offline et diff-check conformes. Exemples JSON régénérés par les tests restaurés à leur état versionné pour exclure les ports/dates/IDs temporaires. Voir `docs/BROWSER_TRANSPORT.md` et `docs/releases/0.2.4.md`.


### Graphiques par API / type et espace disque des profils — 11 octobre 2026

Clarification utilisateur : « par projet / clé API, puis par opération ». Vue Projet par défaut, Clé API en deuxième choix, Endpoint HTTP disponible ensuite ; filtre technique renommé Endpoint HTTP pour éviter de confondre clé et endpoint. Le filtre Type d’appel et la ventilation des opérations restent disponibles pour chaque graphique.

Vue d’ensemble : histogramme global et petits graphiques séparés, regroupement endpoint/projet/clé API, filtre endpoint et type d’opération (recherche, navigation, extraction, capture, suivi/contrôle des jobs, téléchargement…). Échelle verticale commune entre petits graphiques, totaux et ventilation par opération ; heures locales, toujours 24 tranches horaires maximum. Identification interne de la clé authentifiée ajoutée à api.request, y compris erreurs de quota/droits ; aucun jeton stocké. Historique sans clé rattaché à « Clé non renseignée », pas de reconstruction depuis les jobs.

Espace disque des profils visible dans Vue d’ensemble et Projets / Profils : estimation des blocs alloués aux fichiers et taille logique, catégories cookies (DB+journaux), cache Web/CacheStorage, stockage sites, cache graphique/code, fichiers image identifiables et autres. Les images du cache Web restent dans la catégorie mixte cache, aucune précision inventée par MIME. Hors artefacts PQ et métadonnées du système de fichiers. Lecture des seuls stat, hors event loop, sans suivi des symlinks ; hardlinks dédupliqués et fichiers creux mesurés par blocs ; fichiers indisponibles/plafond100000 signalés comme mesure partielle.

Validation : suite 155 passed/15 skipped, plus 1 UI Chromium passed ; graphiques séparés, filtres, appels d’une clé de test, fuseau, tailles/catégories, hardlinks/sparse/symlinks et erreurs testés. Captures desktop/mobile et graphique par clé inspectés ; Ruff/format/Node/diff-check conformes. Huit fichiers runtime déployés après zéro job actif, sauvegarde /private/tmp/pq-api-profile-backup-8kn4cg4q ; hashes identiques, ready/login200, admin API404 et key-info anonyme401. Aucun changement de projet/clé/réseau, aucun push.

### Graphique appels API — 11 octobre 2026

Vue d’ensemble : petit histogramme SVG des appels REST par heure, 24 tranches horaires maximum (heure actuelle partielle), total et filtre par endpoint HTTP normalisé. Heures locales du navigateur ; rendu adapté mobile/desktop, détails des barres au survol et libellés accessibles. Nouveau usage.py : middleware compte une fois les réponses des routes /v1 connues (erreurs HTTP incluses), sans stocker de jeton, corps, query ou identifiant dynamique ; audit api.request conservé selon la rétention existante. Health/admin/WS/routes inconnues exclus. Historique démarrant à cette mise à jour, aucun faux historique reconstruit depuis les jobs.

Validation : 152 tests réussis / 15 ignorés, plus 1 test UI Chromium réussi ; agrégation, bornes, heures vides, erreurs 401/403/404/422/429/500, filtre et fuseau Europe/Warsaw vérifiés. Captures desktop/mobile inspectées ; Ruff, Node et diff-check conformes. Les essais nécessitant sockets ont été relancés hors sandbox après refus de bind local.

Six fichiers runtime déployés après zéro job actif et sauvegardes /private/tmp/pq-api-usage-backup-r5oj4355 et /private/tmp/pq-api-usage-backup-n3cdf8d4 ; LaunchAgent relancé, hashes identiques, ready/login 200, admin API 404 et key-info sans clé 401. Comptage installé vérifié. Aucun changement de projet, clé ou réseau, aucun push.

Dernière mise à jour : 2026-10-11, graphique des appels API sur la vue d’ensemble.

## 10 octobre — commit de release demandé

Demande explicite de publier les changements courants sur GitHub. Lot : filtres pays / période DuckDuckGo, migration 004 et compatibilité des continuations/idempotence, menus console et options client, documentation/exemples avec nom générique ProjectX (`projectx`), correctif du diagnostic Google déjà présent dans le dossier. Publication cible `tmcuh1982/PageQuay`, branche main ; le commit du port HTTPS configurable déjà local fait aussi partie de la synchronisation. Version du contrat conservée à 0.2.0. Contrôles finaux : suite **142 passed / 14 skipped**, 6,40 s ; Ruff check/format, syntaxe Node et diff --check conformes. Les deux tests Chromium liés aux filtres ont passé lors de leur recette ; aucun nouveau diagnostic moteur externe lancé pour la publication.

## 10 octobre — filtres pays / période DuckDuckGo

Ajout de `region` (codes officiels DDG, null = dérivé de locale) et `time_range` (`any`, `day`, `week`, `month`, `year`) à POST /search et aux métadonnées. Console Recherche : menus Pays / région et Période activés pour DuckDuckGo ; client Python : --region et --time-range, filtres liés au checkpoint. Les autres moteurs et auto refusent les filtres explicites plutôt que les perdre lors d’un repli. Dates de publication/mise à jour/événement non vérifiées automatiquement ; fetched_at reste la collecte.

- `kl` et `df` transmis dès la première navigation et réappliqués aux formulaires natifs, sans inventer tokens/offsets. `any` transmet explicitement df vide. Curseurs liés aux filtres à l’admission et à l’exécution ; migration 004 conserve les anciens curseurs. Hashes d’idempotence historiques préservés pour les filtres par défaut.
- Validation : suite normale **142 passed / 14 skipped** hors sandbox réseau ; transport POST Chromium **1 passed** ; UI Chromium **1 passed** après correction des sélecteurs et de l’interception du test. Menus, corps des requêtes, changement de moteur, suppression région vide et rendu desktop/mobile vérifiés. Captures search-filters-desktop.png / search-filters-mobile.png inspectées ; Ruff, format, Node et diff --check conformes. Pas de succès DuckDuckGo filtré en direct revendiqué.
- Déployé dans PageQuayService après contrôle de zéro job actif et sauvegarde privée des sources précédentes sous tmp. Bootout suivi d’un premier bootstrap trop rapide en erreur 5 ; deuxième bootstrap réussi. Sources installées identiques, migration appliquée, schéma public actualisé, login local 200 et admin sur API 404 confirmés. Profils/clés/configurations réels conservés ; aucun push GitHub pour cette modification.

## Objectif et autorisation

L'utilisateur a autorisé le développement depuis l'archive et demandé `memory.md` et `decisions.md`. Nom produit **PageQuay / PQ**. Documents de référence dans `docs/definition/`, avec noms d’exemple rendus génériques à la demande de l’utilisateur.

## État livré

MVP 0.1 dans `src/pagequay/` : migrations SQLite, auth admin Argon2id/sessions/CSRF, projets, clés/scopes/expiration/révocation/rotation, REST, tickets WS uniques, jobs bornés, profils Playwright isolés, proxy à IP validée, extraction/captures/artefacts, recherche multi-adaptateurs, rétention et UI française responsive.

Lockfile, README, SECURITY, exploitation macOS/Tailscale/sauvegardes, architecture, OpenAPI, exemples clients et scripts présents. Dépendances et Chromium installés. Aucun administrateur réel, secret, service launchd ni accès Tailscale créé automatiquement. Aucun processus de test/driver/Chromium restant.

## Vérifications

- Suite `.venv/bin/pytest --browser --headed -q` : **45 passed, 1 skipped**, 52,79 s.
- Après ajout du nettoyage d'un lancement annulé : lifecycle/jobs/proxy, **4 passed**, 0,75 s. **47 tests locaux distincts vérifiés**, hors diagnostic tiers.
- Revalidation navigateur après correction de dernière activité : **1 passed**, 46,86 s. Contrat OpenAPI Bearer vérifié : **1 passed**.
- Ruff check/format, syntaxe zsh/plist, uv sync --frozen et CLI doctor jetable : réussis.
- Deux Chromium **visibles** simultanés, cookies séparés ; API DOM/texte/liens/métadonnées/capture/interactions ; redirection/fetch privés bloqués ; challenge simulé repris ; soft restart/reset/inactivité/récupération vérifiés.
- UI réellement pilotée et desktop/mobile inspectés, aucun pageerror.
- DDG réel : **challenge humain détecté**, timeout humain de test. Aucun succès de recherche en direct. JSON dans `docs/testing/duckduckgo-live.json`.
- Warning Starlette/TestClient/httpx non bloquant, non masqué.

Rapport : `docs/testing/REPORT.md`. LaunchAgent effectif, Tailscale réel, sauvegarde/restauration et résultats DDG restent à vérifier. Recette intégrale non revendiquée.

## Corrections observées

- IP octales macOS/Chromium : parsing différent, formes ambiguës refusées.
- Proxy Python 3.14 : handlers fermés avant server.wait_closed. Ancienne recette suspendue interrompue ; correctif et régression test présents.
- Login HTML : no-referrer produisait Origin null ; same-origin conserve le contrôle strict sans referrer externe.
- Redirection bloquée par proxy signalée comme NAVIGATION_BLOCKED.
- Paramètres réseau répercutés aux contextes actifs ; lancement au redémarrage.
- Flock service/profil, nettoyage d'un lancement annulé ; aucun profil personnel utilisé.

## Démarrage opérateur

Dans `~/Documents/Codex/PageQuay` : `.venv/bin/pq init-admin` puis `./scripts/start.sh`. Console `http://127.0.0.1:8765/admin`. Données par défaut `~/Library/Application Support/PageQuay` ; définir alternativement PQ_DATA_DIR avant **les deux** commandes. Identifiant et mot de passe réels choisis interactivement par l'utilisateur.

## Reprise

Lire ce fichier, decisions, README et rapport. Ne jamais confondre TTL et effacement du profil. Suites : recette Mac mini/launchd/Tailscale, DDG après intervention humaine permise, réglages plus accessibles que JSON, contrôle OS d'egress si confinement renforcé requis. Pas de reset destructeur automatique ni d'exception LAN sans contrôle explicite et recette.

## Test Google / MacBook Air du 10 octobre

- Hôte des commandes confirmé : **Mac mini**, modèle Mac16,11. Le MacBook Air ne doit pas être présenté comme hôte d'un test exécuté ici.
- Peer Air trouvé en ligne sur le tailnet lors du contrôle. SSH dans le sens mini → Air : **port 22, connexion refusée**. Aucun accès distant activé. Les noms réseau, adresses et identifiants personnels sont exclus de cette mémoire publique ; la correction du sens utile est consignée ci-dessous.
- Contrôle UI non abouti : Terminal refusé par l'outil ; Réglages système a échoué avec cgWindowNotFound après une attente anormale. Aucun réglage modifié. Ne pas retenter ces appels sans raison concrète.
- Chromium visible + API Bearer via client ASGI **sur Mac mini** : recherche Google « Playwright Python documentation » redirigée vers `/sorry/index`, reCAPTCHA et message français de trafic exceptionnel. **Aucun résultat ni texte de page trouvée récupéré.** Texte de diagnostic et capture conservés dans `docs/testing/google-live.json` et `google-live.png`.
- Première tentative : faux diagnostic UPSTREAM_CHANGED (`google-live-before-fix.json`). Correctif : détection de l'URL Google `/sorry/` et du message français. Nouvelle tentative : événement challenge.required puis timeout humain volontaire de 5 s. Aucun CAPTCHA résolu.
- Vérifications : suite normale **49 passed, 4 skipped**, 2,67 s ; diagnostic Google et 4 cas de détection **5 passed**, 7,81 s (pass ne signifie pas recherche réussie). Ruff ciblé conforme. Tests navigateur/UI complets du 9 octobre non rejoués.
- Client HTTP autonome prêt : `examples/probe_google.py` (bibliothèque standard Python, clé masquée, recherche → navigation → téléchargement texte, rapport avec nom de machine). Il n'a **pas été exécuté sur le MacBook Air**. Nécessite un service PQ accessible et une clé de projet aux scopes search:read/browser:interact/content:read ; aucun service permanent ni clé réelle créé.
- Correction apportée par l'utilisateur : **`ssh macmini-codex` fonctionne depuis le MacBook Air vers le mini**. La tentative précédente mini → Air était dans le sens inverse et ne prouve aucune panne du SSH utile au client. L'alias n'est pas défini sur le mini (configuration client locale = Include Colima) ; il est utilisé côté Air. Confirmation utilisateur, pas essai de l'agent depuis l'Air.
- Commande de recette prête côté Air : `ssh macmini-codex 'cat Documents/Codex/PageQuay/examples/probe_via_ssh.py' | python3 - --human`. Elle lance `scripts/serve_ssh_probe.py` sur le mini, tunnel loopback vers 18766, profil et clé jetables (15 min max), client HTTP Python standard sur l'Air. Le secret passe uniquement dans le flux SSH privé/env du sous-processus, jamais dans les logs/arguments/rapport. Pas de service installé ni de réglage SSH/Tailscale modifié.
- `--human` permet de taper `reprendre` après intervention manuelle sur Chromium visible du mini, ou `annuler`. Aucun solveur. Rapport copié automatiquement ici : `docs/testing/macbook-air-google.json`, texte `.txt` seulement si extrait. Les scripts arrêtent le service et le tunnel en fin de test. Cette commande n'a **pas encore été exécutée sur l'Air** ; aucune recette distante revendiquée.
- Service temporaire vérifié réellement sur HTTP loopback : health ready, recherche sans clé = 401, rapport sans secret, arrêt et socket fermée. Deuxième vérification avec clé : navigation directe `https://playwright.dev/python/docs/intro`, extraction et téléchargement **3821 caractères**, puis arrêt normal. Rapport et texte dans `docs/testing/ssh-probe-local.json`/`.txt`. URL choisie directement, **pas obtenue par Google**, client mini uniquement.
- Pour terminer la demande : lancer la commande prête sur l'Air et traiter manuellement le challenge Google s'il revient sur le mini. Le seul accès SSH confirmé Air → mini ne valide pas encore Air → API PQ. Tailscale Serve reste non configuré/non validé.

## JSON structuré et DOM — 10 octobre

Demande explicite : ajouter le JSON structuré et vérifier si le DOM complète les pages complexes. Réalisé : `GET .../content?format=structured`, arbre filtré en option `include_dom=true` ; toujours 202 → job → artefact JSON protégé par content:read. Nouveaux `structured.py`/`extraction.js`, format partagé dans models ; OpenAPI exporté actualisé. Aucun nouveau paquet.

- Le DOM rendu est utilisé dans les deux modes : texte après hydratation, listes imbriquées, tables HTML et ARIA, contrôles/labels/formulaires, métadonnées et JSON-LD, Shadow DOM ouvert/slots, documents d'iframes (autre origine aussi). Le HTML rendu simple conserve l'hydratation mais ne développe pas le shadow ni les documents iframe ; preuve dans `tests/test_structured.py`.
- Arbre optionnel avec IDs locaux au document/snapshot et attributs autorisés. JSON compact lisible et régions/relations complémentaires en DOM. Champs input/textarea et valeurs d'options exclus ; scripts/styles/cachés exclus. Pas de JS fourni par client ni d'action/scroll/fetch automatiques.
- Bornes : 4 documents principal compris, 2 000 nœuds visités, profondeur 32, texte et collections bornés. Les nœuds cachés/omis et scripts JSON-LD invalides comptent dans les limites. Truncation/partial/frames indisponibles explicites ; quotas/TTL habituels appliqués.
- Limites : contenu déjà monté seulement (attente/actions explicites pour lazy loading/SPA/listes virtualisées), closed shadows inaccessibles, canvas/SVG visuels nécessitent capture, snapshot non atomique entre frames. Heuristiques de région main et CSS, pas de reconstruction visuelle complète.
- Vérifié : suite hors UI `pytest --browser --headed -q --ignore=tests/test_ui.py` **56 passed, 2 skipped**, 32,42 s. Après renforcement de bornes et nouveau cas de nœuds cachés : structured/OpenAPI **8 passed**, 17,84 s. Tests UI antérieurs non rejoués ; diagnostics Google/DDG non relancés. Ruff/Node syntaxe conformes ; wheel hors ligne avec JS inclus/import depuis wheel décompressé vérifiés.
- Exemples réels fixture : `docs/testing/structured-complex-compact.json` (5 593 octets sérialisation Python sans indentation) et `structured-complex.json` (12 390 octets). Hydratation, open shadow+slot, iframe autre origine, hidden/closed/private values, tables/formulaires/limites/données invalides vérifiés. Aucun contenu privé de fixture dans le résultat.
- Page publique réelle via HTTP sur mini : `https://playwright.dev/python/docs/intro`, **34 blocs**, JSON avec arbre **98 774 octets**, non tronqué à cet essai, téléchargement/copie par serveur temporaire/arrêt vérifiés. `docs/testing/ssh-probe-structured-local.json` et `.content.json`. Essai avant le dernier renforcement du comptage de nœuds, documenté comme tel ; URL directe, pas recherche Google ni test depuis Air.
- Clients de test acceptent `--format structured` et `--include-dom` (text reste défaut) ; fichier `.content.json` séparé du rapport et recopié sur mini. Commande Air actuelle : `ssh macmini-codex 'cat Documents/Codex/PageQuay/examples/probe_via_ssh.py' | python3 - --human --format structured`. Ajouter --include-dom si souhaité. Toujours non exécutée depuis l'Air.

Contrat et sources : `docs/EXTRACTION.md`. Reprise : utiliser le JSON par défaut pour lecture, ajouter l'arbre pour inspection des composants ; ne pas prétendre que le DOM révèle des éléments non chargés, racines fermées ou données de pixels.

## Publication GitHub — 10 octobre

- Demande utilisateur : pousser le projet sous `tmcuh1982`. Compte connecté vérifié ; dépôt existant public `https://github.com/tmcuh1982/PageQuay`, droits admin/push.
- Git local initialisé, `origin` configuré en HTTPS, historique initial distant conservé sur `main`. Identité Git locale configurée avec une adresse GitHub noreply.
- Sources, tests et documents préparés ; captures et diagnostics restent locaux, exclus par `.gitignore`, ainsi que secrets/bases/profils/sauvegardes. Détails personnels réseau/chemins retirés ; `probe_via_ssh.py --remote-root` configurable, défaut relatif au home SSH.
- Vérification avant publication : `pytest -q` **50 passed, 10 skipped**, 2,61 s ; les tests Chromium et diagnostics tiers sont opt-in. Warning Starlette/httpx conservé. Ruff format sur tous les 47 fichiers Python conforme ; aide CLI SSH vérifiée. Deux lignes du client d'exemple ont été reformattées.
- Audit des 71 fichiers préparés : aucun nom/adresse réseau personnels ciblés ni forme de clé privée/token GitHub/AWS ; seuls rapport et deux exemples de fixture inclus dans `docs/testing/`. Aucun fichier de capture, base ou clé préparé.
- Commit local du MVP : `ced0201`, parent distant initial `5e85c7b`. Le push HTTPS a échoué faute d'identifiants GitHub dans le terminal. La validation automatique avait ensuite refusé le transfert via l'application, faute de confirmation de l'exposition publique.
- L'utilisateur a explicitement répondu **« Publier dans le dépôt public existant »**. Ce choix autorise la publication sur `tmcuh1982/PageQuay` public. Transfert via la connexion GitHub de l'application, puis récupération Git HTTPS en lecture pour synchroniser l'historique local ; aucun identifiant terminal créé ni secret copié.
- Nouvelle tentative après confirmation : GitHub a refusé `create_tree` avec **403 Resource not accessible by integration**. Les outils de connexion retournent `installations: []` et `accounts: []` pour ce compte. Le plugin GitHub est installé et le compte OAuth est connecté, mais l'accès en écriture du connecteur au dépôt n'est pas opérationnel. Aucun arbre/commit distant créé ni code publié. Le dépôt distant reste sur `5e85c7b` (README initial). Reconfiguration de la connexion GitHub avec accès au dépôt PageQuay demandée à l'utilisateur ; reprendre l'envoi après configuration, sans redemander la visibilité publique déjà confirmée.

## Mise à jour de la documentation locale et GitHub — 10 octobre

- Demande explicite : actualiser la documentation sur GitHub et dans le dossier local. README enrichi d'un sommaire, d'un état de disponibilité des sources et d'instructions d'installation portables ; diagnostics exclus du dépôt clairement identifiés.
- Nouveaux `docs/STATUS.md` (fonctionnalités, preuves de validation, recettes restantes, état distant) et `docs/PUBLISHING.md` (accès requis, fichiers publiables, synchronisation et vérification). Ils distinguent publication des sources, déploiement du service et simple publication des documents.
- Liens relatifs du README et des deux nouveaux documents contrôlés : aucune cible manquante. Mise à jour documentaire seulement, aucune suite navigateur relancée.
- GitHub recontrôlé : dépôt public et droit utilisateur push/admin ; aucune installation de l'application détectée. README distant toujours une seule ligne. Tentative de mise à jour via l'API Contents (`update_file`, avec le SHA du README relu juste avant) : même **403 Resource not accessible by integration**. La documentation distante n'a pas changé ; les documents locaux sont prêts à publier quand l'accès en écriture sera opérationnel. L'accord de visibilité publique reste acquis.

## Publication effective — 10 octobre

- L'utilisateur a confirmé la reconfiguration du plugin ; les outils ont encore retourné installations vides et 403 sur une création de blob. Le Git HTTPS non authentifié était aussi inutilisable. Ces blocages décrivent les tentatives précédentes, pas l'état actuel de publication.
- Client officiel GitHub CLI **2.102.0** installé via Homebrew sur le mini. Connexion directe par code navigateur validée par l'utilisateur ; `gh api user --jq .login` confirme **tmcuh1982**. Aucun token affiché ou copié dans le projet. Identifiants CLI stockés dans un fichier hors du dépôt, permissions **0600** vérifiées ; stockage système sécurisé non utilisé par gh lors de cette connexion.
- Helper Git configuré **localement dans ce dépôt** pour appeler `/opt/homebrew/bin/gh auth git-credential`. Aucun réglage de credentials des autres projets modifié par cette configuration locale.
- **Premier push réussi** de `5e85c7b` à `ad0c861` sur `origin/main` ; référence distante relue identique. Tous les commits de développement conservés, aucun push forcé. Sources et documentation disponibles sur `https://github.com/tmcuh1982/PageQuay`.
- README, STATUS et PUBLISHING actualisés : publication débloquée, installation par clone public, voie CLI documentée. Les limites de recette Google/Air, déploiement et protection réseau restent celles réellement testées ; aucun nouveau test de navigateur ou de déploiement exécuté pour cette opération.

## 10 octobre — service permanent et administration locale

- Machine vérifiée : Mac mini, hostname Tailscale `VOTRE_MACHINE.VOTRE_TAILNET.ts.net`. Installation explicitement demandée par l’utilisateur.
- LaunchAgent utilisateur `~/Library/LaunchAgents/local.pagequay.gateway.plist` chargé, RunAtLoad/KeepAlive ; runtime `~/Library/Application Support/PageQuayService`, données `~/Library/Application Support/PageQuay`. Le lancement direct depuis Documents était bloqué par macOS. La copie `.venv` utilise son Python Homebrew et son `.pth` vise la copie de sources hors Documents. Pour les futures modifications, synchroniser aussi cette copie et son `.env`, puis recharger le service après arrêt complet.
- Préférence utilisateur : **aucune administration via Tailscale**. CLI ouvre admin locale 8765 et API seule 8766, même runtime/processus. Middleware filtre le port réel 8766 vers `/v1/` et health ; ni cookies, ni Host/headers ne donnent accès à l’admin. `.env` local : origines HTTP loopback, Secure cookies=false ; hostname tailnet autorisé pour l’API.
- Serve toujours non activé : aucune config ; tentatives précédentes en attente vers 8765 annulées. Utiliser désormais le backend **8766**, jamais 8765. Compte admin à initialiser interactivement si absent.
- 51 tests réussis/10 ignorés hors sandbox réseau, Ruff conforme ; nouveau test avec cookie admin explicite réexécuté. Contrôles HTTP réels conformes : login local 200, admin sur API 404, health 200, API anonyme 401. Reboot et accès réel depuis l’Air non vérifiés.

### Connexion locale — correctif CSRF

L’utilisateur a créé son administrateur mais Safari affichait `Invalid login CSRF` sur 127.0.0.1:8765/admin/login. Runtime vérifié : Secure=false, origines locales correctes. Gestion des formulaires corrigée : cookie `pq_login_nonce` sous /admin, indépendant du cookie legacy, nonce stable entre pages, formulaire récupérable avec message français et 403 pour CSRF manquant/périmé ; origine étrangère toujours refusée. Déployé dans PageQuayService/admin.py, service redémarré et Safari rechargé. 53 tests/10 skipped + UI Chromium réel sur compte jetable passent ; CSRF validé en HTTP réel sans mot de passe, admin toujours 404 sur8766. Login réel laissé à l’utilisateur.

### Formulaire de clés API

Aide ajoutée pour requêtes/minute (appels API, suivi/téléchargement inclus, plafond effectif min clé/projet, erreur 429). Expiration par case explicite, désactivée par défaut ; décocher vide/désactive le champ et sérialise null, liste « Sans expiration ». Champ texte vide désactivé pour éviter la date indicative trompeuse de Safari ; datetime-local lorsqu’activé. UI Chromium testée avec/sans expiration, captures inspectées, déploiement template/JS/CSS dans runtime sans arrêt. Safari réel vérifié et formulaire rechargé ; aucune clé réelle créée ou modifiée.

### Modification de la sécurité des clés

Bouton « Modifier la sécurité » et formulaire prérempli ajoutés sur la console locale. Edition nom/scopes/quota/expiration ; projet et secret stables ; Annuler ne sauvegarde pas. GET admin/keys/{id}/edit et POST admin/keys/{id}/update avec session+CSRF, KeyUpdate complet, dates finies futures/null, scopes non vides reconnus, quota 1–600. Clé révoquée verrouillée, clé expirée éditable. Droit retiré : seuls ses jobs sont annulés ; compteur quota conservé. Audit key.updated. Dates préremplies en heure navigateur, timestamp original conservé si inchangé.

63 tests/10 ignorés + UI réelle Chromium réussis. Captures inspectées, table mobile défilante. Runtime admin.py/auth.py/models.py/template/JS/CSS mis à jour et service rechargé sans job actif ; clés réelles inchangées, nouvelle mutation locale anonyme 401 et publique 404. OpenAPI/README/statut actualisés.

### Informations de la clé depuis le client

GET /v1/projects/{slug}/key-info avec Bearer du projet, sans scope supplémentaire : key_id/name/prefix, project slug/name, scopes, expires_at (Unix UTC/null), rate_limit configured_requests_per_minute/project_requests_per_minute/effective_requests_per_minute/window_seconds=60/remaining_requests/resets_at. Quota REST consommé par cet appel, compteur commun conservé ; 429 si déjà épuisé. Réponse filtrée/typée/no-store, aucune donnée privée ni autre clé. Expirée/révoquée 401 ; autre projet ou projet désactivé 403. Limites spécifiques opérations/WS supplémentaires documentées. README/OpenAPI et examples/key_info.py (stdlib, pas de redirection du Bearer) ajoutés/actualisés.

70 tests/10 ignorés, Ruff conforme (52 fichiers), export OpenAPI vérifié. api.py/models.py déployés dans runtime Mac mini, LaunchAgent redémarré sans job actif. Ready 200, nouvelle route anonyme 401 sur8766, admin toujours404 sur8766 et login200 sur8765. Métadonnées réelles inchangées. Serve reste non activé ; authentification info testée sur comptes jetables uniquement.

### Tailscale Serve désormais actif — 10 octobre

Diagnostic : serveur local sain, Tailscale connecté/ShieldsUp=false, mais Serve non activé et aucune route. Safari connecté initialement à un compte Apple sans machines, expliquant probablement la404 du lien dédié au node du réseau GitHub. Utilisateur reconnecté au compte GitHub du réseau attendu puis activation faite par l’utilisateur ; page « Serve is ready to use » observée. La CLI en attente a signalé un conflit etag concurrent mais l’état réel vérifié est correct et persistant : HTTPS443, hostname VOTRE_MACHINE.VOTRE_TAILNET.ts.net, proxy http://127.0.0.1:8766. Aucune route Funnel (AllowFunnel absent), aucune section Foreground.

Adresse client PQ_URL=https://VOTRE_MACHINE.VOTRE_TAILNET.ts.net, sans port8766. Vérification HTTPS depuis le Mac mini avec certificat validé : health/ready200, key-info anonyme401, admin/login/admin/static404. Administration reste locale8765. Accès depuis un autre appareil et ACL/reboot restent non testés. L’ancien état « Serve non activé » décrit les étapes précédant cette activation.

### Fenêtres minimisées pour les ouvertures distantes — 10 octobre

Demande utilisateur : permettre de minimiser les pages ouvertes depuis l’accès distant. Boutons **Minimiser** / **Restaurer** dans Projets / Profils et Sessions / Onglets, mutations admin locales avec session/CSRF, audit browser.minimized/browser.restored. Option globale `browser_start_minimized` (false par défaut), case dans Paramètres synchronisée avec le JSON ; surcharge par projet possible. Le mode headless effectif au lancement est conservé dans BrowserState, sans fenêtre à piloter.

Chromium macOS restaure nativement une fenêtre minimisée lors de context.new_page : l’état natif des fenêtres est lu avant création et réappliqué après, y compris si minimisation avec le bouton jaune macOS. Les animations natives de restauration sont attendues (borne 5 s). Les tâches de navigation/actions/extraction restent opérationnelles. Les captures Playwright et CDP directes bloquent lorsque macOS suspend le rendu de la fenêtre minimisée ; la capture restaure donc brièvement la fenêtre puis la minimise dans finally, y compris après échec/annulation. Cette limite est indiquée dans l’interface et README/OPERATIONS.

Validation finale : 73 tests réussis / 11 ignorés sans Chromium ; 3 tests Chromium visibles réussis (UI réelle, cycle de vie/profils et navigation distante minimisée avec actions/extraction/capture/restauration/isolation). Ruff check/format et git diff --check conformes. Captures UI et artefact PNG de fixture inspectés. Déploiement de browser.py/settings.py/admin.py/template/JS dans PageQuayService, sauvegarde des sources précédentes sous tmp, redémarrage après vérification de zéro job actif. Ready/login locaux 200 ; admin et contrôle fenêtre toujours 404 sur le port API 8766. Réglage de démarrage minimisé laissé désactivé jusqu’à choix dans Paramètres. Aucun projet/clé/profil réel modifié ; fenêtres fermées par le redémarrage du service.

### Recherche DuckDuckGo et intégration ProjectX — contrat 0.2.0

Prompt joint appliqué : pagination native, quotas détaillés, idempotence, cycle de vie des onglets, OpenAPI publié et exemple Python serveur. Diagnostic prouvé : plafond min(request.limit, search_max_results), défaut10 ; quota PageQuay 6 tentatives par fenêtre fixe60s/projet/moteur partagé entre clés/admin, distinct du quota REST par clé. Configuration du projet de référence relue : aucune surcharge, plafond10. Les anciennes observations ne prouvent pas la cause exacte de chaque ancien RATE_LIMITED ni un quota DuckDuckGo.

Search.cursor opaque aléatoire43caractères, snapshots SQLite migration003 (search_cursors/search_idempotency). Reliquats d’une page avant son formulaire Next natif GET/POST, aucun offset fabriqué ; actions HTTPS DuckDuckGo/html bornées, transport navigateur/proxy existant. Liens exact_url et rangs/source conservés en plus du url normalisé historique. Métadonnées compteurs/moteurs/continuation/has_more triétat/motif/partiel. Bornes par défaut10pages/200résultats/15min/100états de curseurs par projet, read200hits max/document. Répétitions/no progress arrêtées. Cursor lié projet/query/engine/locale, réservé atomiquement avec job, consommé après succès, libéré après échec/annulation/restart ; reset/purge invalident. État consommé/expiré effacé, tombstones1jour. Onglet interne propre par search, fermé dans finally, pas d’onglet entre continuations. Allocation protégée pour fermer l’onglet même si annulation arrive pendant sa création ; annulation d’un runner avant première instruction libère aussi réservation/file.

Idempotency-Key optionnel POST/search, namespace projet+clé, corps validé canonique ; même opération24h, corps différent409, persiste après SQLite réouvert/restart. Rejeu REST consomme quota de clé mais aucun nouveau moteur/job. Résultat soumis au TTL habituel, pas garanti24h ; job échoué non rejoué. Retry-After HTTP quand connu, errors.details portée/cause/date/délai/continuation/partiels des jobs. Statuts waiting_for_human et chemins relatifs inchangés ; aucun solveur ni basculement d’un engine explicite. GET/openapi.json maintenant autorisé sur8766/HTTPS, schéma filtré aux routes client/health, contrat version0.2.0.

Livrables : docs/SEARCH_API.md, docs/openapi.json, examples/search_duckduckgo.py (stdlib, multiqueries, checkpoint0600 avant POST, retries idempotents bornés, Bearer uniquement environnement/header, redirects refusés). Versions package/API0.2.0 et docs mises à jour. Dernière suite Chromium visible complète :116passed/3skipped,72.84s ; Ruff42fichiers conforme. Exemple retesté5cas après ajustementcheckpoint/aideCLI. Diagnostic DDG réel :3queries (fr-FR/en-US) toutes CAPTCHA, challenge.required puis TIMEOUT5s, zéro onglet restant. Preuves docs/testing/duckduckgo-native-*.html + duckduckgo-pagination-live.json locales ; trois pages natives réelles non validées.

Déployé aprèszérojobactif, backup privé sources+SQLite sous tmp (pq-search-02-backup-*),16fichiersruntime et LaunchAgent relancé. Ready/login locaux200 ; OpenAPI8766 version0.2.0 ; admin8766 toujours404. HTTPSréel : ready200/OpenAPI200/admin404/searchanonyme401. Aucun jeton réel lu/affiché ; aucun changement de clé/projet réel ni hausse de quota. Rejeu authentifié depuis le client du projet de référence surserviceinstallé non exécuté, les tests moteurs utilisent runtimejetable. Modifications locales non poussées à GitHub dans cette demande.

### Publication du lot 0.2

Demande explicite de commit GitHub sur le dépôt public existant `tmcuh1982/PageQuay`, branche `main`. Le lot inclut sources, tests, contrats et exemples ; secrets, bases, profils, captures, diagnostics privés et checkpoints sont exclus. Les noms Tailscale réels et le compte du réseau ont été remplacés par des indications portables dans cette mémoire et le rapport public.

### Port HTTPS externe global — 10 octobre 2026

Demande utilisateur : configurer le port externe depuis la console, indépendamment des projets, via une redirection Tailscale. Paramètres → Accès externe affiche la route privée réellement active et accepte un port HTTPS de 1 à 65535. Application immédiate par CLI Serve --bg vers le seul listener API ; vérification de la nouvelle route, retrait de l’ancienne, contrôle final et récupération sur erreur. Refus des ports occupés/partagés, Funnel, Serve temporaire et formulaire périmé. CSRF/session locale ; route admin inaccessible sur le listener API. Aucun choix de nouveau port imposé à l’utilisateur.

Validation : suite générale 126 passed/14 skipped ; 20 tests dédiés ; formulaire Chromium réel desktop/mobile réussi avec CLI Tailscale simulée. Ruff et diff --check conformes. Les essais avec sockets nécessitent une exécution hors sandbox. Lecture seule réelle confirme Serve privé HTTPS443. Déploiement des cinq fichiers runtime dans la copie installée après zéro job actif ; redémarrage LaunchAgent et health200. Sauvegarde des sources privée sous /private/tmp/pq-external-port-backup-4md2ra4o. Aucun changement réel de port Tailscale exécuté pour la recette ; cette application sera déclenchée par le bouton admin. Sources non publiées dans cette demande.

### Correctif du bouton Appliquer grisé — 10 octobre 2026

Cause reproduite : le PATH LaunchAgent /usr/bin:/bin:/usr/sbin:/sbin omet le lanceur CLI /usr/local/bin/tailscale. Le fallback direct vers le binaire Tailscale.app renvoie CLIError3 en texte avec code0 ; JSON illisible et available=false. Le lanceur shell répond correctement au status/serve status dans le même environnement. Recherche supplémentaire /usr/local/bin:/opt/homebrew/bin avant fallback app ; priorité du PATH explicite conservée. Deux tests de régression ajoutés, 41 tests ciblés réussis, Ruff conforme. Correctif du seul module external_access déployé après zéro job actif et sauvegarde ; health200. Safari réel rechargé : adresse privée active et bouton Appliquer actif ; saisie utilisateur8443 rétablie sans soumettre ni modifier le port réellement actif443.

### Audit URL / Ko / fonctions / destinations — 10 octobre 2026

Demande utilisateur : voir URL visitées, taille téléchargée en Ko, fonctions appelées et destination obtenue (« next page »). Ajout audit.py/TabAudit, migration005 detailsJSON+indexjob ; écoute request/response/requestfinished/requestfailed/framenavigated, tailles Playwright responseBodySize encodées hors en-têtes. Chaque ressource distincte, codesHTTP/redirections relatifs résolus, taille inconnue=null. Traçage fonctions navigate/actions et chaque action/extract/screenshot/submit_search_form, source et URL obtenue, label pagination canonique next page ; job lifecycle lié ID. Métadonnées d’acteur/job capturées à l’émission de requête, onglet verrouillé pendant opérations, navigation manuelle acteurbrowser ; tâches tailles drainées à l’arrêt. Tous paramètresquery/userinfo/fragments supprimés avant stockage ; chemins visibles ; aucun formulaire/POST/cookie/selector/messagebrut.

UI Audit : colonnes et filtres type/job, filtres conservés, lien parjob, Ko=1024, mesures inconnues visibles, pas de rétroactivité.159passed/4skipped suitecomplèteChromium, Ruff et diff-check conformes ; captures desktop/mobile inspectées ; tests gzip exact,302/303,Next+aria,POSTnative,image,404,blocageprivé,acteurmanuel,upgradeancien,erreurs/annulation,escaping/filtres.

Huit fichiers déployés dans runtime installé ; zéro job actif, backup sources+SQLite /private/tmp/pq-audit-backup-2av65ix9, LaunchAgent rechargé et migration005 vérifiée. Sources runtime identiques parhash ; ready/login200, auditlocalanonyme303, audit8766=404, key-info8766anonyme401. Aucun projet/clé/réglage réseau changé, aucunpush.

### Audit plus compact — 10 octobre 2026

Demande utilisateur : réduire l’espacement entre les lignes de la grille Audit. CSS limité à audit-table : padding cellules vertical16→6px/horizontal10→8px, line-height1.3 ; en-têtes8px et badge pagination plus compact (marge3px, padding2px8px, police10px). CSS seul déployé avec sauvegarde privée sous tmp, sans redémarrage. Vérification du CSS servi et aperçu Chromium jetable : lignes représentatives91.5→65.69px et61→42.89px (environ28–30% moins hautes), capture /private/tmp/pq-audit-compact.png inspectée. Aucun changement de données ou de traitement.

### URL en clair dans l’audit admin — préférence utilisateur, 10 octobre 2026

L’utilisateur refuse les protections de type `q=[masque]&kl=[masque]` côté audit admin. Préférence explicite : conserver/afficher les paramètres d’URL en clair, dont q et kl. audit_url conserve désormais parts.query et parts.fragment sans parse/réencodage ; userinfo toujours retiré. Documentation et aide UI alignées ; cette décision remplace le masquage antérieur pour les nouvelles entrées. L’historique déjà masqué est irréversible. Échappement HTML et accès admin local conservés.

6testsréussis (audit+UIChromium), URLDDG/paramsrépétés/vides/encodages/fragments/redirections testés, corpsPOST/saisies/messagesbruts toujours exclus. Ruff/diff-check conformes. audit.py et template déployés après zéro job actif ; sauvegarde /private/tmp/pq-audit-clear-urls-d132upsq, LaunchAgent rechargé,ready/login200,auditlocalanonyme303,auditAPI404. Aucun changement de clés/projets/réseau ni push.

### Dernière colonne Audit accessible — 10 octobre 2026

Utilisateur : scrollbar absente/dernière colonne invisible. Ajout d’une barre « Colonnes » toujours visible au-dessus du tableau (curseur range et flèches gauche/droite), synchronisée avec scrollLeft, molette/touch et redimensionnement via ResizeObserver. Tableau région focusable, barre native WebKit stylée ; contrôles désactivés aux limites/sans débordement. Grille compacte et URL en clair conservées.

Test UI Chromium existant étendu : flèche droite, curseur End/Home et visibilité géométrique de la dernière colonne sur desktop/mobile, aucun débordement du document ni erreurJS ;1testUIréussi, Ruff/diffcheck conformes, captures inspectées. JS/CSS/template déployés à chaud sans redémarrage, sauvegarde /private/tmp/pq-audit-scroll-jxb7__ui et hashes runtime identiques. Aucun changement aux données/jobs/réseau.

### Job combobox et date-time Audit — 10 octobre 2026

Demande utilisateur : Job en combobox, mêmes hauteurs pour tous filtres, dates+heures et raccourcis last10min/lasthour/Today. Implémenté select natif avec200jobs récents de l’audit (ID/projet/kind/date), sélection horsliste conservée. Grilles CSS responsive/champs+boutons42px. datetime-local step1 initialisés depuis dates UTC validées ; locale/navigateur indiquée, conversion ISO UTC à la soumission ; backend datetime aware respecte offset, naïf=UTC historique, bornes inclusives et intervalle inversé refusé. Raccourcis appliqués immédiatement, filtrescourants préservés, Today=minuitlocal→maintenant. Form.action évité à cause du champ name=action qui masque cette propriété DOM ; getAttribute utilisé.

26tests ciblés validés (audit/security+UIChromium), select/hauteurs/durées600/3600/TodayWarsaw/saisie locale et restitution testés ; desktop/mobile/scrollhorizontal inspectés. Ruff/diffcheck conformes. admin.py+JS+CSS+template déployés après zérojobactif ; sauvegarde /private/tmp/pq-audit-filters-p2ub4be7, LaunchAgent rechargé ;ready/login200,auditlocalanonyme303,auditAPI404. Aucunpush/changementréseau/projets/clés.

### Last hour :20:46UTC/22:46local — 10 octobre 2026

Utilisateur pense last hour décalé2h. Lecture réelle Safari confirme filtres22:05–23:05Europe/Warsaw (query20:05Z–21:05Z), event/grille/Job20:46UTC : filtrecorrect, fuseauxmélangés dansaffichage. Alignement UIAudit : headerDateLocale, cellules data-audit-epoch et optionsJobdate formatées parJS enlocale navigateur ; tooltipcellISOexact+zone. Données/UTC/querybounds inchangées.

7tests audit/UIréussis, fixture2026-10-10T20:46Z affichée22:46dansgrilleetJobWarsaw, presets/localconversions toujoursvalides. JS+template déployésàchaud, backup /private/tmp/pq-audit-local-time-__dk7eaa. Safari réel rechargé et22:46observé dansgrilleetJob avecsélection/période conservées ; aucuneautreinteraction aprèsvalidation. Premier getAppSafari trèslent côtéoutil (840s), appelsensuite<1s. Aucun changementdonnées/jobs/réseau ni push.

### Durées d’exécution dans Audit — 11 octobre 2026

Ajout de la colonne Durée, affichée en ms sous une seconde et en secondes au-delà. Mesures monotones des fonctions, y compris opérations imbriquées, et de chaque requête réseau depuis request jusqu’à requestfinished/requestfailed ; la récupération asynchrone des tailles n’allonge pas la mesure réseau. Durées des jobs terminés/échoués/annulés depuis l’acquisition du créneau d’exécution : file d’attente exclue, attente humaine incluse. Jobs annulés avant exécution et anciens événements sans mesure affichent « — ». Stockage dans details.duration_ms, sans migration supplémentaire. Grille compacte et défilement horizontal conservés.

Validation : 14 tests audit/jobs/UI réussis avec Chromium. Durées déterministes, imbrication, absence d’inflation réseau par collecte de taille, erreurs/annulations, queue exclue, annulation avant lancement et formats ms/s vérifiés ; dernière colonne accessible sur desktop/mobile, captures inspectées. Ruff check/format et diff-check conformes. Quatre fichiers runtime synchronisés après zéro job actif avec sauvegarde privée /private/tmp/pq-audit-duration-pfal2l3w et redémarrage du LaunchAgent ; ready/login 200, audit local anonyme 303 et audit API 404. Aucun changement de projets, clés ou réglages réseau ; aucun push.


### Port API local configurable sans Tailscale — 12 octobre 2026

Paramètres → Accès local : port API modifiable (1024–65535), indépendant du HTTPS Tailscale ; validation stricte, conflit avec la console/port occupé, session admin et CSRF, détection des éditions concurrentes. Surcharge atomique local-api.json (0600) dans PQ_DATA_DIR, prioritaire sur PQ_API_PORT au prochain lancement ; port actif et port enregistré distincts, redémarrage requis visible, annulation possible en enregistrant le port actif. CLI serve/doctor et create_app sans configuration explicite lisent la surcharge ; la CLI transmet ensuite la même configuration résolue aux sockets et au middleware. Aucune route Serve modifiée ; si utilisée, sa destination doit être adaptée séparément.

Validation : suite 176 passed / 15 skipped ; 38 tests local/externe repassés après ajustement de la lecture au démarrage ; recette Chromium 1 passed, formulaire utilisable sans Tailscale, corps envoyé/persistance/avertissement et desktop/mobile inspectés. Bind CLI loopback, refus admin sur le nouveau port et API anonyme401 vérifiés. Ruff check/format et diff-check conformes. Cinq fichiers runtime déployés après zéro job actif, sauvegarde /private/tmp/pq-local-port-backup-gkdviy_l et redémarrage LaunchAgent ; hashes identiques, ready/login200, mutation locale anonyme401 et mutation/adminAPI404. Ports réels8765/8766 conservés, aucune surcharge réelle créée, aucun changement de clés/projets/routes réseau ni push.


### Correctifs Codex Security — 12 octobre 2026

Demande utilisateur : appliquer les propositions de sécurité du scan. Deux findings traités : audit/tâches/commits sans bornes et chaînes de pages transférées ou persistées avant validation. Admission centrale, files/quota/réserve admin, writer SQLite dédié, volume logique plafonné, compteurs API séparés et regroupement signalé. Lectures fixes dans un monde Chromium isolé, bornes avant retour, titres limités à 512 caractères avec indicateur, contenu excessif en 413, résultats/erreurs/partiels de jobs bornés. Migration 006 : compteurs disponibles des dernières 24 h repris une seule fois, statistiques de volume/purge ; anciennes valeurs de jobs excessives retirées explicitement. Aucune dépendance ajoutée.

Revue indépendante : récupération FrameTree et comparaison d’URL avec fragment supprimées ; résolution par contextes/chemin borné, iframe avec #section testée. Aucun flush synchrone sur la boucle asyncio ; rétention avec writer suspendu rend la main en moins de 0,2 s. Surcharge de 300 réponses 401 : total 300 et détail ≤30 ; réserves, plafonds en lignes/octets, alerte visible, panne/réessai, cardinalité élevée, pages hostiles/monkeypatches/surrogates et migration testés.

Validation : suite normale 186 passed / 16 skipped ; Chromium structured/audit/budgets 24 passed ; budgets final 11 passed, puis complément octets 10 passed / 1 skipped ; jobs/local 22 passed. Ruff sur 53 fichiers, Node sur deux scripts et diff-check conformes. Suite intégrale headed : 194 passed / 5 failed / 3 skipped initialement ; quatre assertions d’audit immédiat adaptées et repassées. Seul le test de minimisation macOS échoue encore. Sur les sources d’avant correction, le même test reproduit le timeout natif Browser.getWindowBounds avant les lecteurs modifiés. Recette complète de minimisation non revendiquée ; 198 tests distincts passent. Aucun diagnostic moteur externe lancé.

19 fichiers runtime synchronisés après constat de zéro job inachevé ; sauvegarde privée sources+SQLite sous /private/tmp/pq-security-fix-backup-_dxwo_07, LaunchAgent rechargé, migration 006 et hashes confirmés. Ready/login 200, admin sur API 404, key-info anonyme 401, OpenAPI 200 ; réserves audit dans les plafonds et compteur API persisté. Ports 8765/8766 conservés ; aucun changement de projet/clé/profil/routes Tailscale, aucun push.

Rapport local : /Users/lolo/.codex/state/plugins/codex-security/scans/PageQuay/artifacts-1e5922c55da29fe25860ff1574887403ff9e016bb2ad918ac1d802423f6cfb12/artifacts/fix_report.md.

Limites : audit partiel sous surcharge ; queues/compteurs en attente perdables sur crash ou panne prolongée, réserves également finies. Les plafonds logiques ne réduisent pas immédiatement le fichier SQLite et ne plafonnent pas Chromium/driver. La minimisation macOS reste un problème préexistant distinct.


### Acquisition exacte UniversRobot et diagnostic iframe — 12 octobre 2026

Demandes collées CHG-20261010-004 et CHG-20261012-029. Extension additive 0.2.0 : preuve HTTP principale (URL demandée/finale, statut nullable+motif, Content-Type, chaîne bornée, UTC/navigation_id), expected_url/allow_redirects opt-in, guard CDP de redirections persistant sans lecture de corps, révision nav/frames et même contexte isolé vérifié après capture. HTTPS443 strict ; mode historique HTTP/HTTPS conservé. Couverture redirect OOPIF non attestée : mode strict refuse explicitement tout réseau de frame enfant, export partial ; mode historique et extraction OOPIF publique restent disponibles. Aucun relâchement réseau.

Job/tab/projet/clé corrélés au 202, request_id persisté migration007, idempotence création/navigation réutilisant stockage existant sans modifier anciens hashes search. Fermeture clé propriétaire, timeout/annulation conservent onglet et preuve ; clients annulent/drainent puis ferment seulement ID détenu. Robots opt-in borné en onglet auxiliaire fermé dans finally, PageQuay/0.2.0 déclaré, refus avant document. XPath natif dérivé parents/frères avec null explicite ShadowDOM/bornes. Causes de frames distinctes, étape/durée/budget10s/is_detached ; logs corrélés request/job/tab/frame/artifact, chaîne types/codes expurgée, aucun message arbitraire/page/cookie/Bearer/query/fragment. Ancien reason conservé sans prétendre prouver détachement.

Validation : normal217passed/27skipped avant deux compléments navigateur ; recette globale finale241passed/1failed/4skipped puis correctif de compatibilité job simulé sans kind dans navigateur (test inchangé), audit+acquisition20passed.242testsdistincts validés, aucun échec connu restant. Ciblé lecteurs/OpenAPI/budgets51passed, acquisition réelle13passed ; Ruff63fichiers, Node et diffcheck conformes. Quatre exclusions : minimisation native --headed et trois recettes --live. OpenAPI/docs/ACQUISITION.md, rapport docs/testing/ACQUISITION_REPORT.md et client serveur examples/acquire.py (checkpoint privé avant POST, récupération/annulation explicites, pas de retry création) livrés.

14fichiers runtime synchronisés après zérojobactif, migration007 appliquée, deux backups privés /private/tmp/pq-acquisition-backup-jo4wwihi (avant extension) et /private/tmp/pq-acquisition-backup-kfx1trt0 (avant dernier ajustement). LaunchAgent redémarré ; hashes identiques, ready/login200, APIready200/admin404/key-infoanonyme401/OpenAPIenrichi. Aucun changement de clé/projet/profil/port/Tailscale, aucun push. Redémarrage normal ferme onglets en mémoire ; ancien tab_id KUKA non réutilisé.

KUKA réel non reproduit : Bearer existant agentderecherche indisponible, SQLite stocke son hash. Demande asynchrone d’un chemin de fichier privé (sans coller secret) envoyée ; aucune clé créée/remplacée ou auth contournée. Cause des exports existants UNKNOWN ; un nouvel export via service instrumenté et logs corrélés reste requis. Ne pas assimiler réussite fixture OOPIF à cause ou succès réel KUKA.

Contrôle final en lecture seule : tables api_keys/projects/settings identiques au premier backup ; OpenAPI servi identique à docs/openapi.json.

Choix explicite utilisateur après livraison : « Livrer sans reproduction KUKA réelle ». Cette reproduction est exclue de la livraison acceptée ; aucun Bearer supplémentaire attendu. Cause KUKA conservée UNKNOWN, sans revendication de validation réelle.


### Correctif WORLD_NOT_FOUND KUKA — version 0.2.1, 12 octobre 2026

Nouvelle demande explicite : corriger et valider URL exacte https://my.kuka.com/s/?language=en_US, préserver mondes isolés/réseau/budgets, déployer et fournir traces. Trace originale21:38 retrouvée launchd.err.log : request33b5e8534d47d4983159c573/jobc31730835f8027edd14f0419b6ab54c9/tab1db2ad1f6a57b7aeab1eb96e7c93b8ef/artifact60ac68ea671b46ccbeed7e11003a85cd/f1 WORLD_NOT_FOUND26.01ms attachée. Bearer privé est uniquement sur la machine UniversRobot : utilisateur autorise runtimejetable sans leurclé puis demande déploiement ; UniversRobot relancera elle-même le test installé et transmettraIDs. Ne pas redemander ce chemin ni créer/remplacer une clé live.

Reproduction PageQuay jetable HTTP/ASGI/proxy/navigateur réels : après attente expliciteiframe10s, main69blocs, partialtrue/truncatedfalse, sessionpage2candidats, expected[2] (Playwright.child_frames), observed[[0],[]]. Ordre des objetsFrame non fiable pour indices natifsWindow.frames ; ordre DOM seul également non fiable (régression iframes préfixées). Correction sélecteurfixe pq_frame_slot content_scriptTrue utilityisolé : mappe Window[index]→élémentpropriétaire, vérifie content_frame identité ; aucun pageevaluate/DOMwrite ni comparaisonURLtitre. Chemins revérifiés avant/aprèslecture, mêmecontexteisolé vérifié. TargetCDP duplusprocheancêtre propriétaire choisi pour enfant interneOOPIF ; seuleerreur sanssessionséparée autorise poursuite. Budgets10s/4frames/128candidats/profondeur32/contenu et réseau inchangés ; inventaire128slots/propriétaires, shadow2000éléments, diagnostics8chemins entiers bornés. DOM caché sansrapport ne consomme pas budgetpropriétaires. Logs succès/échec corrélés avec version, ni page/URLquery/cookie/Bearer/messagebrut.

Capture réelle finale0.2.1 UTC20:05:01.931232 (22:05Warsaw) : URLfinaleexacte, main69, f1extracted, partialfalse/truncatedfalse ; sessionpage2candidats, expected/selected[0], observed[[0]],24.409ms, is_detachedfalse. req0eb1a5ac5483988332959676/job64e31857d3201278ff161cab6d8bfbfd/tabcebf49c37576b61e084c366b7b279a7d/artifact390f03a9aad543f474b90906cb6a87cb. Preuveprivée /private/tmp/pq-kuka-real-gmkxjspo/{frames.log,summary.json,artifact.json}, avant /private/tmp/pq-kuka-real-ttkoaw7e. IDs de runtimesjetables, pas APIinstallée. IframeKUKA-player9nœuds/2inclus,0bloctexte monté ; aucuneinterprétationvisuelleapp inventée.

Validation globaleChromium249passed/4skipped (minimisation--headed et3moteurs--live), puis ajustementinventaire final+régressiongrandDOMcaché33passed ciblés acquisition/structured/budgets. RégressionsordreFrame, absencecandidatsvschemins, OOPIFdescendant, FrameDOM vsWindowordre, monkeypatchespagedoc/élément, bornes128 et chemins sansvaleursarbitraires. Ruff64fichiers/format/diffcheck et uvlockcheckoffline conformes. Rapport docs/KUKA_FRAME_FIX.md et OpenAPI0.2.1 publiés dansdépôtlocal, paspush.

Déployé8sourcessourceidentiquesparhash +pyproject/uvlock, packageeditable réinstalléoffline/nodéps ; module/package/OpenAPI0.2.1 confirmés. Zérojobactif avantopération, backupprivé /private/tmp/pq-kuka-021-backup-5gtr49vj avec SQLite/sources/métadonnées/deploymentJSONsha256. LaunchAgent redémarré, ready/login200/APIadmin404/keyinfoanonyme401, OpenAPIliveidentiqueJSONlocal ; tablesapi_keys/projects/settings identiquesaubackup. Aucun assouplissementréseau. TestBearerdu serviceinstallé volontairementconfié àUniversRobot, non revendiqué.

Utilisateur demande aussi optionautorisationredirections : allow_redirects existe auPOSTcréation/navigation, défauttrue ; recette testée avec True explicite. Avec expected_url fixé lafinale doit resteridentique ; sinon caller vérifie finale avantcontent. Respectrobots/strictsubframenetwork peuvent refuser descibles nonattestées, jamaisrelâchés silencieusement. UseragentPageQuay/0.2.0 conservé malgrépatchpackage0.2.1 pour nepaschanger identité.


### Navigation/challenges/portée — 0.2.2 déployée, 12 octobre 2026

Dernière instruction : distinguer navigation et extraction ; attente passive Cloudflare ; waiting_for_human/reprise après intervention ; allow_redirects false jamais implicite ; destination finale différente expected_url -> scope_changed pour revue sans extraction ni transfert d’approbation ; lien avec KUKA WORLD_NOT_FOUND à démontrer séparément. Audit : respect_robots forçait tab.expected_url et client acquire.py forçaitfalse ; checkpoint d’extraction pris avanthumanwait. Correctifs : seulsfalseexplicites bloquentavantfollow (helperrobotsconservefalseexplicite), true défautAPI/consoleWSsearch/client ; robotsfinal réattestées avantlecture siURLdifférenteapprouvée. URLinitiale peutdifférerexpectedfinale avecTrue, HTTPS/443 et refusstrictsubframenetwork inchangés ; scope_url distincte persistéedansTab mémoire et héritéeextractionquandattenteomise, sansadoptertarget. Finalmismatch jobfailed/errorcode scope_changed/cibleredacted+sha/navproofexacte.

Détecteur état automatique/humain dansmondeisolé +signalréponseprincipale cf-mitigated challenge (Cloudflaredocprimaire). Signalconservé pendantrequeststart/hashhistory et effacé seulement aucommit d’uneréponse deremplacementnonchallenge. Sondagepassif250ms surbudgetnavigationrestant30sdepuisgoto, manualouexpired -> waiting_for_human mêmejob, screenshotdiagnostic scoped. Reprisevérifiechallenge puisURL etprendnouveaucheckpoint ; capturesinvalidéesparchallenge jetéesavantpublication, relecturefresh aprèsrésolution ; NAV_CHANGED nonchallenge et WORLD_NOT_FOUND restentrefusés sansretryglobal. Budgetsjob180+human600/lecteur10s/nœudsframesoctets/network inchangés. CLI --allow-redirects défauttrue/--no-allow-redirects/--expected-url/--resume ; checkpointsancienspayloadpréservés ; httpx follow_redirectsFalse APItransport reste pourprotégerBearer.

Suiteglobale265passed4skipped puisfinal48ciblés +5régressionsbrowser/signal (recouvrants) ; suiteantérieure1échecrestorefenêtremacOS durantrecettesconcurrentes résolu parretestisolé puisglobalesolo95s. Ruff60fichiers, lockoffline/diffcheckconformes. OpenAPIfichier interneavecadminpaths corrigéaucontratpublicfiltré ; nouvellerégressionégalitédocument/listener.

KUKAréeljetable revalidé0.2.2 : UTC20:25:38.877649 (22:25Warsaw), req14cdc846d3c4e3d87dbded52/jobe4328c80962996a46a0e875812b6c272/tab3d9d2e348b1819f12677e8b8c2e2ce61/artifactd360f3ee0ededa246a0a35aa0d3f99af/f1 extracted, main69, child0textblocks, partialfalse/truncatedfalse ; sessionpage2candidats expected/selected[0], observed[[0]],26.787ms attachée. Sourcejetable /private/tmp/pq-kuka-real-9506jh9f. Aucun challengeCloudflare réelobservé, liencausalnon démontré ; lecteurKUKA identitéFramePath indépendante inchangé. ToujoursUniversRobotqui faitrecetteBearerinstallée, aucunsecretàdemander/nouvellecléinstalléeàcréer.

Déploiement0.2.2 10sources +métadonnéespackageoffline sansdépendances, hasheségaux/modulepackageOpenAPI0.2.2/readylogin200 APIadmin404 keyinfoanonyme401 ; tablesapi_keys/projects/settings égalesbackup. Zérojobactifavant ; /private/tmp/pq-navigation-022-backup-_vjth5ei sourcesSQLite/métadonnées/deploymentJSONsha. VérificationinitialeinterrompuepardiffdocOpenAPIadminpaths, doccorrigée puisvérificationcomplète réussie sans secondredéploiement. AnciensIDsongletsfermésparrestart, aucunpush. docs/NAVIGATION_SCOPE.md+KUKA_FRAME_FIX.md+STATUS/ACQUISITION/READMEcontrat0.2.2 actualisés.


### Publication GitHub release — 13 octobre 2026

Utilisateur demande « publie sur github release ». Comptegh tmcuh1982/repo public tmcuh1982/PageQuay/main vérifiés, fetch basecc63893 ; 48tests acquisition/client/challenge/OpenAPI etRuff vérifiésànouveau, suiteglobale265+4skip existante conservée. Commitrelease `a763418894ca30adbe5bf3779fa6e7e76fe46882` (38fichiers, améliorationsacquisition+KUKA+navigation0.2.2), pushmain ettagannotév0.2.2 confirmé. Release stablepublique/nonbrouillon https://github.com/tmcuh1982/PageQuay/releases/tag/v0.2.2 créée viaGitHubCLI, notesdocs/releases/0.2.2.md.

Buildoffline uv depuisgitarchive ducommit seulement (pas .env/profile/SQLitecontenu réel). Assets pagequay-0.2.2-py3-none-any.whl, pagequay-0.2.2.tar.gz, SHA256SUMS ; ressourcesJS/migrations/templates/static incluses, installer/docs danssdist. Vérification3fichiersretéléchargés SHAidentiques +tagdereferencecommit. Privé /private/tmp/pq-github-release-022-_ys0k0pa/{summary.json,publication-verification.json,assets,downloaded}. SHAwhl01b1aabe69b3febef6064338991954de943c2ec7ae03766fa057dfbeeabe36ee, SHAsdist3cfe041785c6e89ae3e5497c5be2223e6d2d738a5b3f35bddb28bc99fb96d9f6. Tagreleaseimmuable ; miseàjourdocumentation depublicationseulementsurmain aprèsrelease, sourcesinchangées. AuthprivéeinstallationURtoujoursàleurcharge, pasnouveautestcléinstalléeclaim.


### 14 octobre 2026 — Suppression du User-Agent personnalisé

Utilisateur demande de conserver l’identifiant natif Chromium après boucle Cloudflare Music Store sur recherche Yamaha P-145. Surcharge de lancement supprimée ; preuve robots et règles appliquées à l’en-tête réellement envoyé. Régressions serveur local vérifient UA Mozilla/Chrome et groupes robots natif vs ancien PageQuay ; 64 tests acquisition/API/Chromium passent, dont 4 ciblés UA/robots. Ruff sur les fichiers modifiés passe avant arrivée de modifications concurrentes cookies ; leur formatage/validation ne relève pas de ce changement.

Service installé : seul browser.py avec changements UA/robots déployé depuis baseline vérifiée, sans embarquer le travail cookies concurrent. Ancien job Music Store annulé par sa clé, zéro job actif avant redémarrage LaunchAgent. Ready200, source attendue vérifiée, tables projects/api_keys/settings identiques avant/après. Backup privé `/private/tmp/pq-native-ua-backup-zw8lccfy` (source, SQLite, deployment.json). Version reste 0.2.2, aucun push/release. Nouveau test Music Store via clé testing_codex : accueil encore en waiting_for_human, job b2a8e8decefe81243fea9d8a9a10ff5d, onglet 31bbd4853024eb95b348f042df9030b5. Suppression UA personnalisée insuffisante pour résoudre Cloudflare ; aucun secret enregistré dans le dépôt.

Recette complémentaire demandée : fermer le navigateur testing puis relancer la recherche. Ancien job b2a8e8de annulé, onglets fermés via API, processus Chromium du seul profil testing arrêté, nouveau contexte persistant lancé via POST /tabs sur URL de recherche Yamaha P-145. Job e76848c02bfa0995bd43f94606694544 / tab 7416d7fd73897eb9d84b8d089b297a5a encore waiting_for_human après budget passif. Cookies/profil conservés, aucune validation Cloudflare automatique. Rapport et capture privés `/private/tmp/pq-musicstore-restart/`.


### 14 octobre 2026 — Action API « Valider cookies »

Ajout de `validate_cookies` dans les actions REST/WebSocket, refus par défaut (`value: reject`), acceptation explicite (`accept`), conteneur facultatif via selector. GET/PUT `/v1/projects/{slug}/cookie-policy` avec scopes browser:read/browser:interact ; règle désactivée par défaut, persistée par projet dans migration 008_cookie_policy.sql. Application lors des visites API, recherches/pagination native et après click/wait_for_navigation. Choix relu à chaque opération ; aucun réglage réel de projet modifié par cette tâche.

Détection via locators Playwright : conteneur de consentement et texte associé, libellé exact du choix, iframes visibles (autre origine testée), Shadow DOM ouvert ; huit frames et 32 conteneurs/boutons par frame, temps borné. Refus absent sans repli vers acceptation, ambiguïté/plafonds sans clic. Résultats cookie_consent et audit function.validate_cookies ; clicked signifie clic effectué, sans preuve du consentement enregistré. Contrôles challenge, autorisation et réseau maintenus.

Validation : suite générale 257 passed / 68 skipped (avant ajout du dernier cas navigateur), suite Chromium cookies/navigation/acquisition/titres 37 passed / 1 skipped, dont cinq tests navigateur cookies. Ruff check/format et diff --check conformes ; contrat OpenAPI public et README actualisés. Les premiers essais dans le sandbox bloquaient Chromium et les sockets ; relances autorisées hors sandbox réussies. Sources prêtes dans le dossier de développement ; aucun déploiement du service ni publication exécuté par cette tâche. Des modifications User-Agent concurrentes présentes dans le dossier ont été conservées.


### 14 octobre 2026 — Déploiement cookies et acceptation UniversRobot

Demande explicite : redéployer la nouvelle action et activer l'acceptation automatique pour UniversRobot. Six ressources runtime synchronisées (api.py, browser.py, models.py, storage.py, cookies.py, migration 008) dans PageQuayService ; modification User-Agent native déjà installée conservée. Sauvegarde privée sources et SQLite cohérente `/private/tmp/pq-cookie-deploy-backup-ejtjqhqt`, manifeste et résultat deployment.json. LaunchAgent arrêté proprement puis rechargé, ancien job testing actif interrompu ; zéro job actif après redémarrage.

Migration 008 appliquée et règle UniversRobot (`universrobot`) enregistrée par l'opérateur local autorisé : choice=accept, timeout_ms=1500 ; audit cookie.policy_updated avec source authorized_local_deployment. Réglage réservé au projet, aucune clé créée/lue en clair. Sources installées identiques, ready/login200, contrat API réel expose validate_cookies et GET/PUT cookie-policy, adminAPI404 et cookie-policy/key-info anonymes401. Tables projects/api_keys/settings/admins identiques par empreinte avant/après. Tests préalables policy/OpenAPI 9 passed et Ruff conformes ; tests Chromium antérieurs 37 passed/1 skipped, aucune visite métier ni clic de consentement sur un site réel revendiqué pour ce déploiement.


### 14 octobre 2026 — Préparation du commit et de la release 0.2.3

Utilisateur demande « fait un commit release github en l'état ». Publication publique autorisée sur tmcuh1982/PageQuay/main ; accès gh confirmé, origin/main égal au HEAD initial d6f6ecd. Le lot conserve tout le travail cookies et User-Agent courant et les correctifs déjà publiés depuis v0.2.2 ; version paquet/module/OpenAPI/lockfile mise à 0.2.3, notes docs/releases/0.2.3.md. Suite générale 257 passed/69 skipped, lock offline conforme, Ruff check/format sur onze fichiers du lot conformes. Styles préexistants des diagnostics conservés en l'état, sans nettoyage fonctionnel ou formatage ajouté. Tests Chromium de l'implémentation 37 passed/1 skipped toujours applicables. Paquets à construire depuis le commit Git seulement, puis publication du tag/release v0.2.3 avec wheel, sdist et SHA256SUMS ; vérification distante obligatoire avant annonce de succès. Aucun nouveau redémarrage du service local ni changement du choix UniversRobot pour la préparation de publication.


### 15 octobre 2026 — Release 1.0.1, ports locaux distincts

Ajout du port administrateur dans Paramètres → Accès local, sauvegarde atomique avec le port API dans local-api.json, compatibilité des anciens fichiers et adaptation des origines loopback au démarrage. Déployé : console 8767, API 8787. Tailscale Serve corrigé sur autorisation explicite : HTTPS 8443 conservé, destination 8787. Tests HTTP et Bearer via loopback et HTTPS depuis le Mac réussis ; clés temporaires révoquées. Aucun test depuis un autre appareil revendiqué.

Demande : commit release local. Métadonnées paquet/module/OpenAPI/lock alignées sur 1.0.1 et notes docs/releases/1.0.1.md. Suite générale 276 passed/74 skipped, warning Starlette préexistant ; Ruff ciblé, uv lock --check --offline et diff-check conformes. Aucune publication GitHub demandée pour cette tâche.

### 19 octobre 2026 — GIF/20 Mo validés, release locale 1.2.0

Audit de départ : module/paquet et OpenAPI installé 1.1.1, route existante et
schéma identique au dépôt, base 42aa5d4. Validation explicite du périmètre, puis
implémentation locale du contrat original-gif-20mb-v1 : max_bytes strict ≤20 Mo,
défaut 5 Mo ; allowed_media_types facultatif, GIF sur demande, trois formats
historiques conservés. Nouveau validateur structurel GIF, première image décodée
seulement, 8192/axe, 16 Mpx, 1000 images, 5 s CPU/10 s murales. GET privé borné,
client qualifié, causes/IDs sûrs, pas de rejeu POST incertain. Aucun service ou
fichier UniversRobot modifié, aucune URL Dobot téléchargée, aucun quota accru.

Validation : générale 343 passed/123 skipped (14,37 s), Chromium ciblé 164 passed
(139,41 s), suites recouvrantes ; Ruff/format ciblés, OpenAPI, lock offline et diff
conformes. Pics RSS échantillonnés pytest+descendants : 1,69 Gio pour un original
20 Mo, 2,48 Gio pour quatre (80 Mo supprimés du projet de fixture). Pas de plafond
RSS OS macOS ; trames suivantes vérifiées structurellement sans décodage pixels.
Rapports bilingues détaillent limites et incidents intermédiaires, dont un test
existant de quota audit intermittent passé à la relance sans changer la télémétrie.

Demande suivante : « fait un commit release ». Préparer le commit local main
1.2.0, notes bilingues, README/index/statut actualisés et documentation Pillow
préexistante incluse. Métadonnées module/pyproject/OpenAPI/lock alignées ; pas de
nouvelle installation pour changer les métadonnées des environnements. Sources
installées examinées toujours 1.1.1. Push, tag, release GitHub, recette Dobot et
installation restent distincts ; aucun redémarrage ni secret réel utilisé.


### 19 octobre 2026 — Déploiement 1.2.0 autorisé et vérifié

Après le commit local ebea8c520608a57184f7d10c34df735668dfadb0, l’utilisateur
demande explicitement « déploye et relance le service ». Aucun job actif avant
arrêt et après redémarrage. Sources du commit et métadonnées synchronisées dans
PageQuayService ; installation éditable hors ligne avec --no-deps, seul PageQuay
passe de 1.1.1 à 1.2.0. LaunchAgent rechargé, terminé à 2026-10-19T13:27:22.434176+02:00.

Sauvegarde privée réversible : /private/tmp/pq-120-backup-utxfbl6u (sources
remplacées, métadonnées, base SQLite cohérente, configuration privée et manifeste
deployment.json). Empreintes api_keys/projects/settings/admins/cookie_policies
identiques avant/après ; versions de toutes les autres distributions identiques.
Aucun changement de ports, Tailscale, droits, profils ou quotas.

Ready 200 et OpenAPI exact du commit sur API 8787 ; login 8767 200, admin sur
API 404, key-info anonyme 401. HTTPS privé existant 8443 : ready/OpenAPI 200,
version 1.2.0, maximum 20 000 000 et GIF explicite ; défaut 5 000 000 conservé.
Aucune clé réelle utilisée, aucune recette d’image authentifiée ou URL Dobot
exécutée, aucun raccordement UniversRobot ni push/tag/release GitHub.


### 20 octobre 2026 — Correction DOM 1.2.1, installation et publication autorisées

Deux artefacts LahakX relus : schema 1.0, URL exacte, partial/truncated et depth seuls, 1 199 nœuds visités et 750 inclus. Reproduction protégée identique ; branche galerie coupée à 33, picture à 34 et image agri.png à 35. Aucun texte éditorial supplémentaire retrouvé.

Correction : profondeur comptée 32, trois crédits d’enveloppes neutres maximum par chemin, borne physique 35. DOM conservé ; rôles/ARIA/labels/langue/interaction, hôtes Shadow ouverts et éléments projetés exclus. Quotas et diagnostics préservés ; empreinte du script chargé journalisée. Lecture réelle temporaire corrigée : 1 202 visités, 754 inclus, 16 images contre 15, blocs/liens/contrôles/formulaires/tables inchangés et partial=false.

Installation et redémarrage explicitement demandés avant commit/release. Deux essais hors ligne échoués faute d’outils de build en cache (hatchling puis editables) ; sources anciennes restaurées et service relancé. Installation éditable ensuite vérifiée dans un environnement temporaire, cache complet, puis déploiement 1.2.1 réussi. Sauvegarde privée et SQLite cohérente conservées hors dépôt ; aucun job actif avant/après. Readiness, OpenAPI exact, limites admin/API et empreinte chargée 257af2f714d4d38ed0d6d613536b473393ae74cade9278c884c20b2a9d377a85 vérifiés. Empreintes de configuration persistante et versions des autres distributions inchangées. Aucune clé réelle utilisée ni modification UniversRobot.

Validation : suite générale 347 réussis, Chromium ciblé 29 réussis ; OpenAPI, Ruff/format et lockfile hors ligne conformes. Release 1.2.1 avec notes bilingues et paquets construits depuis le commit, comprenant aussi les commits locaux 1.1.1/1.2.0. La validation UniversRobot reste distincte.


## 26 octobre 2026 — Préparation release 1.2.4

Publication locale et GitHub explicitement demandée. Regroupe protections CAPTCHA, restauration de fenêtre, démarrage minimisé robuste et attente optionnelle download_image déjà présente dans le dépôt. Délai humain partagé 120 s, contrôles espacés, reprises bornées, suspension des scripts après expiration/annulation. OpenAPI et versions alignés sur 1.2.4. Validation : 389 réussis / 178 ignorés ; ciblée Chromium 36 réussis ; Ruff/format conformes. Le service local a été redémarré et ses deux listeners vérifiés avant cette publication. Son installation possède des adaptations de reprise de recherche préservées lors du déploiement ; la publication des paquets ne remplace pas cette installation.
