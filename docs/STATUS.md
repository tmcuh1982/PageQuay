# État de PageQuay — 14 octobre 2026

Version **1.0.0**, MVP développé et vérifié localement sur macOS Apple Silicon. La recette de déploiement et le parcours Google depuis le MacBook Air restent partiels. Ce document décrit l'état observé, sans considérer une confirmation SSH comme un test API réussi.

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
| Suite complète release 0.2.4 avec Chrome/Chromium | 343 réussis, 4 ignorés ; warning Starlette préexistant, Ruff ciblé et lock offline conformes |
| Transport et WebSockets | Contrôles positifs ws/wss, refus sans handshake, constructeur natif, frames/popups/workers, arrêt du listener et maintien HTTP/HTTPS |
| Music Store via API du service | Chrome et Chromium en profils neufs ; cinq recherches et cinq fiches supplémentaires en HTTP 200 dans une même session Chromium |
| Service installé après déploiement | Readiness vérifiée ; configuration et permissions conservées ; métadonnées installées 0.2.2 |
| Accès depuis un autre appareil, ACL Tailscale et restauration complète | Recette restant partielle ; aucun nouveau contrôle distant revendiqué pour 0.2.4 |

Les résultats historiques et les commandes de chaque essai sont dans [le rapport](testing/REPORT.md) ; les nombres de suites historiques ne s’additionnent pas. Le warning Starlette/TestClient/httpx demeure non bloquant.

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


## Release GitHub — 13 octobre 2026

[PageQuay v0.2.2](https://github.com/tmcuh1982/PageQuay/releases/tag/v0.2.2) publiée, release stable et non brouillon. Le tag annoté v0.2.2 désigne le commit de code `a763418894ca30adbe5bf3779fa6e7e76fe46882`, publié sur main. Archives wheel Python et source tar.gz construites depuis ce commit, avec SHA256SUMS. Les trois fichiers ont été téléchargés depuis GitHub et comparés aux fichiers locaux : hashes identiques. Ressources JavaScript, templates, assets statiques et migration007 vérifiés dans le wheel ; script d’installation et notes inclus dans les sources. Aucun environnement, profil, base privée ou secret publié. Notes : [0.2.2](releases/0.2.2.md).


## Version 0.2.3 — 14 octobre 2026

État courant : action REST/WebSocket `validate_cookies`, choix automatique persistant par projet via GET/PUT cookie-policy, refus par défaut pour une action ponctuelle et règle désactivée par défaut. L'acceptation automatique est activée dans le service local pour UniversRobot seulement ; cette configuration privée ne fait pas partie des paquets publiés. User-Agent natif Chromium et règles robots fondées sur l'en-tête observé. Les correctifs d'extraction AgXeed, frames Shadow DOM, widgets CAPTCHA et diagnostics de navigation/démarrage publiés sur main depuis v0.2.2 sont inclus dans la nouvelle release.

L'action cookies et le choix UniversRobot ont été déployés et vérifiés dans le service local, qui conserve actuellement ses métadonnées 0.2.2. La préparation de la release 0.2.3 ne redémarre pas ce service une nouvelle fois. Voir [les notes 0.2.3](releases/0.2.3.md) pour le contrat et les limites.


## Version 0.2.4 — 14 octobre 2026

Port CDP explicite loopback avec relais Playwright et blocage WebSocket par règle de proxy native, sans remplacement JavaScript. Chrome installé et Chromium vérifiés en profils neufs ; cinq recherches et cinq fiches Music Store supplémentaires réussies dans la même session Chromium (HTTP 200, aucun défi Cloudflare observé). Le premier clic a expiré puis la série a utilisé les liens observés via navigation API. Voir [transport et recette](BROWSER_TRANSPORT.md) et [notes 0.2.4](releases/0.2.4.md).

Correctif runtime déployé dans le service, prêt et configuré sur Chromium ; profils précédents sauvegardés, réglages et permissions conservés. Métadonnées installées encore 0.2.2. Le dépôt prépare un commit local 0.2.4 ; aucune publication distante de cette version n’est revendiquée. La session de démonstration reste ouverte, soumise à son délai d’inactivité.


## Version 1.0.0 — 14 octobre 2026

L’utilisateur demande une release v1 à la place de la publication 0.2.4. Le commit 0.2.4 validé est conservé ; seules les métadonnées de version, le contrat public et les documents de release passent à 1.0.0. Code navigateur inchangé, suite complète 343 réussis/4 ignorés toujours applicable ; contrôle séparé du contrat/version avant publication. Notes et liste des archives : [1.0.0](releases/1.0.0.md). Cette publication ne réinstalle ni ne redémarre le service local.
