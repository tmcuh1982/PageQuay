# Transport navigateur et WebSockets — 0.2.4

## Fonctionnement

Chaque projet conserve un profil persistant séparé. `PQ_BROWSER_CHANNEL=chromium` est le défaut ; ce navigateur est fourni par Playwright et son exécutable macOS peut porter le nom « Google Chrome for Testing ». `PQ_BROWSER_CHANNEL=chrome` sélectionne Google Chrome installé dans `/Applications`. Aucun profil personnel Chrome n’est utilisé.

Le lancement conserve `launch_persistent_context` et l’initialisation Playwright. Un relais local termine son pipe interne puis communique avec le navigateur enfant sur un port CDP explicite non nul, lié à `127.0.0.1` et choisi à chaque lancement. L’endpoint doit être celui annoncé par cet enfant, avec l’adresse et le port attendus. Le navigateur ne reçoit pas le pipe. Le wrapper est privé et temporaire ; les arrêts, annulations, EOF et échecs ferment l’enfant. Le port de contrôle n’est pas publié par l’API ou Tailscale Serve, et reste réservé aux processus locaux de confiance.

Les gardes restent actives : sandbox Chromium, proxy à IP publique validée, routes et contrôle des redirections, refus des Service Workers, permissions, téléchargements, QUIC et UDP WebRTC non proxifié. La bibliothèque `websockets>=15,<18` est une dépendance directe du relais.

## Refus natif des WebSockets

Le navigateur reçoit une seule règle de proxy : `http=http://127.0.0.1:<public>;https=http://127.0.0.1:<public>;socks=http://127.0.0.1:<refus>`. La catégorie `socks=` désigne ici les « autres proxys » de Chromium ; l’URI explicite `http://` évite son interprétation comme SOCKS4. Chromium utilise cette catégorie pour `ws://` et `wss://` : [règles officielles](https://chromium.googlesource.com/chromium/src/+/HEAD/net/docs/proxy.md#mapping-websockets-urls-to-a-proxy).

Le listener de refus retourne 403 avant résolution DNS ou connexion amont. Aucun proxy alternatif ni repli direct n’est configuré. Le constructeur JavaScript `WebSocket` reste natif ; `context.route_web_socket` n’est plus installé. Le WebSocket de commande de l’API PageQuay reste disponible.

Les tests réels Chrome et Chromium vérifient des connexions `ws`/`wss` positives sans garde, puis leur refus avec garde, sans handshake reçu en amont. Ils couvrent frames de même origine et d’autre origine, srcdoc, popups, workers dédiés/partagés, constructor natif, HTTP/HTTPS toujours disponibles, et maintien du refus lorsque le listener WebSocket est arrêté. Les tests de proxy couvrent refus avant DNS, fermeture des clients et nettoyage après échec du second bind. Les tests du relais couvrent endpoint, transport, nettoyage et fermeture du navigateur.

## Diagnostic Music Store — 14 octobre 2026

Les comparaisons par facteur ont conservé les autres gardes : trois contrôles complets bloqués, trois essais réussis après retrait du seul `route_web_socket`, et deux essais encore bloqués avec ce routage en simple transfert vers le serveur. Cela suggère un effet de l’instrumentation WebSocket sur ce site ; ce n’est pas une preuve générale de la règle interne utilisée par Cloudflare. Le port CDP explicite seul n’avait pas suffi.

Versions observées : Playwright 1.63.0, Chrome installé 155.0.8059.80, Chromium fourni par Playwright 153.0.8010.12.

Après déploiement dans le service installé, recherche `test`, acceptation des cookies et ouverture de Yamaha P-45 ont réussi avec Chrome installé puis Chromium, chacun avec un profil neuf. Recherche et fiche : HTTP 200 ; même processus conservé pendant chaque parcours. Un premier contrôle de processus Chromium incomplet a été corrigé, puis le parcours revalidé.

Un nouveau profil vierge du service Chromium a ensuite été laissé ouvert. La recherche `test` et la fiche Yamaha P-45, puis la recherche `Shure SM58` et la fiche Shure BLX2/SM58 S8 ont réussi via la clé de test existante, dans le même processus et le même onglet. Cookies acceptés ; fenêtre restaurée pour inspection.

Cinq recherches supplémentaires ont été effectuées dans cette même session :

| Recherche | Fiche ouverte | Recherche / fiche |
| --- | --- | --- |
| Fender Stratocaster | Fender American Professional Stratocaster MN Black | 200 / 200 |
| AKG K240 | AKG K240 MKII | 200 / 200 |
| Focusrite Scarlett | Focusrite Scarlett 2i2 4th Gen | 200 / 200 |
| Yamaha HS5 | Yamaha HS 5 | 200 / 200 |
| Roland FP10 | Roland FP-10 BK | 200 / 200 |

Le premier clic Fender a expiré sans défi Cloudflare détecté. La recherche déjà chargée a été conservée ; les cinq fiches ont ensuite été ouvertes par navigation API vers les liens observés dans les résultats. Les titres et contenus ont été récupérés et les statuts contrôlés dans les preuves de navigation ou l’audit. Cette recette valide cinq navigations de fiches, pas cinq clics réussis. Aucun défi Cloudflare n’a été observé dans la série ; le même processus et le même onglet sont restés ouverts sur la dernière fiche.

## Déploiement et limites

Les sources runtime et la dépendance ont été déployées avec sauvegarde privée, arrêt après contrôle des jobs et vérification de readiness. Les réglages, scopes et clés ont été conservés ; les champs normaux d’activité ont évolué. Les anciens profils de test ont été sauvegardés séparément. Le service reste configuré sur Chromium et ses métadonnées installées restent en 0.2.2 ; le dépôt prépare 0.2.4. Ce commit ne réinstalle pas le paquet et ne redémarre pas la fenêtre conservée.

Les résultats sont propres au site, au réseau, aux versions et à cette session : ils ne garantissent pas l’absence future de challenge. Aucun CAPTCHA n’est résolu automatiquement. La détection conserve ses limites ; les résultats HTTP, titres et contenus complètent l’observation. Le proxy ne remplace pas un pare-feu OS. Les rapports bruts, captures, profils et secrets restent privés et ne sont pas versionnés. Le délai d’inactivité configuré peut fermer le navigateur même si le script de test le laisse ouvert.
