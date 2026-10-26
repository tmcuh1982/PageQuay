# Attente bornée des images — CHG-20261025-055

[Français](UNIVERSROBOT_IMAGE_WAIT_055.md) | [English](UNIVERSROBOT_IMAGE_WAIT_055.en.md)

Demande UniversRobot TODO-359. POST download_image?wait_seconds=0..10 :
200 document du job terminé, sinon même ticket202 ; défaut202 conservé.
Droits relus après attente, aucun replay, quota inchangé.
Patch appliqué seulement à api.py du dépôt et du runtime1.2.2 ; sauvegardes
privées dans PageQuayService/backups/CHG-20261025-055/.
Tests et preuves détaillés dans le dépôt UniversRobot, CHG-20261025-055.
Aucun profil, secret ou base métier modifié.
