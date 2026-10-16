# Rapport de vérification — PageQuay 0.1

[Français](REPORT.md) | [English](REPORT.en.md)

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

Sur le Mac mini : PageQuay écoute sur les deux sockets loopback, ready sur8766 renvoie200. Tailscale Running, aucune alerte et ShieldsUp=false ; aucune configuration Serve/Funnel. Le hostname Tailscale est déjà accepté : requêtes locales avec ce Host, ready200, key-info anonyme 401, admin/login404 sur8766.

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
- Déploiement : sauvegarde privée des sources et de SQLite, vérification de zéro job actif, 16 fichiers synchronisés dans PageQuayService et LaunchAgent rechargé. Migration additive 003 appliquée, paramètres existants et clés/projets réels conservés. Le plafond du projet de référence reste 10, le quota moteur PageQuay reste 6/60 s ; aucune augmentation silencieuse.
- Contrôles du service installé : local ready/login 200, OpenAPI sur8766 200/version0.2.0, admin/login404 sur8766. Sur HTTPS Tailscale avec certificat validé : ready200, OpenAPI 200 avec cursor/idempotence et chemins uniquement client/health, admin/login404, POST search anonyme 401. **Une recherche authentifiée depuis le client du projet de référence sur le service installé n’a pas été rejouée**, faute de clé cliente fournie ; les essais moteurs utilisent un runtime/projet temporaire, et les créations/reprises authentifiées sont testées sur fixtures.


## 10 octobre — nouvelle recette sur le Mac mini

- Suite complète avec Chromium visible : `.venv/bin/pytest --browser --headed -q` → **116 passed, 3 skipped**, 71,06 s. Les trois skips sont les diagnostics externes opt-in. Ruff check et format conformes (58 fichiers). Avertissement Starlette/httpx inchangé.
- La première exécution standard sous sandbox avait trois échecs liés aux sockets localhost interdites ; la suite complète avec sockets autorisées passe. Aucun correctif du service nécessaire.
- Service déjà lancé : LaunchAgent actif ; 27 fichiers de sources/assets/migrations installés identiques au dossier de travail. HTTP local : health live/ready et login 200 ; port API 8766 : ready/OpenAPI 200, admin/login/assets 404, key-info sans clé 401. Schéma client 0.2.0 sans route admin.
- HTTPS privé Tailscale depuis le mini, certificat validé : ready/OpenAPI 200, admin/login 404, key-info sans clé 401 ; backend 8766 confirmé, Funnel désactivé. Aucun test depuis l'Air ni de reboot dans cette recette.
- Diagnostics externes : première exécution **2 passed, 1 failed**, 32,89 s. Le diagnostic Google échouait avec `UnboundLocalError` en tentant une capture sans onglet disponible après nettoyage de la recherche. Capture replacée dans sa condition de disponibilité ; contrôle Google relancé : **1 passed**, 7,82 s ; Ruff ciblé et diff conformes.
- Résultat réel des moteurs : Google et DuckDuckGo demandent une intervention humaine, événement `challenge.required`, délai humain de test cinq secondes puis TIMEOUT ; **aucun résultat de recherche obtenu**. Les trois requêtes de pagination DuckDuckGo restent bloquées, zéro onglet interne restant. Un diagnostic passant ne signifie pas que la recherche a réussi.
- Navigation extérieure indépendante des moteurs : API authentifiée avec clé/projet/profil jetables vers `https://playwright.dev/python/docs/intro`, navigation terminée et téléchargements 200 ; texte **3 832 octets**, JSON structuré **20 719 octets**. Instance et profil temporaires fermés à la fin.
- Capture du dashboard desktop inspectée. Exemples JSON versionnés régénérés par les tests puis restaurés pour éviter les différences de ports temporaires. Aucun compte, clé, profil ou réglage réel modifié ; service existant conservé en fonctionnement.

## Port HTTPS externe dans la console — 10 octobre 2026

- Suite générale : **126 passed, 14 skipped** (`pytest -q` hors sandbox pour les sockets loopback).
- Tests dédiés : **20 passed**, port/range/type, CSRF/session/listener local, refus des ports occupés/partagés/Funnel/temporaires, formulaire périmé, conservation des autres routes et récupération sur échec.
- Chromium réel : **1 passed**, formulaire et corps JSON, changement 443→8443 et première activation, affichage de l’adresse et absence de débordement à 1440/390px ; CLI Tailscale simulée. Captures inspectées sous `/tmp/pagequay-external-access/`.
- Ruff et `git diff --check` conformes. Warning Starlette/TestClient habituel.
- Lecture seule de Tailscale réel : port443 privé reconnu. Copie runtime mise à jour, LaunchAgent relancé après zéro job actif, health200. La modification réelle du port HTTPS par le bouton n’a pas été exécutée ; aucun nouveau port choisi arbitrairement.

## 10 octobre — filtres de recherche DuckDuckGo

`region` et `time_range` ajoutés à l’API, à la console et au client/checkpoint Python. Région officielle explicite, période any/day/week/month/year ; controls kl/df conservés dans la pagination native et liés aux curseurs/idempotence. Migration 004 additive, anciens curseurs et hashes sans filtre conservés. Auto/Brave/Google refusent les filtres explicites à l’admission.

- `.venv/bin/pytest -q` hors sandbox réseau : **142 passed, 14 skipped**, 6,45 s. Le premier passage sous sandbox avait 3 échecs dus à l’interdiction des sockets loopback ; ils passent hors sandbox.
- Transport Chromium : **1 passed** dans le passage UI/transport initial. UI Chromium après correction des sélecteurs, du projet sélectionné et du callback d’interception du test : **1 passed**, 14,06 s. Contrôles pays/période, corps POST, autres moteurs sans filtre, région vide omise, mise en page desktop/mobile et absence de pageerror vérifiés. Captures locales `search-filters-desktop.png` et `search-filters-mobile.png` inspectées.
- Ruff check/format, syntaxe Node et diff --check conformes. Documentation et OpenAPI exporté actualisés. Aucun succès de recherche filtrée sur DuckDuckGo réel revendiqué ; la collecte ne prouve pas la date de publication ni celle de l’événement.
- Runtime permanent mis à jour après contrôle de zéro job actif, sauvegarde privée des sources et arrêt. Premier bootstrap en erreur 5, reprise réussie. Neuf fichiers installés relus identiques ; ready 200, migration 004 appliquée, contrat public avec filtres, login local 200 et console sur API 404 vérifiés. Configurations, profils et clés réels conservés. Aucun push GitHub pour cette tranche.

## Bouton Appliquer grisé avec LaunchAgent — 10 octobre 2026

- Reproduction avec PATH macOS minimal : le binaire de Tailscale.app renvoie un message CLIError3 non JSON avec exit0 ; le lanceur /usr/local/bin/tailscale répond correctement aux deux commandes de lecture.
- Correctif : chercher les répertoires CLI macOS habituels avant le fallback vers le binaire app, conserver la priorité du PATH existant. Deux tests de régression ; `pytest -q tests/test_external_access.py tests/test_security.py` : **41 passed** ; Ruff conforme.
- Déploiement : module seul, sauvegarde privée, aucun job actif, LaunchAgent redémarré, health200. Vérification dans Safari réel : adresse HTTPS privée détectée et bouton Appliquer actif. Saisie8443 préservée ; aucune redirection réseau modifiée par la recette.

### Audit détaillé — 10 octobre 2026

Migration005 conserve les anciens événements et ajoute des métadonnées JSON. Navigation réelle, ressources du navigateur et redirections HTTP enregistrées avec URL masquées, taille encodée du corps de réponse en octets, code HTTP et identifiants de job/onglet. Fonctions navigate/actions/click/fill/select/scroll/attentes/extract/screenshot et pagination native suivies avec URL obtenue ; libellé fixe « next page ». Acteur capturé au début de chaque requête, navigation manuelle attribuée au navigateur. Aucune valeur de formulaire, corps POST, cookie, sélecteur ou erreur brute persistée. Paramètres de toutes les URL, userinfo et fragments retirés ; chemins conservés. Mesures manquantes explicitement indisponibles.

Console locale : colonnes URL/destination, Ko (1 024 octets), fonction, HTTP/résultat et job/onglet ; filtres type et job en plus des filtres existants, choix conservés, lien de regroupement par job. Les anciens événements ne gagnent pas de détails rétroactifs. Rétention habituelle, aucune route API d’audit ajoutée.

Validation finale : **159 passed, 4 skipped**, suite complète avec Chromium ; Ruff check/format et diff --check conformes. Tests dédiés : upgrade d’une base ancienne, suppression de données sensibles dans les URL, accès admin/échappement/filtres/projet, erreur/annulation/mesure indisponible ; fixture Chromium avec réponse gzip (taille compressée vérifiée), ressource image,302/303, clic Next avec texte et aria-label, formulaire POST natif,404, requête privée bloquée et attribution d’une navigation manuelle. Interface Chromium desktop/mobile vérifiée, captures audit-desktop/audit-mobile inspectées.

Déployé dans PageQuayService après zéro job actif, sauvegarde privée sources+SQLite, huit fichiers synchronisés et LaunchAgent redémarré. Migration005 appliquée ; ready/login locaux200, audit local anonyme303, audit sur port API 404 et key-info anonyme 401. Aucun projet, clé ou réglage réseau réel modifié. Sources non publiées dans cette demande.

### Paramètres d’URL en clair dans l’audit admin — 10 octobre 2026

À la demande explicite de l’utilisateur, suppression du remplacement des valeurs de paramètres par `[masque]`. Les paramètres et fragments sont désormais conservés avec leur encodage d’origine : q/kl DuckDuckGo, paramètres répétés/vides, redirections HTTP et URL obtenues restent lisibles. La partie userinfo reste exclue ; l’échappement HTML reste actif pour afficher ces URL comme texte. Les anciens paramètres déjà remplacés en base ne peuvent pas être reconstitués. Cette évolution remplace la politique de masquage décrite dans l’entrée précédente ; README, SECURITY et aide UI actualisés.

Validation ciblée :6testsréussis (audit et interface Chromium desktop/mobile), Ruff et diff--check conformes. Tests mis à jour pour confirmer l’intégrité des paramètres/encodages/fragments, le rendu q/kl en clair et les destinations de redirection ; corps POST/saisies et messages bruts du navigateur toujours absents. Deux fichiers runtime synchronisés après zéro job actif, sauvegarde privée et redémarrage du LaunchAgent. Ready/login200 ; audit local anonyme303 et audit portAPI 404. Aucun réglage réseau, clé ou projet modifié.

### Défilement horizontal visible de l’audit — 10 octobre 2026

Une barre « Colonnes » permanente au-dessus du tableau permet de déplacer la grille même lorsque macOS masque la scrollbar native. Curseur et flèches synchronisés avec le défilement réel et les changements de largeur ; tableau accessible au clavier, contrôles désactivés aux limites. Styles/table compacte conservés.

Test UI Chromium réussi : flèche droite, curseur End/Home, dernière colonne entièrement visible sur desktop et mobile, absence de débordement du document et d’erreurJS. Captures inspectées, Ruff et diffcheck conformes. Trois fichiers statiques/template déployés à chaud avec sauvegarde, sans redémarrage ni interruption des jobs.

### Filtres Audit : Job et périodes — 10 octobre 2026

Champ Job remplacé par un select natif (200 jobs récents observés dans l’audit, ID/projet/type/date ; sélection directe conservée au-delà de la liste). Les champs et boutons ont tous42px de hauteur dans une grille responsive. Depuis/Jusqu’au utilisent datetime-local avec secondes ; l’interface affiche le fuseau local du navigateur, convertit les saisies en ISO UTC et restitue les dates filtrées en heure locale. Le serveur respecte les offsets fournis, conserve la compatibilité des dates naïves UTC et refuse les intervalles inversés.

Boutons last10min/lasthour/Today appliquent immédiatement la période en conservant les autres filtres ; Today commence à minuit local et finit à l’instant du clic. La barre horizontale et les lignes compactes restent opérationnelles.

Validation :26tests ciblés réussis (audit, sécurité, interface Chromium). Bornes inclusives/offsets/intervalle inversé/choix Job testés côté serveur ; hauteur uniforme, select, durées600/3600s, Today Europe/Warsaw, conversion manuelle15:20:30 locale→13:20:30UTC, conservation des filtres et retour des dates contrôlés dans Chromium. Desktop/mobile, dernière colonne et absence d’erreursJS vérifiés ; captures inspectées, Ruff/diffcheck conformes. Quatre fichiers runtime déployés après zéro job actif avec sauvegarde privée et redémarrage ; ready/login 200, audit local anonyme303 et auditAPI 404. Aucun changement de données/projets/clés/réseau.

### Fuseau horaire uniforme dans Audit — 10 octobre 2026

Cause constatée dans Safari réel : filtres Depuis/Jusqu’au en Europe/Warsaw mais dates de grille et labels Job encore en UTC. L’événement20:46UTC correspond à22:46locale ; last hour bornait correctement une heure, le décalage était visuel. La grille porte désormais « Date locale » et affiche les timestamps dans le fuseau du navigateur, comme les dates du menu Job. Le titre de cellule conserve l’instant ISO UTC exact et le fuseau. Aucun timestamp, borne de filtre ni donnée historique modifié.

7tests audit/UI réussis, dont fixture20:46UTC→22:46Europe/Warsaw dans la grille et Job, presets d’une heure/dix minutes/Today et conversions manuelles. JS/template déployés à chaud sans redémarrage après sauvegarde privée ; Safari rechargé sur le même filtre et la même sélection, grille et Job22:46visibles. Ruff/diffcheck conformes.

### Durées d’exécution dans Audit — 11 octobre 2026

Ajout de la colonne Durée, affichée en ms sous une seconde et en secondes au-delà. Mesures monotones des fonctions, y compris opérations imbriquées, et de chaque requête réseau depuis request jusqu’à requestfinished/requestfailed ; la récupération asynchrone des tailles n’allonge pas la mesure réseau. Durées des jobs terminés/échoués/annulés depuis l’acquisition du créneau d’exécution : file d’attente exclue, attente humaine incluse. Jobs annulés avant exécution et anciens événements sans mesure affichent « — ». Stockage dans details.duration_ms, sans migration supplémentaire. Grille compacte et défilement horizontal conservés.

Validation : 14 tests audit/jobs/UI réussis avec Chromium. Durées déterministes, imbrication, absence d’inflation réseau par collecte de taille, erreurs/annulations, queue exclue, annulation avant lancement et formats ms/s vérifiés ; dernière colonne accessible sur desktop/mobile, captures inspectées. Ruff check/format et diff-check conformes. Quatre fichiers runtime synchronisés après zéro job actif avec sauvegarde privée /private/tmp/pq-audit-duration-pfal2l3w et redémarrage du LaunchAgent ; ready/login 200, audit local anonyme 303 et audit API 404. Aucun changement de projets, clés ou réglages réseau ; aucun push.


### Port API local configurable sans Tailscale — 12 octobre 2026

Paramètres → Accès local : port API modifiable (1024–65535), indépendant du HTTPS Tailscale ; validation stricte, conflit avec la console/port occupé, session admin et CSRF, détection des éditions concurrentes. Surcharge atomique local-api.json (0600) dans PQ_DATA_DIR, prioritaire sur PQ_API_PORT au prochain lancement ; port actif et port enregistré distincts, redémarrage requis visible, annulation possible en enregistrant le port actif. CLI serve/doctor et create_app sans configuration explicite lisent la surcharge ; la CLI transmet ensuite la même configuration résolue aux sockets et au middleware. Aucune route Serve modifiée ; si utilisée, sa destination doit être adaptée séparément.

Validation : suite 176 passed / 15 skipped ; 38 tests local/externe repassés après ajustement de la lecture au démarrage ; recette Chromium 1 passed, formulaire utilisable sans Tailscale, corps envoyé/persistance/avertissement et desktop/mobile inspectés. Bind CLI loopback, refus admin sur le nouveau port et API anonyme 401 vérifiés. Ruff check/format et diff-check conformes. Cinq fichiers runtime déployés après zéro job actif, sauvegarde /private/tmp/pq-local-port-backup-gkdviy_l et redémarrage LaunchAgent ; hashes identiques, ready/login 200, mutation locale anonyme 401 et mutation/adminAPI 404. Ports réels8765/8766 conservés, aucune surcharge réelle créée, aucun changement de clés/projets/routes réseau ni push.


## Correctifs de sécurité — 12 octobre 2026

Suite normale finale : **186 passed, 16 skipped**, 9,57 s. Structured/audit/budgets avec Chromium : **24 passed** ; budgets final : **11 passed** ; complément plafond octets : **10 passed, 1 skipped** ; jobs/accès local : **22 passed**. Ruff check/format sur 53 fichiers, Node deux scripts et diff-check conformes. Déclencheurs : 300 requêtes 401, total 300, détail ≤30 et alerte UI, files/réserves/plafonds lignes et octets, requêtes/tâches suspendues, panne du writer/réessai, cardinalité, contenu hostile et modifications de prototypes, titre 512/troncation, HTML/texte 413, surrogate isolé, erreurs/résultats partiels, frames avec ancre et migration unique.

Suite complète headed : **194 passed, 5 failed, 3 skipped** avant adaptation de quatre assertions d’audit au flush asynchrone. Ces quatre cas ont repassé ; le seul échec restant est le test natif macOS de minimisation/navigation. Une exécution identique sur les sources sauvegardées avant correction reproduit le timeout Browser.getWindowBounds, avant les nouveaux lecteurs. **198 tests distincts passent**, aucune suite complète verte ni recette de minimisation complète revendiquées. Les trois diagnostics tiers restent opt-in ; warning Starlette préexistant conservé.

Service installé : zéro job inachevé, sauvegarde privée sources+SQLite, 19 fichiers synchronisés, hashes identiques, migration006, ready/login 200, admin API 404, key-info anonyme 401, OpenAPI 200, budgets respectés et compteur persisté. Ports conservés. Aucun profil/clé/projet ou route externe modifié. Le détail d’audit est partiel sous saturation ; plafonds logiques SQLite et copies applicatives bornées, mémoire native Chromium/driver et crash buffers hors garantie.


## Release 0.2.4 — 14 octobre 2026

Transport navigateur : port CDP explicite loopback via relais du pipe Playwright ; gardes persistantes conservées. Blocage ws/wss par le second listener du proxy natif, sans remplacement de `WebSocket`. Tests réels Chrome/Chromium : témoins positifs ws/wss, refus sans handshake amont, frames/popups/workers, constructor natif, maintien HTTP/HTTPS et absence de repli après fermeture du listener. Arrêt/échec de lancement, endpoint et fermeture des handlers vérifiés.

Validation finale : `PQ_BROWSER_TESTS=1 .venv/bin/pytest -q` : **343 réussis, 4 ignorés**, 95,71 s, warning Starlette préexistant. Ruff check/format ciblés, `uv lock --check --offline`, cohérence paquet/module/OpenAPI/lock 0.2.4 et `git diff --check` conformes. Les tests emploient des profils isolés ; la session de démonstration du service reste ouverte.

Recette installée : recherche et Yamaha P-45 en profils neufs Chrome puis Chromium ; série de cinq recherches et cinq fiches distinctes dans une même session Chromium, chaque recherche et fiche en HTTP200. Premier clic Fender expiré, reprise avec les liens observés via navigation API. Aucun défi Cloudflare observé, sans garantie future ni résolution de CAPTCHA. La fenêtre demeure sur Roland FP-10. [Protocole détaillé et limites](../BROWSER_TRANSPORT.md).

Les changements générés dans les exemples JSON de la fixture complexe (ports, dates et IDs locaux) sont exclus de ce commit. Aucun rapport brut, profil, sauvegarde, secret ou capture du service n’est versionné. Le correctif runtime déployé conserve ses métadonnées installées 0.2.2 ; ce commit prépare le dépôt en 0.2.4 sans redémarrer le service.
