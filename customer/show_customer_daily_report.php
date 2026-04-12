<?php

require_once "../milk_dbconnection.php";

$stmt =$pdo->prepare("SELECT
            c.customer_id,
            c.customer_name,
            d.milk_id,
            d.milk_liter,
            d.milk_rate,
            d.milk_total_price,
            d.snf,
            d.fat,
            d.lacto,
            d.collection_date
    FROM daily_milk d
    JOIN customer c ON d.customer_id = c.customer_id
    ORDER BY d.milk_id DESC");

$stmt->execute();
$customers =$stmt->fetchAll(PDO::FETCH_ASSOC);

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
    <h1>List of Today's Customers Milk Details</h1>
     <input class="search" 
     type="text" 
     id="search" 
    placeholder="...Search Customer by Name" 
    onkeyup="searchTable()">

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
    
   

    <table border="1" id="customerTable">
    <tr>
        <th>Customer Name</th>
        <th>Milk Liter</th>
        <th>Rate</th>
        <th>Total Price</th>
        <th>SNF</th>
        <th>FAT</th>
        <th>Lacto</th>
        <th>Date</th>
        <th>Action</th>
    </tr>

   <?php foreach ($customers as $row): ?>
       
        <tr>

            <td>
                <a href="demo_customer.php?customer_id=<?php echo $row['customer_id']; ?>">
                    <?php echo htmlspecialchars( $row['customer_name']); ?>
                </a>
            </td>
 
            <td><?php echo $row['milk_liter']; ?></td>
            <td><?php echo $row['milk_rate']; ?></td>
            <td><?php echo $row['milk_total_price']; ?></td>
            <td><?php echo $row['snf']; ?></td>
            <td><?php echo $row['fat']; ?></td>
            <td><?php echo $row['lacto']; ?></td>
            <td><?php echo $row['collection_date']; ?></td>

            <td>
                <a class="delete" href="delete_customer_daily_report.php?milk_id=
                <?php echo $row['milk_id']; ?>">Delete</a> <br><br> 
                
                <a class="edit" href="edit_customer_daily_report.php?milk_id=<?php echo $row['milk_id']; ?>">Edit</a>
            </td> 
        </tr>

      <?php endforeach; ?> 
</table>
     <script>
        function searchTable() {
            const input = document.getElementById("search").value.toLowerCase();
            const table = document.getElementById("customerTable");
            const rows = table.getElementsByTagName("tr");

            for (let i=1; i <rows.length; i++) {
                const nameCell = rows[i].getElementsByTagName("td")[0];
                if (nameCell) {
                    const nameText = nameCell.textContent.toLowerCase().trim();

                    if (input === "") {
                        rows[i].style.display = ""; // show all when empty
                    
                    } else {
                        //split name into individual words and check each words
                        const words = nameText.split(" ");
                        const matched = words.some(word => word.startsWith(input));
                        rows[i].style.display = matched ? "" : "none";
                    }
                }
            }
        }
     </script>

         </div> <!-- left navbar div end -->
</main> <!--=====SIDEBAR end From Here=====-->


</body>
</html>