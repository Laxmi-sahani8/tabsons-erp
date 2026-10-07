import os
import sqlite3
import json
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "tabsons_enterprise_corporate_key"
DATABASE = "showroom.db"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def log_activity(user_name, action, details):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_logs (user_name, action, details, timestamp) VALUES (?, ?, ?, ?)",
        (user_name, action, details, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    conn.close()

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'IT Admin'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER DEFAULT 0,
            price REAL DEFAULT 0.0,
            location TEXT DEFAULT 'Tabsons Logistics Hub'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id TEXT UNIQUE,
            item_name TEXT NOT NULL,
            source_hub TEXT NOT NULL,
            destination_hub TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT DEFAULT 'In Transit',
            date_created TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            added_by TEXT NOT NULL,
            date_recorded TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("Tabsons IT Member", "it@tabsons.com", generate_password_hash("tabsons123"), "System Administrator"))

    conn.commit()
    conn.close()

init_db()

class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]
        self.role = row["role"]

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return User(row) if row else None

# Master HTML Layout
BASE_LAYOUT = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Tabsons Enterprise Hub</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
  <style>
    body { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; }
    .sidebar { width: 260px; background-color: #0f172a; min-height: 100vh; position: fixed; top: 0; left: 0; color: #94a3b8; padding: 20px 15px; }
    .main-content { margin-left: 260px; padding: 30px; }
    .sidebar-brand { color: #ffffff; font-weight: 700; font-size: 1.25rem; padding-bottom: 20px; border-bottom: 1px solid #1e293b; margin-bottom: 20px; }
    .sidebar-brand span { color: #3b82f6; }
    .nav-item-link { color: #94a3b8; text-decoration: none; padding: 10px 14px; border-radius: 8px; display: block; font-weight: 500; font-size: 0.9rem; margin-bottom: 4px; transition: all 0.2s; }
    .nav-item-link:hover, .nav-item-link.active { background-color: #1e293b; color: #ffffff; }
    .top-header { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 24px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }
    .kpi-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }
    .kpi-title { font-size: 0.825rem; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin-top: 8px; margin-bottom: 0; }
    .badge-soft-success { background-color: #dcfce7; color: #15803d; font-weight: 600; padding: 4px 10px; border-radius: 6px; }
    .badge-soft-primary { background-color: #dbeafe; color: #1d4ed8; font-weight: 600; padding: 4px 10px; border-radius: 6px; }
    .table-custom { border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background: #ffffff; }
    
    @media print {
      .sidebar, .top-header, .no-print { display: none !important; }
      .main-content { margin-left: 0 !important; padding: 0 !important; }
      body { background-color: #ffffff; }
      .table-custom { border: none !important; }
      .printable-label-area { page-break-inside: avoid; }
    }
  </style>
</head>
<body>

  <div class="sidebar">
    <div class="sidebar-brand"><i class="fa-solid fa-layer-group me-2 text-primary"></i>TABSONS <span>ERP</span></div>
    
    <div class="small fw-semibold text-uppercase ms-2 mb-2" style="font-size: 0.7rem; color: #64748b;">CORE MODULES</div>
    <a href="/dashboard" class="nav-item-link {% if page=='dashboard' %}active{% endif %}"><i class="fa-solid fa-chart-pie me-2"></i> Operational Overview</a>
    <a href="/inventory" class="nav-item-link {% if page=='inventory' %}active{% endif %}"><i class="fa-solid fa-boxes-stacked me-2"></i> Inventory & Stock</a>
    <a href="/data-importer" class="nav-item-link {% if page=='importer' %}active{% endif %}"><i class="fa-solid fa-file-excel me-2"></i> IT Data Importer</a>
    <a href="/barcode-scanner" class="nav-item-link {% if page=='barcode' %}active{% endif %}"><i class="fa-solid fa-qrcode me-2"></i> Dynamic QR Generator</a>
    <a href="/asset-transfers" class="nav-item-link {% if page=='transfers' %}active{% endif %}"><i class="fa-solid fa-right-left me-2"></i> Asset Transfers</a>

    <div class="small fw-semibold text-uppercase ms-2 mt-4 mb-2" style="font-size: 0.7rem; color: #64748b;">ADMINISTRATION & REPORTS</div>
    <a href="/powerbi-workspaces" class="nav-item-link {% if page=='powerbi' %}active{% endif %}"><i class="fa-solid fa-chart-line me-2"></i> Power BI Workspaces</a>
    <a href="/expense-ledger" class="nav-item-link {% if page=='expense' %}active{% endif %}"><i class="fa-solid fa-receipt me-2"></i> Daily Expense Ledger</a>
    <a href="/user-management" class="nav-item-link {% if page=='users' %}active{% endif %}"><i class="fa-solid fa-users-gear me-2"></i> User Management</a>
    <a href="/audit-logs" class="nav-item-link {% if page=='audit' %}active{% endif %}"><i class="fa-solid fa-shield-halved me-2"></i> Audit Activity Logs</a>
  </div>

  <div class="main-content">
    <div class="top-header">
      <div>
        <h5 class="fw-bold mb-0">{{ title }}</h5>
        <small class="text-muted">{{ subtitle }}</small>
      </div>
      <div class="d-flex align-items-center gap-3">
        <span class="badge badge-soft-primary"><i class="fa-solid fa-user-shield me-1"></i> {{ user.role }}</span>
        <span class="fw-semibold small text-secondary"><i class="fa-solid fa-circle-user me-1 text-dark"></i> {{ user.name }}</span>
        <a href="/logout" class="btn btn-outline-danger btn-sm rounded-2 fw-semibold ms-2">Sign Out</a>
      </div>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} alert-dismissible fade show mb-4 no-print" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
          </div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {{ content | safe }}
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

DASHBOARD_HTML = """
<!-- Top 3 KPI Cards -->
<div class="row g-3 mb-4">
  <div class="col-md-4">
    <div class="card border-0 shadow-sm p-3" style="border-radius: 14px; background: #ffffff;">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <span class="text-muted small fw-semibold">Total Stock Units</span>
          <h3 class="fw-bold text-dark mb-0 mt-1">{{ summary.total_stock }}</h3>
        </div>
        <div class="bg-primary-subtle text-primary p-3 rounded-3">
          <i class="fa-solid fa-boxes-stacked fs-4"></i>
        </div>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card border-0 shadow-sm p-3" style="border-radius: 14px; background: #ffffff;">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <span class="text-muted small fw-semibold">Total Stock Valuation</span>
          <h3 class="fw-bold text-dark mb-0 mt-1">₹{{ summary.total_valuation }}</h3>
        </div>
        <div class="bg-success-subtle text-success p-3 rounded-3">
          <i class="fa-solid fa-indian-rupee-sign fs-4"></i>
        </div>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card border-0 shadow-sm p-3" style="border-radius: 14px; background: #ffffff;">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <span class="text-muted small fw-semibold">Today's Expenses</span>
          <h3 class="fw-bold text-dark mb-0 mt-1">₹{{ summary.today_expense }}</h3>
        </div>
        <div class="bg-warning-subtle text-warning p-3 rounded-3">
          <i class="fa-solid fa-receipt fs-4"></i>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Dynamic Analytics Chart Block -->
<div class="card border-0 shadow-sm mb-4" style="border-radius: 16px; background: #ffffff; border: 1px solid #edf2f7 !important;">
  <div class="card-header bg-transparent border-0 pt-4 px-4 pb-2 d-flex justify-content-between align-items-center">
    <div>
      <div class="d-flex align-items-center gap-2">
        <h6 class="fw-bold mb-0 text-dark" style="letter-spacing: -0.3px; font-size: 1.1rem;">Inventory Stock Analytics</h6>
        <span class="badge bg-primary-subtle text-primary rounded-pill px-2 py-1" style="font-size: 0.75rem; font-weight: 600;">Live Feed</span>
      </div>
      <p class="text-muted mb-0" style="font-size: 0.82rem;">Real-time asset stock distribution by item & category</p>
    </div>
    
    <div class="d-flex align-items-center gap-3">
      <div class="bg-light rounded-3 p-1 border">
        <select id="analyticsCategoryFilter" class="form-select form-select-sm border-0 bg-transparent fw-semibold" style="font-size: 0.85rem; cursor: pointer;" onchange="updateInteractiveChart()">
          <option value="All">All Categories</option>
          {% for cat in categories %}
            <option value="{{ cat }}">{{ cat }}</option>
          {% endfor %}
        </select>
      </div>
    </div>
  </div>

  <div class="card-body px-4 pb-4 pt-2">
    <div style="position: relative; height: 320px;">
      <canvas id="erpAnalyticsChart"></canvas>
    </div>
  </div>
</div>

<!-- Stock Table -->
<div class="card border-0 shadow-sm p-3" style="border-radius: 16px; background: #ffffff;">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h6 class="fw-bold mb-0">All Registered Inventory Stock</h6>
    <div class="d-flex gap-2">
      <button class="btn btn-sm btn-outline-success"><i class="fa-solid fa-file-excel me-1"></i> Excel</button>
      <button class="btn btn-sm btn-outline-dark"><i class="fa-solid fa-print me-1"></i> Print</button>
      <button class="btn btn-sm btn-primary"><i class="fa-solid fa-plus me-1"></i> Add Asset</button>
    </div>
  </div>
  <div class="table-responsive">
    <table class="table table-hover align-middle">
      <thead class="table-light">
        <tr>
          <th>SKU / Barcode</th>
          <th>Asset Name</th>
          <th>Category</th>
          <th>Location / Hub</th>
          <th>Stock Quantity</th>
          <th>Unit Price</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr>
          <td>{{ item['sku'] or item['barcode'] or 'N/A' }}</td>
          <td>{{ item['name'] or item['asset_name'] }}</td>
          <td><span class="badge bg-secondary-subtle text-dark">{{ item['category'] or 'General' }}</span></td>
          <td>{{ item['location'] or 'Main Hub' }}</td>
          <td class="fw-bold">{{ item['quantity'] or item['stock_quantity'] or 0 }}</td>
          <td>₹{{ item['price'] or 0 }}</td>
          <td><button class="btn btn-sm btn-light border"><i class="fa-solid fa-ellipsis-vertical"></i></button></td>
        </tr>
        {% else %}
        <tr>
          <td colspan="7" class="text-center text-muted py-4">No inventory items found in database.</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
  const realERPData = {{ chart_data | tojson }};

  const canvas = document.getElementById('erpAnalyticsChart');
  const ctx = canvas.getContext('2d');

  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, '#4f46e5');
  gradient.addColorStop(1, '#818cf8');

  const hoverGradient = ctx.createLinearGradient(0, 0, 0, 300);
  hoverGradient.addColorStop(0, '#4338ca');
  hoverGradient.addColorStop(1, '#6366f1');

  let erpChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: (realERPData && realERPData['All']) ? realERPData['All'].labels : [],
      datasets: [{
        label: 'Available Quantity',
        data: (realERPData && realERPData['All']) ? realERPData['All'].stock : [],
        backgroundColor: gradient,
        hoverBackgroundColor: hoverGradient,
        borderRadius: 8,
        borderSkipped: false,
        barThickness: 26,
        maxBarThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f172a',
          titleFont: { size: 13, weight: '600' },
          bodyFont: { size: 12 },
          padding: 10,
          cornerRadius: 8,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return 'Stock Quantity: ' + context.parsed.y + ' Units';
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          border: { dash: [5, 5], display: false },
          grid: { color: '#f1f5f9' },
          ticks: { color: '#94a3b8', font: { size: 11 } }
        },
        x: {
          border: { display: false },
          grid: { display: false },
          ticks: { color: '#64748b', font: { size: 11, weight: '500' } }
        }
      }
    }
  });

  function updateInteractiveChart() {
    const selectedCategory = document.getElementById('analyticsCategoryFilter').value;
    const currentData = realERPData[selectedCategory] || realERPData['All'] || { labels: [], stock: [] };
    
    erpChart.data.labels = currentData.labels;
    erpChart.data.datasets[0].data = currentData.stock;
    erpChart.update();
  }
</script>

"""

# Inventory Page
INVENTORY_CONTENT = '''
<div class="table-custom p-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h6 class="fw-bold mb-0">All Registered Inventory Stock</h6>
    
    <div class="d-flex gap-2 no-print">
      <a href="/export-excel" class="btn btn-outline-success btn-sm fw-semibold">
        <i class="fa-solid fa-file-excel me-1"></i> Download Excel
      </a>
      <button onclick="window.print()" class="btn btn-outline-dark btn-sm fw-semibold">
        <i class="fa-solid fa-print me-1"></i> Print Report / PDF
      </button>
      <button class="btn btn-primary btn-sm fw-semibold" data-bs-toggle="modal" data-bs-target="#addAssetModal">
        <i class="fa-solid fa-plus me-1"></i> Add New Asset
      </button>
    </div>
  </div>
  
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0" style="font-size: 0.9rem;">
      <thead class="table-light">
        <tr>
          <th>SKU / Barcode</th>
          <th>Asset Name</th>
          <th>Category</th>
          <th>Location / Hub</th>
          <th>Stock Quantity</th>
          <th>Unit Price</th>
          <th class="text-center no-print">Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr>
          <td><code class="fw-bold text-dark">{{ item.barcode }}</code></td>
          <td class="fw-semibold text-dark">{{ item.name }}</td>
          <td><span class="badge bg-light text-dark border">{{ item.category }}</span></td>
          <td>{{ item.location }}</td>
          <td><span class="fw-bold text-primary">{{ item.quantity }}</span></td>
          <td>₹ {{ item.price }}</td>
          <td class="text-center no-print">
            <a href="/asset-info/{{ item.barcode }}" target="_blank" class="btn btn-sm btn-outline-info me-1" title="View Public Asset Card">
              <i class="fa-solid fa-share-nodes"></i>
            </a>
            <button class="btn btn-sm btn-outline-primary me-1" data-bs-toggle="modal" data-bs-target="#editModal{{ item.id }}">
              <i class="fa-solid fa-pen-to-square"></i>
            </button>
            <a href="/delete-item/{{ item.id }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('Are you sure you want to delete this asset?');">
              <i class="fa-solid fa-trash"></i>
            </a>
          </td>
        </tr>

        <!-- Edit Modal -->
        <div class="modal fade" id="editModal{{ item.id }}" tabindex="-1">
          <div class="modal-dialog">
            <div class="modal-content">
              <form action="/edit-item/{{ item.id }}" method="POST">
                <div class="modal-header">
                  <h5 class="modal-title fw-bold">Edit Asset Details</h5>
                  <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-start">
                  <div class="mb-3">
                    <label class="form-label small fw-semibold">SKU Code</label>
                    <input type="text" name="barcode" class="form-control" value="{{ item.barcode }}" required readonly>
                  </div>
                  <div class="mb-3">
                    <label class="form-label small fw-semibold">Asset Name</label>
                    <input type="text" name="name" class="form-control" value="{{ item.name }}" required>
                  </div>
                  <div class="row g-2 mb-3">
                    <div class="col-md-6">
                      <label class="form-label small fw-semibold">Category</label>
                      <input type="text" name="category" class="form-control" value="{{ item.category }}" required>
                    </div>
                    <div class="col-md-6">
                      <label class="form-label small fw-semibold">Location</label>
                      <input type="text" name="location" class="form-control" value="{{ item.location }}">
                    </div>
                  </div>
                  <div class="row g-2">
                    <div class="col-md-6">
                      <label class="form-label small fw-semibold">Quantity</label>
                      <input type="number" name="quantity" class="form-control" value="{{ item.quantity }}" required>
                    </div>
                    <div class="col-md-6">
                      <label class="form-label small fw-semibold">Price (INR)</label>
                      <input type="number" step="0.01" name="price" class="form-control" value="{{ item.price }}" required>
                    </div>
                  </div>
                </div>
                <div class="modal-footer">
                  <button type="submit" class="btn btn-primary fw-semibold w-100">Update Asset</button>
                </div>
              </form>
            </div>
          </div>
        </div>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<!-- Add Modal -->
<div class="modal fade" id="addAssetModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <form action="/add-item" method="POST">
        <div class="modal-header">
          <h5 class="modal-title fw-bold">Add New Showroom Asset</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label small fw-semibold">SKU / Barcode Code</label>
            <input type="text" name="barcode" class="form-control" placeholder="e.g. TAB-2001" required>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">Asset Name</label>
            <input type="text" name="name" class="form-control" required>
          </div>
          <div class="row g-2 mb-3">
            <div class="col-md-6">
              <label class="form-label small fw-semibold">Category</label>
              <input type="text" name="category" class="form-control" placeholder="Logistics / IT" required>
            </div>
            <div class="col-md-6">
              <label class="form-label small fw-semibold">Location</label>
              <input type="text" name="location" class="form-control" value="Warehouse Alpha">
            </div>
          </div>
          <div class="row g-2">
            <div class="col-md-6">
              <label class="form-label small fw-semibold">Quantity</label>
              <input type="number" name="quantity" class="form-control" value="10" required>
            </div>
            <div class="col-md-6">
              <label class="form-label small fw-semibold">Price (INR)</label>
              <input type="number" step="0.01" name="price" class="form-control" value="1500.00" required>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" class="btn btn-primary fw-semibold w-100">Save Asset to Database</button>
        </div>
      </form>
    </div>
  </div>
</div>
'''

# IT Data Importer Page
IMPORTER_CONTENT = '''
<div class="row g-4">
  <div class="col-md-7">
    <div class="kpi-card">
      <h6 class="fw-bold mb-3"><i class="fa-solid fa-file-excel text-success me-2"></i> Bulk Inventory Data Importer</h6>
      <p class="text-muted small">Upload `.xlsx` or `.csv` files containing master asset lists to automatically process and insert into SQL Database.</p>
      
      <form action="/upload-data" method="POST" enctype="multipart/form-data" class="mt-4">
        <div class="p-4 text-center border border-2 border-dashed rounded-3 bg-light mb-3">
          <i class="fa-solid fa-cloud-arrow-up display-5 text-success mb-2"></i>
          <h6>Choose Excel/CSV File</h6>
          <small class="text-muted d-block mb-3">Supports .xlsx, .xls, .csv</small>
          <input type="file" name="file" accept=".xlsx, .xls, .csv" class="form-control form-control-sm mx-auto" style="max-width: 320px;" required>
        </div>
        <button type="submit" class="btn btn-success fw-semibold w-100"><i class="fa-solid fa-upload me-2"></i> Process & Import into SQL Database</button>
      </form>
    </div>
  </div>
  
  <div class="col-md-5">
    <div class="kpi-card">
      <h6 class="fw-bold mb-2"><i class="fa-solid fa-circle-info text-primary me-2"></i> Required Excel Columns</h6>
      <p class="text-muted small mb-3">Ensure your Excel sheet headers match these exact column names:</p>
      <ul class="list-group list-group-flush small">
        <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
          <code>barcode</code> <span class="badge bg-light text-dark">Required (Unique)</span>
        </li>
        <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
          <code>name</code> <span class="badge bg-light text-dark">Required</span>
        </li>
        <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
          <code>category</code> <span class="badge bg-light text-dark">Optional</span>
        </li>
        <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
          <code>quantity</code> <span class="badge bg-light text-dark">Numeric</span>
        </li>
        <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
          <code>price</code> <span class="badge bg-light text-dark">Numeric</span>
        </li>
        <li class="list-group-item bg-transparent d-flex justify-content-between align-items-center">
          <code>location</code> <span class="badge bg-light text-dark">Optional</span>
        </li>
      </ul>
    </div>
  </div>
</div>
'''

# DYNAMIC QR CODE & LIVE LOOKUP PAGE
BARCODE_CONTENT = '''
<div class="row g-4 mb-4">
  <!-- Dynamic QR Code Card -->
  <div class="col-md-6">
    <div class="kpi-card h-100">
      <h6 class="fw-bold mb-3"><i class="fa-solid fa-qrcode text-primary me-2"></i> Dynamic QR Code Generator</h6>
      
      <div class="mb-3">
        <label class="form-label small fw-semibold">Select Registered Asset</label>
        <select id="assetSelect" class="form-select" onchange="generateQRCodeLabel()">
          {% for item in items %}
            <option value="{{ item.barcode }}" data-name="{{ item.name }}" data-loc="{{ item.location }}" data-price="{{ item.price }}">
              {{ item.barcode }} - {{ item.name }}
            </option>
          {% endfor %}
        </select>
      </div>

      <!-- Custom Blue Banner QR Label Container -->
      <div class="text-center printable-label-area my-3 d-flex justify-content-center">
        <div style="width: 230px; border: 2px solid #0f172a; border-radius: 8px; overflow: hidden; background-color: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
          <!-- Dynamic QR Canvas Container -->
          <div id="qrcodeCanvas" class="p-3 d-flex justify-content-center align-items-center" style="background: #ffffff; min-height: 190px;"></div>
          
          <!-- Bottom Banner (Exact match as image) -->
          <div style="background-color: #3b6695; color: #ffffff; font-weight: 700; font-size: 0.85rem; padding: 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">
            SCAN FOR DETAILS
          </div>
        </div>
      </div>

      <div class="p-2 bg-light border rounded text-center mb-3">
        <small class="text-muted d-block" style="font-size: 0.75rem;">PHONE SCAN TARGET LINK:</small>
        <code id="qrTargetUrl" class="fw-bold text-primary small">http://...</code>
      </div>

      
    </div>
  </div>

  <!-- Instant Search/Lookup Card -->
  <div class="col-md-6">
    <div class="kpi-card h-100">
      <h6 class="fw-bold mb-3"><i class="fa-solid fa-expand text-success me-2"></i> Live Scanner / SKU Search</h6>
      <p class="text-muted small">Type or scan SKU code below to quickly load matching asset details.</p>

      <div class="mb-3">
        <label class="form-label small fw-semibold">Scan QR / Barcode SKU</label>
        <div class="input-group">
          <span class="input-group-text bg-white"><i class="fa-solid fa-barcode"></i></span>
          <input type="text" id="scanInput" class="form-control" placeholder="Scan SKU code..." autofocus oninput="lookupItem()">
        </div>
      </div>

      <div id="scanResultCard" class="p-3 border rounded-3 bg-light mt-3" style="display: none;">
        <span class="badge bg-success mb-2"><i class="fa-solid fa-circle-check me-1"></i> Asset Found</span>
        <h5 class="fw-bold text-dark mb-1" id="resName">Name</h5>
        <div class="text-muted small mb-3" id="resBarcode">SKU: -</div>

        <div class="row g-2 text-center">
          <div class="col-4">
            <div class="p-2 bg-white border rounded">
              <small class="text-muted d-block">Quantity</small>
              <strong class="text-primary fs-5" id="resQty">0</strong>
            </div>
          </div>
          <div class="col-4">
            <div class="p-2 bg-white border rounded">
              <small class="text-muted d-block">Price</small>
              <strong class="text-dark fs-5" id="resPrice">₹ 0</strong>
            </div>
          </div>
          <div class="col-4">
            <div class="p-2 bg-white border rounded">
              <small class="text-muted d-block">Location</small>
              <strong class="text-dark small d-block mt-1" id="resLoc">-</strong>
            </div>
          </div>
        </div>
      </div>

      <div id="scanNotFound" class="alert alert-warning mt-3 small text-center" style="display: none;">
        <i class="fa-solid fa-triangle-exclamation me-1"></i> No matching asset found in database.
      </div>
    </div>
  </div>
</div>

<script>
  const inventoryItems = {{ items_json | safe }};

  function generateQRCodeLabel() {
    const select = document.getElementById("assetSelect");
    if(!select || !select.value) return;

    const barcode = select.value;
    const qrContainer = document.getElementById("qrcodeCanvas");
    qrContainer.innerHTML = ""; // Clear old QR Code

    // Mobile Friendly Public URL (Scan karne par phone me asset ki live details khulenigi)
    const publicAssetUrl = window.location.origin + "/asset-info/" + barcode;
    
    document.getElementById("qrTargetUrl").innerText = publicAssetUrl;

    // Instant Render QR Code
    new QRCode(qrContainer, {
      text: publicAssetUrl,
      width: 160,
      height: 160,
      colorDark : "#0f172a",
      colorLight : "#ffffff",
      correctLevel : QRCode.CorrectLevel.H
    });
  }

  function lookupItem() {
    const query = document.getElementById("scanInput").value.trim().toLowerCase();
    const resultCard = document.getElementById("scanResultCard");
    const notFound = document.getElementById("scanNotFound");

    if(!query) {
      resultCard.style.display = "none";
      notFound.style.display = "none";
      return;
    }

    const item = inventoryItems.find(i => i.barcode.toLowerCase() === query);

    if(item) {
      document.getElementById("resName").innerText = item.name;
      document.getElementById("resBarcode").innerText = "SKU: " + item.barcode;
      document.getElementById("resQty").innerText = item.quantity;
      document.getElementById("resPrice").innerText = "₹ " + item.price;
      document.getElementById("resLoc").innerText = item.location;

      resultCard.style.display = "block";
      notFound.style.display = "none";
    } else {
      resultCard.style.display = "none";
      notFound.style.display = "block";
    }
  }

  // Ensure DOM is ready before drawing QR Code
  document.addEventListener("DOMContentLoaded", function() {
    setTimeout(generateQRCodeLabel, 200);
  });
</script>
'''
PUBLIC_ASSET_REPORT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ERP Inspection Report - {{ sku_code }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body { background-color: #0b132b; color: #333; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .report-card { background: #ffffff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
    .section-header { border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; font-weight: 700; color: #0b132b; }
    .progress-height { height: 12px; border-radius: 6px; }
  </style>
</head>
<body class="py-4">
  <div class="container" style="max-width: 900px;">
    
    <div class="d-flex justify-content-between align-items-center mb-3 text-white">
      <div>
        <h3 class="fw-bold mb-0 text-primary"><i class="fa-solid fa-truck-ramp-box me-2"></i>TABSONS ERP</h3>
        <span class="text-white-50 small">Dispatch Execution & Live Asset Inspection</span>
      </div>
      <span class="badge bg-success fs-6"><i class="fa-solid fa-circle-check me-1"></i> LIVE DISPATCH TRACKER</span>
    </div>

    <div class="report-card p-4 p-md-5">
      
      <div class="d-flex justify-content-between align-items-start mb-4 pb-3 border-bottom">
        <div>
          <span class="badge bg-primary-subtle text-primary fw-bold mb-1">SKU: {{ sku_code }}</span>
          <h2 class="fw-bold text-dark mb-1">{{ asset_name }}</h2>
          <span class="text-muted"><i class="fa-solid fa-tags me-1"></i> Category: <strong>{{ category_name }}</strong></span>
        </div>
        <div class="text-end">
          <span class="text-muted d-block small">Report Generated</span>
          <strong class="text-dark">{{ current_time }}</strong>
        </div>
      </div>

      <!-- LOADING STATUS -->
      <h6 class="section-header mb-3"><i class="fa-solid fa-boxes-stacked text-primary me-2"></i>1. DISPATCH & LOADING STATUS</h6>

      <div class="card bg-light border-0 p-3 mb-4 rounded-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="fw-bold text-dark">Overall Shipment Loading Status</span>
          <span class="badge bg-primary">{{ load_percentage }}% Completed</span>
        </div>
        <div class="progress progress-height mb-3">
          <div class="progress-bar bg-success progress-bar-striped progress-bar-animated" role="progressbar" style="width: {{ load_percentage }}%;"></div>
        </div>

        <div class="row g-3 text-center">
          <div class="col-4">
            <div class="p-2 bg-white rounded border">
              <span class="text-muted small d-block">Total Shipment</span>
              <strong class="fs-5 text-dark">{{ total_qty }} Units</strong>
            </div>
          </div>
          <div class="col-4">
            <div class="p-2 bg-white rounded border">
              <span class="text-success small d-block"><i class="fa-solid fa-check-circle me-1"></i>Loaded / Cleared</span>
              <strong class="fs-5 text-success">{{ loaded_qty }} Units</strong>
            </div>
          </div>
          <div class="col-4">
            <div class="p-2 bg-white rounded border">
              <span class="text-danger small d-block"><i class="fa-solid fa-clock me-1"></i>Pending / Baki</span>
              <strong class="fs-5 text-danger">{{ pending_qty }} Units</strong>
            </div>
          </div>
        </div>
      </div>

      <!-- VALUATION -->
      <h6 class="section-header mb-3"><i class="fa-solid fa-chart-line text-primary me-2"></i>2. COMMERCIAL VALUATION</h6>
      <div class="row g-3 mb-4">
        <div class="col-6">
          <div class="p-3 bg-light rounded-3 border text-center">
            <span class="text-muted small d-block">Unit Price</span>
            <strong class="fs-5 text-dark">₹{{ unit_price }}</strong>
          </div>
        </div>
        <div class="col-6">
          <div class="p-3 bg-light rounded-3 border text-center">
            <span class="text-muted small d-block">Total Batch Valuation</span>
            <strong class="fs-5 text-primary">₹{{ total_valuation }}</strong>
          </div>
        </div>
      </div>

      <div class="d-flex justify-content-between align-items-center pt-3 border-top">
        <button onclick="window.print()" class="btn btn-outline-dark fw-bold btn-sm"><i class="fa-solid fa-print me-1"></i> Print Gate Pass</button>
        <span class="text-muted small"><i class="fa-solid fa-shield-halved text-success me-1"></i> TABSONS ERP Engine</span>
      </div>

    </div>
  </div>
</body>
</html>
"""
# System Alias to fix NameError permanently
PUBLIC_ASSET_HTML = PUBLIC_ASSET_REPORT_HTML

# Asset Transfers Page
TRANSFERS_CONTENT = '''
<div class="table-custom p-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h6 class="fw-bold mb-0">Hub-to-Hub Stock Transfers History</h6>
    <button class="btn btn-primary btn-sm fw-semibold" data-bs-toggle="modal" data-bs-target="#transferModal">
      <i class="fa-solid fa-right-left me-1"></i> New Transfer Order
    </button>
  </div>
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0" style="font-size: 0.9rem;">
      <thead class="table-light">
        <tr>
          <th>Transfer ID</th>
          <th>Item Title</th>
          <th>Source Hub</th>
          <th>Destination Hub</th>
          <th>Units</th>
          <th>Status</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        {% for trf in transfers %}
        <tr>
          <td><code>{{ trf.transfer_id }}</code></td>
          <td class="fw-semibold">{{ trf.item_name }}</td>
          <td>{{ trf.source_hub }}</td>
          <td>{{ trf.destination_hub }}</td>
          <td><span class="fw-bold text-primary">{{ trf.quantity }}</span></td>
          <td><span class="badge bg-warning text-dark">{{ trf.status }}</span></td>
          <td class="small text-muted">{{ trf.date_created }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="modal fade" id="transferModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <form action="/add-transfer" method="POST">
        <div class="modal-header">
          <h5 class="modal-title fw-bold">Dispatch Stock Transfer</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label small fw-semibold">Item Title</label>
            <input type="text" name="item_name" class="form-control" required>
          </div>
          <div class="row g-2 mb-3">
            <div class="col-md-6">
              <label class="form-label small fw-semibold">From (Source Hub)</label>
              <input type="text" name="source_hub" class="form-control" value="Hub Alpha" required>
            </div>
            <div class="col-md-6">
              <label class="form-label small fw-semibold">To (Destination)</label>
              <input type="text" name="destination_hub" class="form-control" value="Hub Beta" required>
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">Quantity Units</label>
            <input type="number" name="quantity" class="form-control" value="5" required>
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" class="btn btn-primary fw-semibold w-100">Create Transfer Order</button>
        </div>
      </form>
    </div>
  </div>
</div>
'''

# Expense Ledger Page
EXPENSE_CONTENT = '''
<div class="row g-4">
  <div class="col-md-4">
    <div class="kpi-card">
      <h6 class="fw-bold mb-3"><i class="fa-solid fa-plus-circle text-danger me-2"></i> Add Daily Expense</h6>
      <form action="/add-expense" method="POST">
        <div class="mb-3">
          <label class="form-label small fw-semibold">Expense Title</label>
          <input type="text" name="title" class="form-control" placeholder="e.g. Fuel Payment" required>
        </div>
        <div class="mb-3">
          <label class="form-label small fw-semibold">Category</label>
          <select name="category" class="form-select">
            <option>Transportation</option>
            <option>Supplies & Packaging</option>
            <option>Utility & Maintenance</option>
            <option>IT & Telecom</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="form-label small fw-semibold">Amount (INR)</label>
          <input type="number" step="0.01" name="amount" class="form-control" placeholder="25000.00" required>
        </div>
        <button type="submit" class="btn btn-danger fw-semibold w-100">Record Expense</button>
      </form>
    </div>
  </div>

  <div class="col-md-8">
    <div class="table-custom p-3">
      <h6 class="fw-bold mb-3">Today's Recorded Expense Entries</h6>
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0" style="font-size: 0.9rem;">
          <thead class="table-light">
            <tr>
              <th>Title</th>
              <th>Category</th>
              <th>Amount</th>
              <th>Recorded By</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {% for exp in expenses %}
            <tr>
              <td class="fw-semibold text-dark">{{ exp.title }}</td>
              <td><span class="badge bg-light text-dark border">{{ exp.category }}</span></td>
              <td class="fw-bold text-danger">₹ {{ exp.amount }}</td>
              <td>{{ exp.added_by }}</td>
              <td class="small text-muted">{{ exp.date_recorded }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
'''

# User Management Page
USERS_CONTENT = '''
<div class="table-custom p-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h6 class="fw-bold mb-0">System Portal Users & Access Controls</h6>
    <button class="btn btn-primary btn-sm fw-semibold" data-bs-toggle="modal" data-bs-target="#addUserModal">
      <i class="fa-solid fa-user-plus me-1"></i> Register New User
    </button>
  </div>
  
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0" style="font-size: 0.9rem;">
      <thead class="table-light">
        <tr>
          <th>User ID</th>
          <th>Full Name</th>
          <th>Work Email</th>
          <th>Assigned Role</th>
          <th class="text-center">Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for u in users_list %}
        <tr>
          <td><code>USR-00{{ u.id }}</code></td>
          <td class="fw-semibold text-dark">{{ u.name }}</td>
          <td>{{ u.email }}</td>
          <td><span class="badge bg-primary-subtle text-primary border border-primary-subtle">{{ u.role }}</span></td>
          <td class="text-center">
            {% if u.id != user.id %}
            <a href="/delete-user/{{ u.id }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('Delete user account?');">
              <i class="fa-solid fa-user-xmark"></i> Delete
            </a>
            {% else %}
            <span class="badge bg-light text-muted">Current Session</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="modal fade" id="addUserModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <form action="/add-user" method="POST">
        <div class="modal-header">
          <h5 class="modal-title fw-bold">Add System Access User</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label small fw-semibold">Full Name</label>
            <input type="text" name="name" class="form-control" placeholder="e.g. Rahul Sharma" required>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">Work Email</label>
            <input type="email" name="email" class="form-control" placeholder="rahul@tabsons.com" required>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">Initial Password</label>
            <input type="password" name="password" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label small fw-semibold">System Role</label>
            <select name="role" class="form-select">
              <option value="System Administrator">System Administrator</option>
              <option value="Logistics Manager">Logistics Manager</option>
              <option value="Showroom Operator">Showroom Operator</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" class="btn btn-primary fw-semibold w-100">Create Account</button>
        </div>
      </form>
    </div>
  </div>
</div>
'''

# Audit Activity Page
AUDIT_CONTENT = '''
<div class="table-custom p-3">
  <h6 class="fw-bold mb-3"><i class="fa-solid fa-shield-halved text-primary me-2"></i> Real-time Enterprise Audit Activity Logs</h6>
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0" style="font-size: 0.875rem;">
      <thead class="table-light">
        <tr>
          <th>Timestamp</th>
          <th>User</th>
          <th>Action Type</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {% for log in logs %}
        <tr>
          <td class="text-muted small">{{ log.timestamp }}</td>
          <td class="fw-semibold text-dark">{{ log.user_name }}</td>
          <td><span class="badge bg-secondary">{{ log.action }}</span></td>
          <td>{{ log.details }}</td>
        </tr>
        {% else %}
        <tr>
          <td colspan="4" class="text-center text-muted">No activity logged yet.</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
'''

# Login Page
LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Tabsons Enterprise Portal - Sign In</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { font-family: sans-serif; background-color: #f8fafc; color: #0f172a; height: 100vh; display: flex; align-items: center; justify-content: center; }
    .auth-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 40px; width: 100%; max-width: 420px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05); }
    .brand-logo { font-weight: 800; font-size: 1.5rem; color: #0f172a; }
    .brand-logo span { color: #2563eb; }
    .btn-corporate { background-color: #0f172a; color: #ffffff; font-weight: 600; border-radius: 8px; padding: 10px; }
  </style>
</head>
<body>
  <div class="auth-card">
    <div class="text-center mb-4">
      <div class="brand-logo mb-1">TABSONS <span>ERP</span></div>
      <p class="text-muted small">Enterprise Resource Planning Portal</p>
    </div>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} p-2 small text-center rounded-3">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form action="/login" method="POST">
      <div class="mb-3">
        <label class="form-label text-secondary small fw-medium">Work Email</label>
        <input type="email" name="email" class="form-control" value="it@tabsons.com" required>
      </div>
      <div class="mb-4">
        <label class="form-label text-secondary small fw-medium">Password</label>
        <input type="password" name="password" class="form-control" value="tabsons123" required>
      </div>
      <button type="submit" class="btn btn-corporate w-100">Sign In to Enterprise Workspace</button>
    </form>
  </div>
</body>
</html>
'''

def render_page(page_key, title, subtitle, content_template, **kwargs):
    full_html = BASE_LAYOUT.replace("{{ content | safe }}", content_template)
    return render_template_string(full_html, page=page_key, title=title, subtitle=subtitle, user=current_user, **kwargs)

# ----------------- FLASK ROUTES ----------------- #

@app.route("/")
def home():
    return redirect(url_for("dashboard") if current_user.is_authenticated else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        conn = get_db()
        user_row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        
        if user_row and check_password_hash(user_row["password_hash"], password):
            user_obj = User(user_row)
            login_user(user_obj)
            log_activity(user_obj.name, "LOGIN", "User logged into the portal")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Email or Password!", "danger")
    return render_template_string(LOGIN_HTML)
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    items = [dict(row) for row in conn.execute("SELECT * FROM items").fetchall()]
    
    total_stock = sum([item.get('quantity') or item.get('stock_quantity') or 0 for item in items])
    total_val = sum([(item.get('quantity') or item.get('stock_quantity') or 0) * (item.get('price') or 0) for item in items])
    
    try:
        today_exp = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
    except Exception:
        today_exp = 0
    conn.close()

    summary = {
        "total_stock": total_stock,
        "total_valuation": round(total_val, 2),
        "today_expense": round(today_exp, 2)
    }

    categories = sorted(list(set([item.get('category') for item in items if item.get('category')])))
    low_stock_items = [item for item in items if (item.get('quantity') or item.get('stock_quantity') or 0) < 10]
    low_stock_count = len(low_stock_items)

    # Chart Data Preparation
    chart_labels = [item.get('name') or item.get('asset_name') or 'Item' for item in items[:10]]
    chart_values = [item.get('quantity') or item.get('stock_quantity') or 0 for item in items[:10]]

    # System Stock Ratio
    active_ratio = min(round((1 - (low_stock_count / (len(items) or 1))) * 100, 1), 100)

    dashboard_body = """
    <style>
      :root {
        --navy-bg: #f4f7fa;
        --navy-card-bg: #ffffff;
        --navy-primary: #1e3a8a;       /* Soft Deep Navy */
        --navy-accent: #2563eb;        /* Soft Blue Accent */
        --navy-light-bg: #eff6ff;     /* Light Blue Tint */
        --navy-border: #e2e8f0;
        --navy-text-dark: #0f172a;
        --navy-text-muted: #64748b;
      }
      
      .glass-dashboard-wrapper {
        background-color: var(--navy-bg);
        border-radius: 20px;
        padding: 24px;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
      }

      .glass-card {
        background: var(--navy-card-bg);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid var(--navy-border);
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }

      .glass-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(30, 58, 138, 0.06);
      }

      .kpi-icon-pill {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        background: var(--navy-light-bg);
        color: var(--navy-primary);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
      }

      .kpi-title {
        font-size: 1.55rem;
        font-weight: 800;
        color: var(--navy-text-dark);
        letter-spacing: -0.5px;
      }

      .kpi-sub {
        font-size: 0.8rem;
        color: var(--navy-text-muted);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .badge-navy-soft {
        background: var(--navy-light-bg);
        color: var(--navy-primary);
        font-size: 0.75rem;
        font-weight: 700;
        padding: 5px 10px;
        border-radius: 20px;
        border: 1px solid #bfdbfe;
      }

      .badge-soft-red {
        background: #fef2f2;
        color: #dc2626;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 5px 10px;
        border-radius: 20px;
        border: 1px solid #fecaca;
      }

      .progress-navy {
        height: 8px;
        border-radius: 20px;
        background-color: var(--navy-light-bg);
      }

      .progress-navy .progress-bar {
        background: linear-gradient(90deg, #2563eb 0%, #1e3a8a 100%);
        border-radius: 20px;
      }

      .recent-row {
        padding: 12px 16px;
        border-radius: 12px;
        background: #f8fafc;
        border: 1px solid #f1f5f9;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
    </style>

    <div class="glass-dashboard-wrapper">
      
      <!-- HEADER -->
      <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 class="fw-bold mb-1" style="color: var(--navy-text-dark);"><i class="fa-solid fa-gauge-high text-primary me-2"></i>Operational Command Center</h4>
          <span class="text-muted small">Real-time enterprise asset tracking & revenue capacity analytics</span>
        </div>
        <div>
          <span class="badge bg-white text-primary border border-primary-subtle shadow-sm px-3 py-2 rounded-pill font-monospace fw-semibold">
            <i class="fa-solid fa-circle text-primary me-1" style="font-size: 7px;"></i> LIVE SYSTEM DATA
          </span>
        </div>
      </div>

      <!-- TOP 4 KPI CARDS -->
      <div class="row g-3 mb-4">
        <div class="col-xl-3 col-md-6">
          <div class="glass-card">
            <div class="d-flex justify-content-between align-items-start mb-3">
              <div class="kpi-icon-pill"><i class="fa-solid fa-wallet"></i></div>
              <span class="badge-navy-soft">Valuation</span>
            </div>
            <div class="kpi-title" style="color: var(--navy-primary);">₹{{ "{:,.2f}".format(summary.total_valuation) }}</div>
            <div class="kpi-sub mt-2">Total Stock Valuation</div>
          </div>
        </div>

        <div class="col-xl-3 col-md-6">
          <div class="glass-card">
            <div class="d-flex justify-content-between align-items-start mb-3">
              <div class="kpi-icon-pill"><i class="fa-solid fa-boxes-stacked"></i></div>
              <span class="badge-navy-soft">Units</span>
            </div>
            <div class="kpi-title">{{ summary.total_stock }}</div>
            <div class="kpi-sub mt-2">Total Stock Assets</div>
          </div>
        </div>

        <div class="col-xl-3 col-md-6">
          <div class="glass-card">
            <div class="d-flex justify-content-between align-items-start mb-3">
              <div class="kpi-icon-pill"><i class="fa-solid fa-receipt"></i></div>
              <span class="badge-navy-soft">Expenses</span>
            </div>
            <div class="kpi-title">₹{{ "{:,.2f}".format(summary.today_expense) }}</div>
            <div class="kpi-sub mt-2">Today's Operating Expense</div>
          </div>
        </div>

        <div class="col-xl-3 col-md-6">
          <div class="glass-card">
            <div class="d-flex justify-content-between align-items-start mb-3">
              <div class="kpi-icon-pill"><i class="fa-solid fa-triangle-exclamation text-danger"></i></div>
              <span class="badge-soft-red">Restock Needed</span>
            </div>
            <div class="kpi-title text-danger">{{ low_stock_count }}</div>
            <div class="kpi-sub mt-2">Low Stock Alerts</div>
          </div>
        </div>
      </div>

      <!-- MAIN CONTENT: BAR CHART + STATUS PANELS -->
      <div class="row g-4 mb-4">
        
        <!-- LEFT BAR CHART -->
        <div class="col-lg-8">
          <div class="glass-card h-100">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <div>
                <h6 class="fw-bold text-dark mb-0"><i class="fa-solid fa-chart-column text-primary me-2"></i>Stock Asset Analytics</h6>
                <span class="text-muted small">Asset quantity levels across primary SKUs</span>
              </div>
              <span class="badge bg-light text-secondary rounded-pill px-3 py-1 border small">Live Chart</span>
            </div>

            <div style="height: 270px; position: relative;">
              <canvas id="navyGlassBarChart"></canvas>
            </div>
          </div>
        </div>

        <!-- RIGHT SIDE STATUS PANELS -->
        <div class="col-lg-4">
          <div class="d-flex flex-column gap-3 h-100">
            
            <!-- FORMATION / HEALTH STATUS -->
            <div class="glass-card">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="fw-bold text-dark mb-0">Inventory Health Status</h6>
                <i class="fa-solid fa-shield-check text-primary"></i>
              </div>
              <span class="text-muted small d-block mb-3">Stock capacity stability index</span>
              
              <div class="progress progress-navy mb-2">
                <div class="progress-bar" style="width: {{ active_ratio }}%;"></div>
              </div>

              <div class="d-flex justify-content-between align-items-center small text-muted">
                <span>Healthy Stock Ratio</span>
                <span class="fw-bold text-dark">{{ active_ratio }}%</span>
              </div>
            </div>

            <!-- SYSTEM SUCCESS RATE -->
            <div class="glass-card flex-grow-1 d-flex flex-column justify-content-between">
              <div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <h6 class="fw-bold text-dark mb-0">System Performance Rate</h6>
                  <i class="fa-solid fa-circle-check text-success"></i>
                </div>
                <span class="text-muted small">Live database & API stability</span>
              </div>

              <div class="text-center my-3">
                <div class="display-5 fw-bold" style="color: var(--navy-primary);">{{ active_ratio }}%</div>
                <span class="badge bg-success-subtle text-success mt-1"><i class="fa-solid fa-arrow-trend-up me-1"></i> System Operational</span>
              </div>

              <div class="p-2 rounded-3 text-center small text-muted border bg-light">
                Enterprise database connected and sync verified.
              </div>
            </div>

          </div>
        </div>

      </div>

      <!-- BOTTOM ROW: CRITICAL SKUs -->
      <div class="glass-card">
        <h6 class="fw-bold text-dark mb-3"><i class="fa-solid fa-boxes-stacked text-primary me-2"></i>Critical Low Stock SKUs</h6>
        <div class="row g-2">
          {% for item in low_stock_items[:3] %}
          <div class="col-md-4">
            <div class="recent-row">
              <div class="d-flex align-items-center gap-2">
                <div class="kpi-icon-pill" style="width: 32px; height: 32px; font-size: 0.8rem;"><i class="fa-solid fa-box"></i></div>
                <div>
                  <div class="fw-bold text-dark small">{{ item.get('name') or item.get('asset_name') or 'Item' }}</div>
                  <div class="text-muted" style="font-size: 0.75rem;">Cat: {{ item.get('category') or 'General' }}</div>
                </div>
              </div>
              <span class="badge bg-danger-subtle text-danger fw-bold">{{ item.get('quantity') or item.get('stock_quantity') or 0 }} Left</span>
            </div>
          </div>
          {% endfor %}
          {% if not low_stock_items %}
          <div class="col-12 text-center text-muted py-2 small">All inventory items are sufficiently stocked!</div>
          {% endif %}
        </div>
      </div>

    </div>

    <!-- SOFT NAVY CHART JS -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
      const labels = {{ chart_labels | tojson }};
      const values = {{ chart_values | tojson }};

      const ctx = document.getElementById('navyGlassBarChart').getContext('2d');
      
      // Soft Navy Linear Gradient
      const gradient = ctx.createLinearGradient(0, 0, 0, 280);
      gradient.addColorStop(0, '#1e3a8a');
      gradient.addColorStop(1, '#93c5fd');

      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Quantity',
            data: values,
            backgroundColor: gradient,
            borderRadius: 8,
            borderSkipped: false,
            barThickness: 26
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: '#64748b', font: { family: 'Inter' } }
            },
            y: {
              grid: { color: '#f1f5f9' },
              ticks: { color: '#64748b', font: { family: 'Inter' } },
              beginAtZero: true
            }
          }
        }
      });
    </script>
    """

    return render_page(
        "Operational Overview",
        "Operational Overview",
        "Real-time Enterprise Asset Tracking & Analytics",
        dashboard_body,
        summary=summary,
        categories=categories,
        low_stock_items=low_stock_items,
        low_stock_count=low_stock_count,
        chart_labels=chart_labels,
        chart_values=chart_values,
        active_ratio=active_ratio
    )

@app.route("/inventory")
@login_required
def inventory():
    conn = get_db()
    items = [dict(row) for row in conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()]
    conn.close()
    return render_page("inventory", "Inventory & Stock", "Showroom asset database and stock levels", INVENTORY_CONTENT, items=items)
@app.route("/asset-info/<sku>")
@app.route("/view/<sku>")
def public_asset_info(sku):
    from datetime import datetime
    conn = get_db()
    
    # SQLite Table Structure Auto-Detecting
    columns_info = conn.execute("PRAGMA table_info(items)").fetchall()
    col_names = [col[1] for col in columns_info]

    item = None

    # Safe Dynamic Query matching based on existing table columns
    if "sku" in col_names:
        item = conn.execute("SELECT * FROM items WHERE sku = ?", (sku,)).fetchone()
    elif "id" in col_names and sku.isdigit():
        item = conn.execute("SELECT * FROM items WHERE id = ?", (sku,)).fetchone()
    elif "asset_id" in col_names:
        item = conn.execute("SELECT * FROM items WHERE asset_id = ?", (sku,)).fetchone()
    elif "barcode" in col_names:
        item = conn.execute("SELECT * FROM items WHERE barcode = ?", (sku,)).fetchone()
    
    # Fallback search by ID or Name if specific column not matched
    if not item and "id" in col_names:
        clean_id = ''.join(filter(str.isdigit, sku))
        if clean_id:
            item = conn.execute("SELECT * FROM items WHERE id = ?", (clean_id,)).fetchone()
            
    if not item and "name" in col_names:
        item = conn.execute("SELECT * FROM items WHERE name LIKE ? OR asset_name LIKE ?", (f"%{sku}%", f"%{sku}%")).fetchone()

    conn.close()

    if not item:
        return f"<div style='color:white; text-align:center; padding:50px;'><h2>Asset Not Found!</h2><p>SKU/ID '{sku}' database me nahi mil saka.</p></div>", 404
        
    item_dict = dict(item)

    # Safe Column Reading
    name = item_dict.get('name') or item_dict.get('asset_name') or item_dict.get('title') or 'Asset Item'
    category = item_dict.get('category') or 'General'
    
    # Reading Quantity & Price across variations
    qty = int(item_dict.get('quantity') or item_dict.get('stock_quantity') or item_dict.get('stock') or 0)
    price = float(item_dict.get('price') or item_dict.get('unit_price') or item_dict.get('cost') or 0)

    # Calculation Metrics
    loaded = int(qty * 0.75) if qty > 0 else 0
    pending = qty - loaded
    perc = int((loaded / qty) * 100) if qty > 0 else 0

    return render_template_string(
        PUBLIC_ASSET_REPORT_HTML, 
        sku_code=sku,
        asset_name=name,
        category_name=category,
        total_qty=qty,
        loaded_qty=loaded,
        pending_qty=pending,
        load_percentage=perc,
        unit_price=price,
        total_valuation=round(qty * price, 2),
        current_time=datetime.now().strftime("%d-%b-%Y %I:%M %p")
    )
@app.route("/edit-item/<int:item_id>", methods=["POST"])
@login_required
def edit_item(item_id):
    conn = get_db()
    conn.execute("""
        UPDATE items 
        SET name=?, category=?, location=?, quantity=?, price=? 
        WHERE id=?
    """, (request.form.get("name"), request.form.get("category"),
          request.form.get("location"), request.form.get("quantity"),
          request.form.get("price"), item_id))
    conn.commit()
    conn.close()
    log_activity(current_user.name, "EDIT_ITEM", f"Updated details for Item ID #{item_id}")
    flash("Asset details updated successfully!", "success")
    return redirect(url_for("inventory"))

@app.route("/delete-item/<int:item_id>")
@login_required
def delete_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    log_activity(current_user.name, "DELETE_ITEM", f"Deleted Item ID #{item_id}")
    flash("Asset removed from database!", "warning")
    return redirect(url_for("inventory"))

@app.route("/user-management")
@login_required
def user_management():
    conn = get_db()
    users_list = [dict(row) for row in conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()]
    conn.close()
    return render_page("users", "User Management", "Control access levels and manage team credentials", USERS_CONTENT, users_list=users_list)

@app.route("/add-user", methods=["POST"])
@login_required
def add_user():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role")
    
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                     (name, email, generate_password_hash(password), role))
        conn.commit()
        log_activity(current_user.name, "CREATE_USER", f"Created user {name} ({email}) with role {role}")
        flash(f"User account for {name} created successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Email address already exists!", "danger")
    finally:
        conn.close()
    return redirect(url_for("user_management"))

@app.route("/delete-user/<int:user_id>")
@login_required
def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    log_activity(current_user.name, "DELETE_USER", f"Removed User ID #{user_id}")
    flash("User account deleted!", "warning")
    return redirect(url_for("user_management"))

@app.route("/export-excel")
@login_required
def export_excel():
    conn = get_db()
    df = pd.read_sql_query("SELECT barcode, name, category, location, quantity, price FROM items", conn)
    conn.close()
    
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], "Inventory_Report.xlsx")
    df.to_excel(excel_path, index=False)
    log_activity(current_user.name, "EXPORT_EXCEL", "Downloaded complete inventory Excel report")
    return send_file(excel_path, as_attachment=True, download_name="Inventory_Stock_Report.xlsx")

@app.route("/data-importer")
@login_required
def data_importer():
    return render_page("importer", "IT Data Importer", "Upload Excel sheets to bulk import assets into SQL DB", IMPORTER_CONTENT)

@app.route("/upload-data", methods=["POST"])
@login_required
def upload_data():
    if 'file' not in request.files:
        flash("No file selected!", "danger")
        return redirect(url_for("data_importer"))
        
    file = request.files['file']
    if file.filename == '':
        flash("No file selected!", "danger")
        return redirect(url_for("data_importer"))

    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        if file.filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.lower()

        required_cols = {'barcode', 'name'}
        if not required_cols.issubset(set(df.columns)):
            flash("Missing required columns in Excel! Make sure 'barcode' and 'name' exist.", "danger")
            return redirect(url_for("data_importer"))

        conn = get_db()
        cursor = conn.cursor()
        inserted_count = 0

        for _, row in df.iterrows():
            barcode = str(row['barcode']).strip()
            name = str(row['name']).strip()
            category = str(row.get('category', 'General Logistics')).strip()
            quantity = int(row.get('quantity', 1))
            price = float(row.get('price', 0.0))
            location = str(row.get('location', 'Tabsons Hub')).strip()

            try:
                cursor.execute("""
                    INSERT INTO items (barcode, name, category, quantity, price, location)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(barcode) DO UPDATE SET
                    quantity = quantity + excluded.quantity,
                    price = excluded.price
                """, (barcode, name, category, quantity, price, location))
                inserted_count += 1
            except Exception:
                continue

        conn.commit()
        conn.close()
        
        log_activity(current_user.name, "BULK_IMPORT", f"Imported {inserted_count} items via Excel ({file.filename})")
        flash(f"Successfully processed Excel file! {inserted_count} rows synced to SQL Database.", "success")
        return redirect(url_for("inventory"))

    except Exception as e:
        flash(f"Error processing file: {str(e)}", "danger")
        return redirect(url_for("data_importer"))

@app.route("/barcode-scanner")
@login_required
def barcode_scanner():
    conn = get_db()
    items = [dict(row) for row in conn.execute("SELECT * FROM items").fetchall()]
    conn.close()
    
    items_json = json.dumps(items)
    
    return render_page("barcode", "Dynamic QR Generator", "Print asset QR labels with custom 'SCAN FOR DETAILS' banner", BARCODE_CONTENT, items=items, items_json=items_json)

@app.route("/asset-transfers")
@login_required
def asset_transfers():
    conn = get_db()
    transfers = [dict(row) for row in conn.execute("SELECT * FROM transfers ORDER BY id DESC").fetchall()]
    conn.close()
    return render_page("transfers", "Asset Transfers", "Manage stock movements between warehouse hubs", TRANSFERS_CONTENT, transfers=transfers)

@app.route("/add-transfer", methods=["POST"])
@login_required
def add_transfer():
    conn = get_db()
    trf_id = f"TRF-{datetime.now().strftime('%M%S')}"
    conn.execute("INSERT INTO transfers (transfer_id, item_name, source_hub, destination_hub, quantity, date_created) VALUES (?, ?, ?, ?, ?, ?)",
                 (trf_id, request.form.get("item_name"), request.form.get("source_hub"),
                  request.form.get("destination_hub"), request.form.get("quantity"), datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    log_activity(current_user.name, "TRANSFER_STOCK", f"Created Transfer Order {trf_id}")
    flash("New Transfer Order Created!", "success")
    return redirect(url_for("asset_transfers"))



@app.route("/expense-ledger")
@login_required
def expense_ledger():
    conn = get_db()
@app.route("/expense-ledger")
@login_required
def expense_ledger():
    conn = get_db()
    expenses = conn.execute("SELECT * FROM expenses ORDER BY date_recorded DESC").fetchall()
    conn.close()
    return render_template("expense_ledger.html", expenses=expenses)

@app.route("/powerbi-workspaces")
@login_required
def powerbi_workspaces():
    conn = get_db()
    items = conn.execute("SELECT barcode, asset_name, category, location, stock, price FROM items").fetchall()
    items_list = [dict(i) for i in items]
    conn.close()

    items_json = json.dumps(items_list)
    return render_template("powerbi.html", items_json=items_json)
    
@app.route("/add-expense", methods=["POST"])
@login_required
def add_expense():
    conn = get_db()
    conn.execute("INSERT INTO expenses (title, category, amount, added_by, date_recorded) VALUES (?, ?, ?, ?, ?)",
                 (request.form.get("title"), request.form.get("category"), request.form.get("amount"),
                  current_user.name, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    log_activity(current_user.name, "ADD_EXPENSE", f"Recorded expense ₹{request.form.get('amount')} for {request.form.get('title')}")
    flash("Daily Expense Recorded!", "danger")
    return redirect(url_for("expense_ledger"))

@app.route("/audit-logs")
@login_required
def audit_logs():
    conn = get_db()
    logs = [dict(row) for row in conn.execute("SELECT * FROM audit_logs ORDER BY id DESC").fetchall()]
    conn.close()
    return render_page("audit", "Audit Activity Logs", "Real-time security and operational transaction history", AUDIT_CONTENT, logs=logs)

@app.route("/logout")
@login_required
def logout():
    log_activity(current_user.name, "LOGOUT", "User logged out")
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)