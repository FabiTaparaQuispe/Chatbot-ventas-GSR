from __future__ import annotations

import re
from typing import Any

_MAP: dict[str, str] = {
    "01": "Factura",
    "02": "Recibo por honorarios",
    "03": "Boleta de venta",
    "04": "Liquidación de compra",
    "05": "Boletos de transporte",
    "06": "Carta de porte aéreo",
    "07": "Nota de crédito",
    "08": "Nota de débito",
    "09": "Guía de remisión remitente",
    "11": "Póliza emitida por el SNCE",
    "12": "Ticket o cinta de máquina registradora",
    "13": "Documento emitido por bancos e instituciones financieras",
    "14": "Recibo por servicios públicos",
    "15": "Boletos emitidos por el SNCE",
    "16": "Ticket de viaje",
    "18": "Documento emitido por AFP",
    "20": "Comprobante de retención",
    "21": "Conocimiento de embarque",
    "22": "Documentos emitidos por las COFOPRI",
    "23": "Guía de remisión transportista",
    "24": "Documento del operador",
    "25": "Documento autorizado en el SNCE",
    "26": "Recibo por tarifa portuaria",
    "27": "Documento emitido por el SNCE",
    "28": "Recibo emitido por entidades del sistema financiero",
    "29": "Documentos emitidos por cooperativas",
    "30": "Documento emitido por las empresas desintegradas",
    "31": "Guía de remisión",
    "32": "Documentos emitidos por los sistemas de boleaje",
    "34": "Documento emitido por la recaudación de las cobranzas",
    "35": "Documento emitido por el SNCE",
    "36": "Documento emitido por los sistemas de venta interna",
    "37": "Documento emitido por la administración portuaria",
    "40": "Comprobante de percepción",
    "99": "Otros",
}


def enriquecer_filas_mix_tdoc(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in filas:
        row = dict(f)
        t = str(row.get("tdoc") or "")
        row["tdoc_etiqueta"] = etiqueta_documento(t)
        out.append(row)
    return out


def etiqueta_documento(tdoc: str) -> str:
    raw = tdoc.strip()
    if not raw or raw.casefold() == "(sin tdoc)".casefold():
        return "Sin tipo indicado"
    if raw in _MAP:
        return _MAP[raw]
    solo_digitos = re.sub(r"\D", "", raw)
    if solo_digitos:
        norm = solo_digitos.zfill(2) if len(solo_digitos) <= 2 else solo_digitos
        if norm in _MAP:
            return _MAP[norm]
    return f"Tipo {raw}"
