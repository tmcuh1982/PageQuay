# Diagnostic de démarrage du navigateur

[Français](STARTUP_DIAGNOSTICS.md) | [English](STARTUP_DIAGNOSTICS.en.md)

`BROWSER_CRASHED` conserve son code et son message compatibles. Le retour
ajoute `stage=startup`, `startup_step` et une cause bornée ; jamais une exception
brute, un chemin de profil/exécutable, une commande Chromium ou des variables.

Étapes : proxy_start, playwright_start, selector_registration, browser_launch,
browser_setup. Les erreurs PQ déjà typées et les interruptions restent inchangées,
ainsi que la fermeture du proxy/contexte et la libération du verrou applicatif.

Causes reconnues pendant browser_launch : BROWSER_LAUNCH_TIMEOUT (exception
Playwright Timeout), BROWSER_EXECUTABLE_MISSING (message de lancement ancré),
BROWSER_PROFILE_LOCK_EXISTS (marqueur SingletonLock: File exists dans l'erreur
de lancement). Un verrou existant ne prouve pas qu'un ancien processus est vivant.
Toute autre cause reste UNKNOWN_STARTUP_FAILURE, avec l'étape connue et la classe
bornée PLAYWRIGHT_ERROR/PLAYWRIGHT_TIMEOUT/OTHER. Aucune suppression de profil,
réinitialisation de clé ou bascule headless automatique n'en découle.

## Reproduction sans profil ni clé installés

Prérequis : Python/Playwright de PageQuay, code contenant startup_diagnostics,
driver disponible. Le dépôt avant correction était b7c61ec ; son manager renvoyait
details absent même sur un timeout de lancement (régression rouge).

```sh
PQ_BROWSER_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_startup_diagnostics.py -q
```

Le test réel appelle BrowserManager.start avec un projet synthétique et un profil
temporaire, Playwright réel, chemin exécutable temporaire absent, proxy simulé.
Cible de navigation : aucune (démarrage avant about:blank, avant toute URL HTTP).
Attendu : code BROWSER_CRASHED, étape browser_launch et cause exécutable absent,
aucun chemin dans le retour, proxy fermé et verrou applicatif réacquérable.
Observé : ces contrôles passent sur macOS avec le runtime PageQuay du Mac mini.
Request/job/tab/frame/artifact : non applicables, appel direct du manager sans API.
Date/corrélation de l'exécution : rapport de test de la livraison, pas des IDs inventés.

Les tests synthétiques couvrent timeout/verrou/missing, rejet de marqueurs de
navigation ou d'une exception d'une autre classe et absence de texte SECRET.
Le verrou Chromium n'est pas reproduit par le test de deux contextes sur la
version utilisée : le second lancement réussissait. Il n'est donc couvert que
par le message contrôlé, aucune cause de crash historique déduite.

Pour un incident installé : garder URL exacte (publique), date/version et
request/job/tab IDs rendus, étape/cause bornées. UNKNOWN reste une inconnue :
demander les logs locaux corrélés, sans joindre clés/cookies/profils ou exceptions
brutes à un ticket public. Un succès après changement de session et restart ne
permet pas d'attribuer le crash antérieur à une seule de ces modifications.
