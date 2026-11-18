# Gusto Restaurant Management Software
## Enterprise Desktop Software Specification & DBMS Technical Manual

---

### 1. Executive Summary & Software Architecture

**Gusto POS** is an enterprise-grade desktop software system designed for full-cycle restaurant operations, dine-in seating, kitchen ticket routing, automated recipe inventory depletion, delivery dispatch, customer billing, and role-based access control.

Unlike generic web applications that require external hosting or manual browser navigation, Gusto is engineered as **self-contained Desktop Software**:
- **Execution Mode**: Runs as a native desktop software window via [`main.py`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/main.py) or 1-click batch launcher [`run_software.bat`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/run_software.bat).
- **Desktop Window Technology**: Built with `pywebview` / Windows WebView2 standalone app framing. It renders in its own native desktop window with a custom title, system menu, minimization/maximization controls, and zero browser chrome (no address bars, navigation buttons, or browser tabs).
- **Database Engine**: Embedded **SQLite 3** managed through **SQLAlchemy ORM**. Zero database server configuration (no PostgreSQL, MySQL, or pgAdmin installations needed). Automatically creates and validates tables on startup.
- **Normalization Standard**: Normalized to **3NF / BCNF** to eliminate insertion, update, and deletion anomalies.

---

### 2. Software Subsystems & Functional Modules

```
+-----------------------------------------------------------------------------------+
|                   Gusto Restaurant Management Desktop Software                    |
+-----------------------------------------------------------------------------------+
|  1. Authentication & RBAC Engine (Salted SHA-256 Hashing, 6 Specialized Roles)    |
|  2. Point-of-Sale (POS) & Order Processing (Dine-In, Takeaway, Delivery)          |
|  3. Kitchen Display System (KDS) Live Ticket Engine                               |
|  4. Floor Plan & Table Reservation Manager (Temporal Overlap Conflict Engine)     |
|  5. Financial Billing & Payments Terminal (Balance Constraint Validation)         |
|  6. Delivery Dispatch & Rider Telematics (Zone Minimums & Fee Calculation)        |
|  7. Bill-of-Materials (BOM) & Recipe Inventory Deduction (Atomic On-Close)        |
|  8. Vendor Directory & Purchase Order Procurement (Auto-Restock on Receipt)       |
|  9. Immutable Stock Ledger (Audit Trail of all Quantity Movements)                |
| 10. Executive Analytics & Reporting (Sales Channels, Top Dishes, Rider Metrics)   |
| 11. Central Audit Log (Security & Transaction Monitoring)                         |
| 12. Instant Database Backup & Snapshot Generator                                  |
+-----------------------------------------------------------------------------------+
```

---

### 3. Database Schema: 21 Normalized Models (3NF / BCNF)

| # | Entity / Model | Primary Key | Key Foreign Keys | Unique / Check Constraints | Purpose |
|---|---|---|---|---|---|
| 1 | `user_account` | `id` | - | `username` (UK), `role IN (...)` | User authentication credentials & salted hash |
| 2 | `staff` | `id` | `user_account_id` (UK) | 1-to-1 with `user_account` | Employee operational profile |
| 3 | `customer` | `id` | - | `phone` (UK, Indexed), `email` (UK) | Customer directory |
| 4 | `delivery_zone` | `id` | - | `name` (UK), `fee >= 0`, `min >= 0` | Geographic delivery zones and fees |
| 5 | `address` | `id` | `customer_id`, `delivery_zone_id` | - | Customer delivery addresses |
| 6 | `dining_table` | `id` | - | `table_number` (UK), `capacity > 0` | Physical restaurant floor seating |
| 7 | `reservation` | `id` | `customer_id`, `dining_table_id` | `party_size > 0`, Status constraint | Table bookings (2hr anti-overlap) |
| 8 | `menu_category`| `id` | - | `name` (UK) | Menu food groupings |
| 9 | `menu_item` | `id` | `category_id` | `name` (UK), `price >= 0` | Individual menu dishes and beverages |
| 10| `ingredient` | `id` | - | `name` (UK), `stock >= 0`, `cost >= 0`| Raw inventory goods |
| 11| `recipe` | `id` | `menu_item_id`, `ingredient_id` | Composite `(item_id, ing_id)` (UK) | Bill of Materials (BOM) per portion |
| 12| `supplier` | `id` | - | `name` (UK), `phone` | Raw goods vendors |
| 13| `purchase_order`| `id` | `supplier_id`, `staff_id` | `po_number` (UK), `total >= 0` | Procurement orders |
| 14| `purchase_order_item`| `id` | `purchase_order_id`, `ingredient_id` | `qty > 0`, `cost >= 0` | Line items in purchase order |
| 15| `stock_transaction`| `id`| `ingredient_id`, `staff_id` | `type IN ('Restock', ...)` | Immutable inventory movement ledger |
| 16| `orders` | `id` | `table_id`, `customer_id`, `staff_id`| `order_number` (UK), Type constraint | Order headers (Dine-In, Takeaway, Delivery) |
| 17| `order_item` | `id` | `order_id`, `menu_item_id` | `quantity > 0`, `price >= 0` | Line items recording historical price |
| 18| `bill` | `id` | `order_id` (UK) | `bill_number` (UK), Balance constraints | Financial invoice |
| 19| `payment` | `id` | `bill_id`, `staff_id` | `payment_ref` (UK), `amount > 0` | Transaction receipts (Cash, Card, Online) |
| 20| `delivery` | `id` | `order_id` (UK), `rider_id`, `zone_id` | Status flow constraint | Delivery lifecycle tracking |
| 21| `audit_log` | `id` | `user_id` | Indexed `timestamp` | Central immutable security/action log |

---

### 4. DBMS Business Logic & Transaction Guarantees

#### A. Atomic Order Closing & Recipe Stock Deduction
When the cashier or manager closes an order (`status -> Completed`):
1. The table status is reset to `Available`.
2. The transaction iterates through all dishes in `order_item`.
3. For each dish, the corresponding Bill of Materials (`recipe`) is retrieved.
4. The exact quantity needed: $\Delta Q = \text{portion\_qty} \times \text{recipe.quantity\_required}$.
5. `ingredient.current_stock` is updated.
6. A negative signed row is inserted into `stock_transaction` with `reference_id = order.order_number`.
7. An audit entry is added to `audit_log`.
8. All steps execute within a single atomic `db.session.commit()`. If an error occurs, `db.session.rollback()` ensures the database remains uncorrupted.

#### B. Payment Cannot Exceed Balance
Payment intake verifies that:
$$\text{Payment Amount} \le \text{Bill Total Amount} - \text{Bill Paid Amount}$$
Overpayments are rejected at both API and business layer before any ledger entry is created.

#### C. Temporal Reservation Conflict Engine
A booking request for table $T$ at time $t$ queries:
$$\text{Reservations where } \text{table\_id} = T \land |\text{reservation\_time} - t| < 120 \text{ minutes} \land \text{status} \in \{\text{'Confirmed'}, \text{'Seated'}\}$$
Any matching entry immediately blocks the booking with an HTTP 409 conflict code.

#### D. Delivery Zone Integrity
Delivery orders require that:
$$\text{Items Subtotal} \ge \text{zone.min\_order\_amount}$$
The delivery fee from `delivery_zone` is automatically incorporated into the bill's grand total.

---

### 5. Desktop Software Operation

To launch the software as a desktop application:
1. Double-click [`run_software.bat`](file:///C:/Users/nomad/.gemini/antigravity/scratch/restaurant_management_system/run_software.bat).
2. Or in terminal:
   ```powershell
   python main.py
   ```
The software automatically validates the database, runs seed initialization if needed, and presents a standalone native desktop window.
