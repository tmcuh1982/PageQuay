# Rapport de vérification — PageQuay 0.1

Exécuté le **9 octobre 2026**, macOS Apple Silicon, Python **3.14.7**, Chromium Playwright **1243 / Chrome for Testing 153.0.8010.12**. Versions exactes dans `uv.lock`.

Les captures et diagnostics de navigation restent locaux et sont exclus du dépôt public : ils peuvent contenir des noms de machines, adresses réseau ou pages capturées. Ce rapport conserve leurs résultats ; les exemples structurés issus de la fixture restent versionnés.

## Résultats réels

| Commande / contrôle | Résultat |
| --- | --- |
| `.venv/bin/pytest --browser --headed -q` | **45 passed, 1 skipped**, 52,79 s ; skip = diagnostic tiers opt-in |
| `.venv/bin/pytest tests/test_lifecycle.py tests/test_jobs.py tests/test_proxy_shutdown.py -q`, après durcissement du nettoyage | **4 passed**, 0,75 s ; un nouveau test, trois déjà présents |
| `.venv/bin/pytest tests/test_live_search.py --live -q -s` | Challenge DDG détecté, timeout humain de test après 5 s ; **pas de résultats de recherche obtenus** |
| Recette navigateur après mise à jour de dernière activité | **1 passed**, 46,86 s |
| Contrat OpenAPI Bearer | **1 passed** |
| Ruff check et format --check | Réussis, 28 fichiers conformes |
| zsh -n sur les quatre scripts | Réussi |
| plutil -lint du LaunchAgent | Réussi |
| uv sync --frozen --extra dev | Réussi, 44 packages vérifiés |
| pq doctor avec données jetables sous /private/tmp | Chromium installé, schéma accessible, absence d'admin correctement signalée |
| Inspection finale des processus | Aucun driver, Python de test ou Chrome for Testing restant |

**47 tests locaux distincts vérifiés**, hors diagnostic tiers. Un warning de dépréciation Starlette/TestClient/httpx demeure, sans échec ; aucun warning masqué.

## Couverture vérifiée

- Auth admin/CSRF (login et mutations), origine étrangère refusée, aucune console par clé API, échappement XSS, CSP/no-store, expiration/logout.
- Argon2id, clés aléatoires hachées, secret absent du dump SQLite et du listing, expiration/révocation/rotation.
- Scopes et isolation inter-projets sur onglets/jobs/artefacts/WS ; ticket à usage unique, rejet inter-projets, socket ouverte invalidée après révocation.
- Quotas requêtes/payload/jobs/artefacts ; jobs actifs/en file revalidés ; JSON admin invalide rejeté sans écho sensible.
- Blocage schémas non HTTP(S), loopback/IP privées/métadonnées/tailnet/IPv6 locales/IP ambiguës, DNS mixte privé/public et CONNECT privé.
- **Deux Chromium visibles simultanés**, deux dossiers, cookies A/B distincts ; flock profil et exclusion de deux services sur les mêmes données.
- Navigation API, DOM modifié par JavaScript, HTML/texte/liens/métadonnées et capture PNG récupérés ; click/fill exécutés sur fixture.
- Fetch/redirection privés bloqués, compteur serveur privé **zéro**. Exception localhost injectée seulement dans les tests.
- Challenge simulé : waiting_for_human, capture protégée, reprise sur signal après intervention simulée, aucun solveur ou clic CAPTCHA.
- TTL sans perte de cookie, soft restart persistant, fermeture inattendue sans panne du voisin, hard reset A seul, inactivité/relance B avec cookie conservé.
- Double confirmation et intention serveur éphémère du reset, rejeu refusé.
- Annulation de lancement libérant profil/proxy ; fermeture du proxy avec client inactif sans blocage.
- UI réellement pilotée : login, création projets/clé, disparition du secret après fermeture, deux navigateurs au dashboard, sept écrans, aucun pageerror, aucun débordement global à 390 px.

## Recherche extérieure et inspection visuelle

Diagnostic JSON local `duckduckgo-live.json` : DuckDuckGo a demandé une sélection d'images. Détection vérifiée ; attente expirée volontairement après cinq secondes en headless. Aucun contournement ni résultat inventé. **La recette de résultats DDG en direct demeure non satisfaite dans cet environnement.** Google/Brave sont vérifiés sur fixtures, sans succès en direct revendiqué.

Desktop local `admin-desktop.png` et mobile local `admin-mobile.png` générés avec comptes/projets jetables puis inspectés : deux navigateurs actifs affichés, cards et actions lisibles, navigation mobile défilante. Aucun profil personnel ni secret réel.

## Restant et limites

- LaunchAgent installé, login/reboot/sommeil et recette sur **Mac mini cible** : syntaxe valide, aucune installation système automatique.
- Tailscale Serve HTTPS, ACL et inaccessibilité hors tailnet : procédure écrite, **non testée avec un tailnet réel**.
- Administrateur réel à créer interactivement par l'opérateur ; aucun compte/secret réel créé automatiquement.
- Sauvegarde/restauration et panne OS brutale à vérifier. Le test de crash ferme un contexte de façon inattendue, sans SIGKILL.
- Moteurs/challenges/publicités susceptibles d'évoluer ; locale fiable limitée à Google.
- Réglages de projet en JSON validé. Pas de reset automatique destructeur, snapshots, exception LAN admin, options upload/download, MCP/webhooks, CPU/RAM ni chiffrement applicatif. Rotation manuelle des logs fichiers LaunchAgent ; purge automatique audit/contenus.
- Le proxy/Chromium ne remplace pas un pare-feu OS. WebSockets externes bloqués, limitant certains sites.

Ce rapport décrit un MVP fonctionnel et une recette reproductible, **pas une validation complète de toutes les exigences ni une certification de sécurité**.

## Complément du 10 octobre — Google et client MacBook Air

Le Mac mini exécute les commandes (Mac16,11). Le MacBook Air client a été trouvé sur Tailscale ; la connexion SSH à son port 22 est refusée. **Aucun test exécuté depuis le MacBook Air ni trajet Air → PQ validé.** Le contrôle UI n'a pas fourni d'accès alternatif ; aucun service distant activé.

Essai réel Google via Chromium visible, profil jetable et clé Bearer jetable : « Playwright Python documentation ». Google renvoie `/sorry/index` avec reCAPTCHA et le message français de trafic exceptionnel. Diagnostic initial local `google-live-before-fix.json` : UPSTREAM_CHANGED erroné. Après correction de la détection française et de l'URL : diagnostic final local `google-live.json`, challenge.required puis TIMEOUT humain après cinq secondes. Capture inspectée local `google-live.png`. **Aucun résultat de recherche ni contenu d'une page trouvée téléchargé.** Le texte de blocage provient d'une lecture diagnostique du navigateur, pas d'une extraction réussie via l'API.

| Contrôle supplémentaire | Résultat |
| --- | --- |
| `pytest tests/test_live_search.py::test_live_google_api_and_content tests/test_challenges.py --live --headed -q -s` | **5 passed**, 7,81 s ; diagnostic Google bloqué + quatre cas de détection |
| `pytest -q` | **49 passed, 4 skipped**, 2,67 s ; tests Chromium/UI et diagnostics tiers ignorés |
| Ruff ciblé, aide du client autonome | Réussis |

Le client du diagnostic est ASGI sur le Mac mini ; il n'ouvre pas une connexion HTTP entre machines. Le client [`examples/probe_google.py`](../../examples/probe_google.py) réalise le parcours HTTP complet et conserve le hostname du client, mais nécessite un service PQ accessible et une clé ; **son exécution depuis l'Air reste à faire**. Les scripts launchd, Serve, ACL et admin réel n'ont pas été configurés pour ce test.

### Correction du trajet SSH et recette prête

L'utilisateur confirme que `ssh macmini-codex` fonctionne **depuis l'Air vers le mini**. La tentative précédente dans le sens inverse n'était pas pertinente pour ce client. La confirmation de l'utilisateur ne vaut pas exécution par l'agent d'un test PQ distant.

[`probe_via_ssh.py`](../../examples/probe_via_ssh.py) permet une commande côté Air, avec tunnel SSH local et [`serve_ssh_probe.py`](../../scripts/serve_ssh_probe.py) sur le mini : instance, profil et clé jetables, durée maximum 15 minutes, fermeture en fin de test, rapport recopié dans `macbook-air-google.json`. Option `--human` pour reprise après intervention de l'utilisateur sur Chromium du mini. Aucun service permanent ni accès système créé.

Contrôles supplémentaires réellement exécutés **sur le mini** : health ready, recherche sans clé refusée (401), rapport sans clé, arrêt propre et listener fermé. Parcours HTTP avec clé vers `https://playwright.dev/python/docs/intro`, URL choisie directement : navigation, extraction puis téléchargement de **3821 caractères**, arrêt normal et fermeture de socket. Rapport local local `ssh-probe-local.json`, texte extrait local `ssh-probe-local.txt`. Cela valide la récupération d'une page publique via HTTP ; **ce n'est ni un résultat obtenu par Google ni un test depuis l'Air**. Ruff et aide CLI des nouveaux scripts vérifiés. La commande Air n'a pas encore été exécutée.

## Extraction structurée et DOM — 10 octobre

Livré : `format=structured`, `include_dom=true` optionnel, JSON 1.0/artefact protégé et OpenAPI actualisé. Aucun paquet ajouté. [Contrat et limites](../EXTRACTION.md).

| Vérification exécutée | Résultat |
| --- | --- |
| `pytest --browser --headed -q --ignore=tests/test_ui.py` | **56 passed, 2 skipped**, 32,42 s ; skips = diagnostics tiers opt-in ; UI inchangée non rejouée |
| `pytest tests/test_structured.py tests/test_openapi.py --browser --headed -q` après renforcement des bornes | **8 passed**, 17,84 s ; inclut un nouveau cas de 5 000 éléments cachés |
| Ruff check/format, Node `--check` | Réussis |
| Wheel hors ligne, inclusion de extraction.js et import depuis wheel décompressé | Réussis |
| HTTP réel vers une page officielle publique, extraction structurée/DOM/téléchargement/copie retour/arrêt | Réussis sur mini, **34 blocs**, **98 774 octets**, non tronqué lors de cet essai |

Fixture complexe : hydratation, main/ARIA headings, listes imbriquées, tables HTML/ARIA et spans, labels/options et champ externe associé au form, métadonnées/JSON-LD, open shadow avec slot, closed shadow omis, iframe d'une autre origine (port local distinct), iframe cachée, canvas signalé. Vérifications : aucun champ privé ni script/élément caché retourné ; scopes/projets conservés, option DOM incompatible refusée, format inconnu refusé ; bornes nœuds/profondeur/frames, JSON-LD et niveaux ARIA malformés traités sans JSON invalide, URLs javascript/data exclues.

Le HTML rendu parsé garde l'hydratation mais manque du texte shadow et iframe ; le JSON les récupère. [Compact](structured-complex-compact.json), [avec DOM](structured-complex.json) : **5 593 / 12 390 octets** en sérialisation Python sans indentation, mêmes blocs et collections. Le DOM détaillé sert à inspecter les relations ; il n'est pas nécessaire pour lire ces blocs.

La page publique était `https://playwright.dev/python/docs/intro`, URL directe : rapport HTTP local `ssh-probe-structured-local.json`, JSON récupéré local `ssh-probe-structured-local.content.json`. Cet essai précède le dernier ajustement du comptage des nœuds omis ; les fixtures finales vérifient le nouveau comportement. Ce n'est pas une recherche Google ni une exécution depuis l'Air. Les clients acceptent désormais `--format structured`/`--include-dom`, mais leur trajet SSH Air → mini n'a toujours pas été exécuté par l'agent. Warning Starlette/httpx conservé.

Les pages virtualisées/non chargées, les closed shadows et la sémantique visuelle de canvas/SVG ne deviennent pas accessibles par simple export DOM. Attentes/actions explicites ou captures séparées nécessaires selon le cas ; aucune OCR/interaction automatique ajoutée. La recette intégrale du déploiement reste ouverte.

## Préparation GitHub — 10 octobre

`pytest -q` : **50 passed, 10 skipped**, 2,61 s ; tests navigateur/UI et diagnostics tiers opt-in ignorés, warning Starlette/httpx inchangé. Ruff check et format sur l'ensemble du projet conformes (47 fichiers Python). Aide du client SSH vérifiée après ajout de `--remote-root` ; aucun nouveau test entre machines revendiqué. Captures et diagnostics bruts exclus du dépôt public, résultats conservés dans ce rapport.

## Mise à jour documentaire — 10 octobre

Liens relatifs du README, de `docs/STATUS.md` et de `docs/PUBLISHING.md` contrôlés : aucune cible manquante. Aucun code modifié et aucune suite navigateur relancée pour cette mise à jour. La lecture du README GitHub confirme son contenu initial ; l'API de modification du fichier a refusé l'écriture avec **403 Resource not accessible by integration**. La documentation locale est actualisée ; la publication distante reste non effectuée.

## Publication débloquée — 10 octobre

Le connecteur reste en erreur 403 après reconnexion, mais l'authentification GitHub CLI directe a été validée par l'utilisateur. Login vérifié : `tmcuh1982`. Helper Git configuré dans ce dépôt, premier push réussi de `5e85c7b` à `ad0c861`, référence distante relue identique ; les sources et documents sont maintenant publiés. Les paragraphes précédents décrivent l'historique des essais. README et documents de statut actualisés ensuite. Aucune modification de code ni nouvelle recette navigateur, Google/Air ou déploiement lors de la publication.

## Administration locale et démarrage automatique — 10 octobre

À la demande de l’utilisateur, console réservée à la machine et API prévue pour Tailscale : `pq serve` ouvre 127.0.0.1:8765 et 127.0.0.1:8766 dans un seul processus/runtime. Sur 8766, seules `/v1/`, `/health/live` et `/health/ready` passent ; les routes admin et assets sont refusés selon le port de destination réel, indépendamment de Host, des en-têtes forwarded ou des cookies.

`pytest -q` hors sandbox réseau : **51 passed, 10 skipped**, warning Starlette/httpx inchangé. Contrôle Ruff conforme. Le nouveau test vérifie le refus des pages/mutations admin avec session valide et Host local, l’absence de mutation en base, les endpoints API/health, l’auth Bearer obligatoire et le refus WebSocket admin. Après explicitation du cookie de session dans le test, ce cas a été réexécuté avec succès. La première suite sous sandbox avait trois échecs liés aux sockets localhost interdites ; la suite complète avec sockets autorisées passe.

Déploiement réellement effectué sur le Mac mini : LaunchAgent `local.pagequay.gateway`, RunAtLoad/KeepAlive, runtime privé sous `~/Library/Application Support/PageQuayService` pour éviter le blocage macOS du dossier Documents ; données séparées sous `~/Library/Application Support/PageQuay`. Service arrêté puis rechargé. HTTP réel : 8765 `/admin/login` → 200 ; 8766 `/health/ready` → 200 ; `/admin` et `/admin/login` → 404 ; API sans clé → 401. Configuration locale avec origines loopback et cookies non Secure pour HTTP loopback. Aucun compte administrateur réel créé automatiquement.

Tailscale connecté mais Serve **non activé** dans le tailnet ; aucune configuration Serve présente. Les commandes précédentes en attente vers 8765 ont été terminées. La future commande doit viser `tailscale serve --bg http://127.0.0.1:8766`. Accès entre machines, ACL et reboot restent non testés.

## Connexion locale CSRF — 10 octobre

Après signalement de `Invalid login CSRF` dans Safari sur 127.0.0.1:8765, réglages du runtime confirmés : cookies non Secure et origines loopback. Correction des cas de formulaire périmé : nouveau cookie `pq_login_nonce` sous `/admin`, indépendant de l’ancien cookie qui pouvait avoir été Secure ; nonce conservé entre ouvertures de la page ; mismatch/missing-cookie renvoie un formulaire neuf avec message français et 403, sans authentifier. Les origines étrangères restent rejetées. La cause précise du cookie/formulaire Safari initial n’a pas été inspectée.

53 tests standard réussis/10 ignorés ; test UI Chromium complet réussi avec compte jetable. Cas vérifiés : ancien cookie Secure, deux formulaires, nonce périmé sans session accordée, reprise normale. Runtime mis à jour et redémarré. HTTP réel sans mot de passe : cookie local correct, nonce stable, contrôle CSRF franchi avec identifiant volontairement trop long (400 avant vérification de credentials), admin sur port API toujours 404. Formulaire Safari rechargé ; connexion avec le compte réel à effectuer par l’utilisateur.

## Aide à la création des clés API — 10 octobre

Formulaire enrichi : explication des appels comptabilisés sur 60 secondes, exemple 60, erreur 429 et plafond du projet sélectionné. Expiration explicitement optionnelle : case décochée par défaut, valeur vide et champ désactivé ; décocher efface la date et le JSON envoyé contient `expires_at: null`. Champ obligatoire lorsqu’activé. Liste des clés : « Sans expiration » au lieu d’un tiret. Safari affichait une date indicative dans un datetime-local vide ; le contrôle désactivé utilise désormais un champ texte vide avec placeholder « Sans expiration », puis redevient datetime-local à l’activation.

Test UI Chromium enrichi et réussi : activation/saisie/désactivation, payload nul et stockage SQLite nul, puis création d’une clé avec date, affichage et absence de débordement sur mobile. Captures desktop/mobile inspectées. Fichiers template/JS/CSS déployés dans le runtime sans interruption ; fichiers statiques servis vérifiés. Safari réel vérifié : case décochée et champ désactivé sans date, placeholder « Sans expiration ». Admin toujours refusée sur le port API 8766.

## Modification de la sécurité des clés — 10 octobre

Ajout de GET `/admin/keys/{id}/edit` et POST `/admin/keys/{id}/update` : formulaires préremplis, édition du nom/scopes/quota/expiration, secret et projet conservés. Validation complète des champs et refus des dates passées/non finies, scopes inconnus/vides, quotas hors bornes ou champs supplémentaires. Clé révoquée non modifiable ; clé expirée récupérable par changement explicite de son échéance. Retrait d’un scope annule uniquement les jobs qui le nécessitent. Audit `key.updated`, compteur de quota conservé.

**63 passed, 10 skipped** pour la suite standard ; UI Chromium enrichie **1 passed**. Dix nouveaux cas vérifient CSRF/auth/admin local, conservation du secret, nouveaux droits, quota abaissé immédiatement, invalidité sans modification partielle, expiration/révocation et annulation ciblée des jobs. UI : valeurs préremplies, ajout/retrait de droits, changement du quota, expiration activée puis désactivée, secret réutilisable, annulation sans sauvegarde, captures desktop/mobile inspectées. Un premier contrôle UI a révélé un libellé implicite ambigu du projet désactivé ; aria-label explicite ajouté, contrôle UI final réussi. Table des clés défilante sur mobile pour garder les actions lisibles. OpenAPI exporté actualisé.

Déployé dans la copie d’exécution du Mac mini, puis service redémarré après vérification de l’absence de jobs actifs. Health ready 200 ; mutation anonyme locale 401, même route sur le port API 8766 refusée 404. Les réglages de toutes les clés réelles ont été comparés avant/après déploiement et sont inchangés ; seuls les comptes/clés jetables de test ont été modifiés.

## Informations de la clé appelante — 10 octobre

GET `/v1/projects/{slug}/key-info` avec Bearer : identité publique de la clé, projet, scopes, expiration nullable, quotas clé/projet/effectif, solde après cet appel et timestamp Unix UTC de remise à zéro. Réponse explicitement filtrée et typée dans OpenAPI, Cache-Control no-store. Aucun droit supplémentaire requis ; quota REST commun appliqué, sans contournement quand épuisé. Clé expirée/révoquée ou autre projet/projet désactivé refusés. Les limites des opérations et messages WebSocket restent distinctes.

**70 passed, 10 skipped** pour la suite standard ; Ruff check/format conformes (52 fichiers Python), export OpenAPI comparé au schéma généré et authentification Bearer vérifiée. Sept nouveaux cas : métadonnées uniquement de la clé appelante, absence de secret/hash ou données de l’autre clé, transport API avec admin refusée, mises à jour visibles, plafond du projet, compteur commun et réinitialisation, session admin insuffisante, expiration/révocation/projet désactivé. Exemple Python standard-library ajouté avec refus des redirections pour conserver le Bearer sur l’adresse configurée. Aucun changement UI, suite Chromium non relancée.

Déploiement de api.py/models.py dans PageQuayService après absence de jobs actifs, LaunchAgent arrêté puis rechargé. HTTP réel : ready 200, key-info sans Bearer 401, admin et login sur 8766 refusés 404, login local sur 8765 disponible 200. Métadonnées de toutes les clés réelles identiques avant/après ; réponse authentifiée vérifiée avec les clés jetables des tests. Serve Tailscale n’a pas été activé par ce changement.

## Diagnostic d’accès Tailscale — 10 octobre

Sur le Mac mini : PageQuay écoute sur les deux sockets loopback, ready sur8766 renvoie200. Tailscale Running, aucune alerte et ShieldsUp=false ; aucune configuration Serve/Funnel. Le hostname Tailscale est déjà accepté : requêtes locales avec ce Host, ready200, key-info anonyme401, admin/login404 sur8766.

Commande `tailscale serve --bg http://127.0.0.1:8766` lancée. Elle attend une activation : « Serve is not enabled on your tailnet ». Page officielle ouverte sur le Mac mini ; connexion utilisateur nécessaire. Après signalement d’une404, Safari montrait un compte Apple dans un réseau sans machines, distinct du réseau GitHub du réseau attendu du Mac mini. Reconnexion au compte GitHub du réseau attendu demandée à l’utilisateur. Aucun Serve/Funnel actif confirmé à ce stade, aucun paramètre de sécurité de la console modifié.

### Activation Serve effectuée

L’utilisateur s’est connecté au compte GitHub du réseau attendu puis a activé Serve dans son réseau. La page officielle a affiché « Tailscale Serve is ready to use ». La commande initiale a reçu un conflit etag indiquant une modification concurrente ; l’état courant a ensuite été lu et vérifié : HTTPS443 vers http://127.0.0.1:8766, configuration persistante (aucune section Foreground), aucune route AllowFunnel active. Aucune route vers8765.

Adresse : https://VOTRE_MACHINE.VOTRE_TAILNET.ts.net. HTTP réel via cette adresse depuis le Mac mini, validation TLS normale : ready200, key-info sans Bearer401, /admin404, /admin/login404, /static/admin.js404. Aucun contournement de certificat ni secret utilisé. Contrôle depuis un autre appareil et validation des ACL non effectués par l’agent ; redémarrage macOS non testé. Aucun changement de code ni nouveau test logiciel nécessaire pour cette activation réseau.

## 10 octobre — fenêtres minimisées

- `pytest -q` : **73 passed, 11 skipped** ; les cas Chromium restent opt-in. Avertissement de dépréciation Starlette/httpx inchangé.
- `pytest -q tests/test_ui.py tests/test_browser.py --browser --headed` : **3 passed**. Vérifiés sur Chromium/macOS : case de lancement minimisé, boutons locaux, conservation de la minimisation lors des ouvertures API successives, minimisation native, restauration, isolation entre projets, navigation/actions/extraction et capture.
- Les captures doivent restaurer brièvement la fenêtre pour permettre le rendu macOS ; elle est ensuite minimisée à nouveau. Une capture PNG de fixture et l’interface ont été inspectées visuellement.
- Ruff check/format et diff sans espaces invalides conformes. Service installé mis à jour et redémarré sans job actif ; ready/login locaux 200, contrôles admin refusés sur le port API (404).

## 10 octobre — recherche DuckDuckGo, contrat 0.2.0

- Validation finale : `pytest -q --browser --headed` → **116 passed, 3 skipped**, 72,84 s. Les trois diagnostics externes sont opt-in ; avertissement Starlette/httpx inchangé. La suite couvre compatibilité, trois pages simulées progressives, reliquats, locales/mots-clés, URL exactes/rangs/provenance, doublons et répétitions, curseurs liés/expirés/consommés, quotas HTTP et jobs, idempotence concurrente et SQLite rouvert, CAPTCHA, délais/annulation (y compris avant lancement et pendant allocation), rétention et onglets des autres opérations.
- Fixture Chromium réelle : soumission POST avec champs cachés Unicode/répétés à travers le proxy de PQ ; isolation et fermeture des onglets. Les tests de navigation/extraction et de minimisation existants passent.
- Exemple Python : tests de récupération d’une réception incertaine par checkpoint et même Idempotency-Key, progression/arrêt, clé exclusivement dans le header, retries bornés et mauvais chemins refusés. Après amélioration finale du checkpoint et de l’aide CLI : **5 passed** ciblés, sans nouvelle modification du backend.
- Ruff check et format conformes (42 fichiers Python) ; diff sans espaces invalides. Schéma versionné relu identique à l’export client 0.2.0, liens documentaires vérifiés.
- Essais extérieurs : `pytest -q tests/test_live_search.py::test_live_duckduckgo_native_continuations --live -s` → diagnostic rapporté, **aucun résultat réel obtenu**. Trois queries/locales : robot agriculture/fr-FR, agricultural robotics manufacturers/en-US, robots agricoles France/fr-FR. Toutes ont rencontré le challenge natif DuckDuckGo ; événement `challenge.required`, délai humain de test 5 s, erreur TIMEOUT et fermeture des onglets. Les HTML et JSON bruts sont locaux et ignorés par Git. **Trois pages natives sur DuckDuckGo réel restent non validées** ; aucun solveur/repli non demandé.
- Déploiement : sauvegarde privée des sources et de SQLite, vérification de zéro job actif, 16 fichiers synchronisés dans PageQuayService et LaunchAgent rechargé. Migration additive 003 appliquée, paramètres existants et clés/projets réels conservés. Le plafond UniversRobot reste 10, le quota moteur PageQuay reste 6/60 s ; aucune augmentation silencieuse.
- Contrôles du service installé : local ready/login 200, OpenAPI sur8766 200/version0.2.0, admin/login404 sur8766. Sur HTTPS Tailscale avec certificat validé : ready200, OpenAPI200 avec cursor/idempotence et chemins uniquement client/health, admin/login404, POST search anonyme401. **Une recherche authentifiée depuis UniversRobot sur le service installé n’a pas été rejouée**, faute de clé cliente fournie ; les essais moteurs utilisent un runtime/projet temporaire, et les créations/reprises authentifiées sont testées sur fixtures.

## Port HTTPS externe dans la console — 10 octobre 2026

- Suite générale : **126 passed, 14 skipped** (`pytest -q` hors sandbox pour les sockets loopback).
- Tests dédiés : **20 passed**, port/range/type, CSRF/session/listener local, refus des ports occupés/partagés/Funnel/temporaires, formulaire périmé, conservation des autres routes et récupération sur échec.
- Chromium réel : **1 passed**, formulaire et corps JSON, changement 443→8443 et première activation, affichage de l’adresse et absence de débordement à 1440/390px ; CLI Tailscale simulée. Captures inspectées sous `/tmp/pagequay-external-access/`.
- Ruff et `git diff --check` conformes. Warning Starlette/TestClient habituel.
- Lecture seule de Tailscale réel : port443 privé reconnu. Copie runtime mise à jour, LaunchAgent relancé après zéro job actif, health200. La modification réelle du port HTTPS par le bouton n’a pas été exécutée ; aucun nouveau port choisi arbitrairement.
