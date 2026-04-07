<?php

require_once "../milk_dbconnection.php";
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <link rel="stylesheet" href="../dashboard/dashboard.css">
</head>
<body>
    <h1>Add Customers</h1>

    <fieldset>
        <legend>Customer Details</legend><br>
        <form action="insert_customer.php" method="POST">

        <label for="customer_name">Customer Name:</label>
        <input type="text" placeholder="Enter Customer Name" required
               name="customer_name" id="customer_name" value=""> <br><br>

        <label for="phone_number">Customer Phone Number:</label>
        <input type="text" placeholder="Enter Customer Number" required
               name="phone_number" id="phone_number" value=""> <br><br>

        <label for="gmail">Gmail:</label>
        <input type="email" placeholder="Example@gmail.com" 
               name="gmail" id="gmail" value=""> <br><br>

        <label for="city">City:</label>
        <input type="text" placeholder="City Name" required
               name="city" id="city" value=""> <br><br>

        <label for="village">Village Name:</label>
        <input type="text" placeholder="Village Name" required
               name="village" id="village" value=""> <br><br>

        <label for="ward_name">Ward Name:</label>
        <input type="text" placeholder="Ward_Name" 
               name="ward_name" id="ward_name" value=""> <br>

        <input type="submit" value="Submit" name="submit">
        </form>
    </fieldset>
    

    
</body>
</html>