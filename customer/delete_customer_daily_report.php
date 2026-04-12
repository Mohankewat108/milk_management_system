<?php
require_once "../milk_dbconnection.php";

// Check if ID exists
if (!isset($_GET['milk_id'])) {
    die("Error: Milk ID not specified.");
}

$milk_id = $_GET['milk_id'];

$stmt = $pdo->prepare("DELETE FROM daily_milk WHERE milk_id = ?");
$stmt->execute([$milk_id]);

// Delete from customer table (parent table)
/*$stmt = $pdo->prepare("DELETE FROM customer WHERE customer_id= ?");
$stmt->execute([$customer_id]); */

// Redirect back to list
header("Location: show_customer_daily_report.php");
exit();
?>