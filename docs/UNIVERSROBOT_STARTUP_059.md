# Démarrage Chromium — CHG-20261025-059 / TODO-078

[Français](UNIVERSROBOT_STARTUP_059.md) | [English](UNIVERSROBOT_STARTUP_059.en.md)

Timeout de confirmation de minimisation reproduit, causant une fermeture du navigateur.
Les réglages automatiques de fenêtres ne bloquent plus sur la confirmation native : contrôle CDP borné et trace privée. Les commandes humaines gardent leur confirmation stricte.
Commandes explicites, gardes réseau, clés/profils et attente humaine existante inchangées.
Patchs source/runtime distincts ; aucune trace DEBUG-078 dans le code final.
Sauvegardes privées dans PageQuayService/backups/CHG-20261025-059/.
Résultats de tests et recettes réelles dans UniversRobot, même CHG.
