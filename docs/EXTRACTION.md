# Extraction JSON structurée

[Français](EXTRACTION.md) | [English](EXTRACTION.en.md)

Sur un onglet déjà navigué, avec une clé `content:read` du projet :

```http
GET /v1/projects/{slug}/tabs/{tab_id}/content?format=structured
Authorization: Bearer <clé>
```

La réponse 202 contient l'ID et l'URL du job. Lire le job jusqu'à `completed`, puis télécharger `result.url` avec la même clé : cet artefact contient le JSON, de type `application/json`. Les erreurs et challenges suivent le mécanisme habituel des jobs.

Ajouter `&include_dom=true` pour joindre l'arbre DOM filtré. L'option vaut false par défaut ; true avec un autre format donne INVALID_INPUT (400). Un format inconnu donne 422. Les formats text/html/links/metadata conservent leur contrat.

Les métadonnées attestées, `expected_url`, la provenance XPath et les causes typées de frames sont décrits dans [ACQUISITION](ACQUISITION.md).

## Contrat version 1.0

| Champ | Contenu |
| --- | --- |
| `schema_version`, `source` | `1.0`, `rendered_dom` |
| `url`, `title`, `metadata` | URL courante, titre, langue, canonical, description, liste meta et JSON-LD analysé |
| `blocks` | Blocs dans l'ordre du DOM : heading, paragraph, list, code, quote, table et frame |
| `content_root` | ID du premier main visible s'il existe, sinon body ; les blocs de lecture proviennent de cette région |
| `links`, `images` | Collections globales du document, liens absolus et alternatives textuelles |
| `tables` | Tables HTML et ARIA table/grid/treegrid, captions, lignes/cellules, headers et spans |
| `controls`, `forms` | Types, noms, labels, options textuelles, disabled/required et association au formulaire ; aucune valeur courante ou initiale d'input/textarea |
| `landmarks`, `visuals` | Régions de la page ; canvas/SVG signalés pour interprétation par capture |
| `frame_id`, `frames` | Document principal f0, documents enfants avec ID, parent, URL, nom et statut extracted/omitted/unavailable |
| `stats` | Nœuds visités/inclus, racines shadow ouvertes, caractères copiés |
| `truncated`, `truncation_reasons`, `frame_limit_reached`, `partial` | Limites/éléments malformés rencontrés ; partial vaut aussi true si un document enfant est indisponible |
| `dom` (optionnel) | Racine avec node_id/tag/attributes/children ; nœuds texte avec text, racines `#shadow-root` et contenu projeté des slots |

Les IDs `n1`, `n2`… sont locaux à chaque document et chaque snapshot. Une référence complète comporte aussi le frame_id. Ce ne sont pas des sélecteurs pour les actions ; ils peuvent changer après toute extraction ou mutation. Les blocks table pointent vers leur table_id ; forms portent les control_ids. Les listes contiennent des items `{node_id, text, children}`, où children contient les sous-listes. L'arbre est filtré, et ses attributs suivent une liste autorisée ; il ne constitue pas une copie intégrale du HTML.

Exemples réellement produits sur une fixture locale complexe : [JSON compact](testing/structured-complex-compact.json), [JSON avec DOM](testing/structured-complex.json). Les URLs localhost de ces fixtures sont des adresses de test éphémères.

## Pourquoi utiliser le DOM rendu

Le HTML initial manque des contenus créés par JavaScript. `page.content()` actuel de PQ récupère déjà le HTML du document rendu, mais sa sérialisation ordinaire ne développe ni les racines Shadow DOM ouvertes ni les documents des iframes. La fixture le démontre : son HTML parsé contient le texte hydraté, mais pas le titre du composant shadow ni le texte de l'iframe ; le JSON structuré récupère les trois.

Playwright permet de lire [chaque frame](https://playwright.dev/python/docs/api/class-frame#frame-evaluate), y compris une origine différente, dans un navigateur déjà autorisé par le proxy PQ. Les [Shadow DOM ouverts](https://playwright.dev/python/docs/locators#locate-in-shadow-dom) sont parcourus ; leurs slots utilisent les nœuds réellement projetés. Les racines fermées ne sont pas accessibles par [shadowRoot](https://developer.mozilla.org/en-US/docs/Web/API/Element/shadowRoot).

L'arbre DOM **dans la réponse** est utile pour comprendre un composant personnalisé, ses régions, ses attributs ARIA et la relation entre les blocs et leurs nœuds. Il n'est pas nécessaire pour lire les blocs ou tables déjà présents dans le JSON compact. Sur la fixture, la sérialisation Python sans indentation passe de **5 593 à 12 390 octets** avec le DOM. Aucun nouveau paquet Trafilatura/Extruct n'est ajouté : l'objectif est la structure rendue, pas uniquement l'extraction éditoriale d'articles.

## Bornes et limites

- Quatre lectures de documents visibles maximum, principal compris. Inventaire limité à 32 frames ; les frames cachées sont signalées comme omises sans consommer une lecture, y compris depuis 1.1.0 les iframes dimensionnées portant `aria-hidden="true"`. Inventaire ou lectures visibles excédentaires : frame_limit_reached et partial. Durée totale 40 secondes, au plus 10 secondes par frame ; dépassement global typé TIMEOUT. Les frames détachées/non réactives restent indisponibles.
- Par document : 8 000 nœuds visités (y compris cachés/omis), profondeur comptée 32 avec au plus trois enveloppes neutres non décomptées par chemin (profondeur physique absolue 35, body à 0), budget texte de min(160 000, quota de contenu / 8) caractères ; URL puis titre réservent ce budget avant métadonnées et DOM ; valeurs textuelles bornées. Maximum 400 blocs, 300 liens, 100 images/contrôles, 300 options textuelles par select, 20 tables, 50 lignes et 30 cellules par ligne, 30 formulaires. JSON-LD : 10 scripts visités, y compris invalides, 20 000 caractères par script, objets/niveaux/collections bornés ; contenu parsé, jamais exécuté.
- Le crédit concerne uniquement les `div`, `span` et `picture` dont les attributs sont limités à `id`, `class`, `style` et `data-*` (32 attributs maximum). Les éléments éditables, hôtes Shadow ouverts et éléments projetés par un slot sont exclus. Les rôles, attributs ARIA, labels, attributs de langue ou d’interaction interdisent donc le crédit. Chaque branche hérite du crédit déjà consommé sur son chemin ; les branches sœurs ne partagent pas un compteur global. Les enveloppes restent dans le DOM filtré et consomment les budgets de nœuds et de texte habituels. Texte, images, liens, titres, listes, tables, contrôles, racines Shadow et slots ne reçoivent aucun crédit. Toute coupure conserve `depth`, `truncated` et `partial`. La provenance XPath conserve sa borne indépendante de 32 segments : `xpath=null`, `xpath_reason=depth_limit` peut accompagner un contenu récupéré sans omission.
- Au chargement du module structuré, le journal local `pagequay.extraction` reçoit `structured_reader_loaded` avec la version, le schéma et `script_sha256`, empreinte SHA-256 du script effectivement chargé dans `SCRIPT`. Ce diagnostic fixe ne contient ni URL ni donnée de page ; il ne relit pas le fichier lors des extractions.
- Les limites sont signalées ; le quota global `max_content_bytes`, le quota disque et le TTL s'appliquent aussi à l'artefact. Une représentation encore trop volumineuse est refusée par les contrôles d'artefacts habituels.
- Snapshot des éléments montés actuellement : pour une SPA/hydratation, attendre d'abord un sélecteur pertinent ; pour une liste virtualisée ou lazy loading, effectuer les actions explicites nécessaires puis extraire à nouveau. Aucun scroll/clic/chargement infini automatique.
- Le filtrage CSS est heuristique (display/visibility/content-visibility, hidden et aria-hidden). Il ne reconstitue pas la géométrie, l'occlusion, le contenu des pseudo-éléments ni le rendu visuel exact. Les frames sont des snapshots séparés ; la réponse entière n'est pas une capture atomique de tous les documents.
- Le DOM des racines Shadow fermées n’est pas parcouru. Les frames connues du navigateur peuvent être capturées séparément si leur identité est vérifiable, y compris sous un hôte Shadow fermé. Les données internes JavaScript non exposées ne sont pas récupérées. Le DOM ne transforme pas les pixels d'un canvas ou un graphique SVG en données de graphique : utiliser une capture et, si disponible, les données accessibles textuellement. Aucune OCR ou interprétation d'image ajoutée ici.
- Aucun cookie, storage, script/style ni valeur d'input/textarea dans l'arbre. Les valeurs d'attribut value des options sont aussi exclues. L'extraction reste protégée par le projet et son scope ; elle ne résout pas les CAPTCHA.

## Recette

```sh
.venv/bin/pytest tests/test_structured.py tests/test_openapi.py --browser --headed -q
```

La fixture couvre l'hydratation JavaScript, un Shadow DOM ouvert avec slot, une racine fermée, une iframe d'une autre origine (port local distinct), une iframe cachée, une liste imbriquée, les tables HTML et ARIA, les spans, labels et contrôles externes au form, JSON-LD, canvas, valeurs privées omises, limites de profondeur/nœuds/frames et données malformées. Les serveurs locaux sont autorisés uniquement via la dépendance réseau des tests, pas en production.


### Identité des frames sans slot Window — CHG-20261013-028

Une frame Shadow peut ne pas apparaître dans window.frames. Le lecteur exige alors une session CDP liée à cette frame exacte ; DOM.getFrameOwner distingue la racine (propriétaire hors cible) des descendants locaux, sans FrameTree/TargetInfo ni titres/URL transférés. Une racine unique, le propriétaire monté et le même contexte sont vérifiés avant/après capture. Ancêtre/page ou racines absentes/ambiguës refusés. Diagnostic path_source=frame_target_root, failure=target_root_ambiguous ; compteur stale_candidate_count optionnel0..128, absent=inconnu.

La visibilité est contrôlée avant le schéma : frame cachée omitted/hidden_frame sans lire son contenu ; blob visible reste unavailable/unsupported_frame_scheme. Options publiques de select limitées à300 ; dépassement toujours partial/options, valeurs de formulaire exclues. Aucun solver ni transfert d’approbation.

## Blocs JSON-LD vides et classes CSS

Les blocs JSON-LD vides ou blancs sont ignorés après les contrôles de nombre et
longueur. Un bloc non vide mal formé reste signalé invalid_json_ld. Les classes
CSS ne sont lues et bornées que si include_dom=true ; elles ne participent pas
aux collecteurs sémantiques. Les autres budgets et exclusions restent actifs.
Voir les [tests de régression Addverb](../tests/test_structured_addverb_browser.py).
