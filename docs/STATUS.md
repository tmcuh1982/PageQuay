# État de PageQuay — 10 octobre 2026

Version **0.1.0**, MVP développé et vérifié localement sur macOS Apple Silicon. La recette de déploiement et le parcours Google depuis le MacBook Air restent partiels. Ce document décrit l'état observé, sans considérer une confirmation SSH comme un test API réussi.

## Fonctionnalités livrées

- Administration française, projets et profils Chromium persistants isolés, sessions admin et clés API par projet.
- REST et WebSocket, jobs asynchrones, navigation/actions, captures et artefacts temporaires protégés.
- Adaptateurs Google, DuckDuckGo et Brave ; un challenge humain suspend le job pour une intervention manuelle.
- Extraction texte/HTML/liens/métadonnées et JSON structuré du DOM rendu, avec arbre filtré optionnel.
- Extraction des composants Shadow DOM ouverts et des documents d'iframes, collecte bornée et résultats partiels signalés.
- Proxy validant DNS/IP, refus des destinations privées, quotas, rétention et reset manuel avec confirmations.

Les contrats détaillés sont dans [OpenAPI](openapi.json), [l'extraction](EXTRACTION.md) et [l'architecture](ARCHITECTURE.md).

## Vérifications et limites

| Vérification | Résultat observé |
| --- | --- |
| Dernière suite locale standard | 50 réussis, 10 ignorés ; navigateurs et diagnostics tiers opt-in |
| Suite Chromium visible hors UI | 56 réussis, 2 ignorés avant le dernier renforcement des bornes |
| Extraction structurée/OpenAPI après ce renforcement | 8 réussis, dont le cas de 5 000 éléments cachés |
| Contrôle Ruff de tout le projet | Check et format conformes, 47 fichiers Python |
| Page publique via API HTTP sur le mini | Navigation directe, extraction texte et JSON/DOM téléchargés |
| Recherche Google/DDG en direct | Challenges détectés ; aucun résultat de recherche obtenu |
| SSH MacBook Air → mini | Fonctionnement confirmé par l'utilisateur ; parcours API depuis l'Air non exécuté par l'agent |
| LaunchAgent, Serve/ACL Tailscale, sauvegarde/restauration | Procédures écrites ; recette effective restant à réaliser |

Ces suites se recouvrent : leurs nombres ne s'additionnent pas. Les dates, commandes et réserves de chaque essai sont dans [le rapport](testing/REPORT.md). Le warning Starlette/TestClient/httpx demeure non bloquant.

Les pages virtualisées nécessitent les attentes/actions explicites utiles avant extraction. Une racine Shadow DOM fermée et les données représentées seulement par des pixels ne sont pas accessibles par simple export DOM ; les captures restent une opération séparée. Aucun CAPTCHA n'est résolu automatiquement.

## Publication et synchronisation

Destination : [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), branche `main`, dépôt public **explicitement confirmé par l'utilisateur**. Le dossier local contient les sources, les tests, les documents et les commits préparés ; `origin` pointe vers ce dépôt et `main` suit `origin/main`.

Le dernier état distant vérifié est le commit initial `5e85c7b` avec un README d'une ligne. Le transfert n'a pas abouti : le terminal n'a pas d'identifiants HTTPS et la connexion GitHub de l'application refuse l'écriture avec `403 Resource not accessible by integration`. L'accès utilisateur au dépôt et l'autorisation publique sont acquis ; l'accès en écriture du connecteur reste à configurer.

La demande de mise à jour documentaire a également été traitée localement : README, état du projet, procédure de publication, mémoire et décisions actualisés. La tentative d'actualiser le README via l'API Contents a reçu le même 403 ; les documents distants n'ont donc pas été modifiés.

Les captures de navigation, diagnostics bruts, environnements, secrets, bases et profils restent locaux et sont ignorés par Git. Le rapport de tests et les exemples JSON issus de fixtures sont versionnés. La publication du dépôt concerne les sources ; elle n'expose pas le service PQ ni les données de ses navigateurs.

Pour reprendre : [procédure de publication](PUBLISHING.md), [mémoire de travail](../memory.md) et [décisions](../decisions.md). Ne pas redemander la visibilité déjà confirmée. Une fois l'écriture disponible, publier puis vérifier le commit et le contenu distants avant d'annoncer la synchronisation.
