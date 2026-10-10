# Recherche PageQuay — contrat 0.2.0

Ce contrat ajoute des champs aux réponses et des paramètres optionnels aux requêtes de l’API `/v1`, sans modifier les états ni les chemins des jobs. `GET /openapi.json` publie le schéma des routes client et health sur le port API 8766 et via le HTTPS privé. Aucun login admin ni secret n’y figure. La copie versionnée est [openapi.json](openapi.json).

## Diagnostic des limites précédentes

| Garde prouvée dans le code | Portée et fenêtre | Opérations comptabilisées |
| --- | --- | --- |
| `Search.limit` de 1 à 50, défaut 10 | Validation de chaque requête | Valeur demandée, sans agrégation des pages |
| `search_max_results=10` par défaut | Plafond configurable globalement/par projet | `min(limit, search_max_results)` résultats retournés par job |
| Adaptateur DuckDuckGo HTML | Une navigation initiale, aucun « Next » avant 0.2 | Lecture du premier document uniquement ; l’adaptateur ne demande pas lui-même 50 résultats au moteur |
| Quota PageQuay de moteur : 6/60 s | Couple **projet + moteur**, partagé par toutes ses clés et l’admin | Chaque tentative de chargement d’une page de recherche, y compris une continuation native ; une tentative échouée ou un CAPTCHA consomme sa place |
| Quota REST | **Clé API** ; plafond effectif min(clé, `per_key_rate_limit` du projet), défaut 60/60 s | Appels REST autorisés : création, rejeu idempotent, suivi, contrôle, téléchargements, key-info, etc. ; contrôle d’authentification/scope avant décompte |
| Capacité de jobs | Globale et par projet, défaut 30 jobs actifs/en attente | Admission d’un nouveau job, sans fenêtre temporelle connue |
| Capacité de navigateurs/onglets | Globale 3 navigateurs, par projet 8 onglets par défaut | Démarrage et allocation d’un onglet ; une recherche utilise au plus un onglet interne |

Les fenêtres de quota sont fixes, commencent au premier appel admis et sont persistées dans SQLite. Elles ne sont pas des fenêtres glissantes ni des quotas de DuckDuckGo. Une continuation qui rend seulement un reliquat déjà stocké consomme le quota REST, mais pas de nouvelle tentative moteur ni d’onglet. Les redirections, ressources de la page et reprise du même CAPTCHA ne sont pas de nouvelles tentatives moteur. Les autres gardes REST existantes restent inchangées : captures 6/60 s par clé, messages WS plafonnés à min(quota clé, 60)/60 s, connexions WS bornées ; voir README.

Le plafonnement observé 5/10/10/10 pour des demandes 5/10/20/50 est expliqué par le plafond PageQuay de 10. Les six succès suivis de quatre `RATE_LIMITED` sont compatibles avec le garde projet/moteur trouvé ; les anciennes réponses ne permettent pas de prouver rétrospectivement la cause de chaque échec. Aucune limite exacte de DuckDuckGo n’est déduite de ces observations. La configuration du projet de référence relue sur le service avait `search_max_results=10` et aucune surcharge.

## Première tranche et continuation

Une requête contient `query` (1–500 caractères), `engine`, `limit` (1–50) et `locale` (`fr-FR` par défaut). Plusieurs mots-clés font partie d’une même chaîne `query`. Pour plusieurs recherches distinctes, envoyer plusieurs opérations, chacune avec son propre curseur et sa clé d’idempotence ; aucun batch implicite ne multiplie les requêtes.

### Pays / région et période pour l’actualité

DuckDuckGo accepte deux filtres optionnels, également disponibles dans la console locale **Recherche** après sélection du moteur DuckDuckGo :

| Champ | Valeurs | Défaut |
| --- | --- | --- |
| `region` | Code régional DuckDuckGo, par exemple `fr-fr` (France), `pl-pl` (Pologne), `us-en` (États-Unis), `uk-en` (Royaume-Uni), `wt-wt` (toutes les régions) | `null` : région dérivée de `locale` |
| `time_range` | `any` (toutes les dates), `day` (dernier jour), `week`, `month`, `year` | `any` |

Exemple pour rechercher en France sur la dernière semaine :

```json
{"query":"robot agriculture","engine":"duckduckgo","region":"fr-fr","time_range":"week","limit":10}
```

`region` remplace le contrôle régional dérivé de `locale`, ce qui permet de choisir un autre marché sans modifier celle-ci. Le code combine pays/région et langue, selon la [liste officielle DuckDuckGo](https://duckduckgo.com/duckduckgo-help-pages/settings/params) ; il ne garantit pas une restriction aux seuls sites du pays. Les valeurs explicites non reconnues sont refusées avec HTTP 422. Les anciennes locales restent acceptées et conservent leur transmission historique ; certaines combinaisons peuvent être ignorées par le moteur.

La période est transmise via `df` (`d`, `w`, `m`, `y`, ou une valeur vide pour toutes les dates), avec la correspondance utilisée par l’[adaptateur HTML SearXNG](https://docs.searxng.org/_modules/searx/engines/duckduckgo.html). DuckDuckGo décrit ces [filtres de date](https://duckduckgo.com/duckduckgo-help-pages/features/dates) dans son aide. Chaque chargement transmet explicitement région et période, y compris les continuations natives, afin de ne pas dépendre du choix précédent du profil. Les tokens et offsets restent ceux du formulaire moteur ; aucun offset n’est inventé.

Un filtre explicite (`region` non nul ou période autre que `any`) nécessite le moteur effectif DuckDuckGo. `auto`, Brave et Google sont refusés avec HTTP 422 avant admission ; aucun repli ne supprime silencieusement ces filtres. Si `engine` est omis, le moteur configuré du projet doit être DuckDuckGo.

Les réponses et les résultats partiels rappellent `locale`, `region` et `time_range`. Conserver ces valeurs à chaque reprise ; changer région ou période invalide le curseur. Les filtres participent aussi à l’idempotence. Omettre les filtres et envoyer `region=null,time_range="any"` sont équivalents, y compris pour les associations d’idempotence antérieures à l’ajout des filtres. La migration SQLite conserve les curseurs existants sans filtre.

**Fraîcheur :** `fetched_at` indique la collecte par PageQuay, pas la publication ni l’événement. Une page récemment publiée ou modifiée peut raconter un événement ancien. Pour une veille fiable, consulter l’article et distinguer date de publication, date de mise à jour et date de l’événement ; si elles sont absentes, conserver l’incertitude. Ces filtres ne constituent pas une vérification automatique de ces dates.

`limit` conserve son sens : **maximum de résultats dans cette opération**, plafonné par la configuration du projet. Ce n’est ni un nombre de pages ni une garantie de remplissage. Un appel effectue au plus un chargement de page du moteur. Les résultats de cette page qui dépassent le plafond sont gardés dans le curseur ; des tranches suivantes peuvent les rendre avant de charger une autre page.

Première requête, en HTTPS avec le Bearer fourni par l’environnement serveur et un en-tête `Idempotency-Key` choisi par le client :

```http
POST /v1/projects/projectx/search
Content-Type: application/json
Idempotency-Key: projectx-run-123-query-1-slice-1
```

```json
{"query":"robot agriculture","engine":"duckduckgo","limit":10,"locale":"fr-FR"}
```

Réponse d’admission :

```json
{"job_id":"JOB_ID","status":"queued","url":"/v1/projects/projectx/jobs/JOB_ID","idempotency_replayed":false}
```

Suivre le chemin relatif `url` avec le même Bearer. Dans un job `completed`, `result` conserve `project`, `query`, `results`, `engine_errors` et ajoute :

| Champ | Sens |
| --- | --- |
| `engine`, `engines_used` | Moteur(s) effectivement utilisés pour les résultats ; `mixed` pour une fusion ; un échec sans résultats peut encore indiquer le choix demandé |
| `requested_count`, `effective_limit`, `returned_count` | Demande du client, plafond appliqué, nombre réellement retourné |
| `next_cursor` | Chaîne opaque de 43 caractères, ou `null` si aucune reprise proposée |
| `has_more` | `true` : reliquat ou formulaire natif disponible ; `false` : fin détectée ou arrêt imposé ; `null` : fin inconnue / continuation absente ou inexploitable |
| `cursor_expires_at` | Échéance Unix UTC du curseur proposé, sinon `null` |
| `pages_fetched` | Nombre cumulatif de documents du moteur chargés dans cette chaîne, pas le nombre de tranches |
| `duplicates_discarded` | Doublons cumulés détectés selon l’URL normalisée |
| `stop_reason`, `partial` | Motif de fin de cette tranche et présence d’un arrêt partiel connu |

Reprise : recopier le curseur reçu, conserver projet/query/engine/locale/region/time_range et choisir une **nouvelle** clé d’idempotence pour cette tranche. `limit` peut changer.

```json
{"query":"robot agriculture","engine":"duckduckgo","limit":10,"locale":"fr-FR","cursor":"CURSEUR_OPAQUE_REÇU"}
```

La valeur illustrée doit être remplacée par le vrai curseur de 43 caractères. Si `next_cursor=null`, arrêter explicitement et examiner `has_more`/`stop_reason` ; ne pas relancer la première page comme s’il s’agissait de la suivante.

Chaque résultat garde l’URL normalisée historique dans `url`. `exact_url` contient l’URL cible exacte après déballage du lien de redirection du moteur, en conservant paramètres, encodage et fragment. La déduplication normalise les URL mais ne réécrit pas `exact_url`. `rank` est continu dans la chaîne ; `engine_rank` indique l’ordre des résultats organiques reconnus sur le document, `page_number` le document source. `source_engines` et `fetched_at` gardent la provenance et la date de collecte. Une fusion garde la première URL exacte observée et rassemble les provenances.

Le choix explicite `engine="duckduckgo"` ne bascule jamais vers un autre moteur. `engine="auto"` autorise explicitement le repli/la fusion configurés, avec provenance et erreurs ; ces modes conservent leur comportement initial et ne proposent pas de curseur. Pour une pagination vérifiable, demander DuckDuckGo explicitement. Les locales DuckDuckGo sont transmises avec `kl` pays-langue (`fr-fr`, `us-en`, `pl-pl`, `uk-en` pour `en-GB`), selon les [paramètres officiels](https://duckduckgo.com/duckduckgo-help-pages/settings/params). Toutes les combinaisons langue/pays validées par PQ ne sont pas nécessairement prises en charge par le moteur ; aucune stabilité de classement n’est promise.

## Pagination native et bornes

La continuation reprend uniquement un formulaire « Next » présent dans le HTML DuckDuckGo, son action HTTPS `/html/`, sa méthode GET/POST et ses champs cachés émis par le moteur. Elle ne fabrique pas de numéro de page, offset ni token `vqd`. La soumission utilise Chromium, le profil du projet et le proxy réseau de PQ, avec les mêmes protections que la navigation. Elle n’envoie aucune clé API au moteur.

La chaîne stocke les résultats non encore livrés et les paramètres natifs dans SQLite ; le client ne reçoit qu’un token aléatoire. Une page entièrement répétée, sans URL nouvelle, ou un formulaire déjà suivi arrête la progression. Les doublons partiels sont retirés ; ils ne sont pas présentés comme des résultats nouveaux. L’absence d’un formulaire reconnu ne prouve pas que le moteur n’a plus de résultats : PQ renvoie alors une fin inconnue.

| Réglage | Défaut | Borne configurable |
| --- | --- | --- |
| `search_max_results` par tranche | 10 | 1–50 |
| `search_max_pages` par chaîne | 10 | 1–30 |
| `search_max_total_results` uniques par chaîne | 200 | 1–1000 |
| `search_cursor_ttl_minutes` | 15 | 1–60 |
| `search_max_cursors_per_project` stockant un état actif | 100 | 1–1000 |

Un document est limité par `max_content_bytes` (2 Mo par défaut), le parseur lit au plus 200 résultats par document, titres 500 caractères et extraits 2000. Les paramètres de formulaire sont bornés à 40 champs / 16 Ko. Une opération a un budget total maximal `job_timeout_seconds + human_timeout_seconds` (180 + 600 s par défaut), une navigation au plus 30 s par défaut et chaque attente humaine au plus 600 s ; aucune attente de quota n’est effectuée côté serveur. Les événements `job.progress` indiquent `fetching_search_page`. Un appel retourne au plus une page native ou un reliquat.

`stop_reason` : `result_limit` (reliquat), `page_complete` (formulaire suivant), `exhausted` (fin explicite), `continuation_unavailable` ou `continuation_unusable` (fin inconnue), `repeated_page`, `repeated_continuation`, `no_progress`, `page_limit`, `total_results_limit`, `cursor_capacity`, `cursor_expired`, `pagination_not_supported` pour les autres modes. Un échec peut porter son code en minuscules, par exemple `rate_limited`/`timeout`. Les bornes et répétitions connues portent `partial=true` ; une simple tranche avec continuation n’est pas un échec partiel.

## Durée, rejeu et invalidation des curseurs

- L’échéance est absolue depuis le premier chargement ; une reprise ne prolonge pas la chaîne. Expiration : HTTP 410 `CURSOR_EXPIRED`, ou le même code dans un job expiré pendant son attente en file.
- Le curseur est lié au projet, à la query validée, au moteur DuckDuckGo, à la locale, à la région explicite et à la période. Changer l’un d’eux : HTTP 409 `INVALID_CURSOR`, avant création du job. Une autre clé du même projet avec `search:read` peut le reprendre.
- La réservation du curseur et la création du job sont atomiques. Sans rejeu idempotent, réutiliser un curseur réservé/consommé renvoie HTTP 409 `CURSOR_USED` et le chemin du job existant.
- Une tentative échouée/annulée libère la réservation ; si elle n’est pas expirée, une nouvelle opération peut reprendre ce même curseur. Les erreurs de quota indiquent précisément si cette reprise reste possible. Les jobs interrompus au redémarrage deviennent `failed` et libèrent leur réservation ; les curseurs non expirés gardent leur état dans SQLite.
- Un reset de profil invalide ses curseurs. Purger les contenus supprime leurs états/curseurs. Un redémarrage ordinaire du navigateur conserve le profil et les curseurs ; les paramètres natifs peuvent néanmoins expirer indépendamment chez DuckDuckGo, auquel cas PQ signale l’erreur réellement observée.
- Les états consommés sont effacés après succès. Les états expirés inactifs sont effacés à la prochaine maintenance (30 s), et les traces de curseurs sont supprimées un jour après expiration. Les résultats des jobs suivent encore le TTL de contenus du projet.

## Limitations HTTP et asynchrones

HTTP 429 conserve l’enveloppe `error` et ajoute `details`. `Retry-After` est fourni quand le délai est connu. Une capacité pleine ne permet pas de prédire l’heure d’un départ : délai/date restent `null`.

Exemple de job `failed`, quota PageQuay projet/moteur :

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "PageQuay request quota exhausted; retry after the window resets",
    "details": {
      "scope": "project_engine", "cause": "pagequay_quota", "engine": "duckduckgo",
      "limit": 6, "window_seconds": 60,
      "retry_after_seconds": 24, "retry_at": 1791655220,
      "can_resume_continuation": true, "resume_cursor": "CURSEUR_OPAQUE_REÇU",
      "partial_results": []
    }
  }
}
```

Les autres portées comprennent `api_key`, `job_queue`, `browser_capacity`, `project_tabs`, `upstream_engine`. Une réponse moteur HTTP 429 indique `cause="upstream_http_429"`, avec le `Retry-After` du moteur s’il est exploitable ; un HTML de throttling indique `upstream_throttling`, sans quota supposé. Une cause non identifiée reste `unknown`. Les résultats déjà acquis sont conservés dans `job.result` et, pour une limitation, dans `error.details.partial_results`, avec leur provenance. Un moteur réussi suivi d’une limitation en mode merge produit donc un job échoué mais des résultats partiels inspectables.

Les CAPTCHA restent `waiting_for_human` jusqu’à reprise manuelle, annulation ou délai. La fin du délai donne `TIMEOUT`, pas une preuve de quota DuckDuckGo. Après l’intervention sur le Mac, POST sur le chemin relatif du job + `/resume`. Aucun solveur, clic automatique de vérification ni changement d’identité.

## Idempotence de POST /search

`Idempotency-Key` est optionnel pour préserver les clients existants, mais recommandé. Valeur 1–128 caractères ASCII dans `[A-Za-z0-9._:-]`. Périmètre : projet + clé API + POST /search. Les corps sont comparés après validation et application des valeurs par défaut (`null`/omission équivalents) ; query/locale sont normalisées par les validations existantes.

La même valeur avec le même corps retrouve **le même job**, son état courant et son chemin relatif, avec `idempotency_replayed=true`, pendant 24 h. Un corps différent renvoie HTTP 409 `CONFLICT`. La vérification/réservation/enregistrement SQLite n’a aucun await : les appels concurrents du processus unique retrouvent la même opération. Les associations et jobs survivent au redémarrage ; une création interrompue n’est pas relancée automatiquement. Une clé révoquée/expirée ou privée du droit reste refusée avant tout rejeu.

Un rejeu REST compte dans le quota de la clé, mais ne crée pas de nouveau job et ne consomme pas le quota moteur. Après 24 h, réutiliser la valeur peut créer une autre opération. Le TTL des résultats reste indépendant (60 min par défaut) : retrouver le job ne garantit pas que son résultat n’a pas été purgé. Un job échoué retrouvé par idempotence reste échoué ; pour **réessayer** après un quota, utiliser une nouvelle valeur et le curseur proposé, si `can_resume_continuation=true`.

Conserver la clé d’idempotence et le corps **avant** d’envoyer le POST. En cas de réception incertaine, réenvoyer exactement cette création avec la même clé ; ne pas changer de valeur tant que le résultat de réception n’est pas établi.

## Cycle de vie et exemple ProjectX

Chaque recherche possède son seul onglet interne. Il est fermé dans le nettoyage après succès, erreur, annulation ou délai humain, sans fermer les onglets d’autres opérations. Il reste accessible pendant `waiting_for_human`. Les curseurs ne retiennent pas d’onglet entre les jobs. Une tranche de résultats stockés n’en ouvre aucun.

[search_duckduckgo.py](../examples/search_duckduckgo.py) est un client Python standard utilisable côté serveur pour ProjectX. Il itère plusieurs requêtes, suit les jobs, traite les continuations et s’arrête sur une fin explicite/inconnue, un CAPTCHA, une erreur ou sa borne locale. Il sauvegarde un checkpoint privé (0600) avant création et après réception pour récupérer une création incertaine. Les reprises de quotas connus sont bornées ; les CAPTCHA demandent une intervention manuelle séparée.

```sh
# PQ_API_KEY est fourni par l’environnement ou le gestionnaire de secrets serveur.
python3 examples/search_duckduckgo.py \
  --url https://VOTRE-HOTE-PQ --project projectx \
  --query 'robot agriculture' --query 'robot irrigation' \
  --locale fr-FR --region fr-fr --time-range week --limit 10 --max-slices 3 \
  --checkpoint /chemin/prive/projectx-ddg.json
```

Relancer avec le même checkpoint et les mêmes arguments pour retrouver une opération dont la réception était incertaine. Après intervention humaine et reprise du job, le checkpoint permet d’en lire le résultat. Le nombre de tranches peut inclure des reliquats d’une page ; consulter `pages_fetched` pour vérifier une progression native. La clé Bearer ne figure ni dans le code, le checkpoint, les résultats, les URL, le curseur ou le frontend ; les redirections HTTP du client sont refusées.

## Preuves et réserves

La simulation couvre trois pages progressives, les reliquats, doublons, répétitions, échéances, mauvais projet/query/locale/moteur, bornes, quotas partagés, idempotence concurrente et réouverture SQLite, annulation/délais/CAPTCHA et nettoyage. Une fixture Chromium réelle valide la soumission POST native, les champs répétés/Unicode et le transport par proxy.

Essais extérieurs bornés sur « robot agriculture » (`fr-FR`), « agricultural robotics manufacturers » (`en-US`) et « robots agricoles France » (`fr-FR`) : CAPTCHA DuckDuckGo pour les trois, `challenge.required` observé puis délai humain de test de 5 s, nettoyage des onglets confirmé. **Aucune page de résultats réelle n’a été obtenue, donc les trois pages natives réelles restent non validées.** Les HTML et le rapport brut sont gardés localement sous `docs/testing/duckduckgo-native-*.html` et `duckduckgo-pagination-live.json`, exclus de Git. Un test diagnostic réussi signifie que le résultat a été rapporté, pas que DuckDuckGo a accepté la recherche. Voir [REPORT](testing/REPORT.md) pour les commandes et le statut de déploiement.
