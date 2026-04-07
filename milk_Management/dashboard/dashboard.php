<?php

require_once "../milk_dbconnection.php";

//Query for total milk collection today
$stmt= $pdo->prepare("
      SELECT SUM(milk_liter) AS total_milk
      FROM daily_milk
      WHERE DATE(collection_date) = CURDATE()
");

$stmt->execute();
$result = $stmt->fetch(PDO::FETCH_ASSOC);
$total_milk_today = $result['total_milk'];

//If No milk today, set to 0
if (!$total_milk_today) {
    $total_milk_today = 0;
}

//Query for today total milk price
$stmt2= $pdo->prepare("
SELECT SUM(milk_total_price) AS total_milk_price
FROM daily_milk
WHERE DATE(collection_date) = CURDATE()
");
$stmt2->execute();
$result2= $stmt2->fetch(PDO::FETCH_ASSOC);
$total_milk_price_today= $result2['total_milk_price'] ?? 0;

// for average milk rate per liter today
if ($total_milk_today > 0) {
    $avg_milk_rate_today = $total_milk_price_today/$total_milk_today;
}

else {
    $avg_milk_rate_today = 0;
}

//Recently added top 5 customer
$stmt3= $pdo->prepare("
    SELECT
            c.customer_name,
            d.collection_date,
            d.milk_liter,
            d.milk_rate,
            d.milk_total_price
    FROM daily_milk d
    JOIN customer c ON
    d.customer_id = c.customer_id
    ORDER BY d.milk_id DESC
    LIMIT 5
");
$stmt3->execute();
$result3= $stmt3->fetchAll(PDO::FETCH_ASSOC);

//fetch all customers for dropdown
$customer_stmt= $pdo->query("SELECT customer_id, customer_name FROM customer");
$customers= $customer_stmt->fetchAll(PDO::FETCH_ASSOC);

//fetch all staffs for dropdown
$staff_stmt= $pdo->query("SELECT staff_id, staff_name FROM staff");
$staffs= $staff_stmt->fetchAll(PDO::FETCH_ASSOC);


// Fetch current SNF, FAT, LACTO rates
$stmt = $pdo->query("SELECT * FROM milk_setting WHERE setting_id = 1");
$settings = $stmt->fetch(PDO::FETCH_ASSOC);





?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <link rel="stylesheet" href="dashboard.css">
</head>
<body>
     <h1 class="heading">Milk Management system</h1>
     <main>
        <div class="pannel_left_side">
            <img src="mohan.png" alt="">
            <h1>Mohan</h1>
            <hr><br>

            <h2>Daily Record</h2>
            <hr><br>

            <h2><a href="../customer/create_customer.php">Add New Customer</a></h2>
            <hr><br>

            <h2><a href="../customer/show_customer_daily_report.php">Today Milk Detail</a></h2>
            <hr><br>

            <h2><a href="../customer/show_customer_details.php">Customer Details</a></h2>
            <hr>

            <h2><a href="../setting/milk_quality_parameters.php">setting</a></h2>
            <hr>
            
        </div>

        <div class="pannel_right_side">
            <div class="pannel_right_side_total_div">
                <div class="pannel_right_side__total_div_box">Average Milk Rate Per Liter: <br>
                <span><?php echo number_format($avg_milk_rate_today, 2); ?></span>
            </div>

            <div class="pannel_right_side__total_div_box">Total Milk Today: <br>
                <span id="total_milk_today"><?php echo $total_milk_today; ?></span> Liters
            </div>

            <div class="pannel_right_side__total_div_box">Total Milk Price Today: <br>
                <span id="total_milk_price_today"><?php echo $total_milk_price_today; ?></span>         
            </div>
        </div>

        <div class="milk_record">
            <h1>Add Milk Record</h1>
            <form action='insert_milk.php' method='post'>
               
                <label for="customer_name">Customer Name: </label>
                <input type="text" id="customer_name" list="customer_list"
                        placeholder="--Enter Customer Name--" required>
                <datalist id='customer_list'>
                    <?php foreach ($customers as $customer): ?> 
                        <option value='<?php echo $customer['customer_name']; ?>'>
                        <?php endforeach; ?>
                        </option>
                </datalist>
                <input type="hidden" name="customer_id" id="customer_id">

                <label for="milk_liter">Milk Liters: </label>
                <input type="number"  step="0.01" min="0" name="milk_liter" 
                        id="milk_liter" placeholder="--Enter Liters--" required>


                <label>SNF:</label>
                <input type="number" step="0.01" min="0" name="snf"
                       id="snf" placeholder="---Enter SNF---" required><br><br>

                <label>FAT:</label>
               <input type="number" step="0.01" min="0" name="fat"
                       id="fat" placeholder="---Enter Fat---" required>

                <label>Lacto:</label>
                <input type="number" step="0.01" min="0" name="lacto"
                        id="lacto" placeholder="---Enter Lacto---" required>

                <label for="milk_rate">Milk Rate Per Liter: </label>
                <input type="number" placeholder="00.00" 
                       step="0.01" min="0" name="milk_rate" id="milk_rate" readonly><br><br>

                <label for="staff_name">Staff Name: </label>
                <input type="text" id="staff_name" list="staff_list"
                        placeholder="---Select Staff----">
                <datalist id="staff_list">
                    <?php foreach ($staffs as $staff): ?>
                        <option value="<?php echo $staff['staff_name']; ?>">
                            <?php endforeach; ?>
                        </option>
                </datalist>
                <input type="hidden" name="staff_id" id="staff_id">



                <label for="collection_date">Collection Date: </label>
                <input type="date" name="collection_date" id="collection_date"
                       value="<?php echo date('Y-m-d'); ?>" required>

                 <input type="submit" name="submit" value="Submit">
                 </form>

        </div>
        
        <div class="top_ten_recent_customer">
            <h1 class="top_five_recent_customer_heading">Top Five Recent Customer</h1>
            <table border="1">
                <tr>
                     <th>Customer Name</th>
                    <th>Milk Liter</th>
                    <th>Rate</th>
                    <th>Collection Date</th>
                    <th>Total Price</th>
                    <th>Action</th>
                </tr>
                <?php if (!empty($result3)): ?>
                    <?php foreach ($result3 as $row): ?>
                        <tr>
                            <td><?php echo $row['customer_name']; ?></td>
                            <td><?php echo $row['milk_liter']; ?></td>
                            <td><?php echo $row['milk_rate']; ?></td>
                            <td><?php echo $row['collection_date']; ?></td>
                            <td><?php echo $row['milk_total_price']; ?></td>
                            <td>
                                <a class="delete" href="#">Delete</a> |
                                <a class="edit" href="#">Edit</a>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                        <?php else: ?>
                            <tr>
                                <td colspan="7">No Records Found</td>
                            </tr>
                            <?php endif; ?>
                        </table>
                    </div>
                    <h1>Mohan</h1>
                </div>
            </main>
            <script>
                    const customers = <?php echo json_encode($customers); ?>;
                    const staffs = <?php echo json_encode($staffs); ?>;

                    //SNF, FAT, LACTO rates from database
                    const snf_rate = <?php echo $settings['snf_rate']; ?>;
                    const fat_rate = <?php echo $settings['fat_rate']; ?>;
                    const lacto_rate = <?php echo $settings['lacto_rate']; ?>;


                    //AUTO calculation milk rate when SNF, FAT, LACTO change
                    function calculateRate() {
                        const snf = parseFloat(document.getElementById('snf').value) || 0;
                        const fat = parseFloat(document.getElementById('fat').value) || 0;
                        const lacto = parseFloat(document.getElementById('lacto').value) || 0;
                        const rate = (snf * snf_rate) + (fat * fat_rate) + (lacto * lacto_rate);
                        document.getElementById('milk_rate').value = rate.toFixed(2);
                    }

                    document.getElementById('snf').addEventListener('input', calculateRate);
                    document.getElementById('fat').addEventListener('input', calculateRate);
                    document.getElementById('lacto').addEventListener('input', calculateRate);

                    document.getElementById('customer_name').addEventListener('input', function() {
                        const match = customers.find(c => c.customer_name=== this.value);
                        document.getElementById('customer_id').value = match ? match.customer_id :'';
                    });
                    document.getElementById('staff_name').addEventListener('input', function() {
                        const match = staffs.find(s => s.staff_name === this.value);
                        document.getElementById('staff_id').value = match ? match.staff_id : '';
                    });
            </script>
        </body>
    </html>