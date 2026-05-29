import os
import sys

import pymysql
import pymysql.cursors

# Intentar hosts comunes (Docker vs XAMPP local)
CANDIDATES = [
    {'host': os.getenv('DB_HOST', '127.0.0.1'), 'port': 3306, 'user': 'root', 'password': os.getenv('DB_PASS', '')},
    {'host': '127.0.0.1', 'port': 3306, 'user': 'root', 'password': 'root'},
    {'host': '127.0.0.1', 'port': 3306, 'user': 'root', 'password': ''},
    {'host': 'db', 'port': 3306, 'user': 'root', 'password': 'root'},
]
DB_NAMES = ['grsia', 'cia2026', 'ventasgeneral2']


def connect():
    for cfg in CANDIDATES:
        for db in DB_NAMES:
            try:
                conn = pymysql.connect(
                    host=cfg['host'], port=cfg['port'], user=cfg['user'],
                    password=cfg['password'], database=db,
                    charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=5,
                )
                with conn.cursor() as cur:
                    cur.execute("SHOW TABLES LIKE 'ventasgeneral2'")
                    if cur.fetchone():
                        print(f"OK conexion: {cfg['host']}:{cfg['port']} db={db}")
                        return conn
                conn.close()
            except Exception:
                continue
    # Sin DB: buscar ventasgeneral2 en cualquier schema
    for cfg in CANDIDATES:
        try:
            conn = pymysql.connect(
                host=cfg['host'], port=cfg['port'], user=cfg['user'],
                password=cfg['password'], charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
            )
            with conn.cursor() as cur:
                cur.execute("SHOW DATABASES")
                for row in cur.fetchall():
                    db = list(row.values())[0]
                    if db in ('information_schema', 'mysql', 'performance_schema', 'sys'):
                        continue
                    cur.execute(f"USE `{db}`")
                    cur.execute("SHOW TABLES LIKE 'ventasgeneral2'")
                    if cur.fetchone():
                        print(f"OK conexion: {cfg['host']} db={db}")
                        return conn
            conn.close()
        except Exception:
            continue
    return None


def q(cur, sql, params=None):
    cur.execute(sql, params or {})
    return cur.fetchall()


def main():
    conn = connect()
    if not conn:
        print("ERROR: No se pudo conectar a MySQL. Verifique XAMPP/Docker y .env")
        sys.exit(1)

    with conn.cursor() as cur:
        total = q(cur, "SELECT COUNT(*) AS n FROM ventasgeneral2")[0]['n']
        print(f"\n=== RESUMEN ===\nTotal filas: {total:,}")

        # 1. Cobertura por año
        print("\n--- 1. Cobertura por año ---")
        rows = q(cur, """
            SELECT YEAR(FechaContable) AS anio,
                   COUNT(*) AS filas,
                   COUNT(DISTINCT DATE_FORMAT(FechaContable,'%%Y-%%m')) AS meses,
                   MIN(FechaContable) AS desde, MAX(FechaContable) AS hasta
            FROM ventasgeneral2
            GROUP BY YEAR(FechaContable) ORDER BY anio
        """)
        for r in rows:
            print(f"  {r['anio']}: {r['filas']:,} filas, {r['meses']} meses, {r['desde']} .. {r['hasta']}")

        # 2. Fechas nulas o inválidas
        print("\n--- 2. Fechas problemáticas ---")
        n_null = q(cur, "SELECT COUNT(*) AS n FROM ventasgeneral2 WHERE FechaContable IS NULL")[0]['n']
        n_feb29 = q(cur, """
            SELECT COUNT(*) AS n FROM ventasgeneral2
            WHERE MONTH(FechaContable)=2 AND DAY(FechaContable)=29
        """)[0]['n']
        print(f"  FechaContable NULL: {n_null}")
        print(f"  Registros 29-feb: {n_feb29}")

        # 3. Duplicados lógicos
        print("\n--- 3. Duplicados (fecha+cliente+doc+item) ---")
        dup = q(cur, """
            SELECT COUNT(*) AS grupos_dup FROM (
                SELECT 1 FROM ventasgeneral2
                GROUP BY FechaContable, CodigoCliente, NumeroDocumento, CodigoItem
                HAVING COUNT(*) > 1
            ) t
        """)[0]['grupos_dup']
        dup_rows = q(cur, """
            SELECT SUM(cnt - 1) AS filas_extra FROM (
                SELECT COUNT(*) AS cnt FROM ventasgeneral2
                GROUP BY FechaContable, CodigoCliente, NumeroDocumento, CodigoItem
                HAVING COUNT(*) > 1
            ) t
        """)[0]['filas_extra'] or 0
        print(f"  Grupos duplicados: {dup}")
        print(f"  Filas redundantes (aprox): {int(dup_rows):,}")

        # 4. CodigoDocumento
        print("\n--- 4. Tipo documento (CodigoDocumento) ---")
        for r in q(cur, """
            SELECT CodigoDocumento, COUNT(*) AS n
            FROM ventasgeneral2 GROUP BY CodigoDocumento ORDER BY n DESC LIMIT 15
        """):
            print(f"  {r['CodigoDocumento'] or '(null)'}: {r['n']:,}")

        # 5. LineaComercial
        print("\n--- 5. Líneas comerciales (top 15) ---")
        for r in q(cur, """
            SELECT LineaComercial, CodigoLineaComercial, COUNT(*) AS n
            FROM ventasgeneral2
            GROUP BY LineaComercial, CodigoLineaComercial
            ORDER BY n DESC LIMIT 15
        """):
            print(f"  [{r['CodigoLineaComercial']}] {r['LineaComercial']}: {r['n']:,}")

        # 6. Valores negativos en ventas 01/03
        print("\n--- 6. Valores negativos (docs 01/03) ---")
        neg = q(cur, """
            SELECT COUNT(*) AS n FROM ventasgeneral2
            WHERE CodigoDocumento IN ('01','03')
              AND (Valor < 0 OR Peso < 0 OR Cantidad < 0)
        """)[0]['n']
        print(f"  Filas con Valor/Peso/Cantidad < 0: {neg}")

        # 7. Campos clave vacíos
        print("\n--- 7. Campos clave vacíos ---")
        for col in ('LineaComercial', 'Provincia', 'CodigoCliente', 'NombreCliente'):
            n = q(cur, f"""
                SELECT COUNT(*) AS n FROM ventasgeneral2
                WHERE TRIM(COALESCE({col},'')) = ''
            """)[0]['n']
            pct = 100.0 * n / total if total else 0
            print(f"  {col} vacío: {n:,} ({pct:.1f}%)")

        # 8. Serie mensual 2026 Pollo Vivo (proyección)
        print("\n--- 8. Serie mensual Pollo Vivo (01/03) ---")
        pv = q(cur, """
            SELECT DATE_FORMAT(FechaContable,'%%Y-%%m') AS mes,
                   ROUND(SUM(Valor),2) AS valor, ROUND(SUM(Peso),2) AS peso
            FROM ventasgeneral2
            WHERE CodigoDocumento IN ('01','03')
              AND (CodigoLineaComercial = '601' OR LOWER(TRIM(LineaComercial)) = 'pollo vivo')
            GROUP BY mes ORDER BY mes
        """)
        if pv:
            for r in pv:
                print(f"  {r['mes']}: S/ {r['valor']:,.2f}, {r['peso']:,.2f} kg")
        else:
            print("  (sin datos Pollo Vivo)")

        # 9. Índices
        print("\n--- 9. Índices en ventasgeneral2 ---")
        idx = q(cur, "SHOW INDEX FROM ventasgeneral2")
        if idx:
            seen = set()
            for r in idx:
                if r['Key_name'] not in seen:
                    seen.add(r['Key_name'])
                    print(f"  {r['Key_name']}: {r['Column_name']}")
        else:
            print("  (ninguno)")

    conn.close()
    print("\n=== FIN AUDITORIA ===")


if __name__ == '__main__':
    main()
