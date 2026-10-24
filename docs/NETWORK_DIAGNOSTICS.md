# Diagnostic des refus réseau

Chaque refus conserve code/cause et une URL HTTP(S) publique expurgée, le type de
ressource, le caractère navigation, le rôle de frame et main_document. Ce dernier
vaut true uniquement pour une navigation dans la frame principale ; scripts,
images, fetch et autres sous-ressources valent false, même dans la frame principale.
Les navigations enfants valent false avec is_navigation_request=true.

Les refus DNS des précontrôles de navigation sont exposés dans
error.details.network_refusal, même sans job/onglet. Les refus du garde sont dans
network_policy.refusals des résultats/artefacts. Aucun changement de code HTTP,
droits ou règle de sécurité ; un export affecté reste partiel.

URL sans userinfo, query ni fragment ; url_redacted indique une modification,
url_truncated indique le plafond2048. Les hôtes privés/locaux et URL invalides
sont omis (url=null). Aucun DNS supplémentaire. Ce filtre ne détecte pas tous les
secrets qu’un site pourrait placer dans un chemin public : ces diagnostics gardent
les contrôles d’accès des artefacts privés.32refus maximum, refusals_truncated
signale les suivants. resource_type utilise le vocabulaire Playwright fermé.

[Tests de régression](../tests/test_network_denials_browser.py).
