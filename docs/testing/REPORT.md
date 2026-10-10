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
