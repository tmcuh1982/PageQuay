# AVIF explicite — CHG-20261029-002 / UniversRobot TODO-478

AVIF statique ajouté sur demande explicite à allowed_media_types ; défaut JPEG/PNG/WebP conservé.
Original complet ISO-BMFF borné, avif exigé, avis refusé, top-level boxes exactes ; décodage Pillow AVIF dans le processus jetable CPU5s/wall10s existant.
Dimensions AVIF≤8192/axe et16Mpx, animation refusée,20Mo maximum, URL exacte/proxy/droits/SHA conservés.
Les refus MIME portent observed_mime borné100caractères. Schémas requête/reçu/artefact AVIF alignés.
Aucune migration, permission, clé ou infrastructure ajoutée ; source et runtime modifiés sous préconditions SHA avec sauvegarde.
Tests9AVIF plus42tests image/GIF non-browser réussis dans copie avant installation.
