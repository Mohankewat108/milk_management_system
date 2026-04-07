<?php

require_once "../milk_dbconnection.php";


$stmt =$pdo->prepare("SELECT * FROM customer ORDER BY customer_name ASC");

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
    <h1>List of Customers</h1>
    
    <input type="text" id="search" 
    placeholder="...Search Customer by Name" onkeyup="searchTable()">

    <table border="1" id="customerTable">
    <tr>
        <th>Customer Name</th>
        <th>Phone Number</th>
        <th>Gmail</th>
        <th>City</th>
        <th>Village</th>
        <th>Ward Name</th>
        
    </tr>

   <?php foreach ($customers as $row): ?>
       
        <tr>
            <td><a href="demo_customer.php?customer_id=<?php echo $row['customer_id']; ?>">
                <?php echo htmlspecialchars( $row['customer_name']); ?>

            </a></td>

            <td><?php echo $row['phone_number']; ?></td>
            <td><?php echo $row['gmail']; ?></td>
            <td><?php echo $row['city']; ?></td>
            <td><?php echo $row['village']; ?></td>
            <td><?php echo $row['ward_name']; ?></td>
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


</body>
</html>