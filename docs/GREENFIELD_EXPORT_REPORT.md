# Export Greenfield corrigé dans PageQuay — TODO-304

[VERIFIED — 23/10/2026, Europe/Warsaw] CHG-20261023-996.
Demande : corriger le producteur PageQuay, au-delà du repli HTTPS réussi sous994.
URL exactement autorisée dans le chat et toujours approuvée :
https://www.greenfieldincorporated.com/ ; source204753fc-87f2-4fe6-be42-bcd1ea5c169a.
L’adresse initiale https://www.greenfieldrobotics.com/ reste conservée dans son
dossier d’origine9682dfe7-b8ae-508b-8dfc-98c6ce8ee38b ; aucune permission transférée
à une autre URL. Compétence diagnose, puis qualification métier stricte existante.

## Causes et corrections

1. extraction.js appliquait profondeur32 avec seulement3conteneurs neutres de
   crédit et borne physique35. Le HTML rendu réel présente du texte visible à
   profondeur36 et plus. Rejeu isolé sans réseau :7coupures à36, raison depth ;
   crédit4 encore insuffisant, crédit8 complet. Le producteur autorise maintenant
   au plus8enveloppes neutres par chemin et profondeur physique40. Profondeur
   sémantique32,8000nœuds visités, budget texte, types de conteneurs admissibles,
   exclusions et topologie DOM inchangés. Les div avec rôle/ARIA, racines Shadow,
   slots, contrôles et texte ne reçoivent pas de crédit. XPath garde sa borne32 :
   xpath=null/depth_limit peut accompagner un texte complet et n’est pas inventé.
2. Greenfield réécrit l’historique de la même URL après navigation ; des frames
   se stabilisent aussi après chargement. La garde de génération refusait alors
   export.html.before_publish, même URL attendue/observée. Le cliché divergent
   reste refusé. BrowserManager.extract reprend désormais au maximum2fois un
   cliché non publié dans le même job, avec250ms entre reprises, si URL inchangée
   depuis checkpoint, garde de périmètre valide et budget de navigation non épuisé.
   À chaque reprise : autorisation du job contrôlée, garde humaine habituelle,
   nouveau checkpoint, nouvel identifiant d’artefact et nouvelle lecture complète.
   Aucune nouvelle navigation, action, requête POST du client ou relance de job.
   Changement d’URL, dérive continue après3clichés, garde réseau et refus de
   permission restent bloquants. Aucune publication avant vérification finale.
   capture_restarts dans reçu/diagnostic rend ce mécanisme observable.
3. Côté client métier, une erreur du nouvel export HTML ne reprend plus par
   erreur l’identifiant de l’artefact structuré précédent. Le reçu est remis à
   None avant la nouvelle extraction ; identifiants inconnus restent absents.

La limite de profondeur a changé explicitement ; aucune acceptation de partial,
truncated, frame_limit_reached ou URL différente n’a été ajoutée au consommateur.
Les budgets de caractères/octets/frames, les permissions et l’attestation réseau
sont conservés. Le DNS tiers autrefois défaillant n’est pas ignoré : les refus
réseau continuent de rendre le document partiel. Le succès final n’en contient aucun.

## Reproduction D-146 et preuves avant

Prérequis : PageQuay1.2.2 corrigé, configuration privée habituelle, robots autorisé,
source exacte ci-dessus. Ancienne version avant correction : même numéro1.2.2,
JS SHA41fe579a8f4553093cf07ba31448487f73377f83417d5ca8ee7a2c84175b91e3 ;
le numéro seul n’identifie donc pas la version déployée.

Sur un onglet possédé, appeler extract(format='structured', expected_url=URL),
download, puis extract(format='html', expected_url=URL) et download ; vérifier
l’URL par tab_info avant/après et fermer l’onglet. Attendu : structured complet,
HTML exact et publié seulement après garde. Utiliser les opérations métier
acquire_ordered(manifest,directory,['pagequay']) après précontrôle robots frais
pour vérifier sans repli, puis persist avec revalidation d’approbation habituelle.

Ancien incident22:12 : joba67f021f54600364325c5cc69224d51d, request
22bef92a9542a83b3cfcad83, tabcd1beaafeb3abfeb750f3353edff883a,
artifact3d50bcde33c22d2718ebbf7b71c9a9a8 ; partial/truncated=true, depth.
Rejeu du HTML rendu réel en Chromium sans réseau : principal tronqué avant,
complet après ; une frame chrome-error reste indisponible dans ce rejeu réseau
volontairement bloqué. Ce rejeu n’est pas présenté comme export multi-frame complet.

Après correction JS seule, run79dac38a-e265-4ef0-8d37-239c6adef804 échoue encore
sur HTML : job09ea1e18fa57aa307a71c926c180a875, requestbb0fd9e7d6861b11d4986f57,
tabf3d3af56cbd8739bc12fef0b2a988e8b, causeNAVIGATION_CHANGED,
étapeexport.html.before_publish, artefact candidat24e14ceecfb9c93f82ea96dac7e65714
NON publié. Le diagnostic client initial associait à tort f707f0b3c47525a00461684bb20228ab,
qui est le structured précédent ; correction3ci-dessus. Historique conservé,
aucun artefact fabriqué ou succès réécrit.

## Installation réelle et recette finale

Dépôt PageQuay distant : /Users/lolo/Documents/Codex/PageQuay, HEAD de référence
a64566dc748ad12fa31980f4f0b2dd26ad52a0eb, modifications antérieures préservées.
Runtime : /Users/lolo/Library/Application Support/PageQuayService.
JS installé à22:31:28, méthode extract installée à22:39:17, uniquement après
zéro job queued/running/waiting_for_human vérifié ; deux rechargements supervisés,
ready200 et nouveaux PID. Aucun job actif interrompu. Seule méthode extract
remplacée dans browser.py installé, car il contient d’autres adaptations absentes
du dépôt ; elles sont conservées. API, structured.py et network_diagnostics.py
inchangés par cette correction. Aucun service/clé/profil/règle réseau ajouté.

SHA JS920c23b23a9c4d0f2ff6f46a174ef9e27c0d23ff8dc6cc527de6f13198e16eaa,
attesté par structured_reader_loaded du service. SHA browser installé final
 d2635afb4809c364ba054601377f8b90edfc5a6359b72948dab42db937eadac4 ;
SHA méthode seulec8a12c90cf2a73eabfad956f9fe26fda9caac78ea3ae7c27426cbf1b3a2033b3.
Pas de bump de version ni commit inventé ; patch local installé identifié par hashes.

Recette métier PageQuay SEUL, run24c959bd-66db-4c63-8784-dd05b8dc5ba3 :
robots200/allowed,1source acquise,0échec,0tentative de page Scrapy/Crawl4AI,
1snapshot inséré22c0f0e2-9c09-4da7-be61-a97eb46f0979.
Le précontrôle robots utilise son lecteur dédié ; il n’acquiert pas la page.

| Phase | Fin le23/10, Europe/Warsaw | Job | Request | Artefact |
|---|---|---|---|---|
| navigation |22:39:40.424378+02:00 |cfa89bddae06f4439fca01b7ecad4438 |237d559beea285a5cd2905e3 |aucun |
| structured |22:39:51.403066+02:00 |34fec0df67370932b327e5697cfce4bd |53981e390e6e6703c8279230 |0876ad88d42a246980eb23bf303b2587 |
| HTML |22:39:56.433954+02:00 |c1f1d8b5fa9e60719e414c236f996415 |db108a3c31b5660530609ca7 |670c3d25459e59de5e58df134b62ac1f |

Onglet communc7a749778c2ff7fa75f272cae3fb9c5f, fermé par le contexte possédé.
Structured : partial=false, truncated=false, raisons=[], frame_limit_reached=false,
7blocs/2images du principal ;490nœuds visités,398inclus,5556caractères.
Framef1 extraite (vidéo intégrée publique) ; aucune frame indisponible, aucun refus
réseau.2reprises de cliché structured réelles dans le même job,0pour HTML.
HTML1544556octets, SHA2c84030b22b91db9921d0d4addfae7198086a2e9c59df9c0b06f0f6d87b6f08c.
Approbation et URL exacte revalidées par le parcours d’import ; pas d’analyse IA,
fiche, approbation de fait ou publication déclenchée pour cette correction.

## Validation, ressources et reprise

Tests PageQuay :35tests Chromium structured/depth/Greenfield et84tests
acquisition/course d’export/délai,119distincts. Régressions rouges avant sur
conteneurs profonds et historique ; après : contenu frais,1seul artefact publié,
3clichés maximum, budget épuisé, autre URL avec/sans expected_url, confidentialité,
provenance et bornes. Ruff et diff --check ciblés conformes.
Client UniversRobot :9tests business/diagnostic et10recurring,19distincts ; rouge
avant/vert après pour l’identifiant d’artefact HTML erroné.

Preuves privées0700/0600 : var/diagnostics/greenfield-pagequay-export/ ;
HTML/JSON publics capturés sans clé/cookie, reçus et résultats des sondes. Stockage
métier durable PostgreSQL et copies dans le runtime privé existant, pas dans ces
fichiers de diagnostic. Sondes /private/tmp/ur_greenfield_*.py et copie distante
/private/tmp/pq-greenfield-996/. Sauvegardes runtime :
/var/folders/6s/yfbmscb56691zy45zsnzjx700000gn/T/pq-greenfield-996-y6mfauw5/,
/var/folders/6s/yfbmscb56691zy45zsnzjx700000gn/T/pq-greenfield-capture-996-mvr5xsa1/.
Restaurer uniquement les deux fichiers sauvegardés au repos réintroduirait les
anciens défauts ; aucun rollback global de base ni suppression des copies/reçus.
Les changements concurrents sont préservés. Une remise à HEAD de deux exemples
synthétiques générés par les tests a été refusée par le contrôle automatique pour
risque d’écrasement concurrent ; cette opération a été abandonnée et leurs contenus
sont conservés. Aucun élément nécessaire à la correction ne reste bloqué par ce refus.
