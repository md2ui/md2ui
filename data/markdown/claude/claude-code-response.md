Let's design this as three coordinated pieces: git holds the schema definitions and the "what's active" manifest, Postgres mirrors that for fast runtime lookups and audit trail, and Laravel ties them together with a sync command + resolver service.

## 1. Repo layout

```
resources/schemas/
  ├── transfer-confirmed/
  │     ├── v1.json
  │     └── v2.json
  ├── transfer-failed/
  │     ├── v1.json
  │     └── v2.json
  ├── password-reset/
  │     └── v1.json
  ├── security-alert/
  │     └── v1.json
  └── active.json          ← the "pointer" manifest, also git-tracked
```

`active.json` is the important part — it's what makes git the actual source of truth for *rollback*, not just schema content:

```json
{
  "transfer-confirmed": 2,
  "transfer-failed": 2,
  "password-reset": 1,
  "security-alert": 1
}
```

Schema version files are **immutable once merged** — a change to `order-confirmed` payload shape means adding `v3.json`, never editing `v2.json`. Enforce this in CI (see §4).

## 2. Database schema

Two tables: an append-only version log, and the active pointer (kept separate so "register a version" and "activate a version" are distinct operations — this matters for the deprecation-window case below).

```php
Schema::create('message_schemas', function (Blueprint $table) {
    $table->id();
    $table->string('kind');
    $table->unsignedInteger('version');
    $table->jsonb('schema');
    $table->string('checksum', 64);        // sha256 of the file, detects drift
    $table->string('git_commit_sha', 40);
    $table->enum('status', ['registered', 'active', 'deprecated', 'retired'])
          ->default('registered');
    $table->timestamps();

    $table->unique(['kind', 'version']);
    $table->index('kind');
});

Schema::create('schema_active_versions', function (Blueprint $table) {
    $table->string('kind')->primary();
    $table->unsignedInteger('active_version');
    $table->unsignedInteger('min_supported_version')->default(1); // deprecation floor
    $table->timestamp('activated_at');
});
```

- `message_schemas` is **append-only** — rows are never edited, only status transitions (`registered → active → deprecated → retired`). This is your audit trail: "what did this schema look like when notification X was generated" is always answerable.
- `schema_active_versions` is the fast-lookup pointer table — one row per kind, tells the resolver which version to use when a caller doesn't pin one.
- `min_supported_version` lets you enforce a deprecation window (reject requests pinning a version older than this) without deleting historical rows.

Every row in your `notifications` table stores `schema_version` alongside `kind`, so historical validation/replay is always exact.

## 3. Sync command (git → DB)

```php
// app/Console/Commands/SyncSchemas.php
class SyncSchemas extends Command
{
    protected $signature = 'schemas:sync {--dry-run}';

    public function handle(SchemaSyncer $syncer): int
    {
        $result = $syncer->sync(dryRun: $this->option('dry-run'));

        $this->table(['kind', 'version', 'action'], $result->rows());

        return $result->hasErrors() ? self::FAILURE : self::SUCCESS;
    }
}
```

`SchemaSyncer` logic:

1. Walk `resources/schemas/*/v*.json`, compute sha256 checksum per file.
2. For each file: if `(kind, version)` doesn't exist in `message_schemas` → insert as `registered`. If it exists → **verify checksum matches**; a mismatch is a hard error (someone edited an immutable version file — fail the deploy).
3. Read `active.json`, upsert `schema_active_versions` for each kind — but only if the target version exists in `message_schemas` with status `registered` or `active` (never `retired`).
4. Mark any version that *was* active but no longer is as `deprecated` (not `retired` — still valid for the deprecation window).
5. Stamp `git_commit_sha` from `git rev-parse HEAD` (or CI's `$GITHUB_SHA`) on every inserted row.

This command is **idempotent** — safe to run on every deploy, only acts on diffs.

## 4. Version control and rollback

**Normal path (git-driven):**
- New schema version → add `vN.json`, bump `active.json`, PR review, merge, deploy runs `schemas:sync` → new version registered and activated in one deploy.
- Rollback → **git revert the `active.json` change** (not the schema file itself — that stays, it's immutable history), redeploy, `schemas:sync` flips the pointer back. This is a normal PR/revert, fully auditable through git log.

**Emergency path (DB-direct, faster than a deploy):**

```php
Artisan::call('schemas:rollback', [
    'kind' => 'order-confirmed',
    '--to' => 1,
]);
```

This directly updates `schema_active_versions` without waiting for a deploy — for when a bad schema is actively breaking production and you can't wait for CI. **Requirement**: this command must refuse to activate a version not already `registered` in the DB (so it can only roll back to something that previously existed, never introduce new content out-of-band), and it should emit a Slack/PagerDuty alert plus require someone to backport the equivalent `active.json` change afterward — otherwise the next deploy's `schemas:sync` will silently re-activate the bad version and undo the emergency rollback.

**CI guardrails** (GitHub Actions, before merge):
- Validate every `vN.json` is valid JSON Schema (draft check via `opis/json-schema`'s meta-schema validation).
- Diff against the previous commit: if an existing `vN.json` file changed content → fail the build ("schema versions are immutable, add a new version instead").
- Run `php artisan schemas:sync --dry-run` and post the diff as a PR comment, so reviewers see exactly what will activate.

## 5. How an API request asks for a specific schema

Since this is internal service-to-service, keep it explicit in the payload rather than content-negotiation headers:

```json
POST /internal/notifications
{
  "kind": "order-confirmed",
  "schema_version": 2,
  "user_id": "...",
  "payload": { "orderId": "...", "total": 42.50 }
}
```

- `schema_version` is **optional** — omit it and the resolver uses the current active version for that kind. This is the common case; most callers shouldn't need to know versions exist.
- Pinning it explicitly matters during a migration window — a producer service that hasn't been updated to send the new shape yet keeps pinning `1` while other callers move to `2`, until `min_supported_version` is raised and `1` is retired.

Resolver service:

```php
class SchemaResolver
{
    public function resolve(string $kind, ?int $requestedVersion): MessageSchema
    {
        $version = $requestedVersion
            ?? Cache::remember("schema_active:{$kind}", 300,
                fn () => SchemaActiveVersion::where('kind', $kind)->value('active_version'));

        $minSupported = Cache::remember("schema_min:{$kind}", 300,
            fn () => SchemaActiveVersion::where('kind', $kind)->value('min_supported_version'));

        if ($version < $minSupported) {
            throw new UnsupportedSchemaVersionException($kind, $version, $minSupported);
        }

        return Cache::remember("schema:{$kind}:{$version}", 3600,
            fn () => MessageSchema::where(compact('kind', 'version'))->firstOrFail());
    }
}
```

Validation happens in a `FormRequest` or a dedicated Action, using the resolved schema against `opis/json-schema` (handles draft-07/2020-12, actively maintained, good Laravel fit):

```php
class ValidateNotificationPayload
{
    public function __construct(private SchemaResolver $resolver) {}

    public function handle(array $request): void
    {
        $schema = $this->resolver->resolve($request['kind'], $request['schema_version'] ?? null);

        $validator = new \Opis\JsonSchema\Validator();
        $result = $validator->validate(
            \Opis\JsonSchema\Helper::toJSON($request['payload']),
            \Opis\JsonSchema\Helper::toJSON($schema->schema)
        );

        if (!$result->isValid()) {
            throw new SchemaValidationException($result->error());
        }
    }
}
```

## 6. Caching (keeps the hot path off the DB)

- Compiled schema + active-version pointer cached in Redis (as shown above), TTL 5 min as a safety net.
- `schemas:sync` **actively busts the cache** on activation/rollback (`Cache::forget` for affected keys) rather than relying purely on TTL — so a rollback takes effect immediately, not after the cache naturally expires.
- Optionally preload all active schemas into an in-process array cache at container boot (Fargate task startup) for near-zero-latency validation, refreshing on the same cache-bust signal — same pattern used for the localization strings.

## Summary of the flow

```
PR: add v3.json + bump active.json
  → CI validates immutability + schema correctness
  → merge → deploy runs `schemas:sync`
  → new row inserted (status: registered → active), old row → deprecated
  → cache busted for that kind
  → Generation Service's next request resolves v3 automatically (or v2 if explicitly pinned, until min_supported_version rises)

Bad schema in prod
  → `php artisan schemas:rollback order-confirmed --to=2` (immediate)
  → alert fired, PR opened to revert active.json in git (reconciliation)
```

This keeps git as the reviewable, revertible source of truth for both schema *content* and *what's active*, while Postgres gives you fast runtime resolution and a permanent audit trail tying every generated notification to the exact schema version it was validated against.
