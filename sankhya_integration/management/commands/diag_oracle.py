from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Diagnose Oracle connectivity: shows resolved DSN target and attempts a ping/query."

    def handle(self, *args, **options):
        from sankhya_integration.services.oracle_conn import get_connection
        # Access internal cfg helper for better diagnostics (safe; only reads env and settings)
        try:
            from sankhya_integration.services.oracle_conn import _get_dsn_cfg  # type: ignore
        except Exception:
            _get_dsn_cfg = None  # type: ignore

        self.stdout.write(self.style.NOTICE("Packing House — Oracle diagnostics"))
        cfg = {}
        try:
            cfg = _get_dsn_cfg() if _get_dsn_cfg else {}
        except Exception:
            cfg = {}
        if isinstance(cfg, dict) and cfg:
            host = cfg.get('host')
            port = cfg.get('port')
            service = cfg.get('service_name')
            sid = cfg.get('sid')
            full_dsn = cfg.get('dsn')
            user = cfg.get('user')
            self.stdout.write(f"Target: host={host} port={port} service={service} sid={sid} dsn={full_dsn}")
            self.stdout.write(f"User: {user}")
        else:
            self.stdout.write("Target: <unavailable>")

        # Try connecting and pinging
        try:
            with get_connection() as conn:
                # Prefer ping when available
                try:
                    conn.ping()
                    self.stdout.write(self.style.SUCCESS("DB ping: OK"))
                except Exception:
                    self.stdout.write("DB ping not available; running SELECT 1 FROM DUAL...")
                    cur = conn.cursor()
                    cur.execute("SELECT 1 FROM DUAL")
                    _ = cur.fetchone()
                    self.stdout.write(self.style.SUCCESS("DUAL query: OK"))
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
                    row = cur.fetchone()
                    if row and row[0]:
                        self.stdout.write(f"DB version: {row[0]}")
                except Exception:
                    pass
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Connection failed: {e}"))
            self.stderr.write("Hint: Set environment variables SANKHYA_DB_HOST/PORT/SERVICE (or SANKHYA_DB_DSN), SANKHYA_DB_USER/PASSWORD.\n"
                              "On Windows PowerShell (current session):\n"
                              "$env:SANKHYA_DB_HOST='your-host'; $env:SANKHYA_DB_PORT='1521'; $env:SANKHYA_DB_SERVICE='ORCLPDB1'; $env:SANKHYA_DB_USER='user'; $env:SANKHYA_DB_PASSWORD='pass'")
            return 1
        return 0
