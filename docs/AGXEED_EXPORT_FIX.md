# Export AgXeed et identité sous budget — 13 octobre 2026

Demande utilisateur UniversRobot : traiter TODO-070, terminer Ask IA jusqu’aux avis DeepSeek/Jev et publier corrections/tests. Clés, profil, configuration et approbations conservés.

## Défaut et correction

Avant : https://www.agxeed.com/ atteignait2000nœuds/40000caractères, URL/titre vides, text_budget/nodes/string_length et frame_limit_reached. Jobcb1a20ac2ebd1c63f7afbbf62f518f03, request328040d6efe4a2a86a8f39bb, tab9992df4883ceb1d12cf73585f150c3ba, artifact7324551f36b79ef2b2fca4650957896c ;13octobre2026 19:22:35.281001→19:22:35.595077Europe/Warsaw.

L’identité était copiée après le DOM : le budget commun déjà épuisé supprimait URL/titre. URL puis titre réservent maintenant le budget avant metadata/DOM. Bornes d’URL2048/titre500 conservées ; une identité hors contrat n’est pas remplacée par une URL inventée.

Plafonds DOM/texte recalibrés :8000nœuds visités et min(160000,max_content_bytes/8)caractères par document, profondeur32 et autres limites conservées. Export réel mesure4221nœuds/80281caractères ; les plafonds précédents ne pouvaient pas le contenir. Quatre lectures visibles maximum, principal compris. Inventaire32frames, cachées signalées comme omitted/hidden_frame sans consommer de lecture. Inventaire ou quota visible dépassé restent partial/frame_limit_reached. Durée globale40s et10s/frame ; expiration globale typée TIMEOUT, pas faux succès. Les gardes de contexte/portée/challenge et quota d’artefact restent actifs.

## Reproduction et vérification

Pré requis : PageQuay0.2.2 avec ces corrections sur service installé Mac mini, sessionlolo active, configuration privée existante sans afficher Bearer/cookies. Depuis le portail UniversRobot : ouvrir source3f1ce16b-fa8e-57c4-a215-6c01c134d42a, URL exacte https://www.agxeed.com/, puis Ask IA dans session authentifiée. Une tentative, pas de répétition automatique. Attendu identité intacte et export exploitable pour avis consultatif borné ; limites connues toujours signalées.

Après : jobd44e22124a6c834a23fcd5f4523bb1e7, requestd27f53ee3c4b34137b5d55ca, tabba95a59c46fbf310016576705dbbc43c, artifact73f86e7dd5d8cb53c645b256eefa0c6a. URL https://www.agxeed.com/, titre Home - AgXeed.com,87361octets ;4221nœuds visités/3156inclus/80281caractères, frame_limit_reached=false, deux enfants extracted et huit cachés omitted. Seul motif de troncature string_length. Aucun plafond global de texte/nœuds atteint ni frame unavailable. La troncature de chaînes reste explicite et autorisée uniquement pour l’avis consultatif UniversRobot ; aucune extraction métier complète revendiquée.

Ask IA terminé le13octobre2026 à19:47:56.902529Europe/Warsaw : DeepSeek deepseek-flash et Jev jev-1.13.0 donnent organization. DeepSeek propose approved pour l’accueil fabricant ; aucune décision humaine ni publication appliquée. Audit89f6c5ad-54e9-4bf6-9ec3-0eb92f699956 ; requests modèlesaa64a5aa-1fe1-41f7-9ab4-c20202c32d02 /139be01d-475a-4070-a9b8-6a6e809ba3db. SHA256 JSON canonique dcae5a4743448dcb81929520f8821f296ff299feefe131d7690316dc07c700ce correspond à l’export téléchargé et l’audit.

Tests : reproduction rouge sur identité/DOM/hidden_frames/visible_limit ; six régressions finales incluant inventaire32 et timeout.40tests ciblés avec Chromium et gardes d’acquisition passent ; suite générale233passed/55skipped. Ruff check/format et node --check conformes. Fixtures de dépassement restent supérieures aux nouveaux plafonds, signal nodes conservé, taille/profondeur et vraie limite visible toujours contrôlées.

Fichiers : src/pagequay/extraction.js, src/pagequay/structured.py, tests/test_export_budget.py, tests/test_export_deadline.py, tests/test_structured.py, docs/EXTRACTION.md, docs/ARCHITECTURE.md, cette note. Service installé : deux sources copiées après tests, sauvegardes /private/tmp/pq-extraction-before026.js et pq-structured-before026.py, redémarrage sans job actif. Trace CHG-20261013-026 / TODO-070. Aucun paquet, migration, clé ou profil ajouté.
