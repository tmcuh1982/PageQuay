# Validation download_image — 15 octobre 2026

[Français](DOWNLOAD_IMAGE_REPORT.md) | [English](DOWNLOAD_IMAGE_REPORT.en.md)

Version de travail PageQuay 1.1.0. Ajout REST, pas de sous-commande du lanceur
`pq`. Le service installé et UniversRobot n’ont pas été modifiés.

## Correctif local — 16 octobre 2026

**Non livré et non installé.** La recette externe autorisée ensuite le 16 octobre
est décrite dans la section dédiée ci-dessous.
Base auditée : PageQuay 1.1.0, commit `c6c2ee5`, puis modifications locales non
commitées. Python 3.14.7, Playwright 1.63.0, Pillow 12.3.0. L’ancienne recette
réseau du 15 octobre, conservée plus bas, ne valide pas ce nouveau transport.

### Résultat et périmètre

- Aucun corps binaire CDP n’est lu : fin du chemin `Fetch.takeResponseBodyAsStream`
  / `IO.read` et de son Base64 interne. L’image initiale est contrôlée aux en-têtes
  puis interrompue ; un document vide contrôlé, sans corps encodé ni requête amont,
  permet un GET de lecture dans Chromium. URL exacte, réseau, statut, MIME,
  encodage et longueur sont revérifiés. Blocs BYOB de 64 Kio et sentinelle, EOF,
  SHA-256 et octets originaux de cette seconde réponse. Ce GET supplémentaire
  peut échouer si la ressource change ou si un nouveau challenge HTML apparaît.
- Aucun assouplissement du proxy, des permissions ou des téléchargements natifs.
  Aucun accès universel accordé au monde isolé. Aucun client HTTP vers la source.
- Aucune capture pour l’opération image. Le même job/onglet attend la reprise
  explicite, y compris si l’humain a déjà navigué vers l’image attendue.
- Décodeur jetable, arrêt confirmé après annulation, 5 Mo et 25 millions de pixels,
  cinq secondes CPU. Les plafonds de mémoire OS essayés sont refusés sous macOS :
  aucune limite RSS du navigateur ou du décodeur n’est revendiquée ; les bornes
  d’octets/blocs/pixels restent actives. Aucun réglage système n’a été changé.
- Nettoyage de l’onglet et des gardes sous délai ; erreurs de suppression
  d’artefact explicites, avec ressource concernée, erreur précédente et
  `cleanup_verified=false`. L’artefact non validé est retiré du catalogue avant
  sa suppression physique. Une défaillance de base reste signalée comme non
  confirmée. Un démarrage sans retour de propriété d’onglet ne revendique pas
  une confirmation de nettoyage.
- Diagnostics de validation JSON, de limite de payload, de contrôle des jobs et
  du client enrichis ; identifiant de requête corrélable dans les logs API,
  jobs et opérations navigateur. Les valeurs et noms de champs inconnus ne sont
  pas recopiés. Le client conserve méthode/chemin/corps de sa demande ; en cas
  de rejet JSON, le serveur demande de conserver ce corps pour reproduction.
- Client : suivi `--job-id`, reprise explicite `--resume`, refus d’un service ne
  déclarant pas le nouveau transport, aucun rejeu d’un POST incertain, échéance
  de transfert d’artefact et suppression de sortie partielle.

### Preuves de tests isolés

Les suites utilisent des serveurs loopback, profils, clés et bases temporaires.
L’homonyme UniversRobot présent dans certaines fixtures n’est pas le projet réel.
Aucun service installé, dépendance, clé réelle, profil réel, droit, configuration,
base réelle, pause ou horaire n’a été modifié. Aucun commit, push ou installation.

| Exécution | Début Europe/Warsaw | Résultat |
| --- | --- | --- |
| Transport Chromium, images, client, jobs, contrat, challenges, acquisition | 2026-10-16T15:16:56.468226+02:00 | 98 réussis, zéro échec ; 81,90 s |
| Suite générale finale, incluant marqueur de transport et masquage des champs | 2026-10-16T15:21:17.089081+02:00 | 307 réussis, 104 ignorés, zéro échec ; 12,20 s |

Ces suites se recouvrent, leurs comptes ne s’additionnent pas. Dépréciation
Starlette/httpx existante. Contrat public et `docs/openapi.json` identiques.
Ruff check/format et `git diff --check` : conformes.

Commandes exactes :

```sh
.venv/bin/pytest tests/test_download_image.py tests/test_download_image_client.py tests/test_jobs.py tests/test_openapi.py tests/test_challenges.py tests/test_acquisition_browser.py --browser -q --tb=short -p no:cacheprovider --junitxml=/private/tmp/pagequay-image-isolated.xml
.venv/bin/pytest -q --tb=short -p no:cacheprovider --junitxml=/private/tmp/pagequay-regression-isolated.xml
```

Les JUnit privés ci-dessus identifient chaque cas et son horodatage de suite.
Les tests interdisent explicitement les commandes CDP de lecture binaire et de
capture, le corps encodé de la réponse vide et l’accès universel. JPEG/PNG/WebP
sont acquis dans Chromium et comparés octet pour octet. Sont aussi couverts :
redirection privée ou destination modifiée au second GET, HTML, troncature,
taille dépassée sans Content-Length, reprise explicite du même job, annulation,
révocation, disparition du décodeur, refus de suppression et POST à réponse perdue.

Les ressources navigateur et sockets sont fermées par les fixtures ; les refus
physiques de suppression sont simulés. Les fichiers JUnit et répertoires de
fixtures restent locaux, sous rétention pytest pour ces derniers ; leur purge
physique globale n’a pas été effectuée ni présentée comme confirmée.

### Incidents intermédiaires et reproduction

Tous concernent les sources 1.1.0 en travail avec les versions ci-dessus, sans
recette réelle. Les heures exactes des premières tentatives n’ont pas été
instrumentées : elles restent **inconnues**, plutôt que reconstruites. Ces incidents
sont survenus entre le début d’audit à 14:53 et 15:22 le 16 octobre 2026 (+02:00) ;
aucune heure plus précise n’est attestée pour chacun.
Les identifiants ci-dessous désignent les sorties d’outils de ce chat, pas des
identifiants de jobs PageQuay inventés.

| Reproduction précise | Attendu / observé | Code, étape et cause | Identifiants disponibles |
| --- | --- | --- | --- |
| `.venv/bin/python -m pagequay.image_validator image/png </dev/null`, version intermédiaire appliquant RLIMIT_AS ou RLIMIT_DATA à 512 Mio | Mise en place des limites / `ValueError: current limit exceeds maximum limit` avant décodage, puis trois tests d’images valides refusés | `IMAGE_INVALID`, initialisation du décodeur ; limite OS refusée, également hors sandbox | Sessions outils `19346`, `17772`, sorties `0051d5`, `ccf843` ; aucun job HTTP |
| `.venv/bin/pytest tests/test_download_image.py --browser -q --tb=short -p no:cacheprovider`, ancien scénario `/race` | Navigation pendant lecture / job terminé car le document remplacé a supprimé l’ancien script de navigation | Assertion de test, concurrence ; scénario devenu inopérant après changement de transport, remplacé par une navigation explicite pendant le flux | Session `17011`, sortie `53c7fd`, job `736eb67b14772f2e9905fa3ce620c2aa` ; request ID non conservé |
| Première commande ciblée ci-dessus en sandbox, avant autorisation des sockets | Fixtures loopback disponibles / bind refusé avant lancement des acquisitions, 56 erreurs de setup | `PermissionError`, errno 1, création des fixtures ; restriction de sockets du sandbox | Session `27607`, sortie `9cc8dd` ; aucun job PageQuay créé |
| Commandes Ruff sur les fichiers modifiés | Conformité / import, longueurs et formatage signalés puis corrigés | `I001`, `E501`, `UP031`, analyse statique ; mises en forme locales | Sorties `deea33`, `686bf4` ; aucun job HTTP |
| `.venv/bin/pytest tests/test_download_image.py -k 'admission or dimension' -q --tb=short -p no:cacheprovider`, fixture initiale de 100 Mpx | Refus par plafond 25 Mpx / refus plus précoce par Pillow | `IMAGE_INVALID`, validation ; mauvais choix de fixture pour distinguer les deux garde-fous. Fixture ramenée à 30 Mpx | Sortie `395d3d` ; aucun job HTTP |
| `.venv/bin/pytest tests/test_download_image_client.py tests/test_openapi.py -q --tb=short -p no:cacheprovider` pendant mise à jour du contrat | Schéma identique / ponctuation différente dans la description versionnée | Assertion OpenAPI, documentation ; correction par export du schéma généré, 15 tests ensuite réussis | Sortie `6c03ac`, puis `5a769f` ; aucun job d’image |

### Fichiers concernés

Runtime : `src/pagequay/image_download.py`, nouveaux `image_stream.py` et
`image_validator.py`, `browser.py`, `jobs.py`, `artifacts.py`, `api.py`, `main.py`,
`audit.py`, `usage.py`. Client : `examples/download_image.py`.
Tests : `tests/test_download_image.py`, `test_download_image_client.py`,
`test_openapi.py`. Contrat et documentation : `docs/openapi.json`, les deux
`DOWNLOAD_IMAGE` et les deux rapports présents.

La recette réelle du nouveau transport a ensuite été autorisée et exécutée
ci-dessous. La livraison Git et l’installation attendent leurs accords distincts. UniversRobot n’a pas été raccordé ou modifié.

---

## Recette réelle autorisée — 16 octobre 2026, nouveau transport

Recette demandée explicitement avec le corps JSON indiqué par l’utilisateur.
Commande : `.venv/bin/python /private/tmp/pq-image-recipe-20261016.py`.
Script final conservé dans `/private/tmp/pq-image-live-g7_r1new/recipe.py` (0600).
Sources locales 1.1.0 sur base `c6c2ee5`, Python 3.14.7, Playwright 1.63.0,
Pillow 12.3.0, httpx 0.28.1 ; empreintes des modules dans le rapport JSON privé.

Service ASGI PageQuay jetable, API Bearer réellement vérifiée, Chromium visible
avec profil neuf et réseau de production par défaut, sans exception locale ni
assouplissement de la politique source. L’API PageQuay est appelée en processus
par httpx ; le serveur CDN est contacté uniquement par Chromium. Cela ne valide
pas un listener HTTP installé, Tailscale ou l’intégration UniversRobot.

```json
{
  "url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "expected_url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "allow_redirects": true,
  "max_bytes": 5000000,
  "timeout": 120
}
```

### Résultat réussi

Début `2026-10-16T15:28:36.340274+02:00`, fin
`2026-10-16T15:28:54.580113+02:00`, Europe/Warsaw. Un seul POST d’acquisition
pour ce job. Attendu : image complète originale, URL finale exacte, artefact
privé authentifié, taille/empreinte identiques après GET et nettoyage confirmé.

Observé : **completed**, HTTP source **200**, JPEG **1080 × 1530**,
**689381 octets**, aucune redirection et URL finale exactement égale à celle
attendue. GET authentifié **200**, octets/empreinte concordants, fichier 0600 :

```text
f83f4625a8ee91ae51532e26ac5ee9044d0c972834a44815b7022fa32b4af38c
```

GET anonyme **401**, GET avec la clé d’un autre projet jetable **403** : refus
attendus, pas d’échec de la recette. Le rapport et l’audit privés conservent leurs
identifiants de requête. Les commandes CDP de corps binaire, de capture et de
réponse synthétique encodée étaient interdites par le script. Aucun challenge
Cloudflare réel n’a été observé ; aucune réussite de CAPTCHA n’est revendiquée.

| Corrélation | Identifiant |
| --- | --- |
| request d’acquisition | `4bc0f52413c2728e98de34c0` |
| job | `df9aba01132ba4b65cfe3d6571a39409` |
| tab | `56b9f7b0f861d992addcbf34f662d702` |
| frame Chromium | `511FC28CF0A1283772F5859AF1F57051` |
| request réseau Chromium | `2ABD8FEDA829316FF2ECA4DF391239CB` |
| artefact | `c8e671ef2e756e07ad1530baaa6b5473` |

Preuves privées conservées dans `/private/tmp/pq-image-live-g7_r1new/` :
`report.json`, `audit.json`, `original.jpg` et `recipe.py`, fichiers 0600,
répertoire 0700. Les IDs des lignes de logs sont dans `report.json`.

Onglet fermé, artefact retiré du catalogue et fichier supprimé du service,
zéro job et navigateur actifs, base fermée et répertoire du service jetable
supprimé : tous confirmés. L’image téléchargée et les preuves ci-dessus sont
les sorties privées conservées ; l’ancienne URL d’artefact du service supprimé
n’est plus téléchargeable. Aucune livraison à UniversRobot ni installation.

### Premier essai interrompu : quota du script de recette

Même commande et même corps source, script initial consultant le job toutes les
**0,25 seconde**. Début `2026-10-16T15:27:37.704225+02:00`, erreur
`2026-10-16T15:27:52.978673+02:00`. Attendu : consultation jusqu’à l’état terminal.
Observé : **HTTP 429** sur
`GET /v1/projects/image-recipe/jobs/f4fda08c6e3fb31bd507f1fc594ac753`.
Code du rapport : `RECIPE_FAILED`, étape `job_poll`, cause connue : fréquence du
script dépassant le quota REST par défaut de 60 appels/minute. Ce refus PageQuay
ne provient pas du CDN ou de Cloudflare.

Request d’acquisition `53c244fab7cf79108a176955`, job
`f4fda08c6e3fb31bd507f1fc594ac753`, tab `dc6856bf133f1a9e884c9a0884a61bf9`.
Requête de consultation refusée : `54842d0b4c314bb01e967e48`, ligne d’audit
`6e4ebee491118699525d646b49c26632`. L’audit confirme ensuite `job.cancelled`
(ligne `c953cfd6fb7b5819b46f3ba4250304d2`), fermeture du service et suppression
de son répertoire. Preuves privées : `/private/tmp/pq-image-live-ffdvdjvk/`.

Le script a été corrigé pour consulter toutes les **deux secondes** et attendre
sur un éventuel 429 de GET, puis une recette distincte a été lancée après
annulation confirmée du premier job. Aucun POST à réception incertaine n’a été
rejoué. Aucun fichier runtime du dépôt n’a été modifié pour ce test réel.

---

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

Ces suites historiques se recouvrent et sont distinctes des vérifications du 16 octobre : **292 réussis/96 ignorés** dans la suite générale et **72 réussis** avec Chromium ciblé, voir [les notes de release](../releases/1.1.0.md).

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
