<?php

declare(strict_types=1);

$q = $_SERVER['QUERY_STRING'] ?? '';
$target = 'pareto_clientes_zona.php' . ($q !== '' ? '?' . $q : '');
header('Location: ' . $target, true, 302);
exit;
