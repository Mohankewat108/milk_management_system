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
    <!--=====SIDEBAR Start From Here=====-->
     <main>
       <div class="pannel_left_side">
            <img src="../dashboard/mohan.png" alt="">
            <h1>Mohan</h1>
            <hr><br>

            <h2><a href="../dashboard/index.php">Dashboard</a></h2>
            <hr><br>

            <h2><a href="../customer/create_customer.php">Add New Customer</a></h2>
            <hr><br>

            <h2><a href="../customer/show_customer_daily_report.php">Today Milk Detail</a></h2>
            <hr><br>

            <h2><a href="../customer/show_customer_details.php">Customer Details</a></h2>
            <hr>

            <h2><a href="../setting/milk_quality_parameters.php">setting</a></h2>
            <hr>
            
        </div> <!--======Navbar or Left side side Bar end here=====-->

<!--Right side NavBar Start here  -->
        <div class="pannel_right_side"> <!-- left navbar div start -->
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

     </div> <!-- left navbar div end -->
</main> <!--=====SIDEBAR end From Here=====-->
    

    
</body>
</html>