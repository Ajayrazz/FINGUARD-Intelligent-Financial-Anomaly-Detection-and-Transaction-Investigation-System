from django.db import migrations

FORWARD = """
CREATE SEQUENCE cases_case_ref_seq START 1;

-- a closed case is read-only and no case is ever deleted
CREATE FUNCTION cases_case_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'cases_case rows cannot be deleted';
    END IF;
    IF OLD.status = 'closed' THEN
        RAISE EXCEPTION 'case % is closed and read-only', OLD.case_ref;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER cases_case_guard BEFORE UPDATE OR DELETE ON cases_case
FOR EACH ROW EXECUTE FUNCTION cases_case_guard();

-- history, notes, revisions, evidence and links are append-only
CREATE FUNCTION cases_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only (% blocked)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER cases_caseevent_append_only BEFORE UPDATE OR DELETE ON cases_caseevent FOR EACH ROW EXECUTE FUNCTION cases_append_only();
CREATE TRIGGER cases_casenote_append_only BEFORE UPDATE OR DELETE ON cases_casenote FOR EACH ROW EXECUTE FUNCTION cases_append_only();
CREATE TRIGGER cases_casenoterevision_append_only BEFORE UPDATE OR DELETE ON cases_casenoterevision FOR EACH ROW EXECUTE FUNCTION cases_append_only();
CREATE TRIGGER cases_caseevidence_append_only BEFORE UPDATE OR DELETE ON cases_caseevidence FOR EACH ROW EXECUTE FUNCTION cases_append_only();
CREATE TRIGGER cases_casealert_append_only BEFORE UPDATE OR DELETE ON cases_casealert FOR EACH ROW EXECUTE FUNCTION cases_append_only();
CREATE TRIGGER cases_casetransaction_append_only BEFORE UPDATE OR DELETE ON cases_casetransaction FOR EACH ROW EXECUTE FUNCTION cases_append_only();

-- nothing can be added to a closed case (its history table is exempt: closing itself writes an event)
CREATE FUNCTION cases_no_insert_on_closed() RETURNS trigger AS $$
DECLARE st text; cid bigint;
BEGIN
    IF TG_TABLE_NAME = 'cases_casenoterevision' THEN
        SELECT case_id INTO cid FROM cases_casenote WHERE id = NEW.note_id;
    ELSE
        cid := NEW.case_id;
    END IF;
    SELECT status INTO st FROM cases_case WHERE id = cid;
    IF st = 'closed' THEN
        RAISE EXCEPTION 'case % is closed: no further changes', cid;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER cases_casenote_closed_guard BEFORE INSERT ON cases_casenote FOR EACH ROW EXECUTE FUNCTION cases_no_insert_on_closed();
CREATE TRIGGER cases_casenoterevision_closed_guard BEFORE INSERT ON cases_casenoterevision FOR EACH ROW EXECUTE FUNCTION cases_no_insert_on_closed();
CREATE TRIGGER cases_caseevidence_closed_guard BEFORE INSERT ON cases_caseevidence FOR EACH ROW EXECUTE FUNCTION cases_no_insert_on_closed();
CREATE TRIGGER cases_casealert_closed_guard BEFORE INSERT ON cases_casealert FOR EACH ROW EXECUTE FUNCTION cases_no_insert_on_closed();
CREATE TRIGGER cases_casetransaction_closed_guard BEFORE INSERT ON cases_casetransaction FOR EACH ROW EXECUTE FUNCTION cases_no_insert_on_closed();
"""
REVERSE = """
DROP TRIGGER cases_casetransaction_closed_guard ON cases_casetransaction;
DROP TRIGGER cases_casealert_closed_guard ON cases_casealert;
DROP TRIGGER cases_caseevidence_closed_guard ON cases_caseevidence;
DROP TRIGGER cases_casenoterevision_closed_guard ON cases_casenoterevision;
DROP TRIGGER cases_casenote_closed_guard ON cases_casenote;
DROP FUNCTION cases_no_insert_on_closed();
DROP TRIGGER cases_casetransaction_append_only ON cases_casetransaction;
DROP TRIGGER cases_casealert_append_only ON cases_casealert;
DROP TRIGGER cases_caseevidence_append_only ON cases_caseevidence;
DROP TRIGGER cases_casenoterevision_append_only ON cases_casenoterevision;
DROP TRIGGER cases_casenote_append_only ON cases_casenote;
DROP TRIGGER cases_caseevent_append_only ON cases_caseevent;
DROP FUNCTION cases_append_only();
DROP TRIGGER cases_case_guard ON cases_case;
DROP FUNCTION cases_case_guard();
DROP SEQUENCE cases_case_ref_seq;
"""


class Migration(migrations.Migration):
    dependencies = [("cases", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
