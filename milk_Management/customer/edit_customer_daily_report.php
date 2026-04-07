<?php
require_once "../milk_dbconnection.php";

if (!isset($_GET['milk_id'])) {
    die("Error: Milk ID not specified.");
}

$milk_id = $_GET['milk_id'];

// fetch existing milk record
$stmt = $pdo->prepare("
    SELECT
        d.milk_id,
        d.customer_id,
        d.milk_liter,
        d.milk_rate,
        d.snf,
        d.fat,
        d.lacto,
        d.collection_date,
        d.staff_id,
        c.customer_name,
        s.staff_name
    FROM daily_milk d
    JOIN customer c ON d.customer_id = c.customer_id
    JOIN staff s ON d.staff_id = s.staff_id
    WHERE d.milk_id = ?
");
$stmt->execute([$milk_id]);
$milk = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$milk) {
    die("Record not found.");
}

// fetch all customers
$customer_stmt = $pdo->query("
    SELECT customer_id, customer_name 
    FROM customer 
    WHERE is_deleted = 0
");
$customers = $customer_stmt->fetchAll(PDO::FETCH_ASSOC);

// fetch all staff
$staff_stmt = $pdo->query("
    SELECT staff_id, staff_name 
    FROM staff 
    WHERE is_deleted = 0
");
$staffs = $staff_stmt->fetchAll(PDO::FETCH_ASSOC);

// fetch SNF FAT LACTO rates
$settings_stmt = $pdo->query("SELECT * FROM milk_setting WHERE setting_id = 1");
$settings = $settings_stmt->fetch(PDO::FETCH_ASSOC);
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Milk Record</title>
    <link rel="stylesheet" href="../dashboard/dashboard.css">
</head>
<body>
    <h1>Edit Milk Record</h1>

    <form action="update_customer_daily_report.php" method="POST">

        <input type="hidden" name="milk_id" 
               value="<?php echo $milk['milk_id']; ?>">

        <label>Customer Name:</label>
        <input type="text" id="customer_name" autocomplete="off"
               value="<?php echo $milk['customer_name']; ?>" required><br><br>
        <div id="customer_suggestions" style="border:1px solid #ccc; display:none;
             background:white; max-height:120px; overflow-y:auto; width:300px;"></div>
        <input type="hidden" name="customer_id" id="customer_id"
               value="<?php echo $milk['customer_id']; ?>"><br><br>

        <label>Milk Liters:</label>
        <input type="number" step="0.01" min="0" name="milk_liter"
               value="<?php echo $milk['milk_liter']; ?>" required><br><br>

        <label>SNF:</label>
        <input type="number" step="0.01" min="0" name="snf" id="snf"
               value="<?php echo $milk['snf']; ?>" required><br><br>

        <label>FAT:</label>
        <input type="number" step="0.01" min="0" name="fat" id="fat"
               value="<?php echo $milk['fat']; ?>" required><br><br>

        <label>LACTO:</label>
        <input type="number" step="0.01" min="0" name="lacto" id="lacto"
               value="<?php echo $milk['lacto']; ?>" required><br><br>

        <label>Milk Rate Per Liter (Auto):</label>
        <input type="number" step="0.01" min="0" name="milk_rate" id="milk_rate"
               value="<?php echo $milk['milk_rate']; ?>" readonly><br><br>

        <label>Collection Date:</label>
        <input type="date" name="collection_date"
               value="<?php echo $milk['collection_date']; ?>" required><br><br>

        <label>Staff Name:</label>
        <input type="text" id="staff_name" autocomplete="off"
               value="<?php echo $milk['staff_name']; ?>" required><br><br>
        <div id="staff_suggestions" style="border:1px solid #ccc; display:none;
             background:white; max-height:120px; overflow-y:auto; width:300px;"></div>
        <input type="hidden" name="staff_id" id="staff_id"
               value="<?php echo $milk['staff_id']; ?>"><br><br>

        <input type="submit" name="submit" value="Update"
               style="background-color:green; color:white; padding:10px 20px;
                      border:none; cursor:pointer; border-radius:5px;">

        <a href="show_customer_daily_report.php"
           style="margin-left:10px; color:red;">Cancel</a>

    </form>

    <script>
        const customers = <?php echo json_encode($customers); ?>;
        const staffs    = <?php echo json_encode($staffs); ?>;

        const snf_rate   = <?php echo $settings['snf_rate']; ?>;
        const fat_rate   = <?php echo $settings['fat_rate']; ?>;
        const lacto_rate = <?php echo $settings['lacto_rate']; ?>;

        // auto calculate milk rate
        function calculateRate() {
            const snf   = parseFloat(document.getElementById('snf').value)   || 0;
            const fat   = parseFloat(document.getElementById('fat').value)   || 0;
            const lacto = parseFloat(document.getElementById('lacto').value) || 0;
            const rate  = (snf * snf_rate) + (fat * fat_rate) + (lacto * lacto_rate);
            document.getElementById('milk_rate').value = rate.toFixed(2);
        }

        document.getElementById('snf').addEventListener('input', calculateRate);
        document.getElementById('fat').addEventListener('input', calculateRate);
        document.getElementById('lacto').addEventListener('input', calculateRate);

        // customer search
        document.getElementById('customer_name').addEventListener('input', function() {
            const typed = this.value.toLowerCase();
            const box   = document.getElementById('customer_suggestions');
            box.innerHTML = '';
            document.getElementById('customer_id').value = '';

            if (typed === '') { box.style.display = 'none'; return; }

            const filtered = customers
                .filter(c => c.customer_name.toLowerCase().includes(typed))
                .slice(0, 3);

            if (filtered.length === 0) { box.style.display = 'none'; return; }

            filtered.forEach(c => {
                const div = document.createElement('div');
                div.textContent = c.customer_name;
                div.style.cssText = 'padding:8px; cursor:pointer;';
                div.addEventListener('mouseover', function() { this.style.backgroundColor = '#f0f0f0'; });
                div.addEventListener('mouseout',  function() { this.style.backgroundColor = 'white'; });
                div.addEventListener('click', function() {
                    document.getElementById('customer_name').value = c.customer_name;
                    document.getElementById('customer_id').value   = c.customer_id;
                    box.style.display = 'none';
                });
                box.appendChild(div);
            });
            box.style.display = 'block';
        });

        // staff search
        document.getElementById('staff_name').addEventListener('input', function() {
            const typed = this.value.toLowerCase();
            const box   = document.getElementById('staff_suggestions');
            box.innerHTML = '';
            document.getElementById('staff_id').value = '';

            if (typed === '') { box.style.display = 'none'; return; }

            const filtered = staffs
                .filter(s => s.staff_name.toLowerCase().includes(typed))
                .slice(0, 3);

            if (filtered.length === 0) { box.style.display = 'none'; return; }

            filtered.forEach(s => {
                const div = document.createElement('div');
                div.textContent = s.staff_name;
                div.style.cssText = 'padding:8px; cursor:pointer;';
                div.addEventListener('mouseover', function() { this.style.backgroundColor = '#f0f0f0'; });
                div.addEventListener('mouseout',  function() { this.style.backgroundColor = 'white'; });
                div.addEventListener('click', function() {
                    document.getElementById('staff_name').value = s.staff_name;
                    document.getElementById('staff_id').value   = s.staff_id;
                    box.style.display = 'none';
                });
                box.appendChild(div);
            });
            box.style.display = 'block';
        });

        // hide suggestions when clicking outside
        document.addEventListener('click', function(e) {
            if (e.target.id !== 'customer_name') {
                document.getElementById('customer_suggestions').style.display = 'none';
            }
            if (e.target.id !== 'staff_name') {
                document.getElementById('staff_suggestions').style.display = 'none';
            }
        });
    </script>

</body>
</html>