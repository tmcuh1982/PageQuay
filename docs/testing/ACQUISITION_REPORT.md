# Rapport d’acquisition PageQuay — 12 octobre 2026

[Français](ACQUISITION_REPORT.md) | [English](ACQUISITION_REPORT.en.md)

Demandes : CHG-20261010-004 et diagnostic iframe CHG-20261012-029 fournis par l’utilisateur. Implémentation Python/FastAPI/Playwright, extension additive du contrat 0.2.0, sans dépendance ajoutée. Aucun navigateur client.

## Réalisé

- Navigation principale attestée (URL demandée/finale, HTTP nullable avec motif, Content-Type source, chaîne bornée, UTC et navigation_id), également jointe aux artefacts structurés et aux échecs/attentes de navigation.
- URL exacte opt-in, interception CDP des en-têtes de redirection avant suivi et garde persistante par onglet ; contrôles de navigation/frame avant/après capture et contexte isolé vérifié après lecture.
- Politique publique explicite, HTTPS/443 en mode strict, DNS A/AAAA/proxy à IP validée et refus typés ; trafic des frames enfants refusé en mode strict faute de couverture OOPIF attestée.
- Identifiants projet/clé/onglet réservés au 202, request_id persisté (migration 007), rejeu idempotent de création/navigation, contrôle propriétaire à la fermeture et conservation explicite des onglets d’acquisition après timeout/annulation.
- Robots opt-in borné et user-agent PageQuay déclaré, provenance XPath dérivée du DOM réel, budgets d’artefacts et quotas documentés séparément.
- Causes de frames distinctes, diagnostic borné avec état observé et logs serveur corrélés/expurgés. Ancien reason maintenu. Sélection FRAME_PATH cross-origin/OOPIF vérifiée sans JavaScript appartenant à la page.
- [Contrat détaillé](../ACQUISITION.md), [OpenAPI](../openapi.json) et [client serveur](../../examples/acquire.py) mis à jour. Le client persiste avant création, ne retry pas automatiquement, propose récupération/annulation explicites et n’écrit que des fichiers privés (0600).

## Preuves exécutées

| Cas | Preuve |
| --- | --- |
| Compatibilité des payloads, Bearer, scopes, pagination/idempotence 0.2.0 | Suite HTTP et ancienne recette navigateur complète ; tests search pagination/transport inclus |
| HTTP 200/404, Content-Type principal, sous-ressource 200 ignorée | test_acquisition.py + test_acquisition_browser.py |
| DOM d’erreur sans réponse HTTP : status=null avec motif | Chromium réel : test_error_dom_without_http_response_stays_unknown |
| DOM « Error 500 » réellement servi en 200 | Chromium : statut réellement reçu conservé, aucune interprétation de succès métier |
| Redirections inter-chemins/inter-hôtes avant lecture | Simulation CDP + deux serveurs/routes Chromium : aucun GET de la cible dans le journal de fixture |
| Redirections anciennes autorisées et attestées | Chromium : test_legacy_redirect_chain_is_main_document_evidence |
| Changement de navigation pendant capture, reload à URL identique | Simulation + Chromium : NAVIGATION_CHANGED, aucun artefact stocké |
| CAPTCHA humain, annulation, timeout, onglet conservé | Chromium : état waiting_for_human, timeout avec capture/preuve HTTP, fermeture explicite après drainage |
| DNS privé, mixte, rebinding, IPv6 et URL credentials vides | Tests réseau existants + tests paramétrés des nouvelles causes typées |
| Réponse 202 perdue, même job/onglet retrouvé | HTTP réel ASGI avec navigateur simulé : une seule opération exécutée, IDs et request_id corrélés, conflit de payload 409 |
| Fermeture uniquement par propriétaire | Test du manager avec deux identités distinctes ; contrôles de job existants conservés |
| Robots denied | Chromium via proxy : /robots.txt lu, document refusé jamais demandé ; seul onglet auxiliaire fermé |
| XPath | Chromium : chaque chemin d’une fixture normale résout exactement un nœud ; Shadow DOM porte un motif de null |
| FRAME_PATH d’une autre origine/OOPIF | Chromium : localhost → 127.0.0.1, enfant extrait ; simulation sélectionne le bon contexte parmi plusieurs |
| Timeout / détachement / monde absent / exception JS / taille / schéma | Simulations distinctes avec causes, étapes, durée/budget, is_detached et chaîne d’exceptions expurgée |
| Corrélation diagnostics et absence de fuite de clé | Tests caplog avec secrets injectés, request/job/tab/frame/artifact IDs ; HTTP Bearer absent des résultats/erreurs |
| Cadence moteur vs REST, partiels et continuation | Tests de pagination existants et nouvelle limitation REST : Retry-After/échéance/portée, une seule création |
| Refus strict du trafic enfant | Chromium via injection loopback de test : enfant non demandé, cause typée et export partial=true |

Commandes et résultats :

- `.venv/bin/pytest -q` : **217 passed, 27 skipped** avant les deux derniers cas navigateur (ces deux cas sont ignorés sans --browser).
- `.venv/bin/pytest tests/test_acquisition.py tests/test_openapi.py tests/test_structured.py tests/test_resource_budgets.py --browser -q` : **51 passed**.
- `.venv/bin/pytest tests/test_acquisition_browser.py --browser -q` : **13 passed**, incluant statut inconnu et timeout humain.
- `.venv/bin/ruff check src tests examples`, `ruff format --check`, `node --check` sur les deux lecteurs, `git diff --check` : conformes.
- `.venv/bin/pytest --browser -q -rs` : **241 passed, 1 failed, 4 skipped**. Le seul échec venait du job simulé d’un test d’audit (absence de `kind`) après ajout de la conservation des métadonnées ; le code a été corrigé sans modifier ce test.
- Reprise sur les sources finales : `.venv/bin/pytest tests/test_audit.py tests/test_acquisition_browser.py --browser -q` : **20 passed**, incluant le test d’audit précédemment en échec. **242 tests distincts validés** au total ; aucun échec connu restant.
- Quatre exclusions de la recette globale : minimisation native (`--headed`) et trois recettes de moteurs externes (`--live`). Avertissement Starlette/httpx de dépendance de test, sans échec associé.

Les fixtures autorisent des endpoints loopback/ports éphémères par injection privée. Le cas de refus strict des frames injecte aussi une exemption HTTPS **uniquement dans le test** ; la validation HTTPS/443 de production est testée séparément. Ces tests ne représentent pas des connexions réelles à tous les sites HTTPS publics.

## Service installé

14 fichiers synchronisés dans `~/Library/Application Support/PageQuayService/src/pagequay` après constat de zéro job actif, avec sauvegarde privée des sources et de SQLite sous `/private/tmp/pq-acquisition-backup-jo4wwihi`. Redémarrage LaunchAgent effectué ; hashes des 14 fichiers et migration 007 vérifiés.

Contrôles locaux réels : ready/admin-login 200 ; ready API 200 ; admin sur API 404 ; key-info API sans Bearer 401 ; OpenAPI public contenant expected_url/FrameDiagnostic et aucune route admin. Ni clés, projets, profils ni réglages de ports/Tailscale modifiés. Les onglets en mémoire sont fermés par le redémarrage normal du service ; les anciens IDs de tabs ne sont pas réutilisés.

Dernière synchronisation : les mêmes 14 fichiers, après zéro job actif et sauvegarde privée supplémentaire sous `/private/tmp/pq-acquisition-backup-kfx1trt0`. Elle inclut la conservation des métadonnées d’échec et la compatibilité avec les jobs simulés de l’audit. Hashes des sources finales identiques au runtime ; ready/login/API/isolation/OpenAPI repassés avec les mêmes codes ci-dessus. Le premier backup conserve les sources antérieures à cette extension. Comparaison en lecture seule avec ce backup : tables api_keys, projects et settings identiques. OpenAPI servi identique au JSON du dépôt.

## Limites restantes

- **KUKA réel non reproduit** : le secret Bearer existant `agentderecherche` n’est pas disponible ; la base conserve son hash. Aucune clé créée/remplacée et aucun accès contourné. L’utilisateur a explicitement choisi de livrer sans reproduction KUKA réelle. Aucune clé supplémentaire n’est donc attendue pour cette livraison. La cause des deux exports du 12 octobre reste **UNKNOWN** ; les nouveaux tests OOPIF ne démontrent pas la cause de ce site. Une éventuelle investigation future nécessitera une nouvelle extraction instrumentée et ses logs corrélés ; une simple ligne HTTP ne suffira pas.
- Le mode strict refuse tout trafic de frames enfants ; le mode historique conserve ce trafic public mais ne revendique pas la revalidation DNS à chaque redirect OOPIF dans un tunnel existant. Une couverture OOPIF réseau complète n’est pas livrée sous une attestation trompeuse.
- Cohérence de navigation/frame et contexte isolé vérifiée ; aucune atomicité multi-DOM face aux mutations ordinaires ou garantie de stabilité XPath après mutation. Aucun accès à Shadow DOM fermé, ni transformation de canvas/SVG en données.
- Robots reste opt-in et parser Python borné ; aucune conformité RFC 9309 exhaustive ou preuve de refus extérieur à robots/HTTP. `not_checked` ne constitue jamais une autorisation robots attestée. Un challenge robots passe en attente humaine ; après intervention modifiant le document, une nouvelle acquisition explicite est nécessaire.
- Les logs conservent types/codes/étapes/chaîne de causes, mais retirent intégralement les messages arbitraires et lignes de source. Cela peut limiter le détail d’un bug sans signature connue. Les fichiers LaunchAgent restent soumis à la rotation opérateur.
- Quotas de capacité sans délai prévisible : délai/date null, refus explicite. Un délai d’expiration de stockage n’assure pas que suffisamment d’espace sera libéré. Le téléchargement JSON atteste le fichier généré, pas la vérité du contenu de la page.
- Les tests de moteurs externes et de minimisation native nécessitent leur recette distincte ; aucune validation live externe/KUKA ou minimisation macOS n’est déduite des fixtures. Déploiement local vérifié ; aucune revendication de déploiement distant ou de validation de l’environnement d’UniversRobot.
