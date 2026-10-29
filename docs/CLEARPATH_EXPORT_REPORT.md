# Export Clearpath corrigé côté PageQuay — TODO-401

CHG-20261027-951, vérification 2026-10-27T10:19:13+01:00, Codex/main.
URL exactement approuvée : https://clearpathrobotics.com/husky-a300-unmanned-ground-vehicle-robot/.
Source a2491aa1-5f12-51b8-8685-52c2ed8c1c2b, accord explicite enregistré
df3eed9d-ef79-4ffb-b63b-efb238ccb75d. Aucun modèle Husky fusionné.

## Cause et adaptation

Ancien export : principal et trois vidéos entièrement lus, mais quatrième vidéo
visible absente. MAX_FRAMES=4 incluait le principal ; partial=true,
truncated=true, frame_limit_reached=true, truncation_reasons=[] ; deux frames
cachées omises ne consommaient aucun slot. Ce n’est ni un défaut de profondeur,
ni une frame détachée, ni un refus réseau dans l’artefact observé.

Le producteur structured.py autorise désormais huit documents visibles, principal
compris. Le neuvième rend toujours l’export partiel. Délai global40s,10s/frame,
inventaire32, limites existantes de texte/octets, exclusions cachées/ARIA,
permissions et contrôles de portée inchangés. Les troncatures internes d’une frame
et les inventaires excessifs restent refusés ; aucune acceptation de partial
n’a été ajoutée au client. Le budget chargé est journalisé sans contenu privé.

## Reproduction avant correction — D-146

Ancien job5bdf45202228688a0fede3fdb6839a86,tabc274201708076dc28a0fb4cd103926a3,
request510a19db3c43179e5ce5161e,artifact75b25119e2a5f969dd1385e3818ae9aa.
27octobre2026 vers09:45Europe/Warsaw : navigation exacteHTTP200,
partial_content/validation côté consommateur. Le quatrième lecteur YouTube
vH9O9zhKPdc n’était pas dans les frames exportées. Le test de régression
principal+4vidéos+2cachées reproduit le refus avant modification du plafond.

Prérequis : PageQuay1.2.4 configuré, accord exact et robotsallowed, même URL.
Sur onglet possédé, tab_info doit confirmer l’URL exacte ; appeler extract
structured(expected_url=URL), télécharger et valider strictement, puis extract
html(expected_url=URL), télécharger et revérifier tab_info. Fermer seulement cet
onglet. Aucun clic, scroll, nouvelle destination ou repli automatique nécessaire.
Attendu : quatre vidéos complètes et drapeaux tousfalse ; ancien observé : trois
vidéos puis limite. L’ancienne copie reste rejetée par le validateur après patch.

## Installation et contrôles

Dépôt producteur : /Users/lolo/Documents/Codex/PageQuay, HEAD
ccbf6a43d36edd17439b21e6ae7050873f3026af ; version1.2.4 inchangée, patch identifié
par empreintes. Runtime : /Users/lolo/Library/Application Support/PageQuayService.
Seul fichier installé : src/pagequay/structured.py, SHA avant
b8484d164410a783e3d038ce9a26def210d0da739da2b8e69a692429e5605792,
SHA final 437859261728d71f5c72cfdf0370caf887b555757935ed6636deb1ce1a47fe20.
Deux mises en place (fonctionnelle puis formatée) après deux sondes sans jobs
queued/running/waiting_for_human, sauvegardes privées, SIGTERM supervisé,
ready200 et budget8 chargé. Aucun job actif interrompu. Browser/API/JS/règles
réseau conservés par SHA ; aucun service, secret, profil ou droit nouveau.

Tests :9unitaires/contrats,45Chromium, Ruff et diff --check conformes. Cas positifs
quatrevidéos et huitdocuments ; cas négatifs neuvièmedocument, texte enfant tronqué,
inventaire33, profondeur/exclusionsARIA et cas Addverb/Greenfield. Un avertissement
Starlette/httpx tiers préexistant, sans rapport avec le patch. Fixtures JSON
générées par la recette restituées à leurs octets antérieurs. Aucun commit/push.

## Résultat réel sans repli

Lot métier PageQuay seul16fd3fcf-d6b6-47b4-8a12-d17f72eba305 :1réussite,0échec,
0tentative de pageScrapy/Crawl4AI (précontrôle robots distinct). Copie
5eca703c-7325-49fe-a6c9-2b3bebf4ea1c, pagequay-rendered-content/9,
HTML239991octets, SHAe4e80ea3ac85353a24cfb03ca61aaba1a5c49a69f21294c381dc53053c7636b0,
conforme en SQL et sur disque. Aucune inférence ni fusion ; robot_model inchangé.

Sur la version finale chargée, seconde lecture directe de confirmation :
structuredcaptured_at=2026-10-27T09:15:59.653656+00:00, quatreenfantsextracted(f3–f6),
f1/f2cachéesomises ; partial=false,truncated=false,frame_limit_reached=false,
raisons=[],aucuneframeunavailable,aucunrefusréseau dans l’artefact importé.
Structured : job14d77499d32445cd0d06213d0c3eb102,requestd0b57edafcfca9a130157762,
artifact9d8da0950afd75e384aa912bfa1edfc4.
HTML : job1909437b342a4cf151270ab865ffd320,request778fa30ee11fd791dd55e1fb,
artifactfcc2ba9153604deb0394fb96ce0bd193,238799octets.
Onglet commun89f9f70ff9ce433f628348c46577ff1d, fermé après vérification de l’URL exacte.

## Limites conservées

Contenu DOM monté seulement, pas de scrolling ou action automatique. Plafond8
fini : pages plus complexes restent partielles et refusées ; budget total40s
inchangé. Réseau enfant legacy_public_proxy existant, limitations d’attestation
OOPIF inchangées ; aucun mode strict ni nouvelle garantie activé par ce patch.
Cette réussite ne qualifie pas tous les sites. DENSO reste ouvert dansTODO-401,
ancienne sourceHusky non fusionnée ni suspendue implicitement. Preuves privées
UniversRobot var/diagnostics/clearpath-pagequay-export/ ; scripts de méthode,
artefacts avant/après, tests, hashes et déploiements y sont conservés.
