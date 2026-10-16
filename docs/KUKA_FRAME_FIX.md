# Correctif WORLD_NOT_FOUND de l’iframe KUKA — PageQuay 0.2.1

[Français](KUKA_FRAME_FIX.md) | [English](KUKA_FRAME_FIX.en.md)

## Résultat

Défaut reproduit puis corrigé sur l’URL réelle `https://my.kuka.com/s/?language=en_US`, via un service PageQuay jetable utilisant l’API HTTP/ASGI, Bearer éphémère, proxy public normal et navigateur Chromium. Aucune clé ni aucun profil du service installé utilisés. L’utilisateur a demandé que le test authentifié du service installé soit ensuite effectué depuis UniversRobot avec sa clé existante.

Dernier export réel : URL finale exactement identique, **69 blocs principaux**, `f1.status=extracted`, `partial=false`, `truncated=false`, aucune limite de frames atteinte. Le document sélectionné est `KUKA - player` et son URL correspond à celle de la frame. Le player ne fournit **aucun bloc textuel monté** dans cette capture (9 nœuds visités, 2 inclus) : aucune donnée visuelle ou contenu applicatif n’a été fabriqué. « Complet » décrit ici le snapshot DOM monté dans les bornes existantes, pas une interprétation du player.

Les captures attendent explicitement la présence d’une iframe (10 secondes maximum), puis cinq secondes d’hydratation avant **une seule extraction**. La première navigation seule peut rendre la page avant montage de l’iframe ; un export sans frame ne constitue pas une validation de ce défaut.

## Cause reproduite

Avant correction, deux contextes CDP étaient présents. Le chemin calculé depuis `parent.child_frames.index(frame)` était `[2]` ; les chemins du monde isolé étaient `[0]` et `[]`. L’iframe restait attachée, et la lecture échouait en environ 9 ms à `context_selection` avec `WORLD_NOT_FOUND`.

L’ordre des objets Frame connus de Playwright n’est pas une identité fiable pour les indices natifs de `window.frames`, notamment pendant les créations/destructions de frames transitoires. L’ordre des éléments dans le DOM n’est pas non plus une substitution générale : la régression Chromium couvre des iframes ajoutées puis insérées en tête du DOM, pour lesquelles l’ordre natif reste différent.

Le cas KUKA reproduit utilisait une **session page**, avec un enfant d’une autre origine mais du même site. Il ne prouve pas un défaut OOPIF de ce site. Un problème supplémentaire de sélection des descendants internes d’une OOPIF est couvert séparément par une régression.

## Correction

Le sélecteur fixe `pq_frame_slot`, enregistré avant création du navigateur avec `content_script=True`, relie chaque indice natif `window[i]` à son élément iframe/frame propriétaire. `ElementHandle.content_frame()` vérifie ensuite l’identité du Frame Playwright demandé. Ce mécanisme ne suppose aucun ordre d’attachement ou d’éléments, ne compare pas des URLs/titres et n’écrit pas dans le DOM.

Ce sélecteur est utilisé seul dans le monde utility isolé ; l’extraction reste dans un monde CDP isolé. Aucun appel à evaluate dans le JavaScript de la page n’est ajouté. Le mécanisme de [sélecteurs isolés est documenté par Playwright](https://playwright.dev/python/docs/api/class-selectors#selectors-register). Les protections contre les monkeypatches de page sont vérifiées en Chromium.

Le lecteur cherche le target CDP du frame demandé ou de son plus proche ancêtre propriétaire. Une frame interne d’une OOPIF ne bascule plus vers le target de la page principale. Seule l’erreur attendue « pas de session CDP séparée » fait poursuivre cette résolution ; les autres erreurs sont conservées.

Chemin/identité revérifiés avant et après capture ; même contexte isolé revérifié après lecture. Les échecs continuent à produire `unavailable`/`partial=true`, sans forcer le résultat complet. Les budgets existants restent inchangés : lecture 10 s/frame, 4 documents/export, 128 candidats CDP, chemins de profondeur 32, limites de contenu/nœuds et proxy. L’inventaire d’identité est borné à 128 slots/propriétaires ; l’exploration des racines shadow ouvertes est bornée à 2 000 éléments. Un grand DOM ordinaire n’est pas copié vers le serveur et ne consomme pas le budget des propriétaires de frames.

`context_selection` est ajouté aux diagnostics et aux frames extraites : type de session, nombre de candidats, chemin attendu/sélectionné, au plus 8 chemins observés de 32 entiers maximum, indicateur de troncature et cause `no_candidates` ou `path_mismatch`. Aucun corps de page, URL/query/fragment, cookie ou Bearer. Les événements serveur `frame_read_success` et `frame_read_failure` portent la version et les IDs de corrélation ; les messages arbitraires d’exception restent expurgés.

## Traces réelles corrélées

Reproduction avant correction, runtime jetable :

```json
{
  "request_id": "844fb935ea2823f26458f597",
  "job_id": "c88ada640d410864cd2abb1050a1a176",
  "tab_id": "f9766c05e5a0986f49286df992600ff8",
  "artifact_id": "51e67491222ac01d81cf7f9a3db97cd8",
  "frame_id": "f1",
  "cause": "WORLD_NOT_FOUND",
  "stage": "context_selection",
  "is_detached": false,
  "context_selection": {
    "session_type": "page",
    "candidate_count": 2,
    "expected_path": [2],
    "observed_paths": [[0], []],
    "failure": "path_mismatch"
  }
}
```

Nouvelle trace de succès, **source finale 0.2.1**, UTC `2026-10-12T20:05:01.931232+00:00` (22:05:01 Europe/Warsaw) :

```json
{
  "request_id": "0eb1a5ac5483988332959676",
  "job_id": "64e31857d3201278ff161cab6d8bfbfd",
  "tab_id": "cebf49c37576b61e084c366b7b279a7d",
  "artifact_id": "390f03a9aad543f474b90906cb6a87cb",
  "frame_id": "f1",
  "reader_version": "0.2.1",
  "stage": "context_verification",
  "duration_ms": 24.409,
  "limit_ms": 10000,
  "is_detached": false,
  "context_selection": {
    "session_type": "page",
    "candidate_count": 2,
    "expected_path": [0],
    "selected_path": [0],
    "observed_paths": [[0]],
    "paths_truncated": false,
    "failure": null,
    "path_source": "isolated_frame_owners"
  }
}
```

Fichiers privés sur la machine PageQuay : avant `/private/tmp/pq-kuka-real-ttkoaw7e/frames.log` ; après `/private/tmp/pq-kuka-real-gmkxjspo/frames.log`, `summary.json` et `artifact.json`. Ces IDs appartiennent aux runtimes jetables et ne sont pas téléchargeables depuis l’API installée. Aucun contenu réel ni secret n’est ajouté au dépôt.

La trace originale fournie par UniversRobot a aussi été retrouvée dans le log LaunchAgent, avec les cinq IDs indiqués et UTC `2026-10-12T19:38:28.381257+00:00`.

## Validation et déploiement

- Suite globale Chromium : **249 passed, 4 skipped**. Quatre recettes distinctes non exécutées : minimisation native `--headed` et trois tests de moteurs externes `--live`.
- Après ajustement final de l’inventaire (DOM caché sans rapport) : **33 passed** sur acquisition navigateur, extraction structurée et budgets ; ajout d’une régression couvrant ce cas.
- Régressions simulées : ordre d’attachement incompatible avec les slots réels, choix du target ancêtre OOPIF, absence de candidats vs chemins incompatibles, borne de 128 slots et exclusion de valeurs arbitraires des diagnostics.
- Régressions Chromium : ordre DOM différent des slots natifs, scripts de page hostiles, OOPIF avec descendant interne, grand DOM caché, redirections explicitement autorisées, anciennes extractions et limites.
- Ruff check/format, diff-check et vérification hors ligne du lockfile conformes.

**Version 0.2.1 déployée** dans `~/Library/Application Support/PageQuayService` : 8 fichiers source et métadonnées du package synchronisés après zéro job actif. Réinstallation editable hors ligne, sans changement de dépendances ; version du module, du package installé et de l’OpenAPI toutes vérifiées à 0.2.1. Sauvegarde privée sources/SQLite/métadonnées : `/private/tmp/pq-kuka-021-backup-5gtr49vj`, manifeste SHA-256 dans `deployment.json`.

Ready/admin-login 200, administration sur port API 404, API sans Bearer 401. OpenAPI servi identique au JSON livré ; hashes source/runtime identiques. Tables `api_keys`, `projects` et `settings` vérifiées identiques au backup. Aucun réglage réseau assoupli. Redémarrage normal du service effectué ; les anciens IDs d’onglets en mémoire ne doivent pas être réutilisés.

Le test final avec le Bearer existant du projet installé sera exécuté **par UniversRobot**, selon le choix explicite de l’utilisateur. Aucune reproduction authentifiée du service installé n’est revendiquée ici.

## Option d’autorisation des redirections

Le POST de création/navigation expose déjà `allow_redirects` (défaut historique true). Pour le call KUKA :

```json
{
  "url": "https://my.kuka.com/s/?language=en_US",
  "allow_redirects": true
}
```

Le caller vérifie ensuite que `result.navigation.final_url` reste exactement l’URL attendue avant de demander `content?format=structured`. Avec `expected_url` renseigné, l’URL finale doit toujours correspondre à cette attente, même si le suivi de redirections est autorisé. `allow_redirects=false` bloque une autre cible avant son acquisition. Les gardes DNS/IP/ports restent actives dans tous les cas.

Le mode HTTPS strict déjà livré refuse toujours le réseau des frames enfants faute d’attestation de toutes les redirections OOPIF ; ce correctif n’enlève pas cette restriction. La reproduction ci-dessus suit le mode historique demandé (URL, redirections autorisées, comparaison finale explicite). `respect_robots=true` peut refuser une redirection qui ferait sortir de la cible pour laquelle les règles ont été attestées ; il ne devient pas une autorisation plus large.


## Vérification indépendante 0.2.2 — navigation et lecteur

La gestion des redirections et de l’attente des challenges a été corrigée séparément : [contrat 0.2.2](NAVIGATION_SCOPE.md). Aucun lien causal entre ces changements et WORLD_NOT_FOUND à context_selection n’est démontré. L’identification native des frames et la sélection de leur target CDP restent le correctif du défaut KUKA. `respect_robots` ne force plus implicitement le refus des redirections du document ; son helper conserve ses propres refus explicites.

Nouvelle recette réelle sur KUKA, service jetable, navigation avec `allow_redirects=true` et contrôle exact de la destination, puis extraction avec `expected_url` égal à l’URL originale : **69 blocs principaux, f1 extracted, partial=false, truncated=false**. Le player contient toujours zéro bloc textuel monté ; aucune interprétation visuelle ou applicative n’est revendiquée. Aucune résolution de challenge Cloudflare réel n’a été observée dans cette recette.

Trace `frame_read_success`, UTC `2026-10-12T20:25:38.877649+00:00` (22:25:38 Europe/Warsaw), durée 26.787 ms, étape context_verification, frame attachée :

```json
{
  "request_id": "14cdc846d3c4e3d87dbded52",
  "job_id": "e4328c80962996a46a0e875812b6c272",
  "tab_id": "3d9d2e348b1819f12677e8b8c2e2ce61",
  "artifact_id": "d360f3ee0ededa246a0a35aa0d3f99af",
  "frame_id": "f1",
  "reader_version": "0.2.2",
  "context_selection": {
    "session_type": "page",
    "candidate_count": 2,
    "expected_path": [
      0
    ],
    "observed_paths": [
      [
        0
      ]
    ],
    "paths_truncated": false,
    "failure": null,
    "path_source": "isolated_frame_owners",
    "selected_path": [
      0
    ]
  }
}
```

Preuves privées : `/private/tmp/pq-kuka-real-9506jh9f/{frames.log,summary.json,artifact.json}`. Ces IDs appartiennent au service jetable ; ils ne désignent pas des artefacts de l’API installée. Le test authentifié du service installé reste confié à UniversRobot, avec sa clé privée existante.
