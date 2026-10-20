# Diagnostic borné des timeouts de navigation

Correctif proposé sur PageQuay1.0.0, base56f639e82f1ce0b12f292d144843beca0307ef35.
Aucun déploiement ou modification de profil/configuration inclus.

## Défaut et reproduction sans site réel

BrowserManager.navigate traite goto, garde humaine, contrôle de portée, robots de
la redirection, consentement et titre dans un même bloc. Un PlaywrightTimeout
était converti en TIMEOUT/504 avec details=None ; un timeout PageQuay du titre
n’avait pas non plus de sous-étape. Les erreurs de cinq opérations différentes
étaient donc indiscernables. Cela ne démontre aucune cause réseau ou CAPTCHA.

Prérequis : environnement de développement PageQuay et dépendances de tests déjà
installés. Aucun navigateur, profil, clé ou accès réseau de page nécessaire.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m unittest discover -s tests -p test_navigation_timeout_diagnostics.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m pytest -p no:cacheprovider tests/test_navigation_timeout_diagnostics.py tests/test_navigation_timeout_jobs.py tests/test_navigation_diagnostics.py tests/test_navigation_title.py tests/test_jobs.py -q
```

Le test injecte un PlaywrightTimeout via les vrais appels de navigate pour goto,
human_guard, robots_redirect, cookie_consent et title. Attendu : TIMEOUT/504 et
sous-étape exacte, budget configuré, durée écoulée et aucun texte privé. Avant :
cinq assertions details non nul échouent ; après : cinq nouveaux tests passent,
ainsi que les neuf tests existants navigation/titre. Avec la persistance de job
et les six tests jobs existants :21tests réussis. Un test vérifie aussi le
timeout PageQuay du titre, la priorité des gardes et les détails déjà présents.
Aucun request/job/tab/frame/artifact réel pour ces fixtures ; tab_id est fictif.
Date de vérification :15octobre2026, heure précise dans la preuve d’intégration
UniversRobot CHG-20261015-029. Aucun TIMEOUT réel AgXeed reproduit par ces fixtures.

## Contrat ajouté

Pour le bloc instrumenté, details contient seulement :

```json
{
  "stage": "navigation",
  "cause": "PLAYWRIGHT_TIMEOUT",
  "navigation_step": "goto",
  "budget_ms": 30000,
  "elapsed_ms": 30001
}
```

cause vaut PLAYWRIGHT_TIMEOUT ou PAGEQUAY_TIMEOUT, selon l’origine de l’exception.
navigation_step est fermé : goto, human_guard, scope_check, robots_redirect,
cookie_consent, title, result. Il indique l’opération qui lève le timeout, pas le
premier consommateur du budget ni la cause profonde. human_guard n’atteste pas un
CAPTCHA. budget_ms reprend la politique1–120secondes sélectionnée au début de ce
bloc ; elapsed_ms mesure le temps monotone depuis ce début, y compris les attentes.
Cela ne crée ni nouveau budget, ni limite globale dure, ni preuve de timeout DNS.
Valeurs hors contrat, durée négative/non finie/>24heures ou source inconnue donnent
None plutôt qu’un texte libre. Aucun appel à str(exception), aucune URL, cookie,
clé, réponse, sélecteur ou contenu de page ajouté au diagnostic.

Le code/status/message existants sont conservés. Une erreur de garde prioritaire
ou des details déjà présents ne sont pas remplacés. Les diagnostics TLS existants
restent inchangés. Les corrélations request/job/tab sont celles du service ; aucun
nouvel identifiant n’est fabriqué. La conservation de PQError.details après enregistrement puis relecture du job
est vérifiée sur un stockage SQLite fictif ; le contrat du consommateur doit accepter ces nouveaux champs
avant de promettre leur restitution utilisateur.

## Limites et validation installée restante

Ce correctif ne couvre pas DNS/résolution, attente de verrou, robots initiaux ou
installation des gardes exécutés avant ce bloc, ni l’expiration globale du job.
Ces étapes ne sont pas réétiquetées artificiellement comme goto. La lecture réelle
et sa corrélation doivent être refaites après application à la version du service
identifiée. Ne pas copier aveuglément tout browser.py1.0.0 dans un service ancien :
contrôler version, différences et compatibilité, conserver la récupération.
Aucun allow_redirects, contrôle d’URL finale, robots, challenge, profil ou clé modifié.
