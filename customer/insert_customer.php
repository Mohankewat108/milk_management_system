<?php

require_once "../milk_dbconnection.php";

if (isset($_POST['submit'])) {
    $customer_name = $_POST['customer_name'];
    $phone_number = $_POST['phone_number']; 
    $gmail = $_POST['gmail'];
    $city = $_POST['city'];
    $village = $_POST['village'];
    $ward_name = $_POST['ward_name'];


$stmt = $pdo->prepare("
    INSERT INTO customer (customer_name, phone_number,
         gmail, city, village, ward_name)
    VALUES (?, ?, ?, ?, ?, ?)");

$stmt->execute([
    $customer_name,
    $phone_number,
    $gmail,
    $city,
    $village,
    $ward_name]);

header("Location: create_customer.php");
exit();

}
?>