# RECETTE — Tests de réception vérifiables

Lancer les tests unitaires et d'intégration sur localhost. **Aucun compte Google/Brave/DDG et aucun contournement Cloudflare ne sont nécessaires pour vérifier la sécurité.** Le test de moteur tiers réel est une vérification additionnelle, non une garantie.

## Sécurité / authentification

- [ ] Aucun admin initial anonyme ; CLI de création obligatoire ; hash Argon2id dans SQLite.
- [ ] Login admin incorrect : rejet, ralentissement raisonnable, pas d'informations révélatrices.
- [ ] Actions du panneau admin exigent cookie de session et CSRF ; protection XSS sur HTML distant.
- [ ] Clé `universrobot` : accès universrobot autorisé selon scopes ; accès `projet-b` refusé.
- [ ] Clé `projet-b` : impossibilité d'accéder aux onglets, jobs, captures et WS universrobot même avec des IDs connus.
- [ ] Clé expirée ou révoquée : 401/403 ; connexion WS existante fermée/invalidée au contrôle suivant.
- [ ] Secret complet affiché uniquement à la création, absent des tables SQLite, logs et réponse de listing.
- [ ] Demandes HTTP(S) vers localhost, 192.168.1.1, 10.0.0.1, 169.254.169.254 et IP privée après redirection : bloquées ; vérifier IPv6 et DNS pointant vers IP privée.
- [ ] Aucun port CDP accessible sur réseau ; FastAPI écoute sur 127.0.0.1 uniquement par défaut.
- [ ] Rate limiting et plafond de payload / de jobs opérationnels.

## Navigateurs et profils

- [ ] Deux projets, deux répertoires persistants et deux navigateurs graphiques ouverts **simultanément**.
- [ ] Cookie écrit dans universrobot n'apparaît pas dans projet-b sur un domaine de test local autorisé **exclusivement dans l'environnement de test** ; exception temporaire au blocage local explicite, jamais activée en production.
- [ ] Relancer universrobot et constater que son cookie de test persiste ; cookies de projet-b inchangés.
- [ ] Une deuxième ouverture du même `user_data_dir` ne provoque pas un Chrome concurrent ou une corruption ; retour conflit ou réutilisation de l'instance existante.
- [ ] Navigation autorisée vers site public, extraction DOM rendu/texte/liens/métadonnées, capture accessible au bon scope.
- [ ] Action `click` ou `fill` refusée à une clé de lecture seule ; acceptée à une clé autorisée sur un site de test.
- [ ] Échec/challenge simulé : état `WAITING_FOR_HUMAN`, onglet conservé, reprise sur intervention de test sans solveur CAPTCHA.
- [ ] Crash simulé d'un navigateur : statut cohérent ; projet voisin reste utilisable.

## Rétention / reset

- [ ] Expiration `content_cache_ttl_minutes` purge le cache **sans effacer le cookie** d'une session persistante.
- [ ] Après délai `browser_idle_timeout_minutes`, le navigateur s'arrête correctement sans suppression de son profil ; retour à la demande avec sessions persistantes si encore valides.
- [ ] Soft restart = fermeture/réouverture sans effacement du profil ; différer si job en cours.
- [ ] Hard reset = double confirmation admin ; supprime uniquement le bon `user_data_dir` ; bloqué pendant un travail actif jusqu'au drain/annulation contrôlée ; audité.
- [ ] Rétention audit et artefacts respectée et purge testable.

## Recherche / API

- [ ] Adaptateurs Google, Brave et DDG vérifiés par fixtures, gestion de changements HTML et d'absence de résultats.
- [ ] Déduplication multi-moteur conserve provenance et ordre stable.
- [ ] Validation `limit`, taille `query`, timeouts, erreurs structurées.
- [ ] WebSocket annonce les événements de job et accepte seulement les interactions autorisées.
- [ ] `POST /search` et `GET /jobs/{id}` sont bien isolés par projet.
- [ ] Un test manuel DDG réel peut être tenté, avec résultat ou diagnostic honnête en cas de changement/limitation du moteur.

## Exploitation macOS

- [ ] Démarrage local sans Docker/SaaS ni secrets en dur.
- [ ] Procédure macOS `launchd` LaunchAgent testée ou documentée comme **non testée** si aucun Mac n'est disponible dans l'environnement Codex.
- [ ] Installation de Chromium Playwright et `doctor` affichent des erreurs utiles.
- [ ] Documentation Tailnet HTTPS/Tailscale Serve ; aucune exposition publique par défaut.
- [ ] `README`, `.env.example`, `SECURITY.md`, diagramme composants, commandes et procédure de sauvegarde disponibles.

**Rapport final exigé à Codex** : tests réellement exécutés et résultats, éléments non vérifiables localement, écarts restant à corriger. Ne jamais cocher un test non exécuté comme réussi.
