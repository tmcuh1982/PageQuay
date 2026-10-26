# Acquisition d’une image originale — PageQuay 1.2.0

**Contrat 1.2.0 du 19 octobre 2026 : installé le 19 octobre, inclus dans la release 1.2.1 du 20 octobre.**
GIF et le plafond de 20 Mo exigent le nouveau contrat décrit ci-dessous.
Le service observé pendant l’audit déclarait encore 1.1.1.

Attente optionnelle : `POST download_image?wait_seconds=0..10` retourne HTTP 200 avec le document du job si celui-ci termine pendant ce délai ; sinon, HTTP 202 et le même ticket. Le défaut reste 0 (asynchrone). L’attente ne rejoue ni n’annule le job et les droits sont revérifiés avant la réponse.

[Français](DOWNLOAD_IMAGE.md) | [English](DOWNLOAD_IMAGE.en.md)

**Transport disponible à partir de PageQuay 1.1.1, du 16 octobre 2026.** Les garanties
sans Base64 interne décrites ci-dessous exigent ce correctif ; la release 1.1.0
antérieure utilisait encore le transport binaire CDP. Le client exige maintenant
le marqueur OpenAPI `x-pagequay-image-transport=chromium-byob-integers-v1` avant
le moindre POST d’acquisition ; la seule version 1.1.0 ne suffit pas.

Version minimale du nouveau transport : **1.1.1**, paquet, module et OpenAPI. Les versions 0.2.2 et
1.0.1 ne fournissent pas cette acquisition. `pq` reste le lanceur du service ;
la commande livrée est REST : `POST /v1/projects/{slug}/download_image`.
Le téléchargement d’un artifact préexistant et `screenshot` restent des opérations distinctes.

## Contrat

Authentification Bearer et projet actif ; permissions `content:read` et
`browser:interact` requises à l’admission et revérifiées pendant le job.
Le client lit sa clé depuis un fichier privé ; aucune clé dans une commande,
un ticket, une capture ou un log. Le téléchargement de l’artifact revérifie
l’authentification, le projet et `content:read`.

```json
{
  "url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "expected_url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "allow_redirects": true,
  "max_bytes": 5000000,
  "timeout": 120
}
```

`expected_url` est obligatoire. Comparaison exacte avec l’URL de la réponse
principale Chromium, avant toute lecture des octets image. Les redirections
HTTP et navigations techniques peuvent être suivies avec `allow_redirects=true` ;
elles ne transmettent aucune approbation métier. Un écart produit `scope_changed`
avec URL demandée, attendue, finale et cause. `allow_redirects=false` conserve le
refus préalable des redirections du navigateur. HTTPS/443 seulement, politique
projet/DNS/SSRF et proxy à IP validée inchangés, aucun client HTTP vers la source.

`max_bytes` reste un entier strict, compris entre 1 et **20 000 000 octets**,
avec un défaut inchangé à **5 000 000**. `allowed_media_types` est facultatif :
absent, seuls JPEG/PNG/WebP sont acceptés. Une liste explicite non vide et sans
doublons peut sélectionner `image/jpeg`, `image/png`, `image/webp`, `image/gif`.
`null`, une liste vide et les autres types sont refusés. Avant un POST utilisant
ces options, le client exige le marqueur OpenAPI
`x-pagequay-image-contract=original-gif-20mb-v1`, en plus du marqueur de transport.

`timeout` est un délai total explicite, défaut 120 s, maximum 180 s et
plafonné par `job_timeout_seconds`. Il couvre file d’attente, démarrage,
navigation, challenge automatique, attente humaine, acquisition et validation.
La terminaison du décodeur dispose d’au plus une seconde supplémentaire,
puis le nettoyage de l’onglet et des gardes d’au plus cinq secondes. Les limites de
jobs, onglets, navigateurs, connexions et stockage existantes restent applicables.

La réponse HTTP 202 donne `job_id`, `tab_id` réservé et l’URL de consultation.
Utiliser les opérations existantes :

- `GET /v1/projects/{slug}/jobs/{job_id}` : état et résultat/erreur ;
- `POST /v1/projects/{slug}/jobs/{job_id}/cancel` : abandon explicite ; attendre
  ensuite l’état terminal et `error.details.cleanup_verified` ;
- `POST /v1/projects/{slug}/jobs/{job_id}/resume` : reprise explicite après
  intervention humaine dans l’onglet indiqué, réservée à la clé d’origine.

Les vérifications automatiques Cloudflare peuvent se terminer pendant le budget
navigation configuré, sous réserve du délai total demandé. Un CAPTCHA explicite
ou une vérification non terminée passe à `waiting_for_human`, avec onglet et
diagnostic de navigation, sans capture d’écran pour cette opération.
Aucun solveur ni clic CAPTCHA. L’expiration en attente humaine produit
`HUMAN_REQUIRED_TIMEOUT`. La navigation humaine vers une image n’autorise pas
sa lecture avant la reprise explicite du job.
L’onglet créé par cette commande est fermé à la fin du job.

## Acquisition et intégrité

L’intercepteur de réponses conserve les contrôles du frame principal et laisse
les vérifications HTML autorisées se terminer. Une première réponse image est
contrôlée aux en-têtes puis interrompue sans lire son corps. Dans le même onglet,
une interception **au stade requête** fournit ensuite un document vide à l’URL
exacte attendue, sans requête amont ni corps encodé. Sa CSP interdit les ressources
et limite les connexions à sa propre origine. Aucun droit supplémentaire n’est
accordé au monde JavaScript isolé.

Un second GET est effectué **par Chromium** à cette URL, via les routes et le proxy
existants. Sa réponse est contrôlée de nouveau avant lecture : destination exacte,
statut, MIME, encodage et longueur. Ce second GET peut différer de la réponse
initiale ; l’artefact représente les octets complets de cette seconde réponse,
pas un instantané garanti de la première. Une nouvelle page de challenge à cette
étape est refusée comme HTML ; aucun repli ne la transforme en image.

Un lecteur BYOB fournit des blocs d’au plus 64 Kio, avec un octet sentinelle au-delà
du budget. Ils traversent le protocole comme tableaux d’entiers bornés, puis sont
reconstitués en octets ; aucun Base64, même interne à l’acquisition, Blob, Data URL,
capture ou client HTTP vers la source. `accept_downloads=False` et l’annulation des
téléchargements ordinaires du navigateur restent actifs.

HTTP 200 complet requis ; réponses partielles, HTML, format non autorisé,
MIME/signature incompatibles, troncature et longueur incohérente sont refusés.
Les représentations avec `Content-Encoding` autre qu’identity sont refusées
explicitement, pour éviter une ambiguïté de longueur. JPEG/PNG/WebP restent statiques, avec leur plafond historique de 25 millions
de pixels. GIF87a/GIF89a est accepté sur demande explicite : le parcours
structurel contrôle toutes les tables, extensions, descripteurs et sous-blocs
jusqu’à la terminaison, sans accepter de données après celle-ci. Pillow décode
uniquement la première image ; aucun `n_frames`, parcours ou coalesçage de
l’animation. Écran logique et tous les descripteurs : au plus 8 192 par axe et
16 000 000 pixels, images contenues dans l’écran, au plus 1 000 images. Les pixels
compressés des images suivantes ne sont pas décodés et leur décodabilité n’est
pas garantie. Le validateur enfant conserve cinq secondes CPU et dispose de
dix secondes murales, incluses dans le budget total. Aucun aperçu n’est produit. L’annulation tue cet enfant
et vérifie sa sortie dans une seconde au maximum. Sous macOS, les bornes mémoire
reposent sur les octets, les blocs et les pixels ; aucun plafond OS de mémoire
résidente du navigateur ou du décodeur n’est revendiqué. Les limites RLIMIT_AS/DATA
essayées sur cet hôte sont refusées ; aucun réglage système n’a été modifié.
La lecture atteint EOF ; les terminaisons JPEG/PNG et longueur RIFF WebP sont
également contrôlées. Aucun fichier image partiel n’est publié.

Les blocs BYOB bornent la lecture remise à PageQuay, pas les tampons internes de
Chromium ni les octets qui ont déjà transité sur le réseau. Une longueur HTTP
trop courte peut masquer une suite au-delà du cadrage HTTP ; une image tronquée
visible est refusée, sans revendication sur ces octets invisibles. Le navigateur
effectue toujours une première navigation contrôlée aux en-têtes, puis un second
GET pour les octets originaux. Aucune identité des deux réponses n’est garantie.

### Projet tiers : Pillow

La validation d’image s’appuie sur [Pillow](https://github.com/python-pillow/Pillow),
bibliothèque d’imagerie Python développée par le projet Pillow et ses contributeurs.
Consulter sa [documentation officielle](https://pillow.readthedocs.io/).
Pillow est une dépendance tierce exécutée localement : PageQuay l’utilise pour
vérifier la structure, les dimensions et la décodabilité des images, sans
réencoder les octets qui composent l’artefact.

**Cette validation n’est pas une analyse antivirus.** Le rejet de fichiers
malformés et les limites d’octets ou de pixels réduisent certains risques ;
ils ne prouvent pas l’absence de contenu malveillant. Une image valide peut
encore exploiter une vulnérabilité d’un décodeur ou du logiciel qui l’affiche.
Le processus jetable et les limites ne constituent pas une garantie d’innocuité.

### Artefact et intégrité

Le résultat contient `artifact_id`, `url` de téléchargement, `media_type`
vérifié, `size`, `sha256`, `expires_at`, `requested_url`, `final_url`,
`redirect_chain`, `http_status`, `request_id`, `job_id`, `tab_id`, `frame_id`,
`network_request_id` et `original_bytes=true`. `GET` de l’URL d’artifact retourne
les octets binaires originaux en pièce jointe, sans Base64. L’artifact est privé,
isolé par projet, fichier 0600, soumis au quota et à la durée minimale entre
TTL contenu et rétention d’artifacts. Le mécanisme de rétention existant le
supprime à échéance ; il n’est déjà plus accessible après expiration.
Pour un original identifié par son reçu de job, le GET privé impose une taille
enregistrée ≤20 Mo et la concordance avec le fichier ouvert. Lecture par blocs
≤64 Kio et sentinelle ; aucune lecture jusqu’à EOF non bornée ni `pathsend`.
`Range` est ignoré : réponse complète 200, `Accept-Ranges: none`, budget serveur
30 s et fermeture du fichier sur erreur/annulation. Les autres artefacts gardent
leur chemin historique. Une erreur avant en-têtes peut rendre un JSON typé ;
après en-têtes, le flux est interrompu : le client doit conserver le reçu et
refuser toute taille/empreinte incorrecte, aucun JSON ne peut remplacer le corps
binaire déjà commencé.

Si le job échoue après création mais avant validation terminale, son artifact
non validé est supprimé. Une annulation ferme aussi le flux et l’onglet.

## Erreurs et reproduction

Les erreurs du job donnent code, `details.stage`, cause connue ou `unknown`,
`retryable`, corrélation disponible, version, date ISO avec fuseau, commande
REST et corps exacts, attendu/observé et absence d’artifact partiel.
Leurs étapes distinguent admission, file, démarrage, navigation,
vérification humaine, périmètre final, acquisition, création d’artifact et nettoyage.
Les refus du GET d’artifact indiquent `artifact_download` ; une URL source
indisponible ou non autorisée est déclarée inconnue. Conserver alors le résultat
original du job pour la reproduction de la source. Les erreurs de validation
JSON/authentification ne donnent pas accès aux données d’un autre projet.

Codes spécifiques : `scope_changed`, `IMAGE_HTTP_STATUS`,
`IMAGE_FORMAT_FORBIDDEN`, `IMAGE_ENCODING_UNSUPPORTED`, `IMAGE_TOO_LARGE`,
`IMAGE_INCOMPLETE`, `IMAGE_INVALID`, `IMAGE_HTML_RESPONSE`, `IMAGE_TIMEOUT`,
`HUMAN_REQUIRED_TIMEOUT`, `IMAGE_CANCELLED`, `IMAGE_CLEANUP_FAILED`.
Les codes existants de démarrage/navigation/politique réseau sont conservés.
`IMAGE_ACQUISITION_FAILED` signale une cause encore inconnue ; aucune attribution
inventée au réseau ou au site distant. Un défaut de nettoyage reste explicite, avec `cleanup_verified=false`, l’identifiant
de la ressource et l’erreur précédente si disponible. Une suppression physique
échouée ne doit pas laisser l’artefact non validé téléchargeable. Un corps JSON
invalide n’est pas recopié : conserver la requête du client pour sa reproduction.
Ne pas relancer automatiquement une demande POST dont la réponse a été perdue :
la commande n’offre pas encore d’idempotence. Utiliser les identifiants conservés.

Un rapport partagé doit utiliser une URL publique exacte sans secret, fournir
version, méthode/chemin/corps réels, attendu, observé, date avec fuseau et
identifiants disponibles. Ne jamais y copier les en-têtes Authorization, cookies
ou URL signée contenant une clé. Les échecs historiques du lecteur HTTPS direct
ne sont pas des échecs PageQuay et ne disposent pas de jobs PageQuay rétroactifs.

## Recette UBTECH avec le service installé

Prérequis : PageQuay >=1.1.1 installé et service redémarré avec ses dépendances,
projet/service autorisés, session graphique si navigateur headed, Bearer existant
dans un fichier privé 0600 contenant uniquement le token. Le client d’exemple
nécessite httpx et Pillow. Depuis ce dépôt, adapter uniquement service, projet
et chemin du fichier privé :

```sh
.venv/bin/python examples/download_image.py \
  'https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg' \
  --expected-url 'https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg' \
  --service 'http://127.0.0.1:8766' --project universrobot \
  --bearer-file /chemin/prive/pagequay-token --timeout 120 \
  --allow-redirects --output /chemin/prive/walker-s1-original.jpg
```

Cette commande appelle uniquement le service PageQuay. Elle affiche les
identifiants du job, attend, télécharge l’artifact en streaming dans un fichier
temporaire privé, exige HTTP 200 complet, vérifie le chemin du projet,
la taille/empreinte/signature puis renomme le fichier.
`--max-bytes 20000000 --allowed-media-types image/gif` active explicitement
le nouveau contrat, sans téléchargement réel implicite.
Un échec ne laisse pas de sortie partielle. Une attente humaine est explicite
(code de sortie 2). Relancer le client avec les mêmes arguments et `--job-id ID`
consulte le job existant ; ajouter `--resume` demande explicitement sa reprise.
Ces modes ne soumettent aucun nouveau POST d’acquisition. Sans identifiant après
une réponse perdue, la réception reste incertaine : aucun rejeu automatique.
Le transfert d’artefact vérifie une échéance de 30 secondes entre les blocs,
avec au plus le délai de lecture HTTP de 15 secondes avant de constater un arrêt.
Le résultat attendu est l’original complet ou une erreur typée reproductible.

## Portée UniversRobot

Aucun fichier UniversRobot n’est modifié. Le raccordement consommateur reste
séparé : aucun repli HTTP direct. UniversRobot devra produire localement le PNG
fixe de la première image GIF, ≤320×240 et ≤400 000 octets. PageQuay livre
uniquement l’original privé. Originaux durables, galerie, publication, pauses et
horaires restent hors périmètre. Les deux URL Dobot ne sont pas téléchargées
par cette implémentation ; leur recette exige un accord séparé.

Les résultats des tests simulés et de la recette réseau jetable sont séparés
dans [le rapport](testing/DOWNLOAD_IMAGE_REPORT.md). Ils ne prouvent pas le
déploiement ou la recette authentifiée du service installé d’UniversRobot.
