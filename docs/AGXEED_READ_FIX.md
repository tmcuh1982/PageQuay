# Correction AgXeed UNAVAILABLE — 13 octobre 2026

[Français](AGXEED_READ_FIX.md) | [English](AGXEED_READ_FIX.en.md)

Demande utilisateur UniversRobot : lire les logs, corriger et retester. Service installé 0.2.2, session console lolo active, clés/profil conservés. Commit et push GitHub explicitement demandés ensuite par l’utilisateur pour conserver les corrections dans le dépôt PageQuay.

Erreur historique, SQLite lu en mode readonly : URL https://www.agxeed.com/, job navigate 005425b5c8c68f2031f7079c301cd37a, request e24970adf026c4035e1b5070, tab a0d63808962b3619107c13b19b7d6dd4. Le 13 octobre 2026 à16:48:56.109821UTC, UNAVAILABLE / Document unavailable during extraction, cause WORLD_NOT_FOUND, étape isolated_world, trois candidats et zéro probe.

La sélection interrompait toute lecture dès qu’un candidat CDP avait disparu. Elle poursuit maintenant uniquement sur WORLD_NOT_FOUND avant capture. Les erreurs autres restent bloquantes ; contexte sélectionné et position de frame revérifiés après capture, sans repli vers JavaScript de la page. Le test test_stale_candidate.py reproduit l’échec avant correction et passe après.

Premier retest : NAVIGATION_CHANGED pendant la capture du titre (job b587457a8ff457fdc3c708993c98d379, request9773c4f2ce82ad37efbd36d9,16:55:51→16:55:59UTC). navigation_title rejette ce titre non publié et recommence sous deadline originale ; challenge, portée exacte et erreurs réseau revérifiés, timeout total. Aucun retry d’export incohérent ni élargissement d’approbation.

Recette : ouvrir https://www.agxeed.com/ via POST /v1/projects/{project}/tabs, attendre le job, contrôler URL finale puis demander content structured avec expected_url exact. Authentification existante chargée depuis fichier privé, jamais afficher Bearer/cookies. Dans UniversRobot : asyncio.run(pagequay_page.read('https://www.agxeed.com/',allow_truncated_strings=True)). Une tentative ; attendu export cohérent ou attente humaine typée.

Deux essais après correction : 16:58:36.957620→16:58:54.653239UTC et16:58:54.653400→16:59:07.224709UTC, plus de UNAVAILABLE, waiting_for_human à extraction. Jobs83636965f17bbb34a8ec3bdf5db563ef /71cbece8e2bf5e9ee578c57fd0fe0011 ; requests700501adc59312569c314c94 /243e41691fd9fced14919796 ; tabs a7d1a0d88489756f4dfa3ff2d44d705a /93afa2153d87fe5a4c24169718960d8a ; artifact/frame absents du retour. Les tests ferment leurs onglets. Export complet restant après confirmation humaine ; aucun CAPTCHA résolu ni modèle appelé. KUKA contrôle complet en10,484s, partial=false.

Validation : suite complète PageQuay232passed/44skipped (13octobre2026),43tests ciblés avec Chromium réel, cinq régressions unitaires et Ruff check/format conformes ;99tests client UniversRobot. Ce client conserve désormais UNAVAILABLE et cause/read_stage connus, sans détail d’exception arbitraire.

Fichiers : src/pagequay/page_reader.py, src/pagequay/browser.py, tests/test_stale_candidate.py, tests/test_navigation_title.py, cette note. Service installé : deux fichiers Python copiés après tests, sauvegardes privées /private/tmp/ur-installed-{page-reader,browser}-before023.py, launchctl kickstart après zéro job actif. Aucune clé, configuration ou profil changé. Trace UniversRobot CHG-20261013-023 / TODO-081 Terminé ; reprise humaine TODO-075 séparée.
