# ERP Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix accounting-correctness, crash, and performance defects in the local-only Flask+SQLite ERP without breaking the GitHub-as-transfer multi-machine workflow.

**Architecture:** Additive, SQLite-safe fixes only — server-side recompute of money, single-transaction writes, SQL-side filtering/pagination, UUID-leaning identity; no server DB, no live-sync daemon, no encryption.

**Tech Stack:** Flask 3.1.2, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.44, SQLite, pytest.

**Spec:** `src/REFACTORING_TASKS.md` + agent-board votes of 2026-10-08 (accounting / performance / scope-guard). Board decisions are authoritative for priority; this plan argues from them.

## Global Constraints

- SQLite-only — REJECT Postgres/MySQL/Litestream/live-sync migration.
- GitHub-as-transfer preserved — never sync the live hot `data/shop.db`; transfer artifact only.
- Data-visibility / internet-hardening OUT of scope — no secrecy, CSP, rate-limit-for-internet, or PII-enumeration fixes.
- Single-transaction per mutating `db.*` method with rollback on failure.
- Money recomputed server-side; client `total_amount` is advisory only.
- All new constraints additive + backward-compatible with existing SQLite file.

## Review Focus

- Double-click create with same `Idempotency-Key` returns existing row instead of duplicate — expect 200 with same `display_id`.
- `quantity=abc` in sale form re-renders form with validation message — expect 200 + flash, never 500.
- Editing work-order parts when a linked purchase has `paid_amount > 0` refuses or preserves payment — expect block or preserved `paid_amount`.
- Search `?q=` with 10k shops returns in <1s and ≤200 rows scored — expect SQL prefilter + LIMIT.
- Pulling a transfer artifact twice does not duplicate rows — expect unique `(source_type, source_id)` rejection of replay.

---

### Task 1: Crash guards + 405 fix

**Files:**
- Modify: `src/helpers/utils.py` (add `safe_float`, `safe_int`)
- Modify: `src/services/sale.py:126-128`, `src/services/purchase.py:147-148`
- Modify: `src/db/database.py:1213` (`Buyer.to_dict`), `:534,646` (`int()` paths)
- Modify: `src/routers/shops.py:221,234` (`int(tag_id)`)
- Modify: `main.py:110-121` (405 + 429 fallback)
- Test: `tests/test_helpers.py`, `tests/test_routers.py`

**Interfaces:**
- Consumes: existing `ValidationError` in `src/helpers/exceptions.py`
- Produces: `safe_float(raw: str | None, field: str) -> float`, `safe_int(raw: str | None, field: str) -> int` (raise `ValidationError` on garbage; routers already catch it)

- [ ] **Step 1: Write failing tests for `safe_float`/`safe_int` + Buyer None-date + 405 redirect**

```python
def test_safe_float_rejects_garbage():
    import pytest
    from src.helpers.utils import safe_float
    from src.helpers.exceptions import ValidationError
    with pytest.raises(ValidationError):
        safe_float("abc", field="quantity")

def test_buyer_to_dict_none_date():
    from src.db.database import Buyer
    b = Buyer(company_name="x", created_at=None)
    assert b.to_dict()["created_at"] is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_helpers.py tests/test_routers.py -v`
Expected: FAIL with "safe_float not defined" / `AttributeError: None.isoformat`

- [ ] **Step 3: Implement `safe_float`/`safe_int` in `src/helpers/utils.py`, swap 4 call sites, guard `Buyer.to_dict`, fix `url_for('core.index')` → `url_for('shops.index')` in `main.py`**

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_helpers.py tests/test_routers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/helpers/utils.py src/services/sale.py src/services/purchase.py src/db/database.py src/routers/shops.py main.py tests/test_helpers.py tests/test_routers.py
git commit -m "fix: crash guards and 405 redirect target"
```

### Task 2: Single-transaction writes

**Files:**
- Modify: `src/db/database.py:435-508` (`add/update_sale`), `:522-630` (`add/update_supplier_purchase`), `:640-896` (`add/update_work_order`), `:312-415` (`add/update_buyer`, `add_inventory`)
- Test: `tests/test_database.py`, `tests/test_delete_pipeline.py`

**Interfaces:**
- Consumes: `self.session` (Flask-SQLAlchemy scoped session)
- Produces: same method signatures; on exception session rolled back and exception re-raised (no signature change)

- [ ] **Step 1: Write failing test — failed update leaves original rows intact**

```python
def test_update_sale_rollback_on_bad_item(db_session):
    sale_id = seed_sale(db_session)  # helper in test
    with pytest.raises(Exception):
        db_session_update_sale(sale_id, {"items": [{"quantity": "abc"}]})
    assert count_sale_items(sale_id) == 2  # unchanged, not zero
```

- [ ] **Step 2: Run to verify it fails (currently leaves zero items)**

Run: `pytest tests/test_database.py::test_update_sale_rollback_on_bad_item -v`
Expected: FAIL — items deleted, count 0

- [ ] **Step 3: Wrap each mutating method in `try: <writes + single commit> except: self.session.rollback(); raise`**

One commit per method; remove mid-loop commits; keep `delete_buyer` pattern as template.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_database.py tests/test_delete_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/database.py tests/test_database.py
git commit -m "fix: atomic transactions with rollback for all writes"
```

### Task 3: Server-side money recompute

**Files:**
- Modify: `src/db/database.py:450-451,483-484,539-550,588-607,652-658,771-790`
- Modify: `src/schema/sale.py`, `src/schema/purchase.py` (import-only, no rewrite — wire into routers)
- Test: `tests/test_services.py`, `tests/test_schema.py`

**Interfaces:**
- Consumes: Task 1 `safe_float`, Task 2 transactions
- Produces: `compute_totals(items: list[dict]) -> float`, `derive_pending(quoted: float, paid: float) -> float` (paid clamped `0 <= paid <= quoted`, else `ValidationError`)

- [ ] **Step 1: Write failing tests**

```python
def test_purchase_total_ignores_client_total():
    total = compute_totals([{"quantity": 2, "rate": 100, "total_amount": 9999}])
    assert total == 200.0

def test_pending_derived():
    assert derive_pending(quoted=1000, paid=300) == 700.0
    with pytest.raises(ValidationError):
        derive_pending(quoted=1000, paid=1500)
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_services.py -v`
Expected: FAIL — functions not defined / wrong totals

- [ ] **Step 3: Implement recompute in `database.py` — `total = Σ qty×rate`, ignore client `total_amount` unless within 0.01, derive `pending = quoted - paid`, fix zero-qty `rate = 0` (not `price`)**

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_services.py tests/test_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/database.py tests/test_services.py
git commit -m "fix: server-side money recompute and pending derivation"
```

### Task 4: Non-destructive work-order update

**Files:**
- Modify: `src/db/database.py:748-884` (`update_work_order`)
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: Task 2 transactions, Task 3 money helpers
- Produces: same `update_work_order(id, data)` signature; preserves `display_id/voucher_id/paid_amount/payment_status` on matched purchases; blocks parts-rewrite when `paid_amount > 0` unless explicit `allow_paid_rewrite=True`

- [ ] **Step 1: Write failing test — paid purchase survives parts edit**

```python
def test_update_work_order_preserves_paid():
    wo_id = seed_work_order_with_paid_purchase(paid=500)
    update_work_order(wo_id, {"parts": [{"name": "new-part", "qty": 1}]})
    assert get_linked_purchase(wo_id).paid_amount == 500.0
    assert get_linked_purchase(wo_id).voucher_id == original_voucher_id
```

- [ ] **Step 2: Run to verify fail (currently paid reset to 0 + new voucher)**

Run: `pytest tests/test_database.py::test_update_work_order_preserves_paid -v`
Expected: FAIL

- [ ] **Step 3: Replace bulk-delete (`802-803`) with diff-by-id: keep matched rows, insert/delete delta only**

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/database.py tests/test_database.py
git commit -m "fix: non-destructive work-order update preserves payments"
```

### Task 5: Search prefilter + pagination + every-page tax

**Files:**
- Modify: `src/db/database.py:31-105` (`get_all_shops`, `search_shops`)
- Modify: `src/routers/shops.py:43-57,168-176` (clamp `per_page <= 100`, DB limit/offset for search branch)
- Modify: `src/services/buyer.py:24`, `src/services/sale.py:26`, `src/services/purchase.py:27` (pass limit/offset through)
- Modify: `main.py:67-81,141-145` (skip analytics for `/dashboard/*`, `/api/*`; cache categories)
- Test: `tests/test_routers.py`

**Interfaces:**
- Consumes: existing `query.paginate` / `limit+offset` pattern in `shops.shop_list:46-57`
- Produces: `search_shops(query, limit=200)` — SQL `ilike` prefilter before Python `calculate_score`; `to_dict` only on paginated slice

- [ ] **Step 1: Write failing test — unbounded per_page clamped**

```python
def test_api_shops_per_page_clamped(client):
    r = client.get("/api/shops?per_page=999999")
    assert len(r.get_json()) <= 100
```

- [ ] **Step 2: Run to verify fail (currently full dump)**

Run: `pytest tests/test_routers.py::test_api_shops_per_page_clamped -v`
Expected: FAIL

- [ ] **Step 3: Implement SQL prefilter + LIMIT, clamp per_page, cache categories (TTL/invalidate-on-write), skip analytics for dashboard/api**

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_routers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/database.py src/routers/shops.py src/services/buyer.py src/services/sale.py src/services/purchase.py main.py tests/test_routers.py
git commit -m "perf: prefilter search, clamp pagination, cut per-request tax"
```

### Task 6: Merge-safe identity + constraint guards (additive only)

**Files:**
- Modify: `src/db/database.py` models only (additive): `Sale`, `Buyer` → UUID PK pattern (match `SupplierPurchase:1339`, `WorkOrder:1421`); `CheckConstraint` for `quantity>0`, `movement_type/payment_status` enums; `index=True` on `BuyerContact.buyer_id:1220`, `Sale.buyer_id:1283`, `SaleItem.sale_id:1309`, `InventoryItem.shop_id:1254`; `UniqueConstraint(raw_material_id, source_type, source_id)` on `StockMovement`; `client_key String(64) unique` on `Sale`/`SupplierPurchase` for idempotency
- Create: `docs/transfer-protocol.md` (live-DB never synced; `sqlite3 .backup` artifact + timestamp; WAL/journal discipline)
- Test: `tests/test_config.py`, `tests/test_database.py`

**Interfaces:**
- Consumes: Tasks 2–4 (stable write paths)
- Produces: `generate_id(prefix)` retry-on-`IntegrityError`; routers accept `Idempotency-Key` header → `client_key` lookup-or-create

- [ ] **Step 1: Write failing tests**

```python
def test_duplicate_display_id_retries():
    id1 = generate_id("BEW-S-"); id2 = generate_id("BEW-S-")
    assert id1 != id2

def test_idempotent_create_returns_same_row(client):
    r1 = client.post("/dashboard/sales/new", data=..., headers={"Idempotency-Key": "k1"})
    r2 = client.post("/dashboard/sales/new", data=..., headers={"Idempotency-Key": "k1"})
    assert r1_sale_id == r2_sale_id
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_database.py tests/test_config.py -v`
Expected: FAIL

- [ ] **Step 3: Implement additive constraints + UUID-leaning IDs + idempotency-key column (no table rewrite, no Postgres)**

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_database.py tests/test_config.py tests/test_services.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/database.py docs/transfer-protocol.md tests/test_database.py tests/test_config.py
git commit -m "feat: merge-safe identity and constraint guards"
```
