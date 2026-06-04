"""Verificación de las 58 preguntas: pregunta al chatbot local y compara contra
la BD las que tienen número concreto. Uso interno (no es un test de pytest)."""
import os, re, time, requests, pymysql, pymysql.cursors

BASE = os.getenv('CHAT_BASE_URL', 'http://localhost:5000')
USER = os.getenv('CHAT_USER', 'admin'); PWD = os.getenv('CHAT_PASS', 'qwerty123')
DBP = dict(host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', '3307')),
           user=os.getenv('DB_USER', 'root'), password=os.getenv('DB_PASS', 'root'),
           database=os.getenv('DB_NAME', 'grsia'), cursorclass=pymysql.cursors.DictCursor, charset='latin1')


def db1(sql, p=()):
    c = pymysql.connect(**DBP)
    try:
        with c.cursor() as cur:
            cur.execute(sql, p); return cur.fetchone()
    finally:
        c.close()


def importe(d1, d2, extra='', p=()):
    return float(db1(f"SELECT COALESCE(SUM(Valor),0) v FROM ventasgeneral2 WHERE FechaContable BETWEEN %s AND %s {extra}", (d1, d2, *p))['v'])

def peso(d1, d2, extra='', p=()):
    return float(db1(f"SELECT COALESCE(SUM(Peso),0) v FROM ventasgeneral2 WHERE FechaContable BETWEEN %s AND %s {extra}", (d1, d2, *p))['v'])

def cnt(d1, d2, extra='', p=()):
    return int(db1(f"SELECT COUNT(*) v FROM ventasgeneral2 WHERE FechaContable BETWEEN %s AND %s {extra}", (d1, d2, *p))['v'])

def top_cli(d1, d2, extra='', p=()):
    r = db1(f"SELECT MAX(NombreCliente) n FROM ventasgeneral2 WHERE FechaContable BETWEEN %s AND %s {extra} GROUP BY CodigoCliente ORDER BY SUM(Valor) DESC LIMIT 1", (d1, d2, *p))
    return (r or {}).get('n') or ''

def top_linea(d1, d2):
    r = db1("SELECT LineaComercial n FROM ventasgeneral2 WHERE FechaContable BETWEEN %s AND %s GROUP BY LineaComercial ORDER BY SUM(Valor) DESC LIMIT 1", (d1, d2))
    return (r or {}).get('n') or ''


def nums(t):
    out = []
    for m in re.findall(r'[\d][\d.,]*\d|\d', t or ''):
        raw = m
        if ',' in raw and '.' in raw:
            raw = raw.replace(',', '') if raw.rfind(',') < raw.rfind('.') else raw.replace('.', '').replace(',', '.')
        elif ',' in raw:
            raw = raw.replace(',', '')
        try: out.append(float(raw))
        except: pass
    return out

def has_num(exp, t, tol=1.0):
    if not exp: return any(abs(n) < 1 for n in nums(t))
    return any(abs(n - exp) / abs(exp) * 100 <= tol for n in nums(t))

def has_txt(s, t):
    return (s or '').lower()[:15] in (t or '').lower()


# (idx, pregunta, modo, fn_verdad)  modo: 'num' | 'txt' | 'presencia' | 'meta'
PV = "AND CodigoLineaComercial='601'"
CHECKS = [
 (1,'¿Cuánto se vendió en enero 2026?','num',lambda:importe('2026-01-01','2026-01-31')),
 (2,'Ventas del mes de abril (sin año)','num',lambda:importe('2026-04-01','2026-04-30')),
 (3,'Ventas del 15 de marzo (día único, sin año)','num',lambda:importe('2026-03-15','2026-03-15')),
 (4,'Ventas del 01 de enero 2026 al 31 de enero 2026','num',lambda:importe('2026-01-01','2026-01-31')),
 (5,'Ventas de febrero 2026 (año bisiesto)','num',lambda:importe('2026-02-01','2026-02-28')),
 (6,'Ventas de Pollo Vivo en enero 2026','num',lambda:importe('2026-01-01','2026-01-31',PV)),
 (7,'Ventas de Pollo Vivo en TACNA en marzo 2026','num',lambda:importe('2026-03-01','2026-03-31',PV+" AND Provincia LIKE %s",('%TACNA%',))),
 (8,'Ventas de Embutidos en febrero 2026','num',lambda:importe('2026-02-01','2026-02-28',"AND LineaComercial LIKE %s",('%EMBUTIDO%',))),
 (9,'¿Cuánto pesó Pollo Vivo vendido en abril 2026?','num',lambda:peso('2026-04-01','2026-04-30',PV)),
 (10,'Resumen de ventas por línea comercial de enero 2026','presencia',None),
 (11,'Top 10 clientes en LAJOYA de enero 2026','presencia',None),
 (12,'Top 5 clientes en TACNA de febrero 2026','presencia',None),
 (13,'Top 10 clientes con más venta en la provincia de Arequipa en marzo 2026','presencia',None),
 (14,'¿Cuáles son los 10 clientes que más compraron en abril 2026?','txt',lambda:top_cli('2026-04-01','2026-04-30')),
 (15,'Los 5 mejores clientes por peso en enero 2026','presencia',None),
 (16,'¿Cuánto se vendió en la zona AQP en enero 2026?','presencia',None),
 (17,'Ventas en la provincia de Tacna en febrero 2026','num',lambda:importe('2026-02-01','2026-02-28',"AND Provincia LIKE %s",('%TACNA%',))),
 (18,'Resumen de ventas por provincia en marzo 2026','presencia',None),
 (19,'¿Qué provincias compraron Pollo Vivo en abril 2026?','presencia',None),
 (20,'Ventas en Moquegua en enero 2026','num',lambda:importe('2026-01-01','2026-01-31',"AND Provincia LIKE %s",('%MOQUEGUA%',))),
 (21,'¿Cuáles son los precios de venta más altos del 01 de enero 2026 para Pollo Vivo?','presencia',None),
 (22,'Precio promedio por kg de Pollo Vivo en enero 2026','presencia',None),
 (23,'¿Qué cliente pagó más caro por kg en LAJOYA en febrero 2026?','presencia',None),
 (24,'Precio por kg de Embutidos por provincia en marzo 2026','presencia',None),
 (25,'¿Cuántas notas de crédito hubo en enero 2026?','num',lambda:cnt('2026-01-01','2026-01-31',"AND CodigoDocumento='07'")),
 (26,'¿Cuánto se devolvió en valor en febrero 2026?','num',lambda:abs(importe('2026-02-01','2026-02-28',"AND CodigoDocumento='07'"))),
 (27,'Clientes con nota de crédito en marzo 2026','presencia',None),
 (28,'¿Cuál es la venta neta de enero 2026? (facturas menos NC)','num',lambda:importe('2026-01-01','2026-01-31')),
 (29,'Ventas del cliente PACHO PACHO PEDRO PABLO en enero 2026','num',lambda:importe('2026-01-01','2026-01-31',"AND NombreCliente LIKE %s",('%PACHO PACHO PEDRO PABLO%',))),
 (30,'¿Cuánto compró SALAZAR MACHICAO IVONEE PATRICIA en el primer trimestre 2026?','num',lambda:importe('2026-01-01','2026-03-31',"AND NombreCliente LIKE %s",('%SALAZAR MACHICAO IVONEE%',))),
 (31,'Facturas del cliente SULLCA QUISPE MARTHA de febrero 2026','presencia',None),
 (32,'Busca la factura número 3750004023','presencia',None),
 (33,'¿Qué contiene la boleta 3750004023?','presencia',None),
 (34,'Resumen de enero, febrero y marzo 2026 por mes','presencia',None),
 (35,'¿Cuánto se vendió por semana en enero 2026?','presencia',None),
 (36,'¿Qué día de enero 2026 se vendió más?','presencia',None),
 (37,'Comparar ventas de Pollo Vivo en enero 2026 vs febrero 2026','presencia',None),
 (38,'¿Cuál fue el total vendido en valor y peso en lo que va de mayo 2026?','num',lambda:importe('2026-05-01','2026-05-31')),
 (39,'Top 10 clientes del mes de mayo 2026 por valor','txt',lambda:top_cli('2026-05-01','2026-05-31')),
 (40,'¿Qué línea comercial vendió más en abril 2026?','txt',lambda:top_linea('2026-04-01','2026-04-30')),
 (41,'¿Cuánto representan las notas de crédito sobre el total vendido en abril 2026?','presencia',None),
 (42,'Resumen de ventas por provincia en abril 2026','presencia',None),
 (43,'¿Cuál es el precio promedio por kg de Pollo Vivo en mayo 2026?','presencia',None),
 (44,'¿Qué zonas de precio tuvieron más venta en abril 2026?','presencia',None),
 (45,'Los 5 clientes con mayor volumen en kg en abril 2026','presencia',None),
 (46,'¿Quién es el usuario que más preguntas ha hecho este mes?','meta',None),
 (47,'¿Cuántas preguntas se hicieron en total en abril 2026?','meta',None),
 (48,'¿Cuántas preguntas se hicieron por día en la semana del 5 al 11 de mayo 2026?','meta',None),
 (49,'¿Cuáles fueron las últimas 10 preguntas del administrador?','meta',None),
 (50,'Muéstrame las preguntas del usuario fabiola.tapara en abril 2026','meta',None),
 (51,'¿Quiénes son los 5 usuarios que más usaron el chatbot en mayo 2026?','meta',None),
 (52,'Busca conversaciones donde se preguntó sobre notas de crédito','meta',None),
 (53,'¿Cuántas conversaciones se iniciaron en abril 2026?','meta',None),
 (54,'¿Cuál fue el día con más actividad en el chatbot en mayo 2026?','meta',None),
 (55,'¿Cuáles son los números de documentos de la venta de Huaypuna Mamani para el día 24 de mayo?','presencia',None),
 (56,'¿Cuáles son los códigos de ítem para la venta de Huaypuna Mamani del 24 de mayo?','presencia',None),
 (57,'¿Cuál es el peso de venta que tuvo el corporativo Huaypuna para la venta del día 24 de mayo?','num',lambda:peso('2026-05-24','2026-05-24',"AND NombreCoorporativo LIKE %s",('%HUAYPUNA%',))),
 (58,'¿Qué clientes pertenecen al corporativo Huaypuna Mamani Rony Angel?','presencia',None),
]


def ask(tok, q):
    for _ in range(3):
        try:
            r = requests.post(f'{BASE}/api/chat', json={'messages':[{'role':'user','content':q}]},
                              headers={'Authorization':f'Bearer {tok}'}, timeout=120)
            rep = r.json().get('reply','') if r.status_code==200 else ''
        except Exception:
            rep = ''
        if rep.strip() and 'no pude generar' not in rep.lower():
            return rep
        time.sleep(4)
    return rep


def main():
    tok = requests.post(f'{BASE}/api/auth/token', json={'usuario':USER,'clave':PWD}, timeout=15).json()['access_token']
    ok = bad = pres = meta = 0
    print(f"{'#':>3}  {'VERDICTO':12} PREGUNTA")
    print('-'*100)
    for idx, q, modo, fn in CHECKS:
        rep = ask(tok, q)
        fallo = (not rep.strip()) or ('no pude generar' in rep.lower())
        if modo == 'meta':
            v = 'INFO-meta' if not fallo else 'NO CONTESTO'; meta += 1
        elif fallo:
            v = 'NO CONTESTO'; bad += 1
        elif modo == 'num':
            exp = fn(); v = 'OK' if has_num(exp, rep) else f'REVISAR (BD={exp:,.2f})'
            ok += (v=='OK'); bad += (v!='OK')
        elif modo == 'txt':
            exp = fn(); v = 'OK' if has_txt(exp, rep) else f'REVISAR (BD={exp[:25]})'
            ok += (v=='OK'); bad += (v!='OK')
        else:
            v = 'RESPONDIO'; pres += 1
        print(f"{idx:>3}  {v:12} {q[:72]}")
    print('-'*100)
    print(f"Numéricas OK: {ok} | A revisar/fallo: {bad} | Respondió (lista, manual): {pres} | Meta-historial: {meta}")


if __name__ == '__main__':
    main()
