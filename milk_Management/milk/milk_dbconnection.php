<?php
$host = "localhost";
$database= "milk";
$username= "root";
$password= "root";

try {
    $pdo = new PDO("mysql:host=$host; dbname=$database", $username, $password);
    echo "database connected successfully Mohan";
}

catch (PDOException $e) {
    echo "connection failed Mohan".$e->getMessage();
}