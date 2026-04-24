<?php
declare(strict_types=1);

final class DateRangeValidator
{
    public function __construct(
        private readonly int $maxRangeDays
    ) {
    }

    /**
     * @return array{0: string, 1: string}|array{error: string}
     */
    public function validate(string $desde, string $hasta): array
    {
        $d1 = \DateTimeImmutable::createFromFormat('Y-m-d', $desde);
        $d2 = \DateTimeImmutable::createFromFormat('Y-m-d', $hasta);
        if (!$d1 || $d1->format('Y-m-d') !== $desde) {
            return ['error' => 'fecha_desde invalida; use YYYY-MM-DD'];
        }
        if (!$d2 || $d2->format('Y-m-d') !== $hasta) {
            return ['error' => 'fecha_hasta invalida; use YYYY-MM-DD'];
        }
        if ($d1 > $d2) {
            return ['error' => 'fecha_desde no puede ser mayor que fecha_hasta'];
        }
        $days = $d1->diff($d2)->days;
        if ($days > $this->maxRangeDays) {
            return ['error' => "rango maximo {$this->maxRangeDays} dias"];
        }
        return [$desde, $hasta];
    }
}
