<?php
require_once "../milk/milk_dbconnection.php";

if (isset($_POST['submit'])) {

    $customer_id     = $_POST['customer_id'];
    $milk_liter      = $_POST['milk_liter'];
    $milk_rate       = $_POST['milk_rate'];
    $snf             = $_POST['snf'];
    $fat             = $_POST['fat'];
    $lacto           = $_POST['lacto'];
    $collection_date = $_POST['collection_date'];
    $staff_id        = $_POST['staff_id'];

    if (empty($customer_id)) {
        die("Please select a valid customer name.");
    }
    if (empty($staff_id)) {
        die("Please select a valid staff name.");
    }

    $stmt = $pdo->prepare("
        INSERT INTO daily_milk 
        (customer_id, milk_liter, milk_rate, snf, fat, lacto, collection_date, staff_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ");
    $stmt->execute([
        $customer_id,
        $milk_liter,
        $milk_rate,
        $snf,
        $fat,
        $lacto,
        $collection_date,
        $staff_id
    ]);

    header("Location: dashboard/dashboard.php");
    exit();
}
?>