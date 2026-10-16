# Home Browser Gateway — dossier de consignes pour Codex

[Français](README.md) | [English](README.en.md)

**Archive historique :** le nom HBG est devenu PageQuay. Pour le comportement livré, consulter [le README actuel](../../README.md), [l’état](../STATUS.md) et [OpenAPI](../openapi.json). Ces exigences ne prouvent pas leur réalisation ou leur validation.

Ce ZIP contient un **prompt de réalisation**, pas le programme déjà développé.

## Utilisation

1. Extraire l'archive dans un **nouveau dossier / dépôt Git vide**.
2. Ouvrir ce dossier dans Codex.
3. Envoyer le contenu du fichier **`PROMPT_CODEX.md`** comme instruction principale à Codex.
4. Laisser `SPEC_API.md` et `RECETTE.md` dans le même dossier : le prompt demande à Codex de les lire et de construire l'application.
5. Vérifier ensuite les tests et la documentation générés avant toute exposition via un réseau, même privé.

## Résultat recherché

Un service **gratuit et auto-hébergé sur Mac mini**, avec :

- **1 projet = 1 profil Chromium/Chrome persistant**, isolé ; plusieurs sessions simultanées.
- Recherche Google / Brave / DuckDuckGo par navigateur et normalisation des résultats.
- **REST + WebSocket** pour recherche, navigation, extraction, onglets et progression.
- **Interface Web administrateur** : projets, clés API avec scopes/expiration/révocation, activité, sessions, paramètres.
- **Rétention distincte** du cache de contenu, de la fermeture du navigateur, du soft restart et du hard reset.
- Authentification, quotas, audit, restrictions réseau/SSRF, isolation entre projets.
- Accès privé via Tailscale Serve, sans port ouvert sur le routeur.

## Précisions importantes

- Le profil navigateur n'est **pas** le profil personnel Chrome de macOS : il est généré spécifiquement pour chaque projet.
- La navigation peut déclencher une vérification humaine ; le programme doit le signaler et attendre une validation manuelle, **pas contourner** cette vérification.
- Les moteurs de recherche peuvent faire évoluer leurs pages ou limiter l'automatisation. Le programme doit traiter ces cas honnêtement.
- La durée de conservation des cookies est partiellement contrôlée par les sites : un redémarrage « soft » ne garantit pas le maintien d'une session distante.
- Codex doit documenter ce qui a été réellement testé sur macOS et ce qui reste à vérifier sur un Mac mini.

## Références techniques officielles

- Playwright persistent context : https://playwright.dev/python/docs/api/class-browsertype
- Tailscale Serve : https://tailscale.com/docs/features/tailscale-serve
- FastAPI : https://fastapi.tiangolo.com/

Langue des instructions : français. Les identifiants, endpoints et commentaires de code sont à écrire de manière professionnelle et cohérente, de préférence en anglais pour le code.
