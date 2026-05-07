# Migrating Skillful-Alhazen to a New Machine

## What You Need

1. **The backup bundle** (`alhazen-backup-YYYYMMDD.tar.gz`) — contains TypeDB export + Qdrant snapshots
2. **The git repo** — all code, schemas, and skills are in git
3. **Prerequisites** on the target machine: `uv`, `docker`, `git`

## Step 1: Clone and Build

```bash
git clone https://github.com/sciknow-io/skillful-alhazen
cd skillful-alhazen
make build
```

This installs Python deps, clones all skills, starts TypeDB, and loads schemas into a fresh empty database.

## Step 2: Copy the Backup Bundle

Copy `alhazen-backup-YYYYMMDD.tar.gz` to the target machine, then extract:

```bash
mkdir -p ~/.alhazen/cache
tar xzf alhazen-backup-YYYYMMDD.tar.gz -C ~/.alhazen/cache
```

This creates:
- `~/.alhazen/cache/typedb/alhazen_notebook_export_YYYYMMDD_HHMMSS.zip`
- `~/.alhazen/cache/qdrant-snapshots/*.snapshot`

## Step 3: Restore TypeDB

The fresh `make build` created an empty database with the correct schema. To load data:

```bash
# Delete the empty database
uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions
d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
d.databases.get('alhazen_notebook').delete()
d.close()
print('Deleted empty database')
"

# Import from backup (recreates database with schema + data)
uv run python .claude/skills/typedb-notebook/typedb_notebook.py import-db \
  --zip ~/.alhazen/cache/typedb/alhazen_notebook_export_*.zip \
  --database alhazen_notebook

# Reload current schemas (adds any new types from skills added after the backup)
make db-init
```

**Verify:**
```bash
uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType
d = TypeDB.driver('localhost:1729', Credentials('admin','password'), DriverOptions(is_tls_enabled=False))
with d.transaction('alhazen_notebook', TransactionType.READ) as tx:
    r = list(tx.query('match \$e isa alh-identifiable-entity, has id \$id; fetch { \"id\": \$id };').resolve())
    print(f'Entities: {len(r)}')
d.close()
"
```

## Step 4: Restore Qdrant

Qdrant starts with `docker compose up -d qdrant`. Snapshots must be copied INTO the container, then recovered:

```bash
# Ensure Qdrant is running
docker compose up -d qdrant
sleep 5

# Copy snapshots into the container
docker cp ~/.alhazen/cache/qdrant-snapshots/. alhazen-qdrant:/qdrant/snapshots-import/

# Recover each collection from its snapshot
for snap in ~/.alhazen/cache/qdrant-snapshots/*.snapshot; do
  snap_name=$(basename "$snap")
  # Extract collection name (everything before the first numeric ID segment)
  coll_name=$(echo "$snap_name" | sed 's/-[0-9]\{13,\}-.*//')

  echo "Recovering $coll_name from $snap_name..."
  curl -s -X POST "http://localhost:6333/collections/${coll_name}/snapshots/recover" \
    -H "Content-Type: application/json" \
    -d "{\"location\": \"file:///qdrant/snapshots-import/${snap_name}\"}"
  echo ""
done
```

**Verify:**
```bash
curl -s http://localhost:6333/collections | python3 -c "
import json, sys
colls = json.load(sys.stdin)['result']['collections']
for c in colls:
    name = c['name']
    info = json.loads(__import__('urllib.request', fromlist=['urlopen']).urlopen(f'http://localhost:6333/collections/{name}').read())
    pts = info['result']['points_count']
    print(f'  {name}: {pts} points')
"
```

## Step 5: Restore Artifact Cache (Optional)

If you need cached artifacts (PDFs, HTMLs, JSON exports):

```bash
# On source machine
tar czf alhazen-cache.tar.gz -C ~/.alhazen cache/

# On target machine
tar xzf alhazen-cache.tar.gz -C ~/.alhazen
```

This is only needed if skills reference cached files via `cache-path` attributes. The knowledge graph works without it — you just can't read the original source files.

## Step 6: Start the Dashboard

```bash
# Development mode
cd dashboard && npm install && npm run dev

# Or Docker mode
docker compose build dashboard
docker compose up -d dashboard
# Available at http://localhost:3001
```

## Creating a Backup

On the source machine:

```bash
# TypeDB
make db-export

# Qdrant (all collections)
collections=$(curl -s http://localhost:6333/collections | python3 -c "import json,sys; [print(c['name']) for c in json.load(sys.stdin)['result']['collections']]")
mkdir -p ~/.alhazen/cache/qdrant-snapshots
for coll in $collections; do
  curl -s -X POST "http://localhost:6333/collections/${coll}/snapshots" > /dev/null
  docker cp alhazen-qdrant:/qdrant/snapshots/${coll}/. ~/.alhazen/cache/qdrant-snapshots/
done

# Bundle
tar czf ~/.alhazen/cache/alhazen-backup-$(date +%Y%m%d).tar.gz \
  -C ~/.alhazen/cache \
  typedb/ \
  qdrant-snapshots/
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `make db-init` fails after import | Schema conflict — the backup may have types from an older schema version. Run `make db-init` errors are usually additive `define` conflicts on existing types. These are safe to ignore if the data loaded correctly. |
| Qdrant recovery returns 404 | The collection doesn't exist yet. Qdrant auto-creates it from the snapshot. If it still fails, the snapshot file may be corrupted — re-export from the source. |
| Dashboard shows no data | Check `TYPEDB_DATABASE=alhazen_notebook` is set. The dashboard API routes call `uv run python` which needs the correct database name. |
| `make build` fails on dismech clone | The `alhazen-skill-dismech` repo may be private. Skip it with `make build-env build-skills build-dashboard build-db` (dismech is optional). |
