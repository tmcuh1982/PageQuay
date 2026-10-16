# Validation download_image — 15 octobre 2026

Version de travail PageQuay 1.1.0. Ajout REST, pas de sous-commande du lanceur
`pq`. Le service installé et UniversRobot n’ont pas été modifiés.

## Vérifications locales

- Suite générale finale : **287 passed, 95 skipped**, une dépréciation existante
  Starlette/httpx. Commande : `.venv/bin/pytest -q --tb=short`.
- Suite Chromium ciblée navigation/challenges et client : **63 passed**,
  `.venv/bin/pytest tests/test_download_image.py tests/test_download_image_client.py tests/test_acquisition_browser.py tests/test_challenges.py --browser -q --tb=short`.
  Le blocage natif WebSocket a aussi été validé dans l’exécution précédente
  de 64 tests avec `tests/test_native_websocket_blocking.py`.
- Contrat/jobs/acquisition : **42 passed**,
  `.venv/bin/pytest tests/test_download_image.py tests/test_download_image_client.py tests/test_jobs.py tests/test_openapi.py --browser -q --tb=short`.
- Acquisition Chromium sur l’état final : **27 passed**,
  `.venv/bin/pytest tests/test_download_image.py --browser -q --tb=short`.
  Inclut la navigation concurrente pendant la lecture, refusée sans publication
  d’un ancien corps image ; le code d’erreur dépend de l’ordre des notifications
  Chromium (navigation changée ou corps interrompu invalide).
- Ruff sur tous les fichiers Python modifiés/ajoutés : conforme ;
  `git diff --check` conforme ; `uv sync --locked --extra dev --offline` conforme.
  Paquet/module 1.1.0, OpenAPI public testé contre le fichier versionné.

Les tests d’acquisition utilisent de vrais Chromium et serveur HTTP local simulé.
HTTP local est permis uniquement dans leurs dépendances injectées ; la commande
livrée demeure HTTPS/443. Cas couverts : octets/empreinte identiques, JPEG/PNG/WebP
validés sans réencodage, redirection attendue, refus de destination différente,
refus de redirection quand interdit, refus IP privée, challenge automatique
résolu et attente humaine explicite, délai humain total, HTML et faux MIME,
troncature, absence de Content-Length, taille bornée pendant lecture, statut
HTTP invalide, délai en file et pendant acquisition, annulation en attente humaine
et pendant le flux, révocation, expiration/purge, droits interprojets, fichier
client 0600, client tronqué/trop grand/empreinte différente/interdit, absence de
sortie partielle, suppression d’artifact non validé et échec d’écriture disque.

Les premières exécutions dans le bac à sable ont échoué avant les acquisitions
car les sockets locales étaient interdites. Les commandes ont été relancées
avec cette capacité autorisée ; les résultats ci-dessus correspondent à ces
exécutions réussies. Ces refus ne sont pas attribués à PageQuay ou à UBTECH.

## Recette réseau réelle, distincte des fixtures

Exécutée le **15 octobre 2026 à 23:32:53 Europe/Warsaw (+02:00)**,
soit `2026-10-15T21:32:53.412660+00:00`. Service PageQuay jetable utilisant les sources 1.1.0,
profil Chromium neuf, mode headless, politique réseau de production normale,
projet jetable `image-recipe`, Bearer éphémère jamais affiché. Aucun accès à
la clé UniversRobot installée. Une première exécution à 23:28 a également réussi
avec la même taille et la même empreinte.

Commande shell réelle : `.venv/bin/python /private/tmp/pq-live-image.py`.
Ce script de recette temporaire a appelé, via l’API HTTP/ASGI et sa vérification
Bearer, la commande réelle suivante, puis consulté le job et téléchargé
l’artifact via GET authentifié. La commande publique reproductible équivalente
pour un service installé se trouve dans [DOWNLOAD_IMAGE](../DOWNLOAD_IMAGE.md).

`POST /v1/projects/image-recipe/download_image` :

```json
{
  "url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "expected_url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "allow_redirects": true,
  "max_bytes": 5000000,
  "timeout": 120
}
```

Attendu : JPEG original complet, URL finale exacte, artifact privé binaire,
validation de signature/complétude, taille et SHA-256 identiques entre les
octets acquis et le téléchargement de l’artifact, fermeture et purge vérifiées.

Observé : **job completed**, HTTP 200 ; MIME `image/jpeg` vérifié ;
**689381 octets** ; URL demandée et finale identiques ; aucune redirection ;
validation JPEG réussie. Le GET authentifié a renvoyé la même taille et la même
empreinte SHA-256 :

```text
f83f4625a8ee91ae51532e26ac5ee9044d0c972834a44815b7022fa32b4af38c
```

Corrélation :

| Identifiant | Valeur |
| --- | --- |
| request | `f3cb9a327a2f6ce65bc0bc00` |
| job | `bee737a7219bc4dc589850a505b2a664` |
| tab | `c3b8ad4f8d7e23cf56e2fd51c89b4d81` |
| frame Chromium | `2D0558F7FC37BBA44B2235909BBA32D9` |
| request réseau Chromium | `7CF7C8A1CF557B43C4979838730FA990` |
| artifact | `15b050bcef75f99af24c19cde891b160` |

L’onglet possédé a été fermé ; la purge des artifacts a été vérifiée et le
répertoire de service jetable supprimé. Ces identifiants sont des traces de
recette, plus des ressources téléchargeables. Aucun challenge Cloudflare réel
n’a été observé lors de ces acquisitions : son traitement est testé par fixtures,
aucune réussite CAPTCHA réelle revendiquée.

## Limites et étape installée

Cette recette ne démontre pas la disponibilité de `download_image` dans le
service installé, ni une acquisition avec la session/projet/Bearer UniversRobot,
ni l’ouverture de l’aperçu Walker S1. Ces étapes exigent un déploiement >=1.1.0
et l’exécution de la recette avec la clé privée existante sur sa machine.
Le présent lot ne déploie pas et ne redémarre pas le service installé.

Avant implémentation, l’API inspectée 0.2.2 n’exposait pas `download_image` et
aucun job PageQuay de cette recette n’existait. Les anciens timeouts du lecteur
HTTPS direct restent distincts ; ils ne sont pas attribués à PageQuay.
Aucun accord, publication, changement de pause ou d’horaire n’a été effectué.
