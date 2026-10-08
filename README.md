# Enterprise Asset & Inventory ERP Dashboard

A simple and powerful dashboard built with Flask, SQLite, and Pandas. It helps manage inventory across multiple locations, track file uploads, and view real-time data reports.

🌐 **Live Demo:** [https://tabsons-erp.onrender.com](https://tabsons-erp.onrender.com)

---

## 🌟 Key Features

* **History Storage:** Saves every uploaded file with a batch ID and date, so old data is never lost or deleted.
* **Smart File Reader:** Automatically reads CSV and Excel files even if column names are slightly different.
* **Live Analytics:** Automatically calculates total value, total stock, location distribution, and category reports.
* **Low Stock Alerts:** Instantly highlights items that are running low on stock.
* **Secure Login:** User login system with activity logs for safety.

---

## 🏗️ Tech Stack

* **Backend:** Python, Flask, Flask-Login, Flask-SQLAlchemy
* **Data Processing:** Pandas
* **Database:** SQLite
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js
* **Deployment:** Hosted live on Render with GitHub integration

---

## 🛠️ Database Structure

1. **upload_batches table:** Stores file name, batch ID, and upload date.
2. **items table:** Stores product barcode, name, category, location, stock, and price linked with batch ID.

---

## 🚀 How to Run Locally

```bash
# 1. Clone repository
git clone [https://github.com/Laxmi-sahani8/tabsons-erp.git](https://github.com/Laxmi-sahani8/tabsons-erp.git)
cd tabsons-erp

# 2. Setup virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install packages
pip install -r requirements.txt

# 4. Start app
python app.py
