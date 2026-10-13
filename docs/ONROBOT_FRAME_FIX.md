# Lecture OnRobot RG2 — frames et options — CHG-20261013-028

Demande : résoudre les tickets sources/extraction, conserver les causes précises et publier les corrections PageQuay. TODO-068 (frame), TODO-083 (options), TODO-084 (contrat de diagnostic). Aucun solver, clé/profil/permission ni approbation modifiés.

## Reproduction et défauts

Pré requis : PageQuay installé0.2.2, session graphique lolo sur Mac mini, configuration privée existante sans afficher Bearer/cookies. URL exacte https://onrobot.com/en/products/rg2-finger-gripper. UniversRobot : dossier05f69388-e8da-53d3-be21-ae1a1d4c5b6a, session authentifiée → Ask IA, une tentative. Sonde acquisition : client.page(URL), tab_info URLexacte, extract structured expected_url exact, download. Attendu export cohérent puis avis consultatif ; avant, partial_content avant modèle.

Reproduction13octobre2026 20:23:51.939063→20:23:58.335257Europe/Warsaw : jobab32886b5bd4d7e94cfe03177e2e88ff, requestf946570d51a8d1885ecfabda, tab173e265159feb6045e6375496e80d4c3, artifacte8898990e6e5cb9ece8cc4f1f79b22da. f1WORLD_NOT_FOUND/context_selection/unattached ; f2unsupported_frame_scheme/blob. Export principal2751nœuds/43541caractères, raisonoptions ; plus de saturation de nœuds après CHG-026.

Cas précis reproduit avec Chromium : iframe cross-site dans Shadow DOM ouvert/fermé, window.frames.length=0 malgré frame attachée. Le lecteur par slots Window ne pouvait pas la mapper. Le service OnRobot a la même signature de propriétaire non mappé ; la sélection corrigée est attestée frame_target_root. Le mode exact du Shadow DOM du site n’est pas inféré d’une URL Cloudflare.

## Corrections et refus conservés

Pour une frame non mappée, seule une session CDP liée à cette frame exacte est acceptée. DOM.getFrameOwner retourne des IDs opaques pour descendants locaux ; l’erreur native « Frame with the given id does not belong to the target » identifie le propriétaire hors cible de la racine. Racine unique exigée, propriétaire monté et même contexte vérifiés avant/après. Aucun choix par premier contexte, URL ou titre ; pas de FrameTree/TargetInfo ni repli JavaScript de la page. Session page/ancêtre, racine absente/ambiguë, déplacement ou contexte disparu restent refusés. Les frames in-process sans identité suffisante restent indisponibles : pas de capture devinée.

Visibilité contrôlée avant schéma : f2blob effectivement cachée signalée omitted/hidden_frame sans lire son contenu. Blob visible reste unavailable. Le DOM fermé du parent n’est pas parcouru ; un document iframe connu peut être lu indépendamment si son identité est vérifiée.

Formulaire mesuré :250options montées contre100exportées. Plafond recalibré à300options textuelles ;350options restent partial/options. Valeurs value/input/textarea toujours exclues et quotas de nœuds/texte/octets inchangés. UniversRobot traduit désormais options en « limite d’options de formulaire atteinte », sans accepter de partial supplémentaire.

Diagnostic : path_source=frame_target_root, failure=target_root_ambiguous. Le lecteur produisait aussi stale_candidate_count non déclaré dans son modèle strict ; test writer→modèle échouait extra_forbidden. Champ optionnel0..128, absence=inconnu, contrat OpenAPI régénéré et comparé au listener installé.

## Résultat réel et preuves

Lecture13octobre2026 20:56:54.585200→20:57:04.050800Warsaw :9,465s,12passages,partial=false. Ask IA terminé20:58:21.149591+02 : DeepSeek/deepseek-flash et Jev/jev-1.13.0 accessory. DeepSeek propose approved ; aucune décision humaine appliquée. Citation descriptive du RG2 sur course110mm et force programmable, pas du contenu Cloudflare.

Audit e5abe750-f095-46ee-8591-1c0b8acf73ac ; requests modèles2d0e065d-17a3-4a28-82ed-b19f32219747 et a96403de-d925-48f2-be97-173669dff127. Export jobd07a4403490c9a345c2fc89e749ccd3b, request93c7da912644465d8283c6e8, tab165ecb4009371d906ecd0236db225a31, artifact5225c1af713c09bb513354adedafe7ad ;52444octets,partial=false,aucune raison de troncature, f1extracted/frame_target_root avec2contextes inventoriés, f2hidden omise,250options. Empreinte canonique f7ddb2cd00a4f74810f5d26e1c3ab5e3827ae61926f11d1ef3a3359f94495aa3 identique à l’audit. Sélection IA bornée annoncée comme extraits partiels ; cela ne signifie pas un export incomplet.

Tests :48ciblés avec Chromium/gardes d’acquisition,239généraux/63skipped ;100tests clientUR. Régressions Shadow DOM rouge/vert, enfant local distingué de racine, racines ambiguës/absentes et propriétaire changé refusés ; blobs caché/visible, options250/350 et absence de valeurs, diagnostic writer→modèle/bornes/absence et OpenAPI couverts. Pas d’augmentation de droits ni de quotas de lecture4/inventaire32.
