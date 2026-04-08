"""Add bitrix_id_int BIGINT column to all dynamic Bitrix tables (idempotent, handles legacy numeric bitrix_id).

Приводит все динамические таблицы Bitrix (crm_*, bitrix_*, stage_history_*)
к каноническому виду:
    bitrix_id       VARCHAR(50)  UNIQUE (логический ключ)
    bitrix_id_int   BIGINT       INDEX  (числовое представление для JOIN/FK)

Миграция обрабатывает три состояния:
  A) bitrix_id уже строковый, колонки bitrix_id_int нет
     → ADD COLUMN bitrix_id_int BIGINT + бэкфилл по регекспу + CREATE INDEX
  B) bitrix_id числовой (legacy), колонки bitrix_id_int нет
     → DROP UNIQUE → RENAME bitrix_id → bitrix_id_int → ADD COLUMN bitrix_id VARCHAR(50)
       → бэкфилл из bitrix_id_int::text → CREATE UNIQUE INDEX на bitrix_id
       → CREATE INDEX на bitrix_id_int → SET NOT NULL на bitrix_id
  C) обе колонки уже есть — no-op (skip).

Поддерживает PostgreSQL и MySQL.
Идемпотентна: повторный `alembic upgrade head` не падает на любом состоянии БД.

Revision ID: 021
Revises: 020
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TABLE_PREFIXES = ("crm_", "bitrix_", "stage_history_")

# PG identifier limit is 63 chars. We truncate index names that exceed it.
PG_MAX_IDENT = 63

# String-like data_type values returned by information_schema across dialects.
STRING_TYPES = {
    "character varying",
    "varchar",
    "text",
    "char",
    "character",
    "longtext",
    "mediumtext",
    "tinytext",
}

# Numeric data_type values.
NUMERIC_TYPES = {
    "bigint",
    "integer",
    "int",
    "smallint",
    "numeric",
    "decimal",
    "mediumint",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Best-effort logger — alembic captures print output during migrations."""
    print(f"[migration 021] {msg}")


# ---------------------------------------------------------------------------
# Dialect detection
# ---------------------------------------------------------------------------

def _dialect(bind) -> str:
    """Return 'postgresql' or 'mysql' (or the raw dialect name)."""
    return bind.dialect.name


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------

def _find_tables_with_bitrix_id(bind) -> list[tuple[str, str, bool]]:
    """Return list of (table_name, bitrix_id_data_type, has_bitrix_id_int).

    Uses a single query against information_schema.columns filtered by table
    name prefix (crm_, bitrix_, stage_history_). Works for both PostgreSQL
    and MySQL. On an empty DB returns [].
    """
    dialect = _dialect(bind)

    prefix_conditions = " OR ".join(
        [f"c.table_name LIKE '{p}%'" for p in TABLE_PREFIXES]
    )

    if dialect == "postgresql":
        schema_filter = "c.table_schema = ANY (current_schemas(false))"
    elif dialect == "mysql":
        schema_filter = "c.table_schema = DATABASE()"
    else:
        schema_filter = "1=1"

    sql = f"""
        SELECT
            c.table_name,
            MAX(CASE WHEN c.column_name = 'bitrix_id'      THEN c.data_type END) AS bid_type,
            MAX(CASE WHEN c.column_name = 'bitrix_id_int'  THEN 1 ELSE 0 END)    AS has_int
        FROM information_schema.columns c
        WHERE {schema_filter}
          AND ({prefix_conditions})
          AND c.column_name IN ('bitrix_id', 'bitrix_id_int')
        GROUP BY c.table_name
        HAVING MAX(CASE WHEN c.column_name = 'bitrix_id' THEN 1 ELSE 0 END) = 1
        ORDER BY c.table_name
    """

    rows = bind.execute(sa.text(sql)).fetchall()
    result: list[tuple[str, str, bool]] = []
    for row in rows:
        table_name = row[0]
        bid_type = (row[1] or "").lower()
        has_int = bool(row[2])
        result.append((table_name, bid_type, has_int))
    return result


def _column_exists(bind, tbl: str, col: str) -> bool:
    dialect = _dialect(bind)
    if dialect == "postgresql":
        sql = """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = ANY (current_schemas(false))
              AND table_name = :tbl AND column_name = :col
            LIMIT 1
        """
    elif dialect == "mysql":
        sql = """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :tbl AND column_name = :col
            LIMIT 1
        """
    else:
        return False
    return bind.execute(sa.text(sql), {"tbl": tbl, "col": col}).first() is not None


def _index_exists(bind, tbl: str, idx_name: str) -> bool:
    dialect = _dialect(bind)
    if dialect == "postgresql":
        sql = """
            SELECT 1 FROM pg_indexes
            WHERE schemaname = ANY (current_schemas(false))
              AND tablename = :tbl AND indexname = :idx
            LIMIT 1
        """
        return bind.execute(sa.text(sql), {"tbl": tbl, "idx": idx_name}).first() is not None
    elif dialect == "mysql":
        sql = """
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = :tbl AND index_name = :idx
            LIMIT 1
        """
        return bind.execute(sa.text(sql), {"tbl": tbl, "idx": idx_name}).first() is not None
    return False


def _truncate_ident(name: str, limit: int = PG_MAX_IDENT) -> str:
    if len(name) <= limit:
        return name
    return name[:limit]


def _idx_name_int(tbl: str) -> str:
    return _truncate_ident(f"ix_{tbl}_bitrix_id_int")


def _idx_name_str(tbl: str) -> str:
    return _truncate_ident(f"ix_{tbl}_bitrix_id")


# ---------------------------------------------------------------------------
# UNIQUE / NOT NULL helpers
# ---------------------------------------------------------------------------

def _drop_unique_on_bitrix_id(bind, tbl: str, dialect: str) -> None:
    """Drop any UNIQUE index/constraint sitting on the bitrix_id column.

    PostgreSQL: inspects pg_constraint (for UNIQUE constraints) and pg_indexes
                (for plain UNIQUE indexes).
    MySQL:      uses SHOW INDEX FROM <tbl> WHERE Column_name='bitrix_id'
                AND Non_unique=0.
    If nothing is found — no-op.
    """
    if dialect == "postgresql":
        # 1) Unique constraints that cover exactly the bitrix_id column.
        constraint_sql = """
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel   ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            JOIN LATERAL unnest(con.conkey) AS k(attnum) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = rel.oid AND att.attnum = k.attnum
            WHERE rel.relname = :tbl
              AND ns.nspname = ANY (current_schemas(false))
              AND con.contype = 'u'
              AND att.attname = 'bitrix_id'
            GROUP BY con.conname, con.conkey
            HAVING COUNT(*) = 1
        """
        for row in bind.execute(sa.text(constraint_sql), {"tbl": tbl}).fetchall():
            conname = row[0]
            _log(f"dropping UNIQUE constraint {conname} on {tbl}(bitrix_id)")
            bind.execute(sa.text(f'ALTER TABLE "{tbl}" DROP CONSTRAINT IF EXISTS "{conname}"'))

        # 2) Unique indexes covering exactly bitrix_id (not backed by a constraint).
        index_sql = """
            SELECT i.relname AS index_name
            FROM pg_class i
            JOIN pg_index ix       ON ix.indexrelid = i.oid
            JOIN pg_class t        ON t.oid = ix.indrelid
            JOIN pg_namespace ns   ON ns.oid = t.relnamespace
            JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = t.oid AND att.attnum = k.attnum
            WHERE t.relname = :tbl
              AND ns.nspname = ANY (current_schemas(false))
              AND ix.indisunique = TRUE
              AND NOT ix.indisprimary
              AND att.attname = 'bitrix_id'
            GROUP BY i.relname, ix.indkey
            HAVING COUNT(*) = 1
        """
        for row in bind.execute(sa.text(index_sql), {"tbl": tbl}).fetchall():
            idx_name = row[0]
            _log(f"dropping UNIQUE index {idx_name} on {tbl}(bitrix_id)")
            bind.execute(sa.text(f'DROP INDEX IF EXISTS "{idx_name}"'))

    elif dialect == "mysql":
        show_sql = f"SHOW INDEX FROM `{tbl}` WHERE Column_name='bitrix_id' AND Non_unique=0"
        rows = bind.execute(sa.text(show_sql)).fetchall()
        seen: set[str] = set()
        for row in rows:
            # SHOW INDEX columns: Table, Non_unique, Key_name, Seq_in_index, Column_name, ...
            mapping = row._mapping if hasattr(row, "_mapping") else None
            if mapping is not None and "Key_name" in mapping:
                key_name = mapping["Key_name"]
            else:
                key_name = row[2]
            if key_name in seen or key_name == "PRIMARY":
                continue
            seen.add(key_name)
            _log(f"dropping UNIQUE index {key_name} on {tbl}(bitrix_id)")
            bind.execute(sa.text(f"ALTER TABLE `{tbl}` DROP INDEX `{key_name}`"))
    else:
        _log(f"_drop_unique_on_bitrix_id: unsupported dialect {dialect}")


def _set_not_null_if_no_nulls(bind, tbl: str, col: str, dialect: str) -> None:
    """Set NOT NULL on <tbl>.<col> if no NULL values exist. Otherwise warn."""
    if dialect == "postgresql":
        count_sql = f'SELECT COUNT(*) FROM "{tbl}" WHERE "{col}" IS NULL'
    elif dialect == "mysql":
        count_sql = f"SELECT COUNT(*) FROM `{tbl}` WHERE `{col}` IS NULL"
    else:
        _log(f"_set_not_null_if_no_nulls: unsupported dialect {dialect}")
        return

    null_count = bind.execute(sa.text(count_sql)).scalar() or 0
    if null_count > 0:
        _log(
            f"WARN: {tbl}.{col} has {null_count} NULL rows — skipping SET NOT NULL"
        )
        return

    if dialect == "postgresql":
        _log(f"setting NOT NULL on {tbl}.{col}")
        bind.execute(
            sa.text(f'ALTER TABLE "{tbl}" ALTER COLUMN "{col}" SET NOT NULL')
        )
    elif dialect == "mysql":
        _log(f"setting NOT NULL on {tbl}.{col}")
        bind.execute(
            sa.text(f"ALTER TABLE `{tbl}` MODIFY COLUMN `{col}` VARCHAR(50) NOT NULL")
        )


# ---------------------------------------------------------------------------
# Backfill helper (shared by state A and state C)
# ---------------------------------------------------------------------------

def _backfill_bitrix_id_int(bind, tbl: str, dialect: str) -> int:
    """Populate bitrix_id_int from bitrix_id for rows where it is NULL.

    Only rows where bitrix_id matches a purely numeric regex are touched —
    non-numeric legacy IDs stay NULL (bitrix_id_int is nullable by design).
    Returns the number of affected rows (or 0 on failure). Safe to call
    multiple times; the WHERE clause guarantees it only fills what is empty.
    """
    if dialect == "postgresql":
        sql = (
            f'UPDATE "{tbl}" '
            f"SET bitrix_id_int = CAST(bitrix_id AS BIGINT) "
            f"WHERE bitrix_id_int IS NULL "
            f"  AND bitrix_id IS NOT NULL "
            f"  AND bitrix_id ~ '^[0-9]+$'"
        )
    elif dialect == "mysql":
        sql = (
            f"UPDATE `{tbl}` "
            f"SET bitrix_id_int = CAST(bitrix_id AS SIGNED) "
            f"WHERE bitrix_id_int IS NULL "
            f"  AND bitrix_id IS NOT NULL "
            f"  AND bitrix_id REGEXP '^[0-9]+$'"
        )
    else:
        return 0

    try:
        result = bind.execute(sa.text(sql))
        affected = result.rowcount if result.rowcount is not None else 0
        if affected > 0:
            _log(f"backfilled {affected} row(s) in {tbl}.bitrix_id_int")
        return affected
    except Exception as exc:  # pragma: no cover - best effort
        _log(f"backfill failed for {tbl}: {exc}")
        return 0


# ---------------------------------------------------------------------------
# State A — bitrix_id is already a string, bitrix_id_int missing
# ---------------------------------------------------------------------------

def _upgrade_state_a(bind, tbl: str, dialect: str) -> None:
    _log(f"[state A] {tbl}: adding bitrix_id_int")

    # 1) ADD COLUMN bitrix_id_int BIGINT (idempotent)
    if not _column_exists(bind, tbl, "bitrix_id_int"):
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'ALTER TABLE "{tbl}" ADD COLUMN IF NOT EXISTS bitrix_id_int BIGINT'
                )
            )
        elif dialect == "mysql":
            # MySQL <8.0.29 has no IF NOT EXISTS on ADD COLUMN — we already
            # pre-checked via _column_exists.
            bind.execute(
                sa.text(f"ALTER TABLE `{tbl}` ADD COLUMN bitrix_id_int BIGINT NULL")
            )

    # 2) Back-fill numeric values via regex match.
    _backfill_bitrix_id_int(bind, tbl, dialect)

    # 3) CREATE INDEX ix_<tbl>_bitrix_id_int
    idx_name = _idx_name_int(tbl)
    if not _index_exists(bind, tbl, idx_name):
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                    f'ON "{tbl}" (bitrix_id_int)'
                )
            )
        elif dialect == "mysql":
            bind.execute(
                sa.text(f"CREATE INDEX `{idx_name}` ON `{tbl}` (bitrix_id_int)")
            )


# ---------------------------------------------------------------------------
# State B — bitrix_id is numeric, convert to canonical form
# ---------------------------------------------------------------------------

def _upgrade_state_b(bind, tbl: str, dialect: str) -> None:
    _log(f"[state B] {tbl}: converting numeric bitrix_id to canonical form")

    # 1) Drop UNIQUE on old numeric bitrix_id.
    try:
        _drop_unique_on_bitrix_id(bind, tbl, dialect)
    except Exception as exc:  # pragma: no cover - best effort
        _log(f"[state B] {tbl}: drop UNIQUE failed (continuing): {exc}")

    # 2) RENAME bitrix_id -> bitrix_id_int (only if bitrix_id_int missing).
    if not _column_exists(bind, tbl, "bitrix_id_int"):
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'ALTER TABLE "{tbl}" RENAME COLUMN bitrix_id TO bitrix_id_int'
                )
            )
        elif dialect == "mysql":
            bind.execute(
                sa.text(
                    f"ALTER TABLE `{tbl}` "
                    f"CHANGE COLUMN `bitrix_id` `bitrix_id_int` BIGINT NULL"
                )
            )

    # 3) ADD COLUMN bitrix_id VARCHAR(50) (nullable for now; NOT NULL later).
    if not _column_exists(bind, tbl, "bitrix_id"):
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'ALTER TABLE "{tbl}" '
                    f"ADD COLUMN IF NOT EXISTS bitrix_id VARCHAR(50)"
                )
            )
        elif dialect == "mysql":
            bind.execute(
                sa.text(f"ALTER TABLE `{tbl}` ADD COLUMN `bitrix_id` VARCHAR(50) NULL")
            )

    # 4) Back-fill string representation from the numeric column.
    if dialect == "postgresql":
        backfill_sql = (
            f'UPDATE "{tbl}" '
            f"SET bitrix_id = bitrix_id_int::text "
            f"WHERE bitrix_id_int IS NOT NULL AND bitrix_id IS NULL"
        )
    elif dialect == "mysql":
        backfill_sql = (
            f"UPDATE `{tbl}` "
            f"SET bitrix_id = CAST(bitrix_id_int AS CHAR) "
            f"WHERE bitrix_id_int IS NOT NULL AND bitrix_id IS NULL"
        )
    else:
        backfill_sql = None

    if backfill_sql:
        try:
            bind.execute(sa.text(backfill_sql))
        except Exception as exc:  # pragma: no cover - best effort
            _log(f"[state B] {tbl}: backfill failed: {exc}")

    # 5) CREATE UNIQUE INDEX on new string bitrix_id.
    uniq_name = _idx_name_str(tbl)
    if not _index_exists(bind, tbl, uniq_name):
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "{uniq_name}" '
                    f'ON "{tbl}" (bitrix_id)'
                )
            )
        elif dialect == "mysql":
            bind.execute(
                sa.text(
                    f"CREATE UNIQUE INDEX `{uniq_name}` ON `{tbl}` (bitrix_id)"
                )
            )

    # 6) CREATE INDEX on bitrix_id_int.
    idx_name = _idx_name_int(tbl)
    if not _index_exists(bind, tbl, idx_name):
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                    f'ON "{tbl}" (bitrix_id_int)'
                )
            )
        elif dialect == "mysql":
            bind.execute(
                sa.text(f"CREATE INDEX `{idx_name}` ON `{tbl}` (bitrix_id_int)")
            )

    # 7) Try to SET NOT NULL on bitrix_id.
    try:
        _set_not_null_if_no_nulls(bind, tbl, "bitrix_id", dialect)
    except Exception as exc:  # pragma: no cover - best effort
        _log(f"[state B] {tbl}: SET NOT NULL failed: {exc}")


# ---------------------------------------------------------------------------
# State C — both columns already exist
# ---------------------------------------------------------------------------

def _upgrade_state_c(bind, tbl: str, dialect: str) -> None:
    """Both columns already exist — no DDL needed, but still:
      1) back-fill any rows where bitrix_id_int IS NULL (e.g. column was
         added manually or by a previously interrupted migration that
         never ran the UPDATE step);
      2) ensure the index on bitrix_id_int is present (safety net).
    """
    _log(f"[state C] {tbl}: both columns present, ensuring backfill + index")

    # 1) Back-fill any rows still missing bitrix_id_int.
    _backfill_bitrix_id_int(bind, tbl, dialect)

    # 2) Ensure the index exists.
    idx_name = _idx_name_int(tbl)
    if not _index_exists(bind, tbl, idx_name):
        _log(f"[state C] {tbl}: creating missing index {idx_name}")
        if dialect == "postgresql":
            bind.execute(
                sa.text(
                    f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                    f'ON "{tbl}" (bitrix_id_int)'
                )
            )
        elif dialect == "mysql":
            bind.execute(
                sa.text(f"CREATE INDEX `{idx_name}` ON `{tbl}` (bitrix_id_int)")
            )


# ---------------------------------------------------------------------------
# upgrade / downgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    """Idempotently ensure bitrix_id_int exists on every dynamic Bitrix table.

    Dispatches each table to state A / B / C based on the current column
    shape discovered via information_schema. Safe to re-run.
    """
    bind = op.get_bind()
    dialect = _dialect(bind)
    _log(f"dialect={dialect}")

    tables = _find_tables_with_bitrix_id(bind)
    _log(f"found {len(tables)} dynamic bitrix tables to inspect")

    for tbl, bid_type, has_int in tables:
        try:
            if has_int:
                _upgrade_state_c(bind, tbl, dialect)
                continue

            if bid_type in STRING_TYPES:
                _upgrade_state_a(bind, tbl, dialect)
            elif bid_type in NUMERIC_TYPES:
                _upgrade_state_b(bind, tbl, dialect)
            else:
                _log(
                    f"WARN: {tbl}: unknown bitrix_id type '{bid_type}', skipping"
                )
        except Exception as exc:  # pragma: no cover - best effort logging
            _log(f"ERROR processing {tbl}: {exc}")
            raise


def downgrade() -> None:
    """Best-effort revert of state A only.

    Downgrade reverts only state A (drops bitrix_id_int + its index).
    State B (numeric bitrix_id renamed to bitrix_id_int and a new VARCHAR
    bitrix_id populated from it) is NOT reverted to avoid data loss —
    the original string values, if different from the numeric ones,
    cannot be reconstructed.
    """
    bind = op.get_bind()
    dialect = _dialect(bind)
    _log(f"downgrade dialect={dialect}")

    tables = _find_tables_with_bitrix_id(bind)
    for tbl, _bid_type, has_int in tables:
        if not has_int:
            continue

        idx_name = _idx_name_int(tbl)
        if _index_exists(bind, tbl, idx_name):
            _log(f"dropping index {idx_name}")
            if dialect == "postgresql":
                bind.execute(sa.text(f'DROP INDEX IF EXISTS "{idx_name}"'))
            elif dialect == "mysql":
                bind.execute(
                    sa.text(f"ALTER TABLE `{tbl}` DROP INDEX `{idx_name}`")
                )

        if _column_exists(bind, tbl, "bitrix_id_int"):
            _log(f"dropping column {tbl}.bitrix_id_int")
            if dialect == "postgresql":
                bind.execute(
                    sa.text(
                        f'ALTER TABLE "{tbl}" DROP COLUMN IF EXISTS bitrix_id_int'
                    )
                )
            elif dialect == "mysql":
                bind.execute(
                    sa.text(f"ALTER TABLE `{tbl}` DROP COLUMN `bitrix_id_int`")
                )
