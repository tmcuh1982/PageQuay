# Mémoire de travail — PageQuay (PQ)

Dernière mise à jour : 2026-10-10, préparation de la publication GitHub.

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
- Git local initialisé, `origin` configuré en HTTPS, historique initial distant conservé sur `main`. Identité locale Faxian / adresse GitHub noreply.
- Sources, tests et documents préparés ; captures et diagnostics restent locaux, exclus par `.gitignore`, ainsi que secrets/bases/profils/sauvegardes. Détails personnels réseau/chemins retirés ; `probe_via_ssh.py --remote-root` configurable, défaut relatif au home SSH.
- Vérification avant publication : `pytest -q` **50 passed, 10 skipped**, 2,61 s ; les tests Chromium et diagnostics tiers sont opt-in. Warning Starlette/httpx conservé. Ruff format sur tous les 47 fichiers Python conforme ; aide CLI SSH vérifiée. Deux lignes du client d'exemple ont été reformattées.
- Audit des 71 fichiers préparés : aucun nom/adresse réseau personnels ciblés ni forme de clé privée/token GitHub/AWS ; seuls rapport et deux exemples de fixture inclus dans `docs/testing/`. Aucun fichier de capture, base ou clé préparé.
- Commit local du MVP : `ced0201`, parent distant initial `5e85c7b`. Le push HTTPS a échoué faute d'identifiants GitHub dans le terminal. La validation automatique avait ensuite refusé le transfert via l'application, faute de confirmation de l'exposition publique.
- L'utilisateur a explicitement répondu **« Publier dans le dépôt public existant »**. Ce choix autorise la publication sur `tmcuh1982/PageQuay` public. Transfert via la connexion GitHub de l'application, puis récupération Git HTTPS en lecture pour synchroniser l'historique local ; aucun identifiant terminal créé ni secret copié.
- Nouvelle tentative après confirmation : GitHub a refusé `create_tree` avec **403 Resource not accessible by integration**. Les outils de connexion retournent `installations: []` et `accounts: []` pour ce compte. Le plugin GitHub est installé et le compte OAuth est connecté, mais l'accès en écriture du connecteur au dépôt n'est pas opérationnel. Aucun arbre/commit distant créé ni code publié. Le dépôt distant reste sur `5e85c7b` (README initial). Reconfiguration de la connexion GitHub avec accès au dépôt PageQuay demandée à l'utilisateur ; reprendre l'envoi après configuration, sans redemander la visibilité publique déjà confirmée.
