# État de PageQuay — 20 octobre 2026

[Français](STATUS.md) | [English](STATUS.en.md)

Version courante : **1.2.1**, récupération bornée des enveloppes DOM ; [notes](releases/1.2.1.md). Suite générale 347 réussis ; Chromium ciblé 29 réussis. Service installé et redémarré : OpenAPI exact, empreinte du script chargé, readiness et frontières admin/API vérifiés ; réglages persistants et versions des autres distributions conservés. Release [v1.2.1](https://github.com/tmcuh1982/PageQuay/releases/tag/v1.2.1), avec wheel, archive source et SHA256SUMS.

Historique 1.2.0 : **1.2.0**, GIF explicite et originaux jusqu’à 20 Mo ; [notes](releases/1.2.0.md). Validation : 343 réussis/123 ignorés, suite Chromium ciblée 164 réussis. Recette Dobot et publication encore distinctes. Service 1.2.0 déployé et relancé sur accord explicite ; OpenAPI 20 Mo/GIF vérifié en local et via HTTPS privé 8443, données et dépendances conservées.

Release publique précédente **1.1.0**, publiée sous [v1.1.0](https://github.com/tmcuh1982/PageQuay/releases/tag/v1.1.0), commit source 11ce7dd. Le wheel, l’archive source et SHA256SUMS ont été retéléchargés et comparés aux fichiers construits. La publication n’a ni déployé ni redémarré le service installé. Le déploiement et les recettes Google depuis un autre appareil, ACL Tailscale et restauration complète restent distincts de la publication des sources.

## Fonctionnalités livrées

- Administration locale française, projets/profils Chromium persistants isolés, sessions admin et clés API à scopes. Documentation française et anglaise ; l’interface reste en français.
- Ports administrateur/API locaux distincts et configurables, port HTTPS global via Tailscale Serve privé. Ports locaux actifs/en attente séparés et redémarrage requis ; modification Serve immédiate.
- Modification du nom, des droits, du quota et de l’expiration des clés sans changer secret/projet ; informations de la clé appelante et solde de sa fenêtre.
- REST/WebSocket, jobs asynchrones bornés, navigation/actions, captures et artifacts temporaires protégés.
- Adaptateurs Google/DuckDuckGo/Brave et reprise humaine ; continuations natives DuckDuckGo, quotas, idempotence, nettoyage des onglets et client ProjectX ; filtres région/période persistants.
- Minimisation/restauration et démarrage minimisé ; nouveaux onglets conservant cet état.
- Extraction du DOM rendu texte/HTML/liens/métadonnées/JSON structuré, arbre filtré optionnel, Shadow DOM ouvert et documents iframe bornés avec indication des partiels. Les iframes dimensionnées aria-hidden sont omises sans consommer une lecture.
- Images originales JPEG/PNG/WebP et GIF sur demande explicite, jusqu’à 20 Mo, acquises par le navigateur, URL finale exacte, taille/délai bornés, SHA-256 et artifact binaire privé.
- Proxy DNS/IP validée, refus des destinations privées et des WebSockets de pages, quotas/rétention et reset manuel confirmé.

Contrats : [OpenAPI](openapi.json), [recherche](SEARCH_API.md), [extraction](EXTRACTION.md), [images](DOWNLOAD_IMAGE.md), [architecture](ARCHITECTURE.md).

## Vérifications récentes

| Contrôle | Résultat observé |
| --- | --- |
| Suite générale 1.1.0 | 292 réussis, 96 ignorés ; dépréciation Starlette/httpx existante |
| Chromium réel ciblé | 72 réussis : images/client/acquisition/challenges/WebSocket natif/frames cachées |
| Ruff/format/lock/diff | Fichiers Python modifiés conformes, synchronisation verrouillée offline et diff-check réussis |
| Fichiers de release | Construits depuis le commit ; trois fichiers publiés identiques aux fichiers locaux |
| Recette image réelle du 15 octobre | Service jetable : JPEG UBTECH original de 689381 octets, SHA-256 vérifié ; aucune preuve de déploiement client installé |

Les suites se recouvrent : leurs nombres ne s’additionnent pas. Les fixtures ne prouvent pas la disponibilité des moteurs. Les pages virtualisées exigent des actions explicites ; les racines Shadow fermées, l’état JavaScript non exposé et les données seulement visuelles ne deviennent pas accessibles par simple export DOM. Aucun CAPTCHA résolu automatiquement.

## Historique de publication et déploiement

Le premier push complet a fait avancer main de 5e85c7b à ad0c861 sans réécriture. GitHub CLI a été utilisé après le refus 403 du connecteur ; les credentials restent hors dépôt. Publier les sources n’expose ni le service ni les profils. Captures, diagnostics bruts, environnements, bases et clés restent privés ; seuls les rapports relus et JSON de fixtures sont versionnés.

Le lot initial 0.2 comprenait fenêtres, séparation admin/API, modification des clés et continuations. Les filtres région/période étaient additifs (migration 004), sans succès de recherche filtrée réelle revendiqué. Livraisons suivantes :

- KUKA 0.2.1 : WORLD_NOT_FOUND reproduit/corrigé par slots natifs isolés et target CDP propriétaire. URL finale exacte, 69 blocs, f1 extracted, partial=false/truncated=false ; player sans texte monté. 249 tests réussis/4 ignorés puis 33 ciblés après ajustement final d’inventaire. Sources/paquet/schéma installés vérifiés ; recette privée UniversRobot distincte.
- Navigation 0.2.2 : séparation redirections/challenges/portée, refus strict des sous-frames conservé, égalité OpenAPI public testée. 265 réussis/4 ignorés et sous-ensembles finaux recouvrants. Aucun CAPTCHA réel résolu ; clés/projets/réglages préservés.
- AgXeed/OnRobot : candidats CDP périmés, cohérence du titre, widgets CAPTCHA, réservation du budget identité et target exact des frames Shadow. Voir [lecture AgXeed](AGXEED_READ_FIX.md), [export](AGXEED_EXPORT_FIX.md), [CAPTCHA](CAPTCHA_WIDGET_FIX.md), [OnRobot](ONROBOT_FRAME_FIX.md).
- Transport 0.2.4/v1.0.0 : constructeur WebSocket natif conservé, ws/wss refusés avant DNS. Suite de base 343 réussis/4 ignorés ; six tests de contrat du passage à v1 réussis. Recherches et navigations Music Store HTTP 200 dans Chrome/Chromium neufs puis une session Chromium conservée ; premier clic Fender expiré. Preuve de session/site, aucune garantie future. Métadonnées du service encore 0.2.2 à cette étape historique.
- 1.0.1 : ports admin/API configurables séparément, 276 réussis/74 ignorés ; vérifications installées login/API/HTTPS Tailscale depuis le même Mac réussies, sans nouvelle recette depuis un autre appareil. [Notes](releases/1.0.1.md).

Les essais historiques et recettes restantes sont dans [le rapport](testing/REPORT.md). Les chemins de backups/logs historiques désignent des preuves privées, pas des fichiers distribués ni des garanties d’endpoint actuel. Pour les prochaines modifications, [publier puis vérifier](PUBLISHING.md) le commit et le contenu distants avant d’annoncer la synchronisation.
