<?php

require_once "../milk_dbconnection.php";

if (isset($_POST['submit'])) {

    $customer_id     = $_POST['customer_id'];
    $milk_liter      = $_POST['milk_liter'];
    $milk_rate       = $_POST['milk_rate'];
    $collection_date = $_POST['collection_date'].' '. date('H:i:s');
;
    $staff_id        = $_POST['staff_id'];

    //inserting snf, fat, lacto
    $snf        = $_POST['snf'];
    $fat        = $_POST['fat'];
    $lacto      = $_POST['lacto'];

    if (empty($customer_id)) {
        die("Please select a valid customer name.");
    }

    if (empty($staff_id)) {
        die("Please select a valid staff name.");
    }






    $stmt = $pdo->prepare("
        INSERT INTO daily_milk (customer_id, milk_liter, milk_rate, collection_date, staff_id, snf, fat, lacto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ");

    $stmt->execute([
        $customer_id,
        $milk_liter,
        $milk_rate,
        $collection_date,
        $staff_id,
        $snf,
        $fat,
        $lacto
    ]);

    header("Location: dashboard.php");
    exit();
}
?>
