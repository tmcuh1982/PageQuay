# Distinguer widget CAPTCHA et challenge principal — 13 octobre 2026

[Français](CAPTCHA_WIDGET_FIX.md) | [English](CAPTCHA_WIDGET_FIX.en.md)

Demande UniversRobot : terminer Ask IA AgXeed. L’utilisateur confirme dans Jump Desktop que la page s’ouvre sans CAPTCHA. Ancien job836bf8d624cb1a5d45d517e76917ae10, tabdeae0e88bd2985b0778902496bff568e, request0d9fe12faeef57c2da35e385 : waiting_for_human à extraction alors que la capture montre le site normal.

Cause : la lecture challenge traitait la simple présence d’une iframe recaptcha/hcaptcha comme un challenge humain. Une iframe invisible ou un petit widget de formulaire ne démontre pas que le document principal est bloqué.

Correction : frame reste un signal bloquant pour le marqueur explicite data-pq-challenge ou une iframe CAPTCHA visible couvrant au moins50%du viewport ; captcha_widget décrit séparément sa présence. Parcours borné aux32premiers widgets. Les messages de vérification humains et les signaux automatiques/Cloudflare restent traités par challenge_state. Aucun CAPTCHA résolu, aucun contenu d’iframe ignoré lors de l’export. Ce seuil géométrique est une heuristique ; il ne prouve pas l’absence de tout challenge. Les gardes de portée et de cohérence restent inchangées.

Reproduction sans réseau externe : PYTHONPATH=src .venv/bin/python -m pytest -q --browser tests/test_captcha_widget.py. Les cas iframe invisible/petit widget échouaient avant correction (2failed/4passed) ; tous passent après, dont iframe plein écran, marqueur explicite, message humain et vérification automatique. Ensemble ciblé challenges/acquisition38passed ; suite générale232passed/50skipped, Ruff conforme.

Recette réelle : source UniversRobot https://www.agxeed.com/, session authentifiée → Ask IA, une tentative avec PQ0.2.2 corrigé et session graphique lolo active. Attendu lecture ou challenge réellement bloquant ; observé plus de waiting_for_human. Nouvelle limite distincte : protocol à validation, URL document absente, frame_limit/string_length/text_budget/node_limit. Jobcb1a20ac2ebd1c63f7afbbf62f518f03, tab9992df4883ceb1d12cf73585f150c3ba, request328040d6efe4a2a86a8f39bb, artifact7324551f36b79ef2b2fca4650957896c. Job créé le13octobre2026 à19:22:35.281001Europe/Warsaw, terminé à19:22:35.595077 (SQLite readonly). Aucun modèle appelé ; défaut export suivi par TODO-070 existant. Clés/profil inchangés, service redémarré après zéro job actif. Sauvegarde /private/tmp/ur-reader-before025.js sur Mac mini.

Fichiers : src/pagequay/page_reader.js, tests/test_captcha_widget.py, cette note. Trace UniversRobot CHG-20261013-025 / TODO-082 ; publication des corrections suivant la demande utilisateur de ne pas les laisser uniquement sur Mac mini.
