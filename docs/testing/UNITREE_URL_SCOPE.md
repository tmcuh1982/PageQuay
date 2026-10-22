# Unitree G1 — URL exacte et réécriture différée

Diagnostic du 23 octobre 2026 (Europe/Warsaw), mesures UTC du 22 octobre à partir de
21:59. Source de travail PageQuay 1.2.1, instance jetable, profils neufs et clés de test
éphémères. Aucun appel à UniversRobot, changement de données, d'approbation ou de
configuration du service installé. Les reproductions précèdent la publication 1.2.2 ; le service installé a ensuite été
mis à jour et redémarré le 23 octobre 2026, à la demande de l’utilisateur.

## Cause démontrée

Deux mécanismes réels et opposés :

1. GET HTTPS `/operate/g1` répond **302 Location: /operate/g1/**, puis **200**.
2. GET HTTPS `/operate/g1/` répond directement **200**.
3. Après chargement, le site utilise History API, d'abord à URL identique, puis retire
   réellement le slash. Chromium émet `Page.navigatedWithinDocument` avec
   `navigationType=historyApi`. Aucun nouveau GET principal n'est nécessaire.

La suppression différée a été observée environ 5 à 7 secondes après les premiers
événements History API, pas à une échéance garantie. L'adresse finale varie donc selon
le moment du contrôle. Les reproductions en Chromium headless et graphique ont toutes
deux montré ce comportement. Ce n'est pas une normalisation effectuée par PageQuay.

Conséquences : l'attente avec slash peut passer immédiatement puis être refusée plus
tard ; l'attente sans slash est refusée immédiatement après le 302 et peut correspondre
plus tard après la réécriture. Cela explique aussi la lecture consultative ultérieure
sans slash. **Aucune assimilation des deux chemins n'est correcte.** Une navigation ou
un export conforme à un instant ne garantit pas que le prochain contrôle le sera.
Le client doit continuer à arrêter toute acquisition dont un contrôle échoue.

## Mesures finales, variantes séparées

La [trace JSON](UNITREE_URL_SCOPE_TRACE.json) conserve les réponses HTTP directes,
les événements CDP horodatés, tab_info avant/après, les jobs et les métadonnées des
artefacts. Les corps des pages et les clés ne sont pas conservés. Les IDs appartiennent
à l'instance jetable désormais supprimée, pas au service installé.

| Attente indépendante | tab_info initial | History API retirant le slash (UTC) | Exports après observation de 10 s, même attente |
|---|---|---|---|
| `https://www.unitree.com/operate/g1/` | avec slash | 22:05:41.295799 | structured et HTML : `scope_changed`, avant capture |
| `https://www.unitree.com/operate/g1` | avec slash après 302 | 22:05:53.777382 | structured et HTML réussis, URL sans slash |
| `https://www.unitree.com/g1/` — cas historique distinct | avec slash, HTTP 200 | 22:06:11.298755 | structured et HTML : `scope_changed`, avant capture |

Le cas historique a donc été **nouvellement retesté ici**, indépendamment des deux
variantes `/operate/g1`. Les observations anciennes ne sont pas présentées comme une
recette récente.

Détail important sur la première variante : le premier export structured de la dernière
recette a été invalidé par `NAVIGATION_CHANGED`, à `export.structured.metadata`, alors
que l'URL était encore identique : un appel History API identique est intervenu pendant
la capture. Le HTML suivant a réussi avec slash ; après la réécriture, les deux exports
ont été refusés. Une recette précédente avait permis les deux exports immédiats avec
slash, `schema_version=1.0`, `partial=false`, `truncated=false`,
`frame_limit_reached=false`. Ce résultat dépend du timing, sans promesse de stabilité.

Sur la seconde variante, les deux exports immédiats sont refusés avec
`expected_url=.../operate/g1`, `observed_url=.../operate/g1/`, avant lecture métier.
Les deux exports tardifs réussissent en conservant **l'attente originale sans slash**.
Le structured tardif contient l'URL sans slash et les trois indicateurs à false,
schema 1.0. Aucune destination observée n'est adoptée comme nouvelle attente.

Exemple concret de refus final avec slash :

- `expected_url`: `https://www.unitree.com/operate/g1/`
- `observed_url`: `https://www.unitree.com/operate/g1`
- `stage`: `export.structured.before_capture`
- tab : `dcd2b76982722eb158e481ba8d7c22b0`
- job : `43f568de99adf29833d2c4087e257aca`
- artifact : null (pas de capture allouée/publiée)

Exemple de succès tardif sans slash : tab `680dcc00a9b836412db83917eade24c4`,
structured job `3ec4d585bb4059217f847ca87fb767a4`, artifact
`de64206d53fffb018b42ef9b1f7c280e` ; HTML job
`13a16a4d3a9e8ab7bbfebe4502ac2480`, artifact `62fba45d2103c07d82d77b868df3c70b`.
Les horodatages précis et request IDs sont dans la trace jointe.

## Recoupement du créneau d'échec fourni

Lecture SQLite en mode `ro` de PageQuay, sans modification : job de navigation
`93c32a931c94be3a2ab167bb1ba26731`, onglet
`163adf9a5d235627a7fb45f2c4bb3888`, `status=completed`, URL demandée sans slash,
chaîne 302 vers l'URL avec slash ; commit observé
`2026-10-22T21:43:18.651572+00:00`, finale avec slash.
Aucun job d'extraction n'est enregistré pour cet onglet dans la base consultée.

Cela indique un refus probablement lors du précontrôle du client, avant soumission
d'un export, et non un job structured/HTML échoué pour cet onglet. L'attribution exacte
au code client `RedirectScopeChanged` reste une inférence : ses logs et la réponse
`tab_info` de cet instant ne sont pas disponibles ici. Le job historique n'enregistre
pas de version de service ; la version des fichiers installés consultés est 1.2.1,
ce qui ne prouve pas à elle seule celle exécutée à 21:43. Les nouvelles traces rendent
les refus pendant les exports directement identifiables.

## Corrections PageQuay

- `src/pagequay/navigation.py` : conservation bornée de la réponse HTTP principale
  commise, distincte de l'URL courante ; chronologie de commits et événements CDP
  History API du seul document principal, plafonds de 20 avec saturation signalée ;
  enrichissement des erreurs avec attente, observation, étape, heure et corrélations.
  Le statut HTTP historique peut rester inconnu après History API : aucune réponse
  HTTP n'est inventée pour le nouveau chemin.
- `src/pagequay/browser.py` et `api.py` : contrôle de cohérence de tab_info autour de
  la lecture du titre, étapes explicites de navigation/export, refus de publier un
  structured dont l'URL propre diverge du checkpoint. L'artefact alloué puis jeté
  est distingué d'un artefact publié.
- `src/pagequay/extraction.js` et `structured.py` : identité URL bornée à 4096 comme
  l'API, au lieu de 2048 ; pas de substitution par l'URL demandée. Un test avec query
  supérieure à 2048 caractères vérifie cette cohérence.
- `src/pagequay/models.py`, `docs/openapi.json`, `docs/NAVIGATION_SCOPE.md` : contrat
  additif de preuve et diagnostics. `schema_version` structured reste 1.0.
- `examples/probe_url_scope.py` : reproduction jetable de chaque attente, HTTP direct,
  événements CDP, exports immédiats/tardifs et preuve des artefacts ; échecs de
  précontrôle conservés. Les exports diagnostiques négatifs ne sont pas une recette
  de reprise automatique destinée au client métier.
- `.gitignore` : exceptions limitées aux deux rapports Unitree vérifiés, sans clé,
  cookie, adresse privée ou contenu de page capturé.
- Tests : `tests/test_acquisition.py`, `tests/test_acquisition_browser.py`,
  `tests/test_navigation_title.py` ; rapport et trace dans `docs/testing/`.

Le retrait du slash est réel : le corriger en acceptant les deux chemins affaiblirait
le contrôle. Le correctif porte sur les défauts démontrés d'observabilité, la disparition
de preuve HTTP, le risque d'assembler URL et titre de deux navigations, et la cohérence
des métadonnées d'export. Il ne promet pas de rendre acquérable une URL devenue différente.

## Validation et reproduction

```sh
.venv/bin/pytest --browser -q tests/test_acquisition_browser.py tests/test_acquisition.py tests/test_navigation_title.py tests/test_navigation_diagnostics.py tests/test_openapi.py
.venv/bin/pytest -q
PYTHONPATH=src .venv/bin/python examples/probe_url_scope.py --output /tmp/unitree.json --observe-seconds 10
# Comparaison graphique, toujours dans un profil jetable :
PYTHONPATH=src .venv/bin/python examples/probe_url_scope.py --output /tmp/unitree-headed.json --headed --observe-seconds 10
```

Les tests locaux ne dépendent pas de Unitree : serveur HTTP loopback, 302 ajoutant un
slash ; `history.replaceState` retirant un slash ; domaine, chemin et query changeant
pendant chacun des deux exports ; reload à URL identique ; cohérence tab_info/structured/
HTML ; identité structured incohérente rejetée ; titre lu pendant un changement rejeté ;
trace CDP limitée à la frame principale et bornée ; preuve HTTP invalidée à la nouvelle
requête. La permission HTTPS du serveur local est injectée uniquement dans les tests,
comme dans les tests d'acquisition existants ; aucun garde de production n'est désactivé.

Résultats : **93 tests ciblés avec Chromium réussis**, puis **350 tests généraux
réussis, 157 ignorés** (marqueurs navigateur/live non activés dans la suite générale).
Un test unitaire supplémentaire de bornes CDP, ajouté après la passe Chromium, est
compris dans les 350 ; les tests unitaires acquisition/titre ont aussi passé 42/42.
Ruff sur les fichiers Python modifiés et `git diff --check` passent.
Une première exécution générale sous sandbox avait échoué sur les ouvertures de
sockets loopback ; la même suite, exécutée avec cette capacité, passe. L'avertissement
Starlette/httpx préexistant est sans effet sur ces résultats.

Le scénario d'extraction après mismatch vérifie aussi l'héritage de l'attente initiale
lorsque le paramètre est omis : aucun transfert d'approbation. Les gardes DNS/IP/HTTPS,
les refus de redirection explicites et le traitement des challenges restent actifs.

## Contrat client

Conserver la séquence UniversRobot et ses contrôles exacts. Accepter les nouveaux champs
optionnels de `NavigationMetadata` si le parseur client est strict. Préserver les détails
d'erreur pour afficher destination et étape plutôt que le seul `RedirectScopeChanged`.
Pour une erreur locale de précontrôle tab_info, le client doit produire lui-même l'attente,
l'observation, l'heure et l'étape : aucun export n'a alors été demandé au serveur.

Le structured natif porte l'URL principale dans `url` à la racine ; `document.url`
est le nom éventuel dans une enveloppe client. Le HTML brut ne contient pas de champ
PageQuay d'identité : sa preuve est `result.navigation.final_url` du job, persistée avec
celui-ci. Une canonical du site n'est pas une URL observée. Pas de nouveau schéma requis,
ni modification d'approbation ou de code UniversRobot effectuée dans ce travail.


## Installation et publication 1.2.2 — 23 octobre 2026

Version du dépôt, du package et du runtime alignée sur 1.2.2. Aucun job actif avant
arrêt. Copie des fichiers modifiés dans le runtime PageQuayService, après sauvegarde
privée des fichiers précédents et snapshot SQLite. Réinstallation editable de PageQuay
seul, sans dépendances, puis bootout/bootstrap du LaunchAgent utilisateur.

Vérifications après redémarrage : disponibilité API 8787 et console 8767 (HTTP 200),
login administrateur sur 8767 (200), login administrateur sur API 8787 (404), accès
key-info sans Bearer (401), contrat OpenAPI installé exactement égal au dépôt avec
version 1.2.2. Empreintes des neuf fichiers runtime déployés conformes au dépôt ;
versions des autres distributions inchangées. Aucun réglage de ports, Tailscale,
clé, profil, données métier ou approbation UniversRobot modifié.

Le correctif et ses preuves sont publiés dans le commit de release 1.2.2, avec wheel,
archive source et sommes SHA-256. Les traces JSON conservent volontairement la version
1.2.1 de l'instance de travail qui a produit ces mesures avant la préparation de release.
