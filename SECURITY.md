# Sécurité PageQuay

## Périmètre et invariants

Application privée pour un opérateur et des clients connus. Les pages Web sont non fiables ; les clés API et profils sont des secrets. Chaque ressource possède une relation serveur vers un projet identifié par un ID aléatoire. Les slugs ne deviennent jamais des chemins. Aucun administrateur par défaut, API d'administration pour clés clients, CDP réseau ou exécution de code fourni par un client.

Sessions serveur : token aléatoire de 256 bits, hash SHA-256 dans SQLite, durée absolue de 12 h et inactivité de 30 min ; nouvelle session au login, précédente invalidée, logout et CSRF pour chaque mutation UI. Cookies HttpOnly, SameSite Strict et Secure lorsque configuré pour HTTPS. Login CSRF également protégé et limité à cinq tentatives par transport/cinq minutes avec limite globale. Mots de passe Argon2id, minimum 14 caractères. Les erreurs ne renvoient pas les valeurs invalides des formulaires.

Clés API : 256 bits CSPRNG, hash SHA-256, comparaison en temps constant après lookup, projet unique et scopes explicites. Pour des secrets aléatoires de cette entropie, un hash rapide ne rend pas la recherche exhaustive réaliste ; les mots de passe humains ont, eux, un hash lent Argon2id. Préfixe d'identification non secret, affichage complet une fois, expiration/révocation revalidées pour requêtes, jobs actifs et WebSockets. La modification d’une clé est réservée à une session admin locale avec CSRF : secret/projet conservés, aucune réactivation d’une clé révoquée, date future ou absence d’expiration, au moins un scope reconnu et quota borné. Le compteur de quota est conservé ; les jobs utilisant un droit retiré sont annulés et les requêtes suivantes revalident les droits. Audit `key.updated` sans secret. Pas de secrets complets dans le journal d’audit.

## Egress navigateur

Le proxy propre à chaque profil écoute sur une adresse loopback et un port éphémère. Il analyse URL/schéma/port, vérifie **toutes** les réponses DNS et connecte directement une IP validée. TLS reste vérifié par Chromium à l'intérieur du tunnel CONNECT. Les sous-requêtes sont aussi interceptées par Playwright ; le proxy reste le contrôle de connexion, y compris quand une redirection échappe à l'interception. Loopback, réseaux privés, link-local, tailnet CGNAT, multicast, réservés, IPv6 mapped/6to4/Teredo/NAT64 standard, métadonnées cloud et littéraux IP ambigus sont refusés. Ports publics 80/443 seulement. Liste autorisée exacte ; liste bloquée couvre aussi les sous-domaines.

Chromium est lancé avec `chromium_sandbox=True` : Playwright le désactive sinon par défaut ([documentation officielle](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-option-chromium-sandbox)). QUIC et UDP WebRTC non proxifié sont désactivés ; WebSockets distants et service workers bloqués. Permissions caméra, micro, localisation et clipboard non accordées. Téléchargements annulés, uploads et accès arbitraires aux fichiers non exposés. Les dialogues sont fermés sans validation de challenge.

Ce dispositif **n'est pas un pare-feu OS** : un navigateur compromis, une extension ajoutée manuellement, un processus local autorisé ou une modification manuelle du profil sortent du modèle de confiance. Les tunnels ne déchiffrent pas les requêtes HTTP internes à TLS et ne garantissent pas une politique par URL à eux seuls. Le filtrage par origine, Playwright et l'IP de connexion s'appliquent conjointement. Une infrastructure exigeant un confinement complet doit ajouter un contrôle réseau OS administré. Aucune exception LAN de production dans cette version. Les exceptions des tests sont injectées uniquement en Python dans leur processus.

## Administration, stockage et contenu

Deux listeners imposés à 127.0.0.1 par la CLI : administration locale sur 8765, API seule sur 8766. Le port de destination réel de la socket limite 8766 à `/v1/` et aux deux routes health, pour HTTP et WebSocket ; aucun Host, proxy header ou cookie admin ne lève cette restriction. Transport non loopback refusé par l’application, Host et Origin explicites. Accès distant via Tailscale Serve HTTPS vers **8766 uniquement**, identité/ACL tailnet puis clé API. Le port admin ne doit jamais être publié par un proxy. Pas de Funnel. CSP locale, anti-framing, nosniff, no-store, referrer policy, réponse maximale, queues/onglets/navigateurs/actions/rate limits/artefacts bornés.

Templates Jinja échappés ; JavaScript utilise `textContent`, pas `innerHTML` pour le contenu externe. HTML extrait distribué comme pièce jointe avec CSP sandbox. Captures protégées par session admin ou scope projet. Pages distantes jamais intégrées en iframe. Si un client transmet du contenu à un LLM, traiter ce contenu comme des données non fiables et ne pas suivre ses instructions.

Dossiers 0700 et SQLite/artefacts/verrous 0600, umask 077 dans la CLI. Le profil reste lisible par l'utilisateur macOS et contient des cookies/secrets en clair ; aucune promesse de chiffrement au repos. FileVault est un contrôle macOS séparé. Verrou flock par profil, libéré par le noyau après crash. Reset manuel uniquement, deux confirmations et intention courte liée à la session ; refus si jobs en attente/actifs. Sauvegarder uniquement après arrêt complet.

L'audit conserve action, date, acteur ID et projet, jamais Authorization, cookie, mot de passe, valeur de formulaire, HTML ou screenshot. Les access logs Uvicorn sont désactivés. Les fichiers de logs LaunchAgent sont sous la responsabilité de l'opérateur ; rotation documentée dans `docs/OPERATIONS.md`. Ne pas activer DEBUG/trace Playwright sur des sessions réelles sans examiner ce qu'il enregistre.

## Vérification et signalement

Consulter `docs/testing/REPORT.md`. Les fixtures vérifient des mises en page connues, pas la disponibilité des moteurs. Les tests de crash ferment volontairement un contexte ; ils ne reproduisent pas tous les cas de panne OS. Tailscale ACL, LaunchAgent au login et restauration d'une sauvegarde doivent être validés sur la machine cible.

Pour signaler un défaut, conserver les étapes de reproduction et identifiants non sensibles. Ne pas joindre de profil navigateur, clé API, copie brute de page authentifiée ou capture contenant des secrets à un dépôt public.
