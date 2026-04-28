<?php

declare(strict_types=1);

/**
 * Etiquetas legibles para códigos de tipo de comprobante (SUNAT / catálogo común en Perú).
 * Los datos siguen almacenando el código; esto es solo para presentación.
 */
final class DocumentoTipoEtiqueta
{
    /** @var array<string, string> código normalizado (2 dígitos) => nombre */
    private const MAP = [
        '01' => 'Factura',
        '02' => 'Recibo por honorarios',
        '03' => 'Boleta de venta',
        '04' => 'Liquidación de compra',
        '05' => 'Boletos de transporte',
        '06' => 'Carta de porte aéreo',
        '07' => 'Nota de crédito',
        '08' => 'Nota de débito',
        '09' => 'Guía de remisión remitente',
        '11' => 'Póliza emitida por el SNCE',
        '12' => 'Ticket o cinta de máquina registradora',
        '13' => 'Documento emitido por bancos e instituciones financieras',
        '14' => 'Recibo por servicios públicos',
        '15' => 'Boletos emitidos por el SNCE',
        '16' => 'Ticket de viaje',
        '18' => 'Documento emitido por AFP',
        '20' => 'Comprobante de retención',
        '21' => 'Conocimiento de embarque',
        '22' => 'Documentos emitidos por las COFOPRI',
        '23' => 'Guía de remisión transportista',
        '24' => 'Documento del operador',
        '25' => 'Documento autorizado en el SNCE',
        '26' => 'Recibo por tarifa portuaria',
        '27' => 'Documento emitido por el SNCE',
        '28' => 'Recibo emitido por entidades del sistema financiero',
        '29' => 'Documentos emitidos por cooperativas',
        '30' => 'Documento emitido por las empresas desintegradas',
        '31' => 'Guía de remisión',
        '32' => 'Documentos emitidos por los sistemas de boleaje',
        '34' => 'Documento emitido por la recaudación de las cobranzas',
        '35' => 'Documento emitido por el SNCE',
        '36' => 'Documento emitido por los sistemas de venta interna',
        '37' => 'Documento emitido por la administración portuaria',
        '40' => 'Comprobante de percepción',
        '99' => 'Otros',
    ];

    public static function etiqueta(string $tdoc): string
    {
        $raw = trim($tdoc);
        if ($raw === '' || strcasecmp($raw, '(sin TDoc)') === 0) {
            return 'Sin tipo indicado';
        }

        if (isset(self::MAP[$raw])) {
            return self::MAP[$raw];
        }

        $soloDigitos = preg_replace('/\D/', '', $raw) ?? '';
        if ($soloDigitos !== '') {
            $norm = strlen($soloDigitos) <= 2
                ? str_pad($soloDigitos, 2, '0', STR_PAD_LEFT)
                : $soloDigitos;
            if (isset(self::MAP[$norm])) {
                return self::MAP[$norm];
            }
        }

        return 'Tipo ' . $raw;
    }

    /**
     * @param array<int, array<string, mixed>> $filas filas con clave 'tdoc'
     * @return array<int, array<string, mixed>> mismas filas con 'tdoc_etiqueta' añadida
     */
    public static function enriquecerFilas(array $filas): array
    {
        foreach ($filas as $i => $f) {
            $c = (string) ($f['tdoc'] ?? '');
            $filas[$i]['tdoc_etiqueta'] = self::etiqueta($c);
        }

        return $filas;
    }
}
