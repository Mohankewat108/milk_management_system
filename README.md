Milk Management System
A full-stack web application for managing daily milk collection, customer records, and pricing calculations efficiently.

About The Project

The Milk Management System is designed for dairy businesses to streamline daily operations. It allows staff to record milk collection, track quality parameters, manage customers, and automatically calculate pricing.
This system improves accuracy, reduces manual work, and provides quick insights into daily milk transactions.

Key Features

📊 Dashboard

View total milk collected, average rate per liter, and total earnings for the day.
➕ Add Milk Record

Record daily milk entries with:
Customer name
Milk quantity (liters)
SNF, FAT, Lacto values
Rate per liter
Staff name
Collection date

📅 Today's Milk Details
View all records for the current day
Search functionality
Edit & delete options

👥 Customer Management
Add new customers
Store contact details (phone, email, address)
📋 Customer List
Easily search and browse all customers.
⚙️ Milk Quality Settings
Admin can update:
SNF rate
FAT rate
Lacto rate
💰 Automatic Price Calculation
Total price is calculated automatically using:

Tech Stack
Layer                Technology
Frontend             HTML, CSS, JavaScript
Backend              PHP
Database             MySQL
Tools                phpMyAdmin
Server               XAMpp/ WAMP


Database Design
The system uses 4 main tables:
customer → Stores customer details
daily_milk → Stores milk collection records
staff → Stores staff information
milk_setting → Stores SNF, FAT, Lacto rates

💡 Note:
milk_total_price is a generated column calculated automatically in MySQL.

🚀 Getting Started
✅ Requirements
XAMPP / WAMP
PHP 8.0+
MySQL

⚡ Installation Steps
1. Clone the repository (https://github.com/mohankewat108/milk_management_system.git).
2. Move project ot server folder
.  XAMPP ---> htdocs
3. Import DAtabase
.  Open: http://localhost/phpmyadmin
.  Import milk.sql
4. Configure Database
.  Edit milk_dbconnetion.php
.  #Demo
       $host = "localhost";
       $user = "root";
       $password = "root";
       $database = "milk";
5. Run Project
.  http://localhost/milk_management/


🔮 Future Improvements
🔐 User authentication (Admin/Staff login)
📱 Mobile responsive UI
📊 Advanced reports & analytics
📤 Export data (PDF/Excel)
☁️ Cloud deployment


👨‍💻 Author
Mohan Kewat
🎓 Computer Science Student
🏫 Niels Brock Copenhagen Business College, Denmark
📧 mohankewat108@gmail.com

📄 License
This project is open-source and available for educational purposes.

