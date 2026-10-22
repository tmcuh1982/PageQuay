# Navigation, challenges et portée d’extraction — PageQuay 0.2.2

[Français](NAVIGATION_SCOPE.md) | [English](NAVIGATION_SCOPE.en.md)

## Contrat

Navigation et extraction sont deux opérations. `allow_redirects` vaut **true par défaut**, indépendamment de `expected_url` et `respect_robots`. La navigation peut suivre les destinations intermédiaires autorisées par la politique réseau ; elle attend passivement la fin des vérifications automatiques reconnues. Elle compare ensuite la chaîne complète de l’URL finale à `expected_url`, avant la lecture du titre ou toute extraction métier. Aucune autorisation par domaine/préfixe n’est déduite.

```json
{
  "url": "https://example.org/start",
  "expected_url": "https://example.org/document",
  "allow_redirects": true,
  "respect_robots": true
}
```

Si la destination diffère, le job termine avec `status=failed`, `error.code=scope_changed` (409 dans l’erreur typée), `error.details.target_url` expurgé de query/fragment et le SHA-256 de la cible complète. `error.details.navigation.final_url` contient la destination exacte observée pour revue par le client authentifié. Les métadonnées de navigation restent distinctes des diagnostics de frames, qui ne contiennent jamais d’URL ni de contenu. Aucun artefact métier n’est créé. L’onglet conserve son attente initiale : omettre `expected_url` dans une extraction suivante ne transfère pas l’approbation à la nouvelle destination. Un éventuel accord doit être explicite dans un nouvel appel ; aucune reprise automatique sur cette cible n’est exécutée par le client exemple.

`allow_redirects=false` reste un choix explicite : HTTPS/443, refus d’une autre cible avant suivi (`REDIRECT_BLOCKED` pour HTTP), routage bloquant une autre navigation principale. Dans ce mode, `url` différente de `expected_url` est refusée avant admission avec `URL_MISMATCH`. Avec true, ces deux valeurs peuvent différer : l’attente concerne la destination finale.

## Attente et reprise

Le détecteur distingue les signes d’intervention humaine (CAPTCHA, demande explicite, frames connues) des vérifications automatiques. Le signal de réponse principale `cf-mitigated: challenge` empêche également la capture d’une page Cloudflare personnalisée, conformément à [la documentation Cloudflare](https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/). Ce signal reste associé au document affiché jusqu’au commit d’une réponse principale de remplacement ; un début de requête ou une modification de hash/history ne l’efface pas. Les marqueurs DOM restent conservateurs et ne constituent pas une détection exhaustive de tous les challenges possibles.

L’attente automatique utilise le temps restant du budget de navigation existant (30 s par défaut, depuis le début du `goto`), avec sondage passif espacé de 250 ms. Aucun solveur, clic, reload ni retry de navigation. Une demande humaine explicite, ou une vérification toujours affichée à l’épuisement de ce délai, place le **même job** en `waiting_for_human`. L’URL, l’onglet et une éventuelle capture de diagnostic restent accessibles. La capture PNG exige son scope existant ; ce n’est pas un export de contenu métier.

Après intervention dans le navigateur serveur :

```http
POST /v1/projects/{slug}/jobs/{job_id}/resume
Authorization: Bearer <clé d’origine>
```

Le serveur recontrôle le challenge, puis l’URL finale. Une page toujours en challenge revient en attente ; une cible différente donne `scope_changed`. Le checkpoint de capture est pris **après** cette attente : un reload légitime effectué par l’humain ne provoque plus à lui seul `NAVIGATION_CHANGED`. L’extraction recontrôle la page avant publication. Un challenge arrivé pendant la lecture fait jeter la capture non publiée ; la reprise produit un nouveau snapshot. Les autres changements de navigation restent refusés, et `WORLD_NOT_FOUND` n’est ni réessayé globalement ni masqué par cette logique.

Timeout humain (600 s par défaut), plafond global du job (180 + 600 s), autorisations lors de la reprise, verrous, budgets lecteur (10 s/frame), octets/nœuds/frames et quotas restent inchangés. La reprise n’accorde aucun nouveau budget automatique.

## Réseau, robots et appelants

Les redirections autorisées restent soumises au routage, au guard CDP de réponses et au proxy public épinglé à l’IP validée : credentials, ports, DNS privés/mixtes/rebinding, IPv6, service workers et WebSockets conservent leurs refus. HTTPS/443 demeure exigé avec `expected_url` ou `allow_redirects=false`. La restriction existante des frames enfants en mode HTTPS strict (`strict_subframe_network_unattested`) est conservée : cette version ne certifie pas l’interception de toutes les redirections OOPIF.

`respect_robots` ne met plus implicitement `allow_redirects` à false. Les règles du document initial sont vérifiées avant sa navigation ; si une destination finale approuvée diffère, ses règles sont vérifiées à nouveau avant la lecture métier. Une extraction exige aussi une preuve robots pour son URL actuelle quand l’option a été activée. Aucun refus explicite n’est contourné. Le helper `/robots.txt` conserve sa propre politique **explicite** de refus des redirections : sa preuve n’est pas transférée à une autre ressource.

Audit des appelants : REST création/navigation et WebSocket utilisent `Navigate` (défaut true), la console et la recherche également. L’exemple `examples/acquire.py` utilise désormais true par défaut, avec `--no-allow-redirects` pour demander le refus et `--expected-url` pour désigner une destination finale approuvée. `--resume` contrôle uniquement le job enregistré après intervention. Les checkpoints récupérés conservent leur payload d’origine, y compris un ancien false explicite. `httpx.follow_redirects=False` concerne le **transport API** et reste volontairement inchangé pour ne pas transmettre le Bearer à une autre origine.

## Vérifications séparées

Les régressions locales Chromium couvrent vérification automatique, redirection après vérification, signal Cloudflare personnalisé, attente épuisée, challenge non résolu à la reprise, reprise navigation/extraction sur le même job, changement de portée après intervention, absence d’adoption implicite, capture invalidée et refus d’une redirection privée. Les tests d’interception avec false prouvent toujours que la cible n’est pas demandée. Les ports locaux ne sont autorisés que par injection dans ces fixtures.

Ces pages reproduisent les états de vérification ; aucun challenge Cloudflare réel n’est résolu dans les tests. La validation KUKA réelle, menée séparément, confirme la sélection CDP de `f1`, sans établir de lien causal avec ces redirections : [preuve KUKA](KUKA_FRAME_FIX.md). La recette installée avec le Bearer privé reste confiée à UniversRobot.

## Livraison vérifiée

Version **0.2.2 déployée** dans `/Users/lolo/Library/Application Support/PageQuayService`. Zéro job actif avant l’opération ; sauvegarde privée des sources, métadonnées et de SQLite : `/private/tmp/pq-navigation-022-backup-_vjth5ei`. Dix fichiers source vérifiés par SHA-256, package editable mis à jour hors ligne sans modification des dépendances, module/package/OpenAPI tous à 0.2.2. Ready 200, login admin 200, admin sur port API 404, API sans Bearer 401. Le JSON OpenAPI public livré correspond exactement au schéma servi. Tables `api_keys`, `projects`, `settings` identiques au backup ; aucun Bearer créé ou remplacé dans le service installé. Le redémarrage ferme les anciens onglets en mémoire : utiliser de nouveaux IDs pour la recette UniversRobot.

Validation : suite générale finale `pytest --browser -q -rs`, **265 passed, 4 skipped** (minimisation native `--headed`, trois moteurs externes `--live`). Après le dernier ajustement conservant le signal de challenge jusqu’au commit du document, **48 tests ciblés passent**, ainsi que **5 régressions navigateur/signal Cloudflare** ; ces ensembles se recouvrent. Ruff check/format, lockfile hors ligne et diff-check conformes. Un essai précédent concurrent avait échoué sur une restauration de fenêtre macOS ; ce test a réussi isolément, puis la suite entière a réussi sans autre recette Chromium concurrente. Une erreur de génération du document OpenAPI interne a été corrigée ; une régression vérifie désormais l’égalité du contrat livré avec le listener public.

Logs de la suite finale : `/private/tmp/pq-navigation-022-tests.log`. Manifeste et preuves de déploiement : `deployment.json` dans le backup. La recette KUKA réelle et ses nouveaux IDs sont dans [KUKA_FRAME_FIX](KUKA_FRAME_FIX.md). Aucun push distant ni test authentifié du service installé avec la clé UniversRobot n’est revendiqué.


## Diagnostic de portée et History API (Unitree G1)

L'égalité `expected_url` reste exacte, slash, query et fragment compris. Un site peut
servir une URL puis modifier réellement l'adresse avec History API plusieurs secondes
plus tard. Aucun délai fixe ni transfert d'approbation ne rend ces deux URL équivalentes.
Voir la [reproduction Unitree](testing/UNITREE_URL_SCOPE.md).

Les erreurs `scope_changed`, `NAVIGATION_CHANGED` et `URL_METADATA_MISMATCH` des opérations
de navigation/lecture ajoutent `expected_url`, `observed_url`, `observed_at` (UTC), `stage`,
`service_version`, `tab_id`, `job_id`, `request_id`, `artifact_id` et
`artifact_published=false`. L'identifiant d'artefact peut désigner une capture allouée
mais jetée ; null signifie qu'aucun identifiant n'a encore été alloué. Les URL exactes
sont réservées aux réponses authentifiées, comme `navigation.final_url` ;
`target_url` reste expurgée et `target_sha256` conserve l'empreinte exacte.
`observed_url_truncated=true` signale explicitement le dépassement des 4096 caractères.

Étapes : `navigation.goto`, `navigation.after_wait`, `navigation.title`,
`tab_info.title`, `export.{format}.wait`, `export.{format}.before_capture`,
`export.{format}.capture`, `export.structured.metadata`, `export.{format}.before_publish`.
`tab_info` vérifie le même checkpoint avant/après lecture du titre et peut donc
retourner `NAVIGATION_CHANGED` au lieu d'associer l'ancienne URL au nouveau titre.

`navigation.main_document_response` conserve la dernière réponse HTTP principale
commise (`url`, `http_status`, `content_type`, `observed_at`), séparément de l'adresse
courante. Une nouvelle requête principale l'invalide. Cette preuve ne certifie pas un
statut HTTP pour une URL créée par History API : les champs historiques `http_status`
et `http_status_reason` conservent leur sémantique conservatrice.
`url_changes` trace au plus 20 commits principaux ; une absence de réponse ne suffit
pas à attribuer un commit à JavaScript. `same_document_navigations` trace séparément
les événements CDP du document principal avec `navigation_type=historyApi`, `fragment`,
`other` ou `unknown` ; les deux listes possèdent un indicateur de saturation.

Le schéma structured reste `1.0` : l'URL principale est le champ racine `url`
(`document.url` si le client l'encapsule dans `document`). Elle est lue dans le contexte
isolé, bornée à 4096 caractères comme l'API, et comparée au checkpoint avant publication.
Une incohérence produit `URL_METADATA_MISMATCH` sans artefact. Le HTML reste le DOM brut ;
sa provenance est `result.navigation.final_url`, pas une balise canonical fournie par le
site. Le JSON structured contient aussi `navigation`. Une modification réelle pendant
la capture invalide toujours l'export ; un changement après publication ne réécrit pas
l'artefact précédent et doit être détecté par le contrôle final du client.

Les clients à schéma strict doivent accepter les nouveaux champs optionnels de
`NavigationMetadata` et conserver les détails d'erreur au lieu de les réduire au seul
code. Aucun changement des approbations ni du critère d'égalité n'est requis. Après un
écart, arrêter l'acquisition en cours ; toute nouvelle tentative garde son attente
explicite. Ne jamais adopter automatiquement la destination observée, même si une
approbation distincte existe déjà pour elle.
