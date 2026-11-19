from django.db import migrations

FORWARD = """
CREATE FUNCTION transactions_event_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'transactions_transactionevent is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transactions_event_no_update_delete
BEFORE UPDATE OR DELETE ON transactions_transactionevent
FOR EACH ROW EXECUTE FUNCTION transactions_event_immutable();
"""
REVERSE = """
DROP TRIGGER transactions_event_no_update_delete ON transactions_transactionevent;
DROP FUNCTION transactions_event_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("transactions", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
