# SPEC_API — Contrat de référence (v1)

[Français](SPEC_API.md) | [English](SPEC_API.en.md)

Cette annexe décrit la surface fonctionnelle attendue. Les chemins sont indicatifs mais le schéma livré doit être cohérent, versionné, documenté par OpenAPI et couvert par des tests. **Toute route API client exige authentification ET autorisation par projet.** Les routes d'administration exigent une session admin Web avec CSRF pour mutations, ou un canal administratif strictement séparé non accessible aux clés clients.

**Référence historique :** le contrat livré actuel est [OpenAPI](../openapi.json). Le WebSocket PageQuay livré transmet son ticket dans le premier message, pas dans la query string.

## Administration Web

- `GET /admin` : tableau de bord (login requis).
- `GET /admin/projects` ; formulaires création/édition/activation/arrêt.
- `GET /admin/keys` ; création, affichage initial unique, révocation, rotation, scopes, expiration.
- `GET /admin/settings` ; valeurs globales, overrides par projet, TTL, quotas.
- `GET /admin/audit` ; événements non sensibles.
- `GET /admin/search` ; test manuel de recherche par projet.

## API projet

### Rechercher

`POST /v1/projects/{slug}/search` → `202` + `job_id`, ou résultat immédiat si la tâche est courte et cette variante est documentée.

```json
{
  "engine": "auto",
  "strategy": "fallback",
  "query": "robotique agricole 2026",
  "limit": 10,
  "locale": "fr-FR"
}
```

Réponse finale du job :

```json
{
  "status": "completed",
  "project": "projectx",
  "query": "robotique agricole 2026",
  "results": [
    {
      "rank": 1,
      "title": "Exemple non réel",
      "url": "https://example.org/article",
      "snippet": "Contenu d'exemple",
      "source_engines": ["duckduckgo"],
      "fetched_at": "2026-10-09T18:00:00Z"
    }
  ]
}
```

### Naviguer

`POST /v1/projects/{slug}/tabs` : crée un onglet avec URL autorisée.

```json
{"url": "https://example.org", "wait_until": "domcontentloaded"}
```

`GET /v1/projects/{slug}/tabs` ; `GET /v1/projects/{slug}/tabs/{tab_id}` ; `DELETE /v1/projects/{slug}/tabs/{tab_id}`.

`POST /v1/projects/{slug}/tabs/{tab_id}/navigate` : charge une URL HTTP(S) autorisée ; événement WS en fin de navigation.

`POST /v1/projects/{slug}/tabs/{tab_id}/actions` : actions validées (scope `browser:interact`) :

```json
{
  "actions": [
    {"type": "click", "selector": "#details"},
    {"type": "wait_for_selector", "selector": "article"}
  ]
}
```

### Extraire

`GET /v1/projects/{slug}/tabs/{tab_id}/content?format=text`

`GET /v1/projects/{slug}/tabs/{tab_id}/content?format=html`

`GET /v1/projects/{slug}/tabs/{tab_id}/content?format=links`

`GET /v1/projects/{slug}/tabs/{tab_id}/content?format=metadata`

`GET /v1/projects/{slug}/tabs/{tab_id}/screenshot` (scope `screenshot:read`, taille et fréquence limitées).

### Jobs, événements et authentification WS

`GET /v1/projects/{slug}/jobs/{job_id}` : récupère un job du projet uniquement ; états `queued`, `running`, `waiting_for_human`, `completed`, `failed`, `cancelled`.

`POST /v1/projects/{slug}/jobs/{job_id}/cancel` : annule si autorisé.

`POST /v1/projects/{slug}/ws-ticket` : via Bearer valide, émet ticket WS court, lié à un projet, permissions minimales, usage unique.

`WS /v1/projects/{slug}/events?ticket=<ticket>` : ticket WS **éphémère uniquement**, jamais la clé API ; contrôle Origin lorsque applicable et vérification continue de révocation/permissions. Si un ticket en URL est utilisé, il ne doit jamais être journalisé ; une variante plus sûre en sous-protocole ou message d'authentification initial est acceptable si documentée.

Événement typique :

```json
{
  "event": "challenge.required",
  "project": "projectx",
  "job_id": "opaque-id",
  "tab_id": "opaque-tab-id",
  "at": "2026-10-09T18:00:00Z"
}
```

### État de service

`GET /health/live` : état minimal, aucune information sensible, exposition locale.

`GET /health/ready` : état prêt, informations limitées et authentifiées si sensible.

## En-têtes et erreurs

Appels clients : `Authorization: Bearer <CLE_API>` (jamais dans query string).

Exemple erreur :

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Permission insuffisante pour ce projet",
    "request_id": "opaque-id"
  }
}
```

Codes applicatifs standardisés : `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_INPUT`, `NOT_FOUND`, `RATE_LIMITED`, `NAVIGATION_BLOCKED`, `TIMEOUT`, `BROWSER_CRASHED`, `CHALLENGE_REQUIRED`, `CONFLICT`, `INTERNAL_ERROR`.

Toute ressource créée (job, artefact, onglet, ticket WS, profil) possède un ID non devinable et une relation de propriété serveur vers le projet. Refuser l'accès d'une autre clé même si elle connaît cet ID.

## Extensions futures (hors MVP)

- MCP server sécurisé exposant un jeu limité d'outils, qui appelle l'API interne (pas de CDP public).
- Webhooks sortants signés pour notification des tâches.
- Adaptateurs de recherche additionnels et index de résultats partagés sans mélange des secrets de profils.
- Règles de rétention avancées par domaine.

Ces extensions doivent rester **hors du chemin critique** tant que le socle n'est pas couvert par les tests.
