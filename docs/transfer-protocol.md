# DB transfer protocol — GitHub as the transfer mechanism

> The live database file is **never** committed, synced, or merged.
> GitHub carries **code only**. The database travels between machines as a
> timestamped `sqlite3 .backup` artifact copied out-of-band (USB drive,
> `scp`, shared folder). This document pins that workflow.

## 1. Rules (binding)

1. **Live-DB never synced.** `data/shop.db`, `*.sqlite`, WAL (`-wal`) and
   journal (`-journal`) files MUST NOT be committed to git. They are
   covered by `.gitignore`. If `git status` ever shows a database file,
   stop and remove it from tracking before doing anything else.
2. **Code travels via git; data travels via backup artifact.** To move
   state from machine A to machine B: create a backup artifact on A
   (§2), copy it out-of-band, restore it on B (§3).
3. **One writer per file.** Never open the same DB file from two machines
   (e.g. over a network share). SQLite locking over remote filesystems
   corrupts. Each machine owns its file; the artifact moves point-in-time
   snapshots, and §4 explains how overlapping identities converge.
4. **No Postgres, no live-sync daemons, no encryption, no whole-table
   migrations.** Identity safety comes from `client_key` idempotency +
   unique `display_id` + sequence re-sync (all additive, see §4).

## 2. Creating a backup artifact (source machine)

Quiesce writers first (stop the Flask app), then snapshot — never copy
the live file while the app runs:

```bat
REM Windows (cmd): stop the app, then:
sqlite3 data\shop.db ".backup 'shop-2026-10-08-machineA.db'"
```

```sh
# Linux/macOS: stop the app, then:
sqlite3 data/shop.db ".backup 'shop-2026-10-08-machineA.db'"
```

Name artifacts `shop-<UTC-date>-<machine>.db` so provenance is visible.
`.backup` copies through the SQLite pager (consistent snapshot even with
WAL present); a raw file copy is NOT equivalent.

WAL / journal discipline:

- Default mode keeps rollback-journal files next to the DB. The
  `.backup` output is a single self-contained file — transfer **only**
  that file, never `-wal`/`-journal` sidecars.
- Do not enable WAL (`PRAGMA journal_mode=WAL`) to "share" a DB across
  machines. WAL is a single-host crash-recovery mechanism, not a sync
  transport.

## 3. Restoring on the target machine (destructive — target file is replaced)

```bat
REM Windows (cmd): stop the app, back up the current file, then replace:
copy data\shop.db data\shop.db.before-2026-10-08.bak
copy shop-2026-10-08-machineA.db data\shop.db
python -c "import sqlite3; print(sqlite3.connect('data/shop.db').execute('PRAGMA integrity_check').fetchone())"
```

Start the app afterwards. Startup runs `db.create_all()` plus
`ensure_merge_safe_columns()` (`src/db/database.py`), which backfills
any missing additive guards (`client_key` column, UNIQUE indexes) on the
restored file — no manual migration step.

## 4. How overlapping identities converge

Two machines sharing one DB file lineage will pick overlapping
`BEW-TRX-*` / `BEW-BUY-*` sequence numbers. Three additive guards make
this safe without ever rewriting a table:

1. **`display_id` UNIQUE guards.** `ensure_merge_safe_columns()`
   creates `uq_*_display_id` unique indexes when the legacy file lacks
   them (skipped with a warning if legacy duplicates exist — dedupe
   those rows first; fresh DBs enforce via the model).
2. **Sequence re-sync on collision.** Writers (`add_sale`,
   `add_supplier_purchase`, `add_buyer`, `add_work_order`) catch a
   `display_id` UNIQUE collision, roll back, jump `id_sequences` past
   the highest taken number (`_resync_id_sequence`), and retry (bounded:
   3 attempts). `generate_id()` itself retries `IDSequence`-row races
   and falls back to a `uuid4` suffix under pathological contention.
3. **`client_key` idempotency.** `sales.client_key` /
   `supplier_purchases.client_key` (`String(64)`, UNIQUE, nullable) store
   the caller's `Idempotency-Key` header. Repeat submissions
   (double-click, retry after a timeout, same key from two machines)
   return the original row instead of inserting a duplicate
   (lookup-or-create, including the lost-a-race path). Routers
   (`POST /dashboard/sales/new`, `POST /dashboard/purchases/new`)
   forward the `Idempotency-Key` header; services accept it as
   `client_key`. NULL keys keep legacy behavior (no lookup). Clients
   SHOULD send a UUIDv4 per user intent (one key per "Save" click, not
   per page load).

## 5. Deferred: integer-PK → UUID migration (NOT done)

`Sale.id` / `Buyer.id` stay Integer PKs. Changing a PK type in SQLite
requires rebuilding each table plus every referencing FK column
(`sale_items.sale_id`, `sales.buyer_id`, `work_orders.company_id`,
`buyer_contacts.buyer_id`) — a whole-table rewrite the project rejects
— and would break all `<int:sale_id>` routes and existing FK values.
`SupplierPurchase` / `WorkOrder` already use UUID PKs for new rows.
Revisit only with a tested rebuild migration and route changes; until
then `display_id` + `client_key` are the merge-safe identity.

## 6. Guard reference (fresh DBs enforce via model; legacy files via §3 startup backfill where SQLite allows)

- `CHECK (quantity > 0)` on `sale_items`, `supplier_purchase_items`,
  `work_order_parts (qty)`, `stock_movements`.
- `CHECK (movement_type IN ('IN','OUT','ADJUST'))` on `stock_movements`.
- `CHECK (payment_status IN ('pending','paid','partial','cancelled'))`
  on `supplier_purchases`, `work_orders`.
- `UNIQUE (raw_material_id, source_type, source_id)` on
  `stock_movements` (`uq_stock_movement_source`).
- Indexes on `buyer_contacts.buyer_id`, `sales.buyer_id`,
  `sale_items.sale_id`, `inventory_items.shop_id`,
  `stock_movements.supplier_id`.
- `CHECK` constraints cannot be added to existing tables without a
  rewrite, so legacy files enforce them at the service/schema layer
  (pydantic `ge=0.0`, `PaymentStatus` / `StockMovementType` enums) while
  fresh files enforce them in the database too.
