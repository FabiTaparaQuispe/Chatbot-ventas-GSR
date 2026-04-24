<?php
declare(strict_types=1);

final class Database
{
    private static ?\PDO $pdo = null;

    public static function pdo(array $dbConfig): \PDO
    {
        if (self::$pdo === null) {
            self::$pdo = new \PDO(
                $dbConfig['dsn'],
                $dbConfig['user'],
                $dbConfig['password'],
                [
                    \PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION,
                    \PDO::ATTR_DEFAULT_FETCH_MODE => \PDO::FETCH_ASSOC,
                ]
            );
        }
        return self::$pdo;
    }
}
