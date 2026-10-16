# Acquisition d’une image originale — PageQuay 1.1.0

Version minimale : **1.1.0**, paquet, module et OpenAPI. Les versions 0.2.2 et
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

`max_bytes` est compris entre 1 et **5 000 000 octets** (5 Mo décimaux), défaut
5 Mo. `timeout` est un délai total explicite, défaut 120 s, maximum 180 s et
plafonné par `job_timeout_seconds`. Il couvre file d’attente, démarrage,
navigation, challenge automatique, attente humaine, acquisition et validation.
Le nettoyage terminal dispose d’au plus 5 s supplémentaires. Les limites de
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
diagnostic de navigation, éventuellement capture diagnostique privée séparée.
Aucun solveur ni clic CAPTCHA. L’expiration en attente humaine produit
`HUMAN_REQUIRED_TIMEOUT`. Une capture de diagnostic n’est jamais l’original acquis.
L’onglet créé par cette commande est fermé à la fin du job.

## Acquisition et intégrité

L’intercepteur de réponses déjà utilisé par PageQuay pour les redirections est
étendu sur l’onglet de cette opération. Il traite uniquement la réponse du frame
principal. `Fetch.takeResponseBodyAsStream` et `IO.read` lisent des blocs de
64 Kio au maximum et un seul octet sentinelle au-delà du budget ; dépassement
interrompu immédiatement, même sans `Content-Length`. `accept_downloads=False`
et l’annulation des téléchargements ordinaires du navigateur sont conservés.
Le protocole CDP encode parfois ses blocs binaires en Base64 en interne : ces
blocs sont décodés dans le serveur, jamais exposés par la commande, les logs ou
le téléchargement d’artifact. Aucun fichier Base64 ni image JSON n’est livré.

HTTP 200 complet requis ; réponses partielles, HTML, format non autorisé,
MIME/signature incompatibles, troncature et longueur incohérente sont refusés.
Les représentations avec `Content-Encoding` autre qu’identity sont refusées
explicitement, pour éviter une ambiguïté de longueur. Formats : JPEG, PNG et
WebP statiques. Pillow vérifie la structure et décode pour valider, sans
réencoder ; plafond de validation 25 millions de pixels, animation refusée.
La lecture atteint EOF ; les terminaisons JPEG/PNG et longueur RIFF WebP sont
également contrôlées. Aucun fichier image partiel n’est publié.

Le résultat contient `artifact_id`, `url` de téléchargement, `media_type`
vérifié, `size`, `sha256`, `expires_at`, `requested_url`, `final_url`,
`redirect_chain`, `http_status`, `request_id`, `job_id`, `tab_id`, `frame_id`,
`network_request_id` et `original_bytes=true`. `GET` de l’URL d’artifact retourne
les octets binaires originaux en pièce jointe, sans Base64. L’artifact est privé,
isolé par projet, fichier 0600, soumis au quota et à la durée minimale entre
TTL contenu et rétention d’artifacts. Le mécanisme de rétention existant le
supprime à échéance ; il n’est déjà plus accessible après expiration.
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
inventée au réseau ou au site distant. Un défaut de nettoyage reste explicite.
Ne pas relancer automatiquement une demande POST dont la réponse a été perdue :
la commande n’offre pas encore d’idempotence. Utiliser les identifiants conservés.

Un rapport partagé doit utiliser une URL publique exacte sans secret, fournir
version, méthode/chemin/corps réels, attendu, observé, date avec fuseau et
identifiants disponibles. Ne jamais y copier les en-têtes Authorization, cookies
ou URL signée contenant une clé. Les échecs historiques du lecteur HTTPS direct
ne sont pas des échecs PageQuay et ne disposent pas de jobs PageQuay rétroactifs.

## Recette UBTECH avec le service installé

Prérequis : PageQuay >=1.1.0 installé et service redémarré avec ses dépendances,
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
temporaire privé, vérifie taille/empreinte/signature puis renomme le fichier.
Un échec ne laisse pas de sortie partielle. Une attente humaine est explicite
(code de sortie 2) ; la consultation/reprise/annulation reste disponible via API.
Le résultat attendu est l’original complet ou une erreur typée reproductible.

## Portée UniversRobot

Aucun fichier UniversRobot n’est modifié dans ce lot, conformément à la précision
de l’utilisateur. L’aperçu de la fiche Walker S1 n’a donc pas été testé ici.
Le futur raccordement doit appeler uniquement cette commande PageQuay, conserver
asynchronisme/cache privé et revérifier les autorisations à chaque étape ; aucun
repli HTTPS direct. ImageMagick local produit l’aperçu. Les règles de publication
existantes restent : original conservé, WebP qualité 80, grand côté <=1200 px,
miniature <=400 px sans agrandissement, signalement sous 600 px. Un aperçu
n’accorde ni approbation ni publication. Aucune pause ni aucun horaire modifié.

Les résultats des tests simulés et de la recette réseau jetable sont séparés
dans [le rapport](testing/DOWNLOAD_IMAGE_REPORT.md). Ils ne prouvent pas le
déploiement ou la recette authentifiée du service installé d’UniversRobot.
