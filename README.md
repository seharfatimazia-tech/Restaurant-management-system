# Gusto POS - Restaurant Management Desktop Software

A complete, enterprise-grade **Restaurant Management Desktop Software System with Delivery** built with **Python**, an **embedded SQLite DBMS via SQLAlchemy ORM (3NF/BCNF normalized)**, and a **native desktop software window interface**.

Designed specifically for DBMS course project defense, operational POS reliability, and desktop-first offline execution.

---

## 🖥️ How It Runs as Standalone Desktop Software

Rather than functioning as a standard website in a browser tab, this system is packaged as **Desktop Software**:
1. **Desktop Window Execution**: Launching the software via [`main.py`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/main.py) or [`run_software.bat`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/run_software.bat) opens a **dedicated standalone native desktop software window** (using native WebView2 / standalone desktop framing with custom window title, taskbar icon, and standard minimize/maximize/close controls).
2. **Embedded Zero-Config DBMS**: All 21 relational tables reside in a local `restaurant.db` SQLite database file managed through SQLAlchemy ORM — no external database servers (pgAdmin/PostgreSQL/MySQL) are needed.
3. **One-Click Windows Launcher**: Double-click [`run_software.bat`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/run_software.bat) to start the software directly on Windows.

---

## 👥 Built-In Demo Staff Accounts (6 Roles)

On the login screen, click any role badge to automatically fill in the test credentials:

| Role | Username | Password | Full Name | Capabilities & Access |
|---|---|---|---|---|
| **Admin** | `admin` | `Admin@123` | Alexander Wright | Master system control, staff accounts, audit trail, DB backup |
| **Manager** | `manager` | `Manager@123` | Maria Gomez | Menu management, inventory, purchase orders, sales reports |
| **Cashier** | `cashier` | `Cashier@123` | David Chen | POS order placement, billing terminal, payment intake |
| **Waiter** | `waiter` | `Waiter@123` | Sarah Jenkins | Dining floor map, table bookings, dine-in tickets |
| **Chef** | `chef` | `Chef@123` | Gordon Rossi | Kitchen Display System (KDS), dish recipes & BOM |
| **Delivery Rider** | `rider` | `Rider@123` | Marcus Taylor | Rider dispatch portal, delivery status pipeline |
| **Delivery Rider 2**| `rider2` | `Rider@123` | Elena Rostova | Secondary delivery rider for dispatch testing |

---

## 🚀 How to Run the Desktop Software

### Method A: One-Click Desktop Launcher (Windows)
Double-click:
```
run_software.bat
```
This batch script will automatically check your Python environment, install any missing dependencies, initialize the database on first run, and launch the native desktop software window.

---

### Method B: Launching in VS Code Terminal

1. **Open the project directory in VS Code**:
   ```powershell
   cd "C:\Users\nomad\.gemini\antigravity\scratch\restaurant_management_system"
   code .
   ```
   *(Set this folder as your active VS Code workspace.)*

2. **Activate your Python environment and install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Initialize the database with sample data (optional, auto-runs if DB is missing)**:
   ```powershell
   python seed.py
   ```

4. **Launch the Desktop Software**:
   ```powershell
   python main.py
   ```
   A native desktop software window will open directly on your screen.

---

## 🏛️ DBMS Architecture & Normalization (3NF / BCNF)

For full database documentation, mathematical proofs, functional dependencies, and ER diagrams, see:
- **[`ER_DIAGRAM.md`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/ER_DIAGRAM.md)**: Full Mermaid ER Diagram with cardinality, keys, and 3NF/BCNF proofs.
- **[`SOFTWARE_SPECIFICATION.md`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/SOFTWARE_SPECIFICATION.md)**: Software technical manual and schema dictionary.

### Core Business Rules Enforced by the Software:
1. **Atomic Recipe Stock Deduction**: Closing an order (`Completed`) triggers an atomic deduction of ingredients from `ingredient.current_stock` according to `recipe` BOM quantities, creating ledger records in `stock_transaction`.
2. **Payment Balance Constraint**: Payments cannot exceed `bill.balance`. Overpayments are rejected.
3. **No Double-Booking**: Overlapping reservations within a 2-hour window on the same dining table are blocked with HTTP 409 Conflict.
4. **Delivery Zone Minimums**: Validates that orders meet the minimum required amount for their delivery zone and includes the zone fee in the final invoice.
5. **Delivery Pipeline Flow**: Permitted status flow: `Pending` $\to$ `Assigned` $\to$ `Out for delivery` $\to$ `Delivered` (or `Cancelled`).
6. **Soft Deletions**: Deactivates records (`is_active = False`) instead of raw SQL `DELETE` to maintain referential integrity.
7. **Audit Logging**: All important operations are logged to the immutable `audit_log` table.

---

## 📁 Source Code Structure

```
restaurant_management_system/
├── main.py                     # Desktop Software launcher (Native Window / WebView2)
├── run_software.bat            # 1-Click Windows desktop launcher
├── app.py                      # Core backend engine, RBAC decorators & REST APIs
├── models.py                   # 21 SQLAlchemy ORM models (3NF/BCNF, constraints)
├── seed.py                     # Database initialization and sample data populator
├── requirements.txt            # Python dependencies (Flask, SQLAlchemy, pywebview)
├── SOFTWARE_SPECIFICATION.md   # Complete software manual and technical specification
├── ER_DIAGRAM.md               # Mermaid Entity-Relationship Diagram & 3NF proofs
├── README.md                   # Desktop setup & usage documentation
├── templates/
│   ├── login.html              # Desktop login screen with 1-click role autofill
│   └── index.html              # Main Desktop POS interface (14 integrated modules)
└── static/
    ├── css/style.css           # Desktop POS styling
    └── js/app.js               # Frontend interactive controller & state engine
```
