# Diagnostics de navigation

Une navigation refusée par Chromium reste refusée. PageQuay conserve le code
`UPSTREAM_UNAVAILABLE` et le message générique `Navigation failed`, mais ajoute
des `error.details` lorsque la première ligne de l'erreur `Page.goto` contient
un code réseau reconnu :

```json
{
  "cause": "TLS_CERTIFICATE_DATE_INVALID",
  "stage": "navigation",
  "browser_error": "ERR_CERT_DATE_INVALID"
}
```

Ce code indique une période de validité TLS incorrecte ; il ne distingue pas
à lui seul certificat expiré et certificat pas encore valide. Aucune URL,
exception brute, call log ou en-tête n'est repris. Une erreur JavaScript,
une mention dans le call log, un code inconnu ou un autre point d'appel n'est
pas interprété comme un diagnostic réseau. Les refus réseau, les délais et les
crashes gardent leur classification existante. Aucun certificat n'est ignoré.

## Reproduction TM Robot

URL exacte : `https://www2.tm-robot.com/zh-hant/tm-robot/`.
Service PageQuay configuré et clé existante avec `browser:interact` et accès
au job ; ne pas copier sa valeur dans une procédure ou un log. Créer un onglet
avec cette URL et `allow_redirects: true`, puis consulter le job retourné.
À la date du 14 octobre 2026, le site présente un certificat expiré : attendu,
job `failed`, `UPSTREAM_UNAVAILABLE`, détails ci-dessus, aucun contenu extrait.
Après renouvellement du certificat, le site peut légitimement réussir.

Sur un service/profil jetables au code préparé, la recette API réelle donne :
job `e0ee802ddb201290b56775325f906ae8`, tab `f28ce658458781e0301f7246705ab616`,
request `6bd3a8bb61bdf84222e3dd5b`, avec les détails attendus. Source initiale
`af4642f`, correctif de cette branche ; aucune installation ou clé existante
modifiée durant la recette. Pas d'artefact ni de frame disponible.

## Vérification

Tests du point d'appel `BrowserManager.navigate`, délais/crashes inchangés et
non-divulgation d'URL/call log, puis suite générale : 245 réussis, 63 ignorés
(notamment recettes navigateur facultatives). Test API jetable avec Chromium
réel distinct de cette suite. Ce changement ne rétablit pas le certificat du
site et ne transfère pas l'approbation à une autre URL.
