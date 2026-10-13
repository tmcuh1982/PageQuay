# État de PageQuay — 12 octobre 2026

Version **0.2.2**, MVP développé et vérifié localement sur macOS Apple Silicon. La recette de déploiement et le parcours Google depuis le MacBook Air restent partiels. Ce document décrit l'état observé, sans considérer une confirmation SSH comme un test API réussi.

## Fonctionnalités livrées

- Administration française, projets et profils Chromium persistants isolés, sessions admin et clés API par projet.
- Port HTTPS Tailscale configurable dans Paramètres → Accès externe, adresse active affichée, application immédiate et persistante ; le port API loopback et la console restent séparés.
- Modification des clés existantes depuis la console locale : autorisations, quota, expiration et nom, secret conservé.
- Informations de la clé appelante via REST : scopes, expiration, quotas configurés/effectifs et solde de la fenêtre courante.
- REST et WebSocket, jobs asynchrones, navigation/actions, captures et artefacts temporaires protégés.
- Adaptateurs Google, DuckDuckGo et Brave ; un challenge humain suspend le job pour une intervention manuelle.
- Continuations DuckDuckGo opaques, quotas détaillés, POST /search idempotent, nettoyage des onglets et exemple Python pour ProjectX.
- Filtres DuckDuckGo pays / région et période, conservés dans les continuations ; menus dans la console et options dans le client Python.
- Fenêtres minimisables/restaurables et option de lancement minimisé ; nouvelles ouvertures conservent la minimisation.
- Extraction texte/HTML/liens/métadonnées et JSON structuré du DOM rendu, avec arbre filtré optionnel.
- Extraction des composants Shadow DOM ouverts et des documents d'iframes, collecte bornée et résultats partiels signalés.
- Proxy validant DNS/IP, refus des destinations privées, quotas, rétention et reset manuel avec confirmations.

Les contrats détaillés sont dans [OpenAPI](openapi.json), [recherche](SEARCH_API.md), [l'extraction](EXTRACTION.md) et [l'architecture](ARCHITECTURE.md).

## Vérifications et limites

| Vérification | Résultat observé |
| --- | --- |
| Suite finale de cette publication sans Chromium | 142 réussis, 14 tests navigateur/diagnostics externes ignorés |
| Console des filtres et transport POST avec Chromium | 2 tests réussis séparément ; menus, corps POST et rendu desktop/mobile vérifiés |
| Dernière suite complète avec Chromium visible, avant les filtres | 116 réussis, 3 diagnostics externes ignorés ; voir le rapport 0.2 |
| Suite Chromium visible hors UI | 56 réussis, 2 ignorés avant le dernier renforcement des bornes |
| Extraction structurée/OpenAPI après ce renforcement | 8 réussis, dont le cas de 5 000 éléments cachés |
| Contrôle Ruff de tout le projet | Check et format conformes, 46 fichiers Python source/tests/exemples |
| Page publique via API HTTP sur le mini | Navigation directe, extraction texte et JSON/DOM téléchargés |
| Recherche Google/DDG en direct | Challenges détectés ; trois queries DDG récentes bloquées, trois pages natives réelles non validées |
| SSH MacBook Air → mini | Fonctionnement confirmé par l'utilisateur ; parcours API depuis l'Air non exécuté par l'agent |
| LaunchAgent sur le mini | Installé ; redémarrage du service et health vérifiés, reboot restant à vérifier |
| Séparation console/API | Console locale 8765 ; API/health/OpenAPI 0.2 sur8766 ; admin refusée (tests + HTTP/HTTPS réels) |
| Serve/ACL Tailscale, sauvegarde/restauration | Serve HTTPS activé vers8766, certificat/health/auth/admin vérifiés depuis le mini ; accès depuis un autre appareil, ACL et sauvegarde restant à vérifier |

Ces suites se recouvrent : leurs nombres ne s'additionnent pas. Les dates, commandes et réserves de chaque essai sont dans [le rapport](testing/REPORT.md). Le warning Starlette/TestClient/httpx demeure non bloquant.

Les pages virtualisées nécessitent les attentes/actions explicites utiles avant extraction. Une racine Shadow DOM fermée et les données représentées seulement par des pixels ne sont pas accessibles par simple export DOM ; les captures restent une opération séparée. Aucun CAPTCHA n'est résolu automatiquement.

## Publication et synchronisation

Destination : [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), branche `main`, dépôt public **explicitement confirmé par l'utilisateur**. Le dossier local contient les sources, les tests, les documents et les commits préparés ; `origin` pointe vers ce dépôt et `main` suit `origin/main`.

Les sources initiales et documents sont **publiés** : le premier push complet a fait avancer `main` de `5e85c7b` à `ad0c861`, confirmé par lecture de la référence distante. Les commits locaux du développement et le commit initial GitHub sont conservés, sans push forcé. Les documents de statut sont ensuite actualisés pour refléter cette publication.

La reconnexion du plugin n'a pas levé son erreur 403. La publication utilise donc GitHub CLI, installé sur le mini et authentifié directement avec **tmcuh1982** après validation du code navigateur par l'utilisateur. Le dépôt local utilise son helper de credentials ; aucun token n'est copié dans le projet. Les identifiants CLI sont stockés hors du dépôt dans un fichier local de permissions 0600, le stockage sécurisé système n'ayant pas été utilisé par cette connexion.

Les captures de navigation, diagnostics bruts, environnements, secrets, bases et profils restent locaux et sont ignorés par Git. Le rapport de tests et les exemples JSON issus de fixtures sont versionnés. La publication du dépôt concerne les sources ; elle n'expose pas le service PQ ni les données de ses navigateurs.

Le lot de publication 0.2 comprend les fenêtres minimisables, la séparation console/API, la gestion des clés et les continuations DuckDuckGo, avec leurs tests, contrats et exemples. Ces fonctionnalités sont aussi déployées dans le service installé.

Cette mise à jour ajoute les filtres pays / période DuckDuckGo et généralise les noms dans la documentation et les exemples à **ProjectX** (`projectx`). Le contrat reste en version 0.2.0, avec paramètres optionnels et migration additive 004. Les filtres sont déployés dans le service local ; aucun succès de recherche filtrée sur le moteur réel n’est revendiqué.

Pour reprendre : [procédure de publication](PUBLISHING.md), [mémoire de travail](../memory.md) et [décisions](../decisions.md). La visibilité publique et la connexion directe sont déjà confirmées. Pour chaque modification future, publier puis vérifier le commit et le contenu distants avant d'annoncer la synchronisation.


## Correctif iframe KUKA — 0.2.1

WORLD_NOT_FOUND reproduit sur le site réel puis corrigé dans un runtime jetable : identité des slots natifs de frames dans un monde utility isolé, sélection du target CDP ancêtre pour les descendants OOPIF et diagnostics bornés. Version0.2.1 déployée dans le service installé, sans changement de clés/projets/réseau. Le test authentifié de ce service est confié à UniversRobot avec sa clé existante ; les preuves et limites sont dans [KUKA_FRAME_FIX](KUKA_FRAME_FIX.md).


## Navigation et portée — 0.2.2

Version 0.2.2 déployée : redirections autorisées par défaut sans false implicite dû à robots, attente passive bornée des vérifications automatiques, reprise du même job après intervention humaine, URL finale contrôlée avant extraction et refus scope_changed sans adoption implicite. Les gardes réseau, mondes isolés et budgets existants sont conservés. Suite générale265passed/4skipped, compléments finaux48passed et5passed (ensembles recouvrants), contrat OpenAPI livré identique au listener public et sources/package/module vérifiés. Sauvegarde /private/tmp/pq-navigation-022-backup-_vjth5ei ; clés/projets/réglages inchangés.

KUKA réel revalidé séparément en service jetable : URL finale identique, 69blocs, f1extracted, partialfalse/truncatedfalse. Aucun lien causal entre redirections/Cloudflare et WORLD_NOT_FOUND n’est démontré. Le test authentifié installé reste à effectuer par UniversRobot. Voir [contrat et preuves](NAVIGATION_SCOPE.md) et [traces KUKA](KUKA_FRAME_FIX.md).
