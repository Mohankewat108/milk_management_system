<?php

require_once "../milk_dbconnection.php";

// Get customer_id from URL
$customer_id = $_GET['customer_id'] ?? 0;

//Filter by from to date 
$from_date = $_GET['from_date'] ?? '';
$to_date = $_GET['to_date'] ?? '';

// ✅ Get single customer
$stmt = $pdo->prepare("SELECT * FROM customer WHERE customer_id = ?");
$stmt->execute([$customer_id]);
$customer = $stmt->fetch(PDO::FETCH_ASSOC);

//Getting milk record by filtering date
if ($from_date && $to_date) {
    $stmt2= $pdo->prepare("
        SELECT * FROM daily_milk
        WHERE customer_id = ?
        AND DATE(collection_date) >= ?
        AND DATE(collection_date) <= ?
        ORDER BY collection_date DESC
    ");
    $stmt2->execute([$customer_id, $from_date, $to_date]);
} else {
    // ✅ Get milk records for that customer only
$stmt2 = $pdo->prepare("
    SELECT * FROM daily_milk 
    WHERE customer_id = ?
    ORDER BY collection_date DESC");
$stmt2->execute([$customer_id]);

}


$milk_records = $stmt2->fetchAll(PDO::FETCH_ASSOC);

/* $stmt = $pdo->prepare("SELECT 
                c.customer_id,
                c.customer_name,
                c.phone_number,
                c.gmail,
                c.city,
                c.village,
                c.ward_name,
                c.created_at,
                d.milk_id,
                d.customer_id,
                d.milk_liter,
                d.milk_rate,
                d.milk_total_price,
                d.collection_date,
                d.snf,
                d.fat,
                d.lacto
        FROM daily_milk d 
        JOIN customer c ON d.customer_id = c.customer_id
        ORDER BY  d.collection_date DESC");
    
    $stmt->execute();
    $customers = $stmt->fetch(PDO::FETCH_ASSOC) */

    // milk total_div_box
    $total_liter = array_sum(array_column($milk_records, 'milk_liter'));
    $total_price = array_sum(array_column($milk_records, 'milk_total_price'));;
    $avg_snf = count($milk_records) ? array_sum(array_column($milk_records, 'snf')) / count($milk_records): 0;
    $avg_fat = count($milk_records) ? array_sum(array_column($milk_records, 'fat')) / count($milk_records): 0;
    $avg_lacto = count($milk_records) ? array_sum(array_column($milk_records, 'lacto')) / count($milk_records): 0;

?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <link rel="stylesheet" href="customer.css">
</head>
<body>
    
<div class="customer-top-grid">

    <div class="customer-detail"><hr>
        
        <h1 style="text-align: center; color:brown;"><span><?php echo htmlspecialchars($customer['customer_name']); ?></span></h1><hr>
        <p>Phone Number: &nbsp;&nbsp;&nbsp;<span><?php echo htmlspecialchars($customer['phone_number']); ?></span></p><hr>
        <p>Email: &nbsp;&nbsp;&nbsp;<span><?php echo htmlspecialchars($customer['gmail']); ?></span></p><hr>
        <p>City: &nbsp;&nbsp;&nbsp;<span><?php echo htmlspecialchars($customer['city']); ?></span></p><hr>
        <p>Village: &nbsp;&nbsp;&nbsp;<span><?php echo htmlspecialchars($customer['village']); ?></span></p><hr>
        <p>Ward: &nbsp;&nbsp;&nbsp;<span><?php echo htmlspecialchars($customer['ward_name']); ?></span></p><hr>
        <p>Joined: &nbsp;&nbsp;&nbsp;<span><?php echo htmlspecialchars($customer['created_at']); ?></span></p> <hr>
        </div>
  
    <div class="total-div">
        
        <div class="total-div-box"><h2>Total collection time:</h2> <h1><?php echo count($milk_records); ?></h1></div>
        <div class="total-div-box"><h2>Total Milk:</h2><h1> <?php echo number_format($total_liter, 2); ?></h1></div>
        <div class="total-div-box"><h2>Total Amount:</h2><h1> <?php echo number_format($total_price,2); ?></h1></div>
        <div class="total-div-box"><h2>Average Rate/liter</h2></div>

        <div class="total-div-box"><h2>Average/SNF: </h2><h1><?php echo number_format($avg_snf, 2); ?></h1></div>
        <div class="total-div-box"><h2>Average/Fat: </h2><h1><?php echo number_format($avg_fat, 2); ?></h1></div>
        <div class="total-div-box"><h2>Average/Lacto:</h2><h1><?php echo number_format($avg_lacto, 2); ?></h1></div>
        <div class="total-div-box"><h2>Life Time Income</h2></div>
    </div>
</div><hr>

    <h1 id="filter">Filter By Date</h1>
    <form method="GET" action="#filter">
        <input type="hidden" name="customer_id"
        value="<?php echo $customer_id ?>">
    <div class="filter-date-div">
        <div class="filter-date">
            <label for="from_date">From Date</label><br><br>
            <input type="date" name="from_date" id="from_date"
                   value="<?php echo htmlspecialchars($from_date); ?>">
        </div>

        <div class="filter-date">
            <label for="to_date">To Date</label><br><br>
            <input type="date" name="to_date" id="to_date"
                   value="<?php echo htmlspecialchars($to_date); ?>">

            <button>Apply Filter</button>
            <a href="?customer_id=<?php echo htmlspecialchars($customer_id); ?>">Reset</a>
            
        </div>
    </div><br>
    </form>
    <?php if ($from_date && $to_date): ?>
        <p>Showing Filter Result From
            <strong><?php echo $from_date; ?></strong>
            To
            <strong><?php echo $to_date ?></strong>
        </p>
        <?php endif; ?>
    <table border="1">
        <tr>
            <th>Date</th>
            <th>Liter</th>
            <th>Rate</th>
            <th>Total</th>
            <th>SNF</th>
            <th>Fat</th>
            <th>Lacto</th>
            <th>Action</th>
        </tr>
        <?php foreach ($milk_records as $records): ?>
        <tr>
            <td><?php echo htmlspecialchars($records['collection_date']); ?></td>
            <td><?php echo htmlspecialchars($records['milk_liter']); ?></td>
            <td><?php echo htmlspecialchars($records['milk_rate']); ?></td>
            <td><?php echo htmlspecialchars($records['milk_total_price']); ?></td>
            <td><?php echo htmlspecialchars($records['snf']); ?></td>
            <td><?php echo htmlspecialchars($records['fat']); ?></td>
            <td><?php echo htmlspecialchars($records['lacto']); ?></td>
            <td>Delete | Edit</td> 
        </tr>
        <?php endforeach; ?>
    </table>

</body>
</html>