# Publier et synchroniser PageQuay

Le dépôt cible est [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), public, branche `main`. La publication publique a été explicitement autorisée. Le dépôt Git local est configuré avec `origin` en HTTPS et `main` suit `origin/main`.

## Accès GitHub requis

Le compte `tmcuh1982` possède les droits de modification du dépôt. Cela ne suffit pas à donner au connecteur de l'application l'accès en écriture : la dernière tentative a reçu `403 Resource not accessible by integration`, et aucune installation d'application n'a été détectée par ce connecteur.

Configurer la connexion GitHub de l'application avec l'accès au dépôt PageQuay, puis vérifier à nouveau les droits effectifs. Une autre voie est un client Git déjà authentifié sous le compte prévu, avec les droits d'écriture de ce dépôt. Aucun mot de passe, token ou clé privée ne doit être copié dans les documents ou transmis dans le chat. La visibilité publique n'est plus une question en attente.

## Contenu versionné

Sources dans `src/`, tests et fixtures dans `tests/`, scripts/exemples, `pyproject.toml`, `uv.lock`, README, politique de sécurité, documentation, `memory.md` et `decisions.md`.

`.gitignore` exclut les environnements, secrets `.env`, bases SQLite, profils, artefacts, sauvegardes, logs et diagnostics locaux. `.env.example` est conservé comme configuration sans secrets. Dans `docs/testing/`, seuls le rapport et les deux JSON issus de la fixture complexe sont versionnés ; les captures et rapports de navigation peuvent contenir des informations propres aux machines.

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
