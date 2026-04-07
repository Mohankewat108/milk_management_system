<?php

require_once "../milk/milk_dbconnection.php";

if (isset($_POST['submit'])) {
    $stmt= $pdo->prepare(" 
    UPDATE milk_setting 
    SET snf_rate = ?, fat_rate = ?, lacto_rate = ?
        WHERE setting_id = 1");

    $stmt->execute([
        $_POST['snf_rate'],
        $_POST['fat_rate'],
        $_POST['lacto_rate'],

    ]);


}

$stmt = $pdo->query("SELECT * FROM milk_setting WHERE setting_id = 1");
$settings = $stmt->fetch(PDO::FETCH_ASSOC);

?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>milk_quality_parameters</title>
    <link rel="stylesheet" href="../dashboard/dashboard.css">
</head>
<body>
    <Table border="1">
        <tr>
            <th>SNF Rate</th>
            <th>FAT Rate</th>
            <th>Lacto Rate</th>
            <th>Last Time Updated</th>

        </tr>

        <tr>
            <td><?php echo $settings['snf_rate']; ?></td>
            <td><?php echo $settings['fat_rate']; ?></td>
            <td><?php echo $settings['lacto_rate']; ?></td>
            <td><?php echo $settings['update_at']; ?></td>
        </tr>
    </Table>

    <form method="POST">
        <label for="snf_rate">SNF Rate:</label>
        <input type="number" step="0.01" min="0" name="snf_rate"
               value="<?php echo $settings['snf_rate']; ?>"><br><br>

        <label for="far_rate">Fat Rate: </label>
        <input type="number" step="0.01" min="0" name="fat_rate"
               value="<?php echo $settings['fat_rate']; ?>"><br><br>


        <label for="lacto_rate">Lacto Rate: </label>
        <input type="number" step="0.01" min="0" name="lacto_rate"
               value="<?php echo $settings['lacto_rate']; ?>"><br><br>


        <input type="submit" name="submit" value="Update Rates"> 
    </form>  
</body>
</html>