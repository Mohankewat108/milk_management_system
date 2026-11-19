from django.db import migrations

# Dynamic SQL identifiers below are fixed by these migration-owned maps and are
# quoted by the backend; request data is never interpolated into the statements.

TENANT_REFERENCES = {
    "parties_customer": {
        "branch_id": "organizations_branch",
    },
    "parties_farmer": {
        "branch_id": "organizations_branch",
    },
    "pricing_pricingconfiguration": {
        "branch_id": "organizations_branch",
    },
    "pricing_qualityconfiguration": {
        "branch_id": "organizations_branch",
    },
    "collections_milkcollection": {
        "branch_id": "organizations_branch",
        "farmer_id": "parties_farmer",
        "customer_id": "parties_customer",
        "pricing_id": "pricing_pricingconfiguration",
    },
    "finance_payment": {
        "branch_id": "organizations_branch",
        "customer_id": "parties_customer",
        "farmer_id": "parties_farmer",
    },
    "finance_expense": {
        "branch_id": "organizations_branch",
    },
    "finance_account": {
        "parent_id": "finance_account",
    },
    "finance_journalentry": {
        "branch_id": "organizations_branch",
        "period_id": "finance_accountingperiod",
        "reversal_of_id": "finance_journalentry",
    },
    "finance_ledgerconfiguration": {
        "cash_account_id": "finance_account",
        "bank_account_id": "finance_account",
        "mobile_wallet_account_id": "finance_account",
        "online_clearing_account_id": "finance_account",
        "other_payment_account_id": "finance_account",
        "receivables_account_id": "finance_account",
        "farmer_payable_account_id": "finance_account",
        "procurement_expense_account_id": "finance_account",
        "sales_revenue_account_id": "finance_account",
        "default_expense_account_id": "finance_account",
    },
    "inventory_inventoryitem": {
        "branch_id": "organizations_branch",
        "supplier_id": "inventory_supplier",
    },
    "inventory_stockmovement": {
        "item_id": "inventory_inventoryitem",
    },
}

RELATED_ORGANIZATION_PAIRS = (
    (
        "organizations_branchassignment",
        "membership_id",
        "branch_id",
        "organizations_membership",
        "organizations_branch",
    ),
    (
        "organizations_staffinvitation_branches",
        "staffinvitation_id",
        "branch_id",
        "organizations_staffinvitation",
        "organizations_branch",
    ),
    ("finance_journalline", "entry_id", "account_id", "finance_journalentry", "finance_account"),
)

SCHEDULE_TABLES = ("pricing_pricingconfiguration", "pricing_qualityconfiguration")


def _trigger_sqlite_tenant_triggers(schema_editor):
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for table_index, (table, references) in enumerate(TENANT_REFERENCES.items()):
            for reference_index, (column, referenced_table) in enumerate(references.items()):
                for action in ("INSERT", "UPDATE"):
                    name = f"dairy_tenant_{table_index}_{reference_index}_{action.lower()}"
                    cursor.execute(
                        f"""
                        CREATE TRIGGER {quote(name)}
                        BEFORE {action} ON {quote(table)}
                        WHEN NEW.{quote(column)} IS NOT NULL
                         AND NEW.{quote("organization_id")} IS NOT (
                             SELECT {quote("organization_id")}
                             FROM {quote(referenced_table)}
                             WHERE {quote("id")} = NEW.{quote(column)}
                         )
                        BEGIN
                            SELECT RAISE(ABORT, 'tenant relationship mismatch');
                        END
                        """
                    )

        for pair_index, (table, left_column, right_column, left_table, right_table) in enumerate(
            RELATED_ORGANIZATION_PAIRS
        ):
            for action in ("INSERT", "UPDATE"):
                name = f"dairy_related_{pair_index}_{action.lower()}"
                cursor.execute(
                    f"""
                    CREATE TRIGGER {quote(name)}
                    BEFORE {action} ON {quote(table)}
                    WHEN (SELECT {quote("organization_id")} FROM {quote(left_table)}
                          WHERE {quote("id")} = NEW.{quote(left_column)})
                         IS NOT
                         (SELECT {quote("organization_id")} FROM {quote(right_table)}
                          WHERE {quote("id")} = NEW.{quote(right_column)})
                    BEGIN
                        SELECT RAISE(ABORT, 'tenant relationship mismatch');
                    END
                    """
                )

        for table_index, table in enumerate(SCHEDULE_TABLES):
            for action in ("INSERT", "UPDATE"):
                name = f"dairy_schedule_overlap_{table_index}_{action.lower()}"
                soft_delete_filter = (
                    " AND existing.deleted_at IS NULL"
                    if table == "pricing_pricingconfiguration"
                    else ""
                )
                cursor.execute(
                    f"""
                    CREATE TRIGGER {quote(name)}
                    BEFORE {action} ON {quote(table)}
                    WHEN {("NEW.deleted_at IS NULL AND " if table == "pricing_pricingconfiguration" else "")}
                    EXISTS (
                        SELECT 1 FROM {quote(table)} AS existing
                        WHERE existing.organization_id = NEW.organization_id
                          AND existing.branch_id IS NEW.branch_id
                          AND (existing.effective_to IS NULL
                               OR existing.effective_to >= NEW.effective_from)
                          AND (NEW.effective_to IS NULL
                               OR NEW.effective_to >= existing.effective_from)
                          AND existing.id != NEW.id
                          {soft_delete_filter}
                    )
                    BEGIN
                        SELECT RAISE(ABORT, 'overlapping schedule');
                    END
                    """
                )

        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_entry_posted_insert
                BEFORE INSERT ON finance_journalentry
                WHEN NEW.status = 'posted'
                BEGIN
                    SELECT RAISE(ABORT, 'journal entries must be balanced before posting');
                END
                """
        )
        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_entry_validate_update
                BEFORE UPDATE ON finance_journalentry
                WHEN OLD.status = 'posted'
                  OR NOT EXISTS (
                      SELECT 1 FROM finance_accountingperiod AS period
                      WHERE period.id = NEW.period_id
                        AND period.organization_id = NEW.organization_id
                        AND period.starts_on <= NEW.entry_date
                        AND period.ends_on >= NEW.entry_date
                  )
                  OR (
                      NEW.status = 'posted'
                      AND (
                          SELECT COUNT(*) FROM finance_journalline AS line
                          WHERE line.entry_id = NEW.id
                      ) < 2
                  )
                  OR (
                      NEW.status = 'posted'
                      AND ROUND(
                          (SELECT COALESCE(SUM(line.debit), 0)
                           FROM finance_journalline AS line WHERE line.entry_id = NEW.id),
                          2
                      ) <= 0
                  )
                  OR (
                      NEW.status = 'posted'
                      AND ROUND(
                          (SELECT COALESCE(SUM(line.debit), 0)
                           FROM finance_journalline AS line WHERE line.entry_id = NEW.id),
                          2
                      ) != ROUND(
                          (SELECT COALESCE(SUM(line.credit), 0)
                           FROM finance_journalline AS line WHERE line.entry_id = NEW.id),
                          2
                      )
                  )
                BEGIN
                    SELECT RAISE(ABORT, 'journal entry is invalid or unbalanced');
                END
                """
        )
        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_entry_validate_insert
                BEFORE INSERT ON finance_journalentry
                WHEN NOT EXISTS (
                    SELECT 1 FROM finance_accountingperiod AS period
                    WHERE period.id = NEW.period_id
                      AND period.organization_id = NEW.organization_id
                      AND period.starts_on <= NEW.entry_date
                      AND period.ends_on >= NEW.entry_date
                )
                BEGIN
                    SELECT RAISE(ABORT, 'journal entry date is outside its accounting period');
                END
                """
        )
        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_entry_reject_delete
                BEFORE DELETE ON finance_journalentry
                WHEN OLD.status = 'posted'
                BEGIN
                    SELECT RAISE(ABORT, 'posted journal entries are immutable');
                END
                """
        )
        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_line_reject_insert
                BEFORE INSERT ON finance_journalline
                WHEN EXISTS (
                    SELECT 1 FROM finance_journalentry AS entry
                    WHERE entry.id = NEW.entry_id AND entry.status = 'posted'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'posted journal entries are immutable');
                END
                """
        )
        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_line_reject_update
                BEFORE UPDATE ON finance_journalline
                WHEN EXISTS (
                    SELECT 1 FROM finance_journalentry AS entry
                    WHERE entry.id IN (OLD.entry_id, NEW.entry_id) AND entry.status = 'posted'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'posted journal entries are immutable');
                END
                """
        )
        cursor.execute(
            """
                CREATE TRIGGER dairy_journal_line_reject_delete
                BEFORE DELETE ON finance_journalline
                WHEN EXISTS (
                    SELECT 1 FROM finance_journalentry AS entry
                    WHERE entry.id = OLD.entry_id AND entry.status = 'posted'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'posted journal entries are immutable');
                END
                """
        )

        cursor.execute(
            f"""
                CREATE TRIGGER {quote("dairy_stock_movement_apply")}
                AFTER INSERT ON {quote("inventory_stockmovement")}
                BEGIN
                    UPDATE {quote("inventory_inventoryitem")}
                       SET {quote("current_stock")} = {quote("current_stock")} + NEW.{quote("quantity_delta")}
                     WHERE {quote("id")} = NEW.{quote("item_id")}
                       AND {quote("current_stock")} + NEW.{quote("quantity_delta")} >= 0;
                    SELECT CASE WHEN changes() = 0
                        THEN RAISE(ABORT, 'stock movement would make stock negative')
                    END;
                END
                """
        )
        cursor.execute(
            f"""
            CREATE TRIGGER {quote("dairy_stock_movement_immutable_update")}
            BEFORE UPDATE ON {quote("inventory_stockmovement")}
            BEGIN
                SELECT RAISE(ABORT, 'stock movements are immutable');
            END
            """
        )
        cursor.execute(
            f"""
            CREATE TRIGGER {quote("dairy_stock_movement_reverse_delete")}
            AFTER DELETE ON {quote("inventory_stockmovement")}
            BEGIN
                UPDATE {quote("inventory_inventoryitem")}
                   SET {quote("current_stock")} = {quote("current_stock")} - OLD.{quote("quantity_delta")}
                 WHERE {quote("id")} = OLD.{quote("item_id")}
                   AND {quote("current_stock")} - OLD.{quote("quantity_delta")} >= 0;
                SELECT CASE WHEN changes() = 0
                    THEN RAISE(ABORT, 'stock movement deletion would make stock negative')
                END;
            END
            """
        )

        for action in ("INSERT", "UPDATE"):
            name = f"dairy_accounting_period_overlap_{action.lower()}"
            cursor.execute(
                f"""
                CREATE TRIGGER {quote(name)}
                BEFORE {action} ON {quote("finance_accountingperiod")}
                WHEN EXISTS (
                    SELECT 1 FROM {quote("finance_accountingperiod")} AS existing
                    WHERE existing.organization_id = NEW.organization_id
                      AND existing.starts_on <= NEW.ends_on
                      AND existing.ends_on >= NEW.starts_on
                      AND existing.id != NEW.id
                )
                BEGIN
                    SELECT RAISE(ABORT, 'overlapping accounting periods');
                END
                """
            )


def _trigger_postgresql_tenant_triggers(schema_editor):
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE FUNCTION dairy_check_tenant_references() RETURNS trigger AS $$
            DECLARE
                expected_org uuid;
                referenced_org uuid;
                reference_id text;
                reference_index integer;
            BEGIN
                expected_org := NEW.organization_id;
                FOR reference_index IN 0..((TG_NARGS / 2) - 1) LOOP
                    reference_id := to_jsonb(NEW) ->> TG_ARGV[reference_index * 2];
                    IF reference_id IS NULL THEN
                        CONTINUE;
                    END IF;
                    EXECUTE format(
                        'SELECT organization_id FROM %I WHERE id = $1',
                        TG_ARGV[reference_index * 2 + 1]
                    ) INTO referenced_org USING reference_id::uuid;
                    IF referenced_org IS DISTINCT FROM expected_org THEN
                        RAISE EXCEPTION 'tenant relationship mismatch'
                            USING ERRCODE = '23514';
                    END IF;
                END LOOP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table_index, (table, references) in enumerate(TENANT_REFERENCES.items()):
            arguments = ", ".join(
                "'" + item.replace("'", "''") + "'"
                for column, referenced_table in references.items()
                for item in (column, referenced_table)
            )
            name = f"dairy_tenant_{table_index}"
            cursor.execute(
                f"""
                CREATE TRIGGER {quote(name)}
                BEFORE INSERT OR UPDATE ON {quote(table)}
                FOR EACH ROW EXECUTE FUNCTION dairy_check_tenant_references({arguments})
                """
            )

        cursor.execute(
            """
            CREATE FUNCTION dairy_check_related_organizations() RETURNS trigger AS $$
            DECLARE
                left_org uuid;
                right_org uuid;
                left_id uuid;
                right_id uuid;
            BEGIN
                left_id := (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
                right_id := (to_jsonb(NEW) ->> TG_ARGV[2])::uuid;
                EXECUTE format('SELECT organization_id FROM %I WHERE id = $1', TG_ARGV[3])
                    INTO left_org USING left_id;
                EXECUTE format('SELECT organization_id FROM %I WHERE id = $1', TG_ARGV[4])
                    INTO right_org USING right_id;
                IF left_org IS DISTINCT FROM right_org THEN
                    RAISE EXCEPTION 'tenant relationship mismatch'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for pair_index, (table, left_column, right_column, left_table, right_table) in enumerate(
            RELATED_ORGANIZATION_PAIRS
        ):
            name = f"dairy_related_{pair_index}"
            arguments = ", ".join(
                "'" + item.replace("'", "''") + "'"
                for item in (table, left_column, right_column, left_table, right_table)
            )
            cursor.execute(
                f"""
                CREATE TRIGGER {quote(name)}
                BEFORE INSERT OR UPDATE ON {quote(table)}
                FOR EACH ROW EXECUTE FUNCTION dairy_check_related_organizations({arguments})
                """
            )

        cursor.execute(
            """
            CREATE FUNCTION dairy_reject_schedule_overlap() RETURNS trigger AS $$
            DECLARE
                overlapping boolean;
                statement text;
            BEGIN
                PERFORM 1 FROM organizations_organization
                 WHERE id = NEW.organization_id FOR UPDATE;
                IF TG_ARGV[1] = 'soft'
                   AND (to_jsonb(NEW) ->> 'deleted_at') IS NOT NULL THEN
                    RETURN NEW;
                END IF;
                statement := format(
                    'SELECT EXISTS (
                        SELECT 1 FROM %I AS existing
                        WHERE existing.organization_id = $1
                          AND existing.branch_id IS NOT DISTINCT FROM $2
                          AND existing.effective_from <= $4
                          AND COALESCE(existing.effective_to, DATE ''9999-12-31'') >= $3
                          AND existing.id <> $5',
                    TG_ARGV[0]
                );
                IF TG_ARGV[1] = 'soft' THEN
                    statement := statement || ' AND existing.deleted_at IS NULL';
                END IF;
                statement := statement || ')';
                EXECUTE statement INTO overlapping
                    USING NEW.organization_id, NEW.branch_id, NEW.effective_from,
                          COALESCE(NEW.effective_to, DATE '9999-12-31'), NEW.id;
                IF overlapping THEN
                    RAISE EXCEPTION 'overlapping schedule' USING ERRCODE = '23P01';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table_index, table in enumerate(SCHEDULE_TABLES):
            name = f"dairy_schedule_overlap_{table_index}"
            deleted_at_flag = "soft" if table == "pricing_pricingconfiguration" else "none"
            cursor.execute(
                f"""
                CREATE TRIGGER {quote(name)}
                BEFORE INSERT OR UPDATE ON {quote(table)}
                FOR EACH ROW EXECUTE FUNCTION dairy_reject_schedule_overlap(
                    '{table}', '{deleted_at_flag}'
                )
                """
            )

        cursor.execute(
            """
            CREATE FUNCTION dairy_reject_accounting_period_overlap() RETURNS trigger AS $$
            BEGIN
                PERFORM 1 FROM organizations_organization
                 WHERE id = NEW.organization_id FOR UPDATE;
                IF EXISTS (
                    SELECT 1 FROM finance_accountingperiod AS existing
                    WHERE existing.organization_id = NEW.organization_id
                      AND existing.starts_on <= NEW.ends_on
                      AND existing.ends_on >= NEW.starts_on
                      AND existing.id <> NEW.id
                ) THEN
                    RAISE EXCEPTION 'overlapping accounting periods' USING ERRCODE = '23P01';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for action in ("INSERT", "UPDATE"):
            cursor.execute(
                f"""
                CREATE TRIGGER dairy_period_overlap_{action.lower()}
                BEFORE {action} ON finance_accountingperiod
                FOR EACH ROW EXECUTE FUNCTION dairy_reject_accounting_period_overlap()
                """
            )

        cursor.execute(
            """
            CREATE FUNCTION dairy_validate_journal_entry() RETURNS trigger AS $$
            DECLARE
                line_count bigint;
                debit_total numeric;
                credit_total numeric;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status = 'posted' THEN
                        RAISE EXCEPTION 'posted journal entries are immutable'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN OLD;
                END IF;
                IF TG_OP = 'UPDATE' AND OLD.status = 'posted' THEN
                    RAISE EXCEPTION 'posted journal entries are immutable'
                        USING ERRCODE = '23514';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM finance_accountingperiod AS period
                    WHERE period.id = NEW.period_id
                      AND period.organization_id = NEW.organization_id
                      AND period.starts_on <= NEW.entry_date
                      AND period.ends_on >= NEW.entry_date
                ) THEN
                    RAISE EXCEPTION 'journal entry date is outside its accounting period'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.status = 'posted' THEN
                    SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                      INTO line_count, debit_total, credit_total
                      FROM finance_journalline WHERE entry_id = NEW.id;
                    IF line_count < 2 OR debit_total <= 0 OR debit_total <> credit_total THEN
                        RAISE EXCEPTION 'journal entry is unbalanced'
                            USING ERRCODE = '23514';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for action in ("INSERT", "UPDATE", "DELETE"):
            cursor.execute(
                f"""
                CREATE TRIGGER dairy_journal_entry_validate_{action.lower()}
                BEFORE {action} ON finance_journalentry
                FOR EACH ROW EXECUTE FUNCTION dairy_validate_journal_entry()
                """
            )
        cursor.execute(
            """
            CREATE FUNCTION dairy_reject_posted_journal_line_mutation() RETURNS trigger AS $$
            BEGIN
                IF TG_OP <> 'INSERT' AND EXISTS (
                    SELECT 1 FROM finance_journalentry
                    WHERE id = OLD.entry_id AND status = 'posted'
                ) THEN
                    RAISE EXCEPTION 'posted journal entries are immutable'
                        USING ERRCODE = '23514';
                END IF;
                IF TG_OP <> 'DELETE' AND EXISTS (
                    SELECT 1 FROM finance_journalentry
                    WHERE id = NEW.entry_id AND status = 'posted'
                ) THEN
                    RAISE EXCEPTION 'posted journal entries are immutable'
                        USING ERRCODE = '23514';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for action in ("INSERT", "UPDATE", "DELETE"):
            cursor.execute(
                f"""
                CREATE TRIGGER dairy_journal_line_reject_{action.lower()}
                BEFORE {action} ON finance_journalline
                FOR EACH ROW EXECUTE FUNCTION dairy_reject_posted_journal_line_mutation()
                """
            )

        cursor.execute(
            """
            CREATE FUNCTION dairy_apply_stock_movement() RETURNS trigger AS $$
            BEGIN
                UPDATE inventory_inventoryitem
                   SET current_stock = current_stock + NEW.quantity_delta
                 WHERE id = NEW.item_id
                   AND current_stock + NEW.quantity_delta >= 0;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'stock movement would make stock negative'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER dairy_stock_movement_apply
            AFTER INSERT ON inventory_stockmovement
            FOR EACH ROW EXECUTE FUNCTION dairy_apply_stock_movement()
            """
        )
        cursor.execute(
            """
            CREATE FUNCTION dairy_reject_stock_movement_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'stock movements are immutable' USING ERRCODE = '23514';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for action in ("UPDATE",):
            cursor.execute(
                f"""
                CREATE TRIGGER dairy_stock_movement_immutable_{action.lower()}
                BEFORE {action} ON inventory_stockmovement
                FOR EACH ROW EXECUTE FUNCTION dairy_reject_stock_movement_mutation()
                """
            )
        cursor.execute(
            """
            CREATE FUNCTION dairy_reverse_stock_movement() RETURNS trigger AS $$
            BEGIN
                UPDATE inventory_inventoryitem
                   SET current_stock = current_stock - OLD.quantity_delta
                 WHERE id = OLD.item_id
                   AND current_stock - OLD.quantity_delta >= 0;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'stock movement deletion would make stock negative'
                        USING ERRCODE = '23514';
                END IF;
                RETURN OLD;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER dairy_stock_movement_reverse_delete
            AFTER DELETE ON inventory_stockmovement
            FOR EACH ROW EXECUTE FUNCTION dairy_reverse_stock_movement()
            """
        )


def validate_existing_integrity(apps, schema_editor):
    quote = schema_editor.quote_name
    mismatch_operator = (
        "IS DISTINCT FROM" if schema_editor.connection.vendor == "postgresql" else "IS NOT"
    )
    checks = []
    for table, references in TENANT_REFERENCES.items():
        for column, referenced_table in references.items():
            checks.append(
                (
                    f"{table}.{column}",
                    f"""
                    SELECT COUNT(*)
                    FROM {quote(table)} AS source
                    JOIN {quote(referenced_table)} AS target
                      ON target.id = source.{quote(column)}
                    WHERE source.{quote(column)} IS NOT NULL
                      AND source.organization_id {mismatch_operator} target.organization_id
                    """,
                )
            )
    for table, left_column, right_column, left_table, right_table in RELATED_ORGANIZATION_PAIRS:
        checks.append(
            (
                f"{table}.{left_column}/{right_column}",
                f"""
                SELECT COUNT(*)
                FROM {quote(table)} AS link
                JOIN {quote(left_table)} AS left_row ON left_row.id = link.{quote(left_column)}
                JOIN {quote(right_table)} AS right_row ON right_row.id = link.{quote(right_column)}
                WHERE left_row.organization_id {mismatch_operator} right_row.organization_id
                """,
            )
        )
    with schema_editor.connection.cursor() as cursor:
        for table in SCHEDULE_TABLES:
            ignored_deleted = (
                " AND left_row.deleted_at IS NULL AND right_row.deleted_at IS NULL"
                if table == "pricing_pricingconfiguration"
                else ""
            )
            branch_equal = (
                "IS NOT DISTINCT FROM" if schema_editor.connection.vendor == "postgresql" else "IS"
            )
            checks.append(
                (
                    f"{table} overlapping ranges",
                    f"""
                    SELECT COUNT(*)
                    FROM {quote(table)} AS left_row
                    JOIN {quote(table)} AS right_row
                      ON right_row.organization_id = left_row.organization_id
                     AND right_row.branch_id {branch_equal} left_row.branch_id
                     AND right_row.id > left_row.id
                     AND (left_row.effective_to IS NULL
                          OR right_row.effective_from <= left_row.effective_to)
                     AND (right_row.effective_to IS NULL
                          OR left_row.effective_from <= right_row.effective_to)
                     {ignored_deleted}
                    """,
                )
            )
        checks.append(
            (
                "finance_accountingperiod overlapping ranges",
                """
                SELECT COUNT(*)
                FROM finance_accountingperiod AS left_row
                JOIN finance_accountingperiod AS right_row
                  ON right_row.organization_id = left_row.organization_id
                 AND right_row.id > left_row.id
                 AND right_row.starts_on <= left_row.ends_on
                 AND right_row.ends_on >= left_row.starts_on
                """,
            )
        )
        checks.append(
            (
                "collection calculated totals",
                """
                SELECT COUNT(*) FROM collections_milkcollection
                WHERE total_amount != ROUND(quantity_litres * milk_rate, 2)
                """,
            )
        )
        checks.append(
            (
                "payment direction and party",
                """
                SELECT COUNT(*) FROM finance_payment
                WHERE NOT (
                    (customer_id IS NOT NULL AND farmer_id IS NULL AND direction = 'incoming')
                    OR (customer_id IS NULL AND farmer_id IS NOT NULL AND direction = 'outgoing')
                )
                """,
            )
        )
        checks.append(
            (
                "posted journal entries",
                """
                SELECT COUNT(*)
                FROM (
                    SELECT entry.id
                    FROM finance_journalentry AS entry
                    LEFT JOIN finance_accountingperiod AS period
                      ON period.id = entry.period_id
                     AND period.organization_id = entry.organization_id
                    LEFT JOIN finance_journalline AS line ON line.entry_id = entry.id
                    WHERE entry.status = 'posted'
                    GROUP BY entry.id, period.id, period.starts_on, period.ends_on,
                             entry.entry_date
                    HAVING COUNT(line.id) < 2
                        OR ROUND(COALESCE(SUM(line.debit), 0), 2) <= 0
                        OR ROUND(COALESCE(SUM(line.debit), 0), 2)
                           != ROUND(COALESCE(SUM(line.credit), 0), 2)
                        OR period.id IS NULL
                        OR entry.entry_date < period.starts_on
                        OR entry.entry_date > period.ends_on
                ) AS invalid_entries
                """,
            )
        )
        invalid = []
        for description, statement in checks:
            cursor.execute(statement)
            rows = cursor.fetchone()
            count = rows[0] if rows else 0
            if count:
                invalid.append(f"{description}: {count}")
        if invalid:
            raise RuntimeError(
                "Tenant integrity migration preflight failed; resolve these records "
                "before retrying: " + "; ".join(invalid)
            )


def install_integrity_triggers(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        _trigger_sqlite_tenant_triggers(schema_editor)
    elif schema_editor.connection.vendor == "postgresql":
        _trigger_postgresql_tenant_triggers(schema_editor)
    else:
        raise RuntimeError(
            f"Tenant integrity triggers are not implemented for {schema_editor.connection.vendor}."
        )


def remove_integrity_triggers(apps, schema_editor):
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor == "sqlite":
            for table_index, references in enumerate(TENANT_REFERENCES.values()):
                for reference_index in range(len(references)):
                    for action in ("insert", "update"):
                        cursor.execute(
                            f"DROP TRIGGER IF EXISTS "
                            f"{quote(f'dairy_tenant_{table_index}_{reference_index}_{action}')}"
                        )
            for pair_index in range(len(RELATED_ORGANIZATION_PAIRS)):
                for action in ("insert", "update"):
                    cursor.execute(
                        f"DROP TRIGGER IF EXISTS {quote(f'dairy_related_{pair_index}_{action}')}"
                    )
            for table_index in range(len(SCHEDULE_TABLES)):
                for action in ("insert", "update"):
                    cursor.execute(
                        f"DROP TRIGGER IF EXISTS "
                        f"{quote(f'dairy_schedule_overlap_{table_index}_{action}')}"
                    )
            cursor.execute(f"DROP TRIGGER IF EXISTS {quote('dairy_stock_movement_apply')}")
            cursor.execute(
                f"DROP TRIGGER IF EXISTS {quote('dairy_stock_movement_immutable_update')}"
            )
            cursor.execute(f"DROP TRIGGER IF EXISTS {quote('dairy_stock_movement_reverse_delete')}")
            for action in ("insert", "update"):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {quote(f'dairy_accounting_period_overlap_{action}')}"
                )
            for name in (
                "dairy_journal_entry_posted_insert",
                "dairy_journal_entry_validate_update",
                "dairy_journal_entry_validate_insert",
                "dairy_journal_entry_reject_delete",
                "dairy_journal_line_reject_insert",
                "dairy_journal_line_reject_update",
                "dairy_journal_line_reject_delete",
            ):
                cursor.execute(f"DROP TRIGGER IF EXISTS {quote(name)}")
        elif schema_editor.connection.vendor == "postgresql":
            for table_index, table in enumerate(TENANT_REFERENCES):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {quote(f'dairy_tenant_{table_index}')} "
                    f"ON {quote(table)}"
                )
            for pair_index, (table, *_rest) in enumerate(RELATED_ORGANIZATION_PAIRS):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {quote(f'dairy_related_{pair_index}')} "
                    f"ON {quote(table)}"
                )
            for table_index, table in enumerate(SCHEDULE_TABLES):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {quote(f'dairy_schedule_overlap_{table_index}')} "
                    f"ON {quote(table)}"
                )
            for action in ("insert", "update"):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {quote(f'dairy_period_overlap_{action}')} "
                    "ON finance_accountingperiod"
                )
            for action in ("insert", "update", "delete"):
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS dairy_journal_entry_validate_{action} "
                    "ON finance_journalentry"
                )
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS dairy_journal_line_reject_{action} "
                    "ON finance_journalline"
                )
            cursor.execute(
                "DROP TRIGGER IF EXISTS dairy_stock_movement_apply ON inventory_stockmovement"
            )
            cursor.execute(
                "DROP TRIGGER IF EXISTS dairy_stock_movement_immutable_update "
                "ON inventory_stockmovement"
            )
            cursor.execute(
                "DROP TRIGGER IF EXISTS dairy_stock_movement_reverse_delete "
                "ON inventory_stockmovement"
            )
            cursor.execute("DROP FUNCTION IF EXISTS dairy_check_tenant_references()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_check_related_organizations()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_reject_schedule_overlap()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_reject_accounting_period_overlap()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_apply_stock_movement()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_reject_stock_movement_mutation()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_reverse_stock_movement()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_validate_journal_entry()")
            cursor.execute("DROP FUNCTION IF EXISTS dairy_reject_posted_journal_line_mutation()")


class Migration(migrations.Migration):
    dependencies = [
        ("collections", "0005_milkcollection_collection_total_matches_rate"),
        ("finance", "0006_payment_payment_direction_matches_party"),
        ("inventory", "0003_inventoryitem_inventory_stock_nonnegative_and_more"),
        ("organizations", "0004_branch_soft_delete"),
        ("parties", "0002_soft_delete"),
        ("pricing", "0003_pricing_soft_delete"),
    ]

    operations = [
        migrations.RunPython(validate_existing_integrity, migrations.RunPython.noop),
        migrations.RunPython(install_integrity_triggers, remove_integrity_triggers),
    ]
