# Publier et synchroniser PageQuay

[Français](PUBLISHING.md) | [English](PUBLISHING.en.md)

Le dépôt cible est [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), public, branche `main`. La publication publique a été explicitement autorisée. Le dépôt Git local est configuré avec `origin` en HTTPS et `main` suit `origin/main`.

## Accès GitHub requis

Le compte `tmcuh1982` possède les droits de modification du dépôt. Le connecteur de l'application continue à refuser l'écriture avec `403 Resource not accessible by integration` après sa reconnexion. La publication effective utilise **GitHub CLI 2.102.0**, installé sur le mini et authentifié directement avec ce compte. Le premier push du code et des documents a été confirmé.

Pour une autre installation, avec `gh` disponible :

```sh
gh auth login --hostname github.com --git-protocol https --web
gh api user --jq .login
git config --local credential.https://github.com.helper ''
git config --local --add credential.https://github.com.helper '!gh auth git-credential'
```

Valider le code navigateur sous le compte prévu, puis vérifier que le login retourné est `tmcuh1982` avant publication. Le helper est configuré seulement pour le dépôt courant ; dans l'environnement du mini, il utilise le chemin absolu du binaire installé. Aucun mot de passe, token ou clé privée n'est copié dans les documents ou transmis dans le chat. La visibilité publique est déjà confirmée.

Lors de cette connexion, GitHub CLI a stocké ses identifiants dans un fichier local hors du projet, de permissions 0600, plutôt que dans le stockage sécurisé système. Ne pas ajouter ce fichier à une sauvegarde publique ni au dépôt ; aucun identifiant n'est nécessaire pour cloner les sources publiques en lecture.

## Contenu versionné

Sources dans `src/`, tests et fixtures dans `tests/`, scripts/exemples, `pyproject.toml`, `uv.lock`, README, politique de sécurité, documentation, `memory.md` et `decisions.md`.

`.gitignore` exclut les environnements, secrets `.env`, bases SQLite, profils, artefacts, sauvegardes, logs et diagnostics locaux. `.env.example` est conservé comme configuration sans secrets. Dans `docs/testing/`, seuls les rapports explicitement autorisés par `.gitignore` et les JSON de la fixture complexe sont versionnés ; les captures et rapports de navigation peuvent contenir des informations propres aux machines.

Avant publication, inspecter les fichiers suivis et la différence préparée ; un `.gitignore` ne retire pas un fichier déjà suivi par Git.

## Mise à jour locale puis distante

Depuis le dossier PageQuay, vérifier le travail et récupérer l'état distant :

```sh
git status --short --branch
git fetch origin main
git log --oneline origin/main..HEAD
git diff --check
```

Mettre à jour les documents avec les fonctionnalités et vérifications réellement observées. Consigner les décisions dans `decisions.md` et l'état de reprise dans `memory.md`. Après une modification du code, exécuter les contrôles adaptés et reporter leurs résultats ; une simple correction documentaire ne justifie pas de relancer tous les navigateurs.

Avec un client Git authentifié, préparer les fichiers concernés, créer le commit, puis publier :

```sh
git add README.md docs memory.md decisions.md
git diff --cached --check
git diff --cached --stat
git commit -m "Update PageQuay documentation"
git push origin main
```

Examiner le diff préparé avant le commit, particulièrement si d'autres modifications étaient déjà dans l'index. Un push normal conserve l'historique initial ; aucun push forcé n'est nécessaire. Si le distant a avancé, examiner ses changements et les intégrer avant de publier.

La connexion de l'application peut aussi publier via l'API GitHub quand ses droits fonctionnent. Dans ce cas, conserver le parent distant et les modes exécutables des scripts, contrôler la tête de branche avant sa mise à jour, puis récupérer les commits publics dans le dossier local. Le contenu local et distant doit être comparé avant tout réalignement de l'historique.

## Vérification de la synchronisation

```sh
git fetch origin main
git rev-parse HEAD
git rev-parse origin/main
git diff HEAD origin/main -- README.md docs memory.md decisions.md
git status --short --branch
```

Pour un push Git complet, les deux commits doivent être identiques et le dossier propre. Si seuls les documents ont été publiés par API, comparer ces fichiers explicitement : cela ne signifie pas que le code a aussi été publié. Actualiser [l'état du projet](STATUS.md) et la mémoire seulement d'après les résultats confirmés. Publier le dépôt n'installe ni le LaunchAgent ni Tailscale Serve et ne lance pas le service.

## Documentation bilingue

Les guides publics, notes de version, rapports publiés et références initiales possèdent une version française `.md` et une version anglaise `.en.md`, reliées depuis [l’index](README.md). Toute modification de comportement ou de preuve doit être reportée dans les deux versions, en conservant endpoints, clés JSON, commandes, versions, dates et mesures. OpenAPI, code et fixtures JSON sont communs. `memory.md` et `decisions.md` sont des journaux internes de développement en français, distincts des guides publics. Les consignes d’origine restent des exigences historiques, pas une preuve de réalisation.

La release stable 1.1.0 a été publiée le 16 octobre 2026 depuis 11ce7dd, avec wheel, archive source et SHA256SUMS vérifiés. Les mises à jour documentaires ultérieures de main ne modifient ni le tag ni ces paquets ; la description GitHub peut pointer vers la documentation bilingue actuelle.

La release [1.2.1](https://github.com/tmcuh1982/PageQuay/releases/tag/v1.2.1) du 20 octobre 2026 regroupe la correction de profondeur DOM et les commits locaux 1.1.1/1.2.0. Wheel, archive source et SHA256SUMS sont construits depuis le commit de release. Le service local 1.2.1 a été installé et redémarré sur demande explicite ; ses contrôles de santé, de contrat et d’empreinte chargée sont distincts de la publication GitHub.
