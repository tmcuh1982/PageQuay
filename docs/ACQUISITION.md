# Acquisition exacte et diagnostic des frames — extension du contrat 0.2.0

[Français](ACQUISITION.md) | [English](ACQUISITION.en.md)

Cette extension est additive : Bearer, projets/scopes, formats historiques, curseurs DuckDuckGo et hashes d’idempotence des anciennes recherches sont conservés. Aucun navigateur n’est nécessaire sur le serveur client. [Exemple Python](../examples/acquire.py), [OpenAPI](openapi.json), [preuves et limites](testing/ACQUISITION_REPORT.md).

## Navigation et acquisition

Depuis 0.2.2, attente automatique bornée, reprise humaine et contrôle de portée sont séparés de l’extraction : [contrat et preuves](NAVIGATION_SCOPE.md).

```http
POST /v1/projects/{slug}/tabs
Authorization: Bearer <clé avec browser:interact>
Idempotency-Key: <valeur persistée avant envoi>
Content-Type: application/json

{"url":"https://example.org/document","expected_url":"https://example.org/document","allow_redirects":true,"respect_robots":true}
```

Le 202 fournit `job_id`, `tab_id` réservé, `project`, `client_id` (identifiant de clé, jamais son secret) et `url` du job. Le tab_id reste corrélable si la navigation échoue ou attend un humain ; un job annulé en file peut avoir un ID réservé sans onglet réellement créé. Le job expose aussi le `request_id` HTTP d’origine, persisté par migration 007. Pour une navigation d’onglet existant, les mêmes options et l’en-tête d’idempotence sont disponibles sur POST `/tabs/{tab_id}/navigate`.

`expected_url` compare la chaîne complète à l’URL du navigateur, sans autorisation par domaine, section ou préfixe. Fournir l’URL telle que Chromium la sérialise, notamment le `/` final d’une origine. `expected_url` concerne la destination finale après résolution du challenge. Avec `allow_redirects=true` (défaut), `url` peut désigner un point de départ différent ; avec false, elles doivent être identiques à la création. Avec `allow_redirects=false`, une cible HTTP différente est refusée à l’interception des en-têtes, avant suivi/lecture de la cible ; l’erreur `REDIRECT_BLOCKED` conserve origine/chemin et SHA-256 de la cible complète. Query/fragment/credentials sont absents de cette erreur. Les navigations principales par script vers une autre adresse sont aussi refusées par le routage ; un changement local de hash/history est détecté lors de la capture, sans promesse de bloquer une mutation DOM avant qu’elle se produise.

Une navigation stricte (`expected_url` renseigné ou `allow_redirects=false`) exige HTTPS sur 443. Les anciens payloads conservent HTTP/HTTPS sur 80/443 et les redirections. Une extraction reçoit l’attente exacte séparément :

```http
GET /v1/projects/{slug}/tabs/{tab_id}/content?format=structured&expected_url=https%3A%2F%2Fexample.org%2Fdocument
Authorization: Bearer <clé avec content:read>
```

Le verrou de l’onglet sérialise les opérations API ; la révision de navigation/frames est vérifiée avant et après lecture, et entre frames. Toute navigation commencée pendant la capture, même un reload à la même URL, invalide la capture avec `NAVIGATION_CHANGED`. Si elle révèle un challenge reconnu, la capture est jetée et le job attend sa résolution avant une nouvelle capture. Le même contexte CDP isolé est vérifié après chaque lecture. Une URL finale différente donne `scope_changed`, avec cible pour revue et sans transfert implicite d’approbation. Aucun artefact mêlant ces navigations n’est publié. Les documents sont capturés successivement : les mutations ordinaires du DOM entre frames ne sont pas gelées. Ce contrôle de cohérence de navigation n’est pas une capture atomique de tous les DOM.

## Preuves de document et d’artefact

`result.navigation`, le résultat d’extraction et le JSON structuré portent :

| Champ | Origine / signification |
| --- | --- |
| requested_url / final_url | Requête principale observée / URL actuelle Chromium |
| http_status / http_status_reason | Réponse HTTP du document principal ; null et motif explicite si non observée |
| content_type | En-tête HTTP du document principal, nullable ; aucun type deviné depuis le DOM |
| redirect_chain / redirect_chain_truncated | Réponses principales 3xx observées, maximum 20 |
| observed_at / navigation_id | Commit de frame principale, UTC ISO 8601 / identifiant local unique |

Un titre « Error 500 » dans une vraie réponse 200 garde **le 200 observé**, sans prétendre que l’acquisition est un succès métier. Un DOM d’erreur Chromium ou `set_content` sans réponse n’obtient jamais un 200 déduit. Un CAPTCHA ayant réellement reçu HTTP 200 peut attester ce statut, tout en restant `waiting_for_human` ; son DOM n’est pas extrait automatiquement. Le résultat d’attente garde capture et preuve HTTP, y compris en fin de délai/annulation.

Le JSON structuré ajoute `captured_at`, `artifact_id`, `robots` et `network_policy`. `media_type` et le Content-Type du téléchargement décrivent **le fichier produit** (`application/json` pour structured), distinct de l’en-tête du document source. Limites de nœuds, frames, octets, stockage et TTL existantes maintenues ; JSON complet trop grand : 413. Aucun status, robots ni XPath ne provient d’une affirmation du texte de page.

Chaque bloc possède `node_id` et `provenance.xpath`, construits sur les parents/frères du DOM réel dans le monde isolé : positions `*[n]`, et `text()[n]` pour le texte. Le chemin peut désigner un nœud filtré dans l’arbre optionnel ; il reste celui du DOM source au moment de lecture. Pas de XPath inventé pour Shadow DOM : null et `xpath_reason=shadow_root`. Bornes explicites de profondeur/frères, et références locales au snapshot/frame ; les chemins ne sont pas garantis après mutation et ne franchissent pas les frontières de documents.

## Destinations publiques : preuves et refus

Le routage applique URL/credentials/ports et DNS ; chaque adresse A/AAAA doit être publique. Le proxy résout de nouveau avant connexion et se connecte **à l’IP littérale validée**, sans résolution intermédiaire. Loopback, privé, link-local, multicast, réservé, IPv6 mappé/6to4/Teredo et NAT64 connu sont refusés. Réponses DNS mixtes refusées. Un changement DNS vers une adresse privée est refusé à la validation suivante ; un tunnel existant reste connecté à son IP publique validée. WebSockets et service workers sont bloqués.

L’interception CDP des redirections reste active sur l’onglet jusqu’à fermeture, y compris après `domcontentloaded`. Chaque cible de redirection du target principal est validée avant suivi ; les sous-ressources de ce target suivent les mêmes contrôles HTTPS/DNS. Les refus routés sont bornés à 32 et publiés comme codes/causes dans `network_policy.refusals`, sans URL de diagnostic.

**Limite traitée par refus en mode strict :** la couverture de redirection CDP des OOPIF n’est pas attestée. Tout trafic provenant d’une frame enfant est donc refusé dans ce mode (`strict_subframe_network_unattested`, `subframe_network=denied`), et un export affecté indique `partial=true`. Le mode historique conserve les iframes publiques et leur proxy ; il ne prétend pas garantir la revalidation DNS de chaque redirect OOPIF dans un tunnel réutilisé. L’extraction isolée cross-origin/OOPIF est testée séparément en mode historique. Cette restriction opt-in ne constitue pas une couverture générale de tous les OOPIF.

Les preuves s’appliquent au trafic Web médié par ces contrôles. Les tests ne certifient pas tout le trafic interne possible de Chromium/OS, un NAT64 personnalisé ou l’environnement réseau distant de production. Les ports locaux privés ne sont autorisés que par injection dans les tests, sans option publique pour les activer.

## Robots et user-agent

Le navigateur conserve le User-Agent natif de Chromium, sans surcharge personnalisée. `respect_robots=true` utilise un onglet auxiliaire détenu, via le proxy et les gardes, pour `/robots.txt`, puis le ferme dans un finally. Lecture limitée à 65 536 octets, Content-Type text/plain attesté, parser Python `RobotFileParser`, agent réellement envoyé par Chromium dans la requête robots. `Disallow`, HTTP 401/403 : `ROBOTS_DENIED` avant chargement du document demandé. HTTP 404/410 : autorisation fondée explicitement sur absence de robots ; autres statuts/type incohérent : `ROBOTS_UNAVAILABLE` (429 conserve RATE_LIMITED). Un challenge robots reste en attente humaine ; après intervention modifiant le document, une nouvelle acquisition explicite est nécessaire. Le helper robots refuse explicitement ses redirections. Les redirections du document suivent `allow_redirects` ; les règles de la destination finale approuvée sont vérifiées à nouveau avant lecture métier, sans transférer la preuve initiale. En cas d’autorisation, l’export contient statut, date, type, User-Agent observé et digest du texte effectivement analysé. Sans option, `status=not_checked` : **aucune preuve robots**. Le parser ne revendique pas une conformité exhaustive RFC 9309 ni la couverture d’interdictions hors robots/HTTP.

## Diagnostic des frames

L’ancien `reason=frame_detached_or_unresponsive` est conservé uniquement pour compatibilité ; il ne prouve pas un détachement. `cause_code` / `diagnostic.cause` distingue FRAME_DETACHED, TIMEOUT, WORLD_NOT_FOUND, JAVASCRIPT_EXCEPTION, SIZE_LIMIT, SCHEMA_REJECTED, OTHER_ERROR. `is_detached` est un fait Playwright au moment de l’échec, distinct d’un indicateur d’exception. Étape bornée : visibility, cdp_session, context_selection, isolated_world, extraction, serialization, context_verification ; durée monotone, budget 10 000 ms par frame, timestamp UTC.

Le logger serveur `pagequay.extraction` produit `frame_read_failure` avec request_id/job_id/tab_id/frame_id/artifact_id, étapes et chaîne originale de **types/codes** d’exceptions. Texte arbitraire et lignes de source sont entièrement expurgés : aucune query/fragment, cookie, Bearer ni corps de page. Les identifiants de l’artefact sont réservés avant lecture : un log d’échec peut référencer un fichier qui n’a jamais été créé. Les logs LaunchAgent nécessitent la rotation opérateur existante. Aucun fallback vers JavaScript appartenant à la page, ni relâchement réseau, ni retry global de lecture.

Les anciennes erreurs agrégées KUKA de 17:26 ne permettent pas de reconstruire rétroactivement leur cause. Le défaut WORLD_NOT_FOUND signalé à 21:38 a ensuite été reproduit et corrigé sur le site réel avec traces bornées : voir [le correctif 0.2.1](KUKA_FRAME_FIX.md). Le test authentifié de cette version sur le service installé sera effectué par UniversRobot.

## Contrôle, pertes de réponse et quotas

La clé d’origine seule peut contrôler son job ou fermer un onglet API qu’elle a créé ; l’admin conserve son contrôle local, les onglets historiques non attribués gardent leurs règles. Même projet/scopes ne donnent pas la propriété d’un nouvel onglet d’une autre clé. Le tab_id/job_id sont persistés dès admission. Le `client_id` est l’identité de la clé serveur ; aucun identifiant de client librement forgé n’est accepté.

Annulation : POST `/jobs/{id}/cancel`, attendre une fin de job, puis DELETE `/tabs/{tab_id}`. Une opération active ou en attente humaine tient le verrou et donne 409 à la fermeture ; annuler d’abord. Les métadonnées de la navigation échouée restent dans `job.result` avec le tab_id. Un timeout/annulation ne ferme pas silencieusement l’onglet d’acquisition : ses IDs restent dans le job. Un onglet réservé peut ne pas exister (404). Les recherches gardent leur nettoyage limité à leurs propres onglets. Après redémarrage, les jobs actifs échouent sans rejeu, et les onglets restaurés ont de nouveaux IDs ; leur attribution ancienne n’est pas revendiquée.

Persisté avant POST, `Idempotency-Key` retrouve le même job et tab_id pendant 24 h même si le 202 a été perdu. Payload/route différent : 409 ; aucune création/retry automatique. L’exemple n’émet qu’un POST de création et demande `--recover` pour un rejeu explicite, ou `--resume` pour reprendre le job après intervention humaine. Une réponse d’extraction perdue reste une opération incertaine distincte : son GET n’est pas idempotent au sens job, et peut créer une seconde extraction lors d’une reprise explicite ; aucune seconde navigation n’est créée.

Le quota REST est partagé par **clé** entre créations, polling, commandes, téléchargements et key-info (min limite de clé/projet, fenêtre fixe 60 s). La cadence DuckDuckGo PageQuay est séparée : **6 tentatives/60 s par projet et moteur** ; ce n’est pas un quota attribué à DuckDuckGo. 429 HTTP : Retry-After quand connu, sinon date/délai null avec cause/portée explicites. Quotas de capacité sans échéance prévisible restent inconnus. Stockage d’artefacts expose l’expiration la plus proche comme prochaine échéance possible, sans garantir qu’elle libérera assez d’espace. Erreurs moteur conservent partiels et continuation comme dans [SEARCH_API](SEARCH_API.md). Polling et rejeu comptent au quota REST ; pas de retry implicite de création, CAPTCHA ou changement silencieux de moteur dans l’acquisition.


## Correctif lecteur 0.2.1

Le défaut de sélection WORLD_NOT_FOUND sur KUKA est désormais reproduit et corrigé ; voir [preuves, traces et limites](KUKA_FRAME_FIX.md). `context_selection` distingue absence de candidats et chemins incompatibles, et expose les sélections réussies. L’extraction conserve les mondes isolés et tous les refus réseau existants. La validation du service installé avec la clé privée d’UniversRobot reste à effectuer depuis ce client.
