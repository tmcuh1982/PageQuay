# Sunflower — CHG-20261027-017

Correction autorisée le 27 octobre 2026 depuis UniversRobot : filtrer le schéma avant url_length ; export HTML sur clone avec suppression explicite des attributs binaires data:image/video/audio, reçu html-inline-media-omission/1 et SHA256 du HTML. Aucun texte retiré, aucune mutation du DOM vivant, pas de relèvement du plafond. Les URL HTTP(S) longues et les limites de texte restent signalées.

Tests Chromium test_sunflower_export.py : données binaires, longues URL HTTPS, DOM vivant intact et plafond texte. 45 régressions structurées/frames réussies sur le candidat runtime. Correctifs du parseur et recette métier dans UniversRobot. Source et runtime patchés séparément pour préserver leurs différences existantes d’attente humaine. Sauvegarde runtime/backups/CHG-20261027-017 ; aucun commit/push effectué par cette livraison.
