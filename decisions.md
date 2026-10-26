# Décisions — PageQuay (PQ)

## D001 — Nom et sources (2026-10-09)

PageQuay/PQ remplace Home Browser Gateway/HBG dans l'application. Les documents sources restent intacts dans `docs/definition/` pour conserver la traçabilité.

## D002 — Application locale Python

FastAPI, Jinja2, JavaScript/CSS locaux et Playwright ; un seul processus Uvicorn, sans worker distribué ni CDN. L'écoute est imposée à `127.0.0.1` par les scripts. Les profils nécessitent la session graphique de l'utilisateur en mode visible.

## D003 — SQLite et migrations SQL

SQLite via la bibliothèque standard et migrations SQL numérotées, transactions explicites, WAL et clés étrangères. Cela réduit les dépendances et rend les contrôles de propriété visibles dans les requêtes. Écart assumé par rapport au souhait SQLAlchemy/Alembic : aucun ORM ni Alembic dans ce MVP ; migrations versionnées réellement appliquées.

## D004 — Identifiants et secrets

IDs opaques générés côté serveur. Clés API de 256 bits aléatoires, SHA-256 stocké, comparaison constante ; cette entropie rend inutile un hash lent conçu pour les mots de passe. Mot de passe administrateur Argon2id ; sessions serveur et CSRF. Aucun compte ou secret par défaut.

## D005 — Réseau du navigateur

Validation des URL et sous-requêtes, plus proxy local propre à chaque profil : résolution DNS vérifiée puis connexion à l'IP validée pour empêcher le rebinding entre validation et connexion. Les tunnels HTTPS conservent la vérification TLS du navigateur. Service workers, téléchargements et WebSockets distants sont bloqués par défaut. Les limites OS/Chromium seront documentées ; aucune promesse de confinement OS complet.

## D006 — Tests hors services tiers

La recette sécurité utilise des fixtures et un serveur local de test explicitement autorisé seulement dans les tests. Les tests de navigateur réel sont séparés ; les moteurs tiers sont essayés sans contournement et leurs blocages sont rapportés honnêtement.

## D007 — Effacement du profil uniquement manuel dans le MVP

Le reset destructeur nécessite une intention serveur éphémère liée à la session et au projet, le slug saisi et l'acquittement de la perte des données. Aucun reset automatique ni snapshot de session dans cette version. Le réglage d'effacement automatique est refusé plutôt que présenté comme une option opérationnelle.

## D008 — Authentification WebSocket sans secret dans l'URL

Ticket de 30 secondes à usage unique obtenu par REST Bearer. Envoyé dans le premier message WebSocket sous cinq secondes ; origine contrôlée, durée de connexion limitée, révocation revalidée chaque seconde. Aucun ticket ni clé longue durée dans les URLs. Les scripts désactivent les access logs.

## D009 — Formulaires natifs et Referrer-Policy

`same-origin` empêche la transmission du referrer à un autre site et conserve une origine exploitable pour les formulaires natifs. Le test Chromium réel a montré que `no-referrer` produit `Origin: null` au login ; les contrôles d'origine restent stricts, ils ne sont pas relâchés pour accepter `null`.

## D010 — Fermeture des sockets Python 3.14

Fermer l'écoute, annuler/drainer les handlers du proxy, puis attendre `server.wait_closed()`. Attendre le serveur avant de fermer ses connexions actives peut bloquer la fermeture en Python 3.14. Une recette avec client inactif couvre ce comportement.

## D011 — Un service par dossier de données

Flock de service avant initialisation des jobs : interdit qu'une deuxième instance marque les jobs du premier service comme interrompus. Verrou de profil distinct. Le noyau libère les verrous après mort du processus ; l'annulation de lancement ferme le proxy et libère son verrou.

## D012 — Réglages et limites du MVP

JSON strict validé, valeurs effectives et origine Global/Projet visibles. Listes réseau répercutées aux contextes actifs, options de lancement au redémarrage. Concurrence navigateurs/jobs globale. Pas de LAN/uploads/downloads, métrique RAM approximative ou chiffrement prétendu. Rotation manuelle des logs fichiers LaunchAgent ; purge automatique audit/artefacts.

## D013 — Recette extérieure honnête

DDG a présenté un challenge d'images le 9 octobre. Détection vérifiée sans résolution. Le test de diagnostic rapportant ce blocage ne vaut pas recherche réussie ; rapport distinguant les 47 tests locaux et la recherche restant bloquée.

## D014 — Origine du client et blocage Google (10 octobre 2026)

Le client ASGI sur Mac mini valide l'API et le navigateur local, sans valider un trajet depuis le MacBook Air. La connexion SSH au peer Air étant refusée, ce trajet reste explicitement non testé. Un client HTTP autonome rapporte son hostname et distingue recherche réussie et contenu effectivement téléchargé.

La page Google française de trafic exceptionnel avait été classée UPSTREAM_CHANGED. L'URL Google `/sorry/` et le message français sont désormais reconnus comme challenge humain, même avant chargement de l'iframe CAPTCHA. Le nouvel essai a émis challenge.required ; aucune résolution automatique ni tentative de contournement. Les attentes humaines de diagnostics jetables sont limitées à cinq secondes ; le service garde son budget habituel.

## D015 — Recette Air → mini par SSH existant

L'utilisateur confirme `ssh macmini-codex` depuis l'Air vers le mini. Ce sens permet un forward local ; aucun SSH entrant sur l'Air n'est nécessaire. La tentative précédente de joindre l'Air ne valide pas ce trajet.

La recette utilise un serveur PQ temporaire sur loopback 18766 et un tunnel SSH limité au loopback client. Dossier de données isolé, clé et durée de service limités à 15 minutes ; fermeture en fin de test et suppression du profil. Le client standard Python s'exécute sur l'Air, rapporte son hostname et recopie le résultat sur le mini. Le mode `--human` propose une reprise uniquement après intervention de l'utilisateur sur le Chromium du mini. Aucun service permanent, accès système, Serve ni Funnel ajouté. La vérification HTTP locale et l'extraction publique directe sont réussies ; la commande Air reste à exécuter.

## D016 — JSON structuré du DOM rendu, arbre en option

Demandé et autorisé le 10 octobre. `format=structured` produit un contrat versionné 1.0 via un script Playwright fixe en lecture, sans dépendance d'extraction supplémentaire. Le DOM rendu est nécessaire pour la visibilité, les composants Shadow DOM ouverts et les iframes ; la fixture démontre les pertes du HTML sérialisé ordinaire. Le JSON donne les blocs sémantiques et collections nécessaires à la lecture ; `include_dom=true` joint l'arbre filtré pour les relations et composants personnalisés. Le compact fait 5 593 octets, contre 12 390 avec arbre sur la fixture : aucun arbre volumineux imposé au client.

Quatre documents maximum, collecte bornée par nœuds/profondeur/texte/collections et délais, quotas d'artefacts conservés. La limite de nœuds compte aussi les éléments omis/cachés pour borner le travail. Les valeurs des champs, scripts/styles et éléments cachés sont exclus ; JSON-LD parsé uniquement. Frames indisponibles et résultats partiels signalés. Pas d'auto-clic/scroll ni d'extraction d'état JavaScript interne, de closed shadow ou de données graphiques à partir de pixels. Les attentes/interactions restent des actions séparées autorisées, les captures gardent leur scope distinct.

Routes/anciens formats compatibles. Les clients SSH peuvent demander structured et DOM, contenu `.content.json` distinct du rapport. Contrat détaillé, limites et sources primaires dans `docs/EXTRACTION.md` ; recette Chromium et HTTP public réelle consignées dans le rapport de tests.

## D017 — Publication GitHub (10 octobre 2026)

Publication demandée sous `tmcuh1982`. Le dépôt existant `https://github.com/tmcuh1982/PageQuay` est public, avec un commit initial README sur `main` ; cet historique est conservé, sans push forcé. Identité de commit : compte GitHub vérifié, adresse noreply. Les sources, tests, lockfile et documents de suivi sont versionnés.

Les secrets, environnements, bases, profils, sauvegardes et diagnostics/captures locaux sont exclus par `.gitignore`. Les exemples JSON issus de la fixture restent publiables ; le rapport conserve les résultats des diagnostics exclus. Les détails personnels du réseau et chemins utilisateurs ont été retirés des documents publics. Le client SSH accepte `--remote-root` avec un chemin par défaut relatif au home distant, pour éviter un chemin utilisateur figé.

L'utilisateur a ensuite explicitement confirmé **« Publier dans le dépôt public existant »**, levant le refus initial lié à la visibilité. Le terminal n'ayant pas d'identifiants HTTPS, la publication utilise la connexion GitHub de l'application, puis Git récupère les commits publics pour aligner le dossier local. Aucun identifiant terminal ni secret n'est créé ou copié.

État avant la connexion CLI décrite en D019 : nouvelle tentative autorisée refusée par GitHub (**403 Resource not accessible by integration**), aucune installation/account d'application détecté par le connecteur. Publication alors non effectuée ; reconfiguration de la connexion avec accès au dépôt requise. La confirmation publique restait acquise, le blocage concernait uniquement l'accès technique GitHub.

## D018 — Documentation locale et distante cohérente (10 octobre 2026)

À la demande de l'utilisateur, le README devient le point d'entrée vers architecture, extraction, exploitation, tests et suivi. `docs/STATUS.md` distingue fonctionnalités livrées, tests exécutés, recette distante non effectuée et état de publication. `docs/PUBLISHING.md` décrit les accès et contrôles nécessaires pour synchroniser les documents et les sources, sans assimiler une mise à jour documentaire à un déploiement du service.

La mise à jour du README distant est tentée par l'API Contents avec son SHA courant ; GitHub refuse aussi cette voie avec 403. Conserver et versionner la documentation locale prête, sans annoncer une mise à jour GitHub non effectuée. Une fois l'accès opérationnel, publier les documents liés ensemble et vérifier leur contenu distant.

## D019 — Publication par GitHub CLI après authentification directe (10 octobre 2026)

La reconfiguration du plugin n'a pas levé le refus 403. Installer le client GitHub officiel puis effectuer sa connexion par code navigateur, validée par l'utilisateur sous `tmcuh1982`, fournit l'accès en écriture nécessaire. Le helper de credentials est configuré uniquement dans le dépôt PageQuay, sans token dans les arguments, sources ou documents.

Push Git normal réussi : historique initial et commits locaux conservés ; code et documentation publiés ensemble sur `main`. Le statut bloqué dans les documents est remplacé par le résultat observé. GitHub CLI a stocké ses identifiants hors du dépôt dans un fichier privé 0600, plutôt que dans le stockage système sécurisé. Les futurs pushes peuvent utiliser cette connexion ; la visibilité publique ne nécessite aucune nouvelle confirmation.

## 10 octobre — console locale, API Tailscale sur une socket distincte

L’utilisateur exclut l’administration du tailnet. Deux sockets loopback (8765 console, 8766 API) partagent le processus/runtime pour conserver les mêmes profils, jobs et limites. Le port réel fourni par Uvicorn détermine le filtrage de routes, sans confiance dans Host ou les headers proxy. Tailscale Serve doit viser 8766 uniquement. Cookies et origines admin adaptés au HTTP loopback. Déploiement dans une copie privée hors Documents pour éviter le refus d’accès macOS au LaunchAgent ; mise à jour de cette copie requise lors des futurs déploiements.

### Formulaires de connexion périmés

Conserver le nonce de login pendant les ouvertures successives de la page pour éviter qu’un onglet invalide un autre. Utiliser un cookie distinct du cookie legacy après passage HTTPS→HTTP local. Un nonce absent/incohérent n’authentifie jamais : retour 403 avec formulaire récupérable et message français ; une origine étrangère reste une erreur CSRF.

### Clés modifiables sans rotation

Autoriser l’opérateur local à changer les réglages de sécurité d’une clé existante sans remplacer son secret. Préserver le projet et la révocation, garder le compteur de quota pour appliquer une réduction dès l’appel suivant, annuler les jobs affectés par un retrait de scope. Une échéance future ou aucune échéance permet à l’opérateur de remettre en service une clé expirée ; la révocation reste définitive pour cette clé.

## Recherche 0.2 — curseurs et idempotence

- Conserver `limit` comme plafond par job et `search_max_results=10` pour les clients existants. La pagination ajoute un curseur, rend d’abord le reliquat puis suit les champs réellement émis par DuckDuckGo ; un numéro de page serait insuffisant pour les paramètres natifs. Les autres moteurs/modes restent sans curseur.
- Snapshots bornés en SQLite, sans onglet conservé entre jobs, afin de nettoyer les recherches et permettre les reprises après redémarrage. Expiration absolue de la chaîne, réservation atomique, rejeu consommé409 et idempotence24h par projet/clé. État consommé/expiré effacé ; paramètres moteur potentiellement expirables indépendamment.
- Garder le quota moteur partagé 6/60s, identifier sa portée et le distinguer d’un throttling tiers. Aucun sommeil de quota côté serveur ; client borné avec Retry-After. Conserver les résultats/provenances partiels des jobs échoués.
- Publier un contrat client 0.2 via `/openapi.json` sur le port API, sans routes admin. Les essais live CAPTCHA ne constituent pas une validation de pagination native ; cette réserve reste explicite malgré la simulation et la fixture de transport réussies.

## Port HTTPS Tailscale configurable globalement

Le port externe désigne le port HTTPS utilisé par les clients, indépendant de chaque projet et du port API loopback. Le réglage est géré globalement dans Paramètres, appliqué explicitement avec la CLI Tailscale Serve et persisté par --bg dans Tailscale. Lire l’état réel plutôt que conserver une préférence potentiellement différente de la route active. Les autres services sont préservés ; toute route partagée/occupée, Funnel ou Serve temporaire sur le port concerné est refusé. Le changement crée et vérifie la nouvelle route avant de retirer l’ancienne, puis vérifie l’état final ; récupération contrôlée en cas d’échec. La console reste locale et la cible est toujours le listener API.

## Filtres d’actualité DuckDuckGo

Exposer `region` comme code officiel pays/région-langue avec priorité sur la locale, et `time_range` comme choix lisible (`any/day/week/month/year`). Réappliquer uniquement `kl/df` aux continuations émises par le moteur ; conserver les tokens/offsets natifs. Lier ces filtres aux curseurs et checkpoints et préserver les hashes des requêtes historiques sans filtre. Refuser les filtres explicites pour auto/Brave/Google afin qu’un repli ne change pas leur sens. La date de collecte reste distincte de la publication et de l’événement ; aucune date n’est déduite de la seule présence dans des résultats récents.


## Port API local indépendant de Tailscale

Proposer un réglage local global dans la console, utilisable sans accès externe. Enregistrer une surcharge privée atomique dans PQ_DATA_DIR plutôt que modifier le .env d’installation ; priorité explicite sur PQ_API_PORT et retour au .env par retrait de la surcharge après arrêt. Appliquer au prochain lancement, sans mutation à chaud des sockets ni du contrôle d’administration ; afficher séparément le port actif et le port enregistré. Vérifier le bind loopback à l’enregistrement sans réserver le port, et laisser le démarrage refuser un conflit apparu entre-temps. Résoudre une seule fois la configuration utilisée par les deux sockets et leur middleware. Le réglage local ne change aucune route Tailscale Serve.


## 12 octobre 2026 — Budgets détenus aux frontières de ressources

À la demande d’appliquer les propositions Codex Security, l’audit devient explicitement partiel sous surcharge : quotas, queues et volume bornés, réserve administrative séparée et signalisation des omissions/purges/erreurs. Les totaux API sont persistés indépendamment du détail ; les dimensions sont regroupées à capacité. Un worker possède la connexion d’écriture, les lecteurs asyncio attendent explicitement hors boucle lorsque nécessaire.

Les lectures de contenu externe passent par des fonctions fixes en monde Chromium isolé, avec limites avant retour ; aucune récupération préalable de l’arbre complet ou des titres de targets. Les résultats de jobs sont bornés au point de persistance commun. Les valeurs excessives échouent explicitement, sans tronquer silencieusement un résultat complet. Les titres restent un résumé borné avec indicateur.

Ces budgets concernent la rétention et les lectures détenues par PageQuay. La mémoire native Chromium/driver, la perte de buffers sur crash et la réduction physique SQLite restent des contraintes d’exploitation distinctes, documentées. Les paramètres et fragments d’URL restent visibles dans l’audit selon la préférence utilisateur existante, dans le budget de taille.


## 12 octobre 2026 — Contrat exact et attestation limitée

L’acquisition exacte est opt-in (`expected_url`, `allow_redirects=false`) et exige HTTPS443 ; les payloads historiques et l’idempotence search0.2.0 restent valides. L’attestation HTTP provient uniquement du document principal observé, jamais de son DOM ; statut inconnu = null+motif. La cohérence de navigation/frame n’est pas une atomicité multi-DOM.

Faute de couverture CDP démontrée de tous les redirects OOPIF, le mode strict refuse le trafic de frames enfants avec cause explicite ; il n’élargit pas son attestation aux garanties du proxy historique. Les lecteurs cross-origin/OOPIF restent isolés sans fallback page-owned. XPath de ShadowDOM inaccessible = null+motif, et robots non vérifié ne devient pas une preuve.

Les logs d’extraction gardent les classes/codes/chaînes d’exceptions et étapes corrélées ; texte arbitraire d’exception intégralement expurgé pour exclure secrets et corps de page. Le reason agrégé des anciennes frames reste compatible mais ne prouve pas détachement. Aucun diagnostic rétroactif KUKA revendiqué ; reproduction exige le Bearer existant, sans créer/remplacer de clé.


## 12 octobre 2026 — Identité de frame et correctif KUKA 0.2.1

Les indices de Playwright.child_frames et l’ordre des éléments DOM ne constituent pas l’identité native d’un contexte. Relier les slots Window.frames aux propriétaires iframe/frame et comparer content_frame, dans le monde utility isolé avec un moteur fixe utilisé seul ; sélectionner ensuite un monde CDP isolé dont le chemin correspond. Chercher le target ancêtre OOPIF pour les descendants en processus interne. Aucun fingerprintURL/titre, DOMwrite ou evaluate dans le monde page.

Utiliser le runtimejetable sans BearerUniversRobot pour reproductionréelle autorisée ; après déploiement0.2.1, leur client privé effectuera le test du serviceinstallé. Les artefacts jetables ne sont pas des jobs de ce service. Export complet=DOM monté dans les bornes, pas données visuelles du player. Redirections autorisables explicitement par allow_redirectsTrue, sans supprimer expected_url ni gardesréseau/robots.


## 2026-10-12 — Navigation, challenge et portée d’extraction (0.2.2)

À la demande utilisateur, le suivi des redirections est indépendant du contrôle de portée final : allow_redirects true par défaut, refus avant suivi seulement avec false explicite. Robots ne force pas false sur le document ; son helper conserve un refus explicite séparé. Vérifications automatiques attendues passivement dans le budget existant ; intervention humaine et délai épuisé donnent waiting_for_human, reprise du même job après contrôle du challenge et de l’URL. Une destination différente donne scope_changed sans extraction métier ni adoption automatique. L’extraction conserve l’attente définie à la navigation quand son appel omet expected_url. Une approbation d’autre cible nécessite un nouvel appel explicite.

Conserver HTTPS/ports, proxy public/IP/DNS, refus strict des frames non attestées, mondes isolés et budgets. Détection Cloudflare via réponse principale cf-mitigated et marqueurs conservateurs ; le signal reste valable pendant les requêtes en cours et les changements de hash. Capture jetée si challenge intervient, sans retry global ni masquage des erreurs du lecteur. Client serveur expose --no-allow-redirects et --resume ; ne pas suivre les redirections HTTP du transport API avec Bearer.

WORLD_NOT_FOUND KUKA reste un défaut de correspondance d’identité de frames/target CDP vérifié séparément. Recette réelle0.2.2 confirme f1extracted/partialfalse, sans établir de causalité avec Cloudflare/redirections. Version0.2.2 déployée, étatauthprojetsréglages vérifié inchangé ; UniversRobot exécute la recette installée avec sa clé existante.


## 2026-10-13 — Publication de la release 0.2.2

À la demande explicite de l’utilisateur, publier les changements d’acquisition, KUKA et navigation sur main et créer la release stable v0.2.2. Construire les paquets depuis le commit Git seul pour exclure les données privées ; joindre wheel, archive source et SHA256SUMS. Release publiée et fichiers retéléchargés vérifiés, tag conservé sur le commit de code a763418. L’actualisation documentaire après publication ne déplace pas ce tag immuable.


## 2026-10-14 — User-Agent natif du navigateur

À la demande de l’utilisateur, supprimer la surcharge `PageQuay/0.2.0` au lancement Chromium. Conserver le User-Agent natif du moteur, sans valeur forgée ni rotation. La preuve robots et `RobotFileParser.can_fetch` utilisent le User-Agent réellement envoyé dans la requête `/robots.txt`. Cette modification de compatibilité ne garantit pas la résolution des challenges Cloudflare.


## 2026-10-14 — Consentement cookies par API

« Valider cookies » est une action `validate_cookies`, avec refus par défaut et acceptation seulement explicite. Une règle persistante par projet est exposée par GET/PUT cookie-policy, désactivée par défaut et distincte de la configuration générale afin que browser:interact ne puisse modifier aucune autre politique. La détection exige un conteneur de consentement, du texte associé et un libellé exact ; l'absence du refus, une ambiguïté ou un dépassement de bornes n'autorisent aucun repli vers l'acceptation. Application aux visites pilotées par API ; les bannières tardives ou parcours de préférences non reconnus utilisent une action explicite. Les résultats rapportent le clic observé sans prétendre vérifier les cookies décidés par le site.


## 2026-10-14 — Acceptation automatique UniversRobot

L'utilisateur demande explicitement le redéploiement et l'activation de l'acceptation automatique pour UniversRobot. Activer choice=accept avec budget de détection 1500 ms uniquement pour universrobot, via le stockage de l'option déployée ; aucune activation globale. Le choix s'applique aux prochaines visites pilotées par API où une bannière et un bouton d'acceptation sont reconnus. Redémarrage du service autorisé, sources et base sauvegardées, profils conservés ; le job testing actif est interrompu par l'arrêt normal.


## 2026-10-14 — Release 0.2.3 depuis l'état courant

À la demande de l'utilisateur, publier l'ensemble des changements courants dans un commit sur main et une nouvelle release stable v0.2.3, en conservant v0.2.2. Seules les métadonnées de version et la documentation de release complètent le travail existant ; les fichiers de diagnostics déjà publiés restent en l'état. Construire les assets depuis le commit Git, sans données locales de profils ou de configuration, et vérifier les références et les fichiers publiés. La configuration d'acceptation cookies UniversRobot est un réglage du service installé, pas un défaut de distribution.


## 2026-10-14 — CDP explicite, refus WebSocket natif et release 0.2.4

Conserver `launch_persistent_context` et toutes ses gardes, mais terminer le pipe Playwright dans un relais privé ; seul le navigateur enfant utilise un port CDP explicite non nul sur loopback. Vérifier l’endpoint annoncé par cet enfant et nettoyer le transport et les processus sur arrêt/échec.

Refuser ws/wss par la catégorie native « autres proxys » de Chromium, avec un listener HTTP de refus distinct, sans remplacement JavaScript ni repli direct. Ne pas exposer le CDP local par l’API ou un proxy distant. Les essais Music Store constituent une observation limitée, pas une garantie d’accès ni un contournement automatique de CAPTCHA.

Préparer et valider un commit local de release 0.2.4 avec notes, version, contrat et lock cohérents. Conserver le navigateur de démonstration déjà ouvert ; les tests automatisés utilisent leurs profils séparés. Le runtime installé conserve ses métadonnées 0.2.2 et sa configuration Chromium. La demande actuelle ne publie pas de tag ni de release GitHub.


## 2026-10-14 — Première release v1

La consigne « fais une v1 en release » remplace la publication prévue de 0.2.4 par v1.0.0. Conserver le commit 0.2.4 dans l’historique et aligner les métadonnées publiques sur 1.0.0 sans modifier le code navigateur validé. Publier le commit et le tag annoté, construire les archives uniquement depuis ce commit et vérifier les assets retéléchargés. Ne pas modifier les releases antérieures ni redémarrer le service installé.

## 16 octobre 2026 — Transport image et release locale 1.1.1

Le refus de Base64 couvre aussi les octets internes du protocole image. Les corps binaires CDP sont donc remplacés par un lecteur BYOB dans un monde isolé Chromium, sans accès universel. Le second GET est déclaré explicitement, ses en-têtes et sa destination sont revérifiés ; une réponse HTML nouvelle échoue. Le projet conserve son proxy et ses interdictions de téléchargements natifs. Les limites d’octets et de pixels sont maintenues ; pas de plafond RSS OS revendiqué sur macOS. Le marqueur OpenAPI est requis par le client pour éviter un ancien service 1.1.0. La demande « fait le commit release » autorise le commit local 1.1.1 ; push, tag distant, publication et installation restent distincts.

## 19 octobre 2026 — GIF/20 Mo et commit local 1.2.0

Après audit en lecture seule, l’utilisateur valide l’extension compatible de
`download_image` : défaut 5 Mo/trois formats, GIF explicite et maximum 20 Mo,
validation structurelle GIF complète et décodage de première image seulement,
GET privé borné. Pas de plafond RSS OS revendiqué sous macOS, pas de nouvelle
dépendance, quota global ou modification UniversRobot. Les recettes réseau Dobot,
livraison distante et installation restent soumises à leurs accords distincts.
La demande « fait un commit release » autorise le commit local 1.2.0 sur main,
avec notes bilingues et documentation Pillow préexistante conservée ; pas de
push, tag ou publication GitHub implicite.


## 20 octobre 2026 — Profondeur DOM et release 1.2.1

Le diagnostic LahakX montre une image utile à profondeur 35 derrière des enveloppes Wix ; le texte éditorial est déjà présent. Conserver la profondeur comptée de 32 et accorder au plus trois crédits par chemin aux seuls div/span/picture sans sémantique déclarée, avec borne physique 35. Préserver enveloppes, budgets, contrôles réseau, URL exacte et toute indication d’omission réelle. Les frontières Shadow/slot ne reçoivent pas de crédit. Le journal local atteste l’empreinte du script chargé à l’import.

L’utilisateur autorise explicitement l’implémentation puis l’installation, le redémarrage, le commit et la release GitHub. Le patch devient 1.2.1 ; les commits locaux 1.1.1 et 1.2.0 sont inclus dans cette publication après la dernière release publique 1.1.0. Les paquets sont construits depuis le commit publié ; aucun changement UniversRobot.


## 26 octobre 2026 — CAPTCHA et release 1.2.4

Les reprises humaines partagent une échéance par job. Une attente abandonnée désactive les scripts puis suspend la page via CDP ; réactivation sur une opération explicite, fermeture tentée si la suspension échoue. Afficher une fenêtre minimisée seulement quand une intervention humaine est nécessaire, une fois par séquence ; borner les appels natifs et conserver l’attente si l’affichage échoue. Aucune garantie de plafond système CPU/mémoire. L’utilisateur autorise le commit local, le push main et la release GitHub avec les paquets Python et leurs empreintes.
