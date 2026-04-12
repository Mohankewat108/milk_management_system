<?php
require_once "../milk_dbconnection.php";

if (isset($_POST['submit'])) {

    $milk_id         = $_POST['milk_id'];
    $customer_id     = $_POST['customer_id'];
    $milk_liter      = $_POST['milk_liter'];
    $milk_rate       = $_POST['milk_rate'];
    $snf             = $_POST['snf'];
    $fat             = $_POST['fat'];
    $lacto           = $_POST['lacto'];
    $collection_date = $_POST['collection_date'].' '.date('H:i:s');
    $staff_id        = $_POST['staff_id'];

    if (empty($customer_id)) {
        die("Please select a valid customer name.");
    }
    if (empty($staff_id)) {
        die("Please select a valid staff name.");
    }

    $stmt = $pdo->prepare("
        UPDATE daily_milk
        SET
            customer_id     = ?,
            milk_liter      = ?,
            milk_rate       = ?,
            snf             = ?,
            fat             = ?,
            lacto           = ?,
            collection_date = ?,
            staff_id        = ?
        WHERE milk_id = ?
    ");

    $stmt->execute([
        $customer_id,
        $milk_liter,
        $milk_rate,
        $snf,
        $fat,
        $lacto,
        $collection_date,
        $staff_id,
        $milk_id
    ]);

    header("Location: show_customer_daily_report.php");
    exit();
}
?>