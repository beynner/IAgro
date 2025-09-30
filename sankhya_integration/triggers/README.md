This folder stores database trigger definitions (DDL) exported from the ERP schema for documentation and future validations.

How to update:
- List triggers by pattern:
  ```powershell
  python manage.py dump_triggers --like %CAB% --owner SANKHYA --no-body
  ```
- Save trigger DDLs locally (writes .sql into `triggers/triggers/`):
  ```powershell
  python manage.py save_triggers --like %CAB% --owner SANKHYA
  ```
- Individual trigger body:
  ```powershell
  python manage.py show_trigger TRG_INC_TGFCAB
  ```

Notes:
- .sql files live under `triggers/triggers/`; the index is generated at `triggers/INDEX.md`.
- Files are named as `<OWNER>.<TRIGGER_NAME>.sql` when owner is provided; otherwise `TRIGGER_NAME.sql`.
- DDL is fetched using ALL_TRIGGERS / ALL_SOURCE; formatting may differ from original.
