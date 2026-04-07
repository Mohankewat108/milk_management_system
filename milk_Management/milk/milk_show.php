<?php
require_once "milk_dbconnection.php";

//selecting sql query
$sql = "SELECT 
    s.staff_name,
    c.customer_name,
    d.collection_date,
    d.milk_liter,
    d.milk_rate,
    d.milk_total_price
FROM daily_milk d
JOIN customer c ON d.customer_id = c.customer_id
JOIN staff s ON d.staff_id = s.staff_id
ORDER BY d.collection_date, s.staff_name, c.customer_name;";

$stmt = $pdo->query($sql);

$records = $stmt->fetchAll();

$page = <<<page

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>

<header>
<a href="show.php">Display Record</a>
<a href="create_student.html">New Record</a>
</header>



   <header>
    <h1>Milk Management System</h1>
   </header> 
   <table border="1">
    <tr>
        <th>staff_name</th>
        <th>customer_name</th>
        
        <th>milk_liter</th>
        <th>milk_rate</th>
        <th>collection_date</th>
        <th>milk_total_price</th>
        <th>Action</th>
    </tr>

page;
echo $page;

foreach ($records as $milk) {
    echo"
    <tr>
        <td>$milk[staff_name]</td>
        <td>$milk[customer_name]</td>
       
        <td>$milk[milk_liter]</td>
        <td>$milk[milk_rate]</td>
        <td>$milk[collection_date]</td>
        <td>$milk[milk_total_price]</td>
        

        <td>
          <a href='#'>Delete</a> |
          <a href='#'>Edit</a>
        </td>
    </tr>";
}
echo "</table>
</body>
</html>";