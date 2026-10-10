# Mémoire de travail — PageQuay (PQ)

Dernière mise à jour : 2026-10-10, publication GitHub et synchronisation de la documentation.

## Objectif et autorisation

L'utilisateur a autorisé le développement depuis l'archive et demandé `memory.md` et `decisions.md`. Nom produit **PageQuay / PQ**. Sources originales intactes dans `docs/definition/`.

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

### Recherche DuckDuckGo et intégration UniversRobot — contrat 0.2.0

Prompt joint appliqué : pagination native, quotas détaillés, idempotence, cycle de vie des onglets, OpenAPI publié et exemple Python serveur. Diagnostic prouvé : plafond min(request.limit, search_max_results), défaut10 ; quota PageQuay 6 tentatives par fenêtre fixe60s/projet/moteur partagé entre clés/admin, distinct du quota REST par clé. Configuration réelle UniversRobot relue : aucune surcharge, plafond10. Les anciennes observations ne prouvent pas la cause exacte de chaque ancien RATE_LIMITED ni un quota DuckDuckGo.

Search.cursor opaque aléatoire43caractères, snapshots SQLite migration003 (search_cursors/search_idempotency). Reliquats d’une page avant son formulaire Next natif GET/POST, aucun offset fabriqué ; actions HTTPS DuckDuckGo/html bornées, transport navigateur/proxy existant. Liens exact_url et rangs/source conservés en plus du url normalisé historique. Métadonnées compteurs/moteurs/continuation/has_more triétat/motif/partiel. Bornes par défaut10pages/200résultats/15min/100états de curseurs par projet, read200hits max/document. Répétitions/no progress arrêtées. Cursor lié projet/query/engine/locale, réservé atomiquement avec job, consommé après succès, libéré après échec/annulation/restart ; reset/purge invalident. État consommé/expiré effacé, tombstones1jour. Onglet interne propre par search, fermé dans finally, pas d’onglet entre continuations. Allocation protégée pour fermer l’onglet même si annulation arrive pendant sa création ; annulation d’un runner avant première instruction libère aussi réservation/file.

Idempotency-Key optionnel POST/search, namespace projet+clé, corps validé canonique ; même opération24h, corps différent409, persiste après SQLite réouvert/restart. Rejeu REST consomme quota de clé mais aucun nouveau moteur/job. Résultat soumis au TTL habituel, pas garanti24h ; job échoué non rejoué. Retry-After HTTP quand connu, errors.details portée/cause/date/délai/continuation/partiels des jobs. Statuts waiting_for_human et chemins relatifs inchangés ; aucun solveur ni basculement d’un engine explicite. GET/openapi.json maintenant autorisé sur8766/HTTPS, schéma filtré aux routes client/health, contrat version0.2.0.

Livrables : docs/SEARCH_API.md, docs/openapi.json, examples/search_duckduckgo.py (stdlib, multiqueries, checkpoint0600 avant POST, retries idempotents bornés, Bearer uniquement environnement/header, redirects refusés). Versions package/API0.2.0 et docs mises à jour. Dernière suite Chromium visible complète :116passed/3skipped,72.84s ; Ruff42fichiers conforme. Exemple retesté5cas après ajustementcheckpoint/aideCLI. Diagnostic DDG réel :3queries (fr-FR/en-US) toutes CAPTCHA, challenge.required puis TIMEOUT5s, zéro onglet restant. Preuves docs/testing/duckduckgo-native-*.html + duckduckgo-pagination-live.json locales ; trois pages natives réelles non validées.

Déployé aprèszérojobactif, backup privé sources+SQLite sous tmp (pq-search-02-backup-*),16fichiersruntime et LaunchAgent relancé. Ready/login locaux200 ; OpenAPI8766 version0.2.0 ; admin8766 toujours404. HTTPSréel : ready200/OpenAPI200/admin404/searchanonyme401. Aucun jeton réel lu/affiché ; aucun changement de clé/projet réel ni hausse de quota. Rejeu authentifié depuis UniversRobot surserviceinstallé non exécuté, les tests moteurs utilisent runtimejetable. Modifications locales non poussées à GitHub dans cette demande.

### Publication du lot 0.2

Demande explicite de commit GitHub sur le dépôt public existant `tmcuh1982/PageQuay`, branche `main`. Le lot inclut sources, tests, contrats et exemples ; secrets, bases, profils, captures, diagnostics privés et checkpoints sont exclus. Les noms Tailscale réels et le compte du réseau ont été remplacés par des indications portables dans cette mémoire et le rapport public.

### Port HTTPS externe global — 10 octobre 2026

Demande utilisateur : configurer le port externe depuis la console, indépendamment des projets, via une redirection Tailscale. Paramètres → Accès externe affiche la route privée réellement active et accepte un port HTTPS de 1 à 65535. Application immédiate par CLI Serve --bg vers le seul listener API ; vérification de la nouvelle route, retrait de l’ancienne, contrôle final et récupération sur erreur. Refus des ports occupés/partagés, Funnel, Serve temporaire et formulaire périmé. CSRF/session locale ; route admin inaccessible sur le listener API. Aucun choix de nouveau port imposé à l’utilisateur.

Validation : suite générale 126 passed/14 skipped ; 20 tests dédiés ; formulaire Chromium réel desktop/mobile réussi avec CLI Tailscale simulée. Ruff et diff --check conformes. Les essais avec sockets nécessitent une exécution hors sandbox. Lecture seule réelle confirme Serve privé HTTPS443. Déploiement des cinq fichiers runtime dans la copie installée après zéro job actif ; redémarrage LaunchAgent et health200. Sauvegarde des sources privée sous /private/tmp/pq-external-port-backup-4md2ra4o. Aucun changement réel de port Tailscale exécuté pour la recette ; cette application sera déclenchée par le bouton admin. Sources non publiées dans cette demande.
