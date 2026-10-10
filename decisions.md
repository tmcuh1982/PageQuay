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
