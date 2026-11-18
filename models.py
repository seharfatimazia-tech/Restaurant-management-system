"""
Restaurant Management System - Database Models
DBMS 3NF / BCNF Normalized Schema with SQLAlchemy ORM
"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()

# ==============================================================================
# 1. USER & AUTHENTICATION MODELS (BCNF: Separated Auth from Staff Profile)
# ==============================================================================

class UserAccount(db.Model):
    """
    User Account Table: Handles authentication and role-based access control (RBAC).
    Passwords are never stored in plain text; only salted hashes are persisted.
    """
    __tablename__ = 'user_account'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(60), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    staff_profile = db.relationship('Staff', backref='user_account', uselist=False, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user_account', lazy='dynamic')

    __table_args__ = (
        CheckConstraint(
            "role IN ('Admin', 'Manager', 'Cashier', 'Waiter', 'Chef', 'Delivery Rider')",
            name='ck_user_account_role'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Staff(db.Model):
    """
    Staff Profile Table: Holds employee demographic and operational details.
    Maintains 3NF normalization by isolating staff profile attributes from credential store.
    """
    __tablename__ = 'staff'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_account_id = db.Column(db.Integer, db.ForeignKey('user_account.id', ondelete='CASCADE'), unique=True, nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    hire_date = db.Column(db.Date, default=date.today, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    orders_taken = db.relationship('Orders', backref='staff', foreign_keys='Orders.staff_id')
    deliveries_assigned = db.relationship('Delivery', backref='rider', foreign_keys='Delivery.rider_id')
    payments_processed = db.relationship('Payment', backref='processed_by', foreign_keys='Payment.processed_by_staff_id')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return {
            'id': self.id,
            'user_account_id': self.user_account_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'hire_date': self.hire_date.strftime('%Y-%m-%d'),
            'is_active': self.is_active,
            'username': self.user_account.username if self.user_account else None
        }


# ==============================================================================
# 2. CUSTOMER, ADDRESS & DELIVERY ZONE MODELS (3NF Normalized)
# ==============================================================================

class DeliveryZone(db.Model):
    """
    Delivery Zone Table: Geographically defines coverage zones with delivery fees
    and minimum required order values.
    """
    __tablename__ = 'delivery_zone'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    delivery_fee = db.Column(db.Float, nullable=False, default=0.0)
    min_order_amount = db.Column(db.Float, nullable=False, default=0.0)
    estimated_delivery_minutes = db.Column(db.Integer, nullable=False, default=30)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    addresses = db.relationship('Address', backref='delivery_zone', lazy='dynamic')
    deliveries = db.relationship('Delivery', backref='delivery_zone', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('delivery_fee >= 0', name='ck_delivery_zone_fee_positive'),
        CheckConstraint('min_order_amount >= 0', name='ck_delivery_zone_min_order_positive'),
        CheckConstraint('estimated_delivery_minutes > 0', name='ck_delivery_zone_est_minutes_positive'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'delivery_fee': round(float(self.delivery_fee), 2),
            'min_order_amount': round(float(self.min_order_amount), 2),
            'estimated_delivery_minutes': self.estimated_delivery_minutes,
            'is_active': self.is_active
        }


class Customer(db.Model):
    """
    Customer Table: Master record for restaurant patrons.
    Phone is uniquely indexed to allow fast customer lookup at POS.
    """
    __tablename__ = 'customer'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    addresses = db.relationship('Address', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Orders', backref='customer', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='customer', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Address(db.Model):
    """
    Address Table: 1-to-N relationship with Customer; links to DeliveryZone.
    Maintains 3NF normalization to avoid duplicate customer locations.
    """
    __tablename__ = 'address'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    delivery_zone_id = db.Column(db.Integer, db.ForeignKey('delivery_zone.id'), nullable=False)
    street = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    deliveries = db.relationship('Delivery', backref='delivery_address', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else None,
            'customer_phone': self.customer.phone if self.customer else None,
            'delivery_zone_id': self.delivery_zone_id,
            'zone_name': self.delivery_zone.name if self.delivery_zone else None,
            'delivery_fee': self.delivery_zone.delivery_fee if self.delivery_zone else 0.0,
            'min_order_amount': self.delivery_zone.min_order_amount if self.delivery_zone else 0.0,
            'street': self.street,
            'city': self.city,
            'postal_code': self.postal_code,
            'notes': self.notes,
            'is_active': self.is_active,
            'full_address': f"{self.street}, {self.city} {self.postal_code or ''}".strip()
        }


# ==============================================================================
# 3. DINING TABLES & RESERVATIONS (Double-booking constraint support)
# ==============================================================================

class DiningTable(db.Model):
    """
    Dining Table Table: Physical seating arrangement in the restaurant.
    """
    __tablename__ = 'dining_table'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    table_number = db.Column(db.String(20), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Available', nullable=False)
    location_area = db.Column(db.String(50), default='Main Dining', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    reservations = db.relationship('Reservation', backref='table', lazy='dynamic')
    orders = db.relationship('Orders', backref='table', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('capacity > 0', name='ck_dining_table_capacity_positive'),
        CheckConstraint("status IN ('Available', 'Occupied', 'Reserved')", name='ck_dining_table_status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'table_number': self.table_number,
            'capacity': self.capacity,
            'status': self.status,
            'location_area': self.location_area,
            'is_active': self.is_active
        }


class Reservation(db.Model):
    """
    Reservation Table: Booking entries linking Customer and DiningTable at a specified timestamp.
    Application enforces DBMS rule: No double-booking within overlapping reservation timeframes (2-hour window).
    """
    __tablename__ = 'reservation'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    dining_table_id = db.Column(db.Integer, db.ForeignKey('dining_table.id'), nullable=False)
    reservation_time = db.Column(db.DateTime, nullable=False, index=True)
    party_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Confirmed', nullable=False)
    special_requests = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint('party_size > 0', name='ck_reservation_party_size_positive'),
        CheckConstraint("status IN ('Confirmed', 'Seated', 'Cancelled', 'Completed')", name='ck_reservation_status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else None,
            'customer_phone': self.customer.phone if self.customer else None,
            'dining_table_id': self.dining_table_id,
            'table_number': self.table.table_number if self.table else None,
            'reservation_time': self.reservation_time.strftime('%Y-%m-%d %H:%M'),
            'party_size': self.party_size,
            'status': self.status,
            'special_requests': self.special_requests,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ==============================================================================
# 4. MENU CATEGORY & MENU ITEMS (3NF Normalized)
# ==============================================================================

class MenuCategory(db.Model):
    """
    Menu Category Table: Normalized categorization for menu offerings.
    """
    __tablename__ = 'menu_category'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    items = db.relationship('MenuItem', backref='category', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'display_order': self.display_order,
            'is_active': self.is_active,
            'item_count': self.items.filter_by(is_active=True).count()
        }


class MenuItem(db.Model):
    """
    Menu Item Table: Individual food and drink items available for ordering.
    """
    __tablename__ = 'menu_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_id = db.Column(db.Integer, db.ForeignKey('menu_category.id'), nullable=False)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    recipes = db.relationship('Recipe', backref='menu_item', lazy='dynamic', cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', backref='menu_item', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('price >= 0', name='ck_menu_item_price_positive'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'name': self.name,
            'description': self.description,
            'price': round(float(self.price), 2),
            'is_available': self.is_available,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ==============================================================================
# 5. INVENTORY, RECIPES, SUPPLIERS & PURCHASE ORDERS
# ==============================================================================

class Ingredient(db.Model):
    """
    Ingredient Table: Raw stock items used in cooking recipes.
    """
    __tablename__ = 'ingredient'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # kg, g, liters, units, slices
    current_stock = db.Column(db.Float, default=0.0, nullable=False)
    minimum_stock = db.Column(db.Float, default=5.0, nullable=False)
    cost_per_unit = db.Column(db.Float, default=0.0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    recipes = db.relationship('Recipe', backref='ingredient', lazy='dynamic')
    po_items = db.relationship('PurchaseOrderItem', backref='ingredient', lazy='dynamic')
    stock_transactions = db.relationship('StockTransaction', backref='ingredient', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('current_stock >= 0', name='ck_ingredient_stock_positive'),
        CheckConstraint('minimum_stock >= 0', name='ck_ingredient_min_stock_positive'),
        CheckConstraint('cost_per_unit >= 0', name='ck_ingredient_cost_positive'),
    )

    @property
    def is_low_stock(self):
        return self.current_stock <= self.minimum_stock

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'unit': self.unit,
            'current_stock': round(float(self.current_stock), 2),
            'minimum_stock': round(float(self.minimum_stock), 2),
            'cost_per_unit': round(float(self.cost_per_unit), 2),
            'is_low_stock': self.is_low_stock,
            'is_active': self.is_active
        }


class Recipe(db.Model):
    """
    Recipe Table (Bill of Materials / BOM):
    Composite relationship linking MenuItem to Ingredients with required quantities.
    Follows BCNF: primary composite candidate key (menu_item_id, ingredient_id).
    """
    __tablename__ = 'recipe'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id', ondelete='CASCADE'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    quantity_required = db.Column(db.Float, nullable=False)

    __table_args__ = (
        UniqueConstraint('menu_item_id', 'ingredient_id', name='uq_recipe_item_ingredient'),
        CheckConstraint('quantity_required > 0', name='ck_recipe_qty_positive'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'menu_item_id': self.menu_item_id,
            'menu_item_name': self.menu_item.name if self.menu_item else None,
            'ingredient_id': self.ingredient_id,
            'ingredient_name': self.ingredient.name if self.ingredient else None,
            'unit': self.ingredient.unit if self.ingredient else '',
            'quantity_required': round(float(self.quantity_required), 3)
        }


class Supplier(db.Model):
    """
    Supplier Table: Master record for raw material suppliers.
    """
    __tablename__ = 'supplier'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    contact_person = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'is_active': self.is_active
        }


class PurchaseOrder(db.Model):
    """
    Purchase Order Table: Procurement documents for inventory replenishment.
    """
    __tablename__ = 'purchase_order'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    received_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='Draft', nullable=False)
    total_cost = db.Column(db.Float, default=0.0, nullable=False)
    created_by_staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)

    # Relationships
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy='dynamic', cascade='all, delete-orphan')
    created_by = db.relationship('Staff', backref='purchase_orders_created', foreign_keys=[created_by_staff_id])

    __table_args__ = (
        CheckConstraint("status IN ('Draft', 'Ordered', 'Received', 'Cancelled')", name='ck_po_status'),
        CheckConstraint('total_cost >= 0', name='ck_po_total_positive'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'po_number': self.po_number,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier.name if self.supplier else None,
            'order_date': self.order_date.strftime('%Y-%m-%d %H:%M:%S'),
            'received_date': self.received_date.strftime('%Y-%m-%d %H:%M:%S') if self.received_date else None,
            'status': self.status,
            'total_cost': round(float(self.total_cost), 2),
            'item_count': self.items.count()
        }


class PurchaseOrderItem(db.Model):
    """
    Purchase Order Item Table: Line items in a purchase order.
    """
    __tablename__ = 'purchase_order_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id', ondelete='CASCADE'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_po_item_qty_positive'),
        CheckConstraint('unit_cost >= 0', name='ck_po_item_cost_positive'),
        CheckConstraint('subtotal >= 0', name='ck_po_item_subtotal_positive'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'purchase_order_id': self.purchase_order_id,
            'ingredient_id': self.ingredient_id,
            'ingredient_name': self.ingredient.name if self.ingredient else None,
            'unit': self.ingredient.unit if self.ingredient else '',
            'quantity': round(float(self.quantity), 2),
            'unit_cost': round(float(self.unit_cost), 2),
            'subtotal': round(float(self.subtotal), 2)
        }


class StockTransaction(db.Model):
    """
    Stock Transaction Table (Ledger): Immutable history of inventory changes.
    Guarantees full traceability: restocks, recipe deductions upon order closing, waste, adjustments.
    """
    __tablename__ = 'stock_transaction'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    transaction_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Positive for additions, negative for deductions
    unit_cost = db.Column(db.Float, default=0.0, nullable=False)
    reference_id = db.Column(db.String(50), nullable=True)  # e.g., 'ORDER-101', 'PO-202'
    notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_by_staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)

    created_by = db.relationship('Staff', backref='stock_transactions_recorded', foreign_keys=[created_by_staff_id])

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('Restock', 'Order_Deduction', 'Waste', 'Adjustment')",
            name='ck_stock_transaction_type'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'ingredient_id': self.ingredient_id,
            'ingredient_name': self.ingredient.name if self.ingredient else None,
            'unit': self.ingredient.unit if self.ingredient else '',
            'transaction_type': self.transaction_type,
            'quantity': round(float(self.quantity), 2),
            'unit_cost': round(float(self.unit_cost), 2),
            'reference_id': self.reference_id,
            'notes': self.notes,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': self.created_by.full_name if self.created_by else 'System'
        }


# ==============================================================================
# 6. ORDERS, ORDER ITEMS, BILLING & PAYMENTS
# ==============================================================================

class Orders(db.Model):
    """
    Orders Table: Core transaction header supporting Dine-In, Takeaway, and Delivery.
    """
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    order_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey('dining_table.id'), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    order_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    bill = db.relationship('Bill', backref='order', uselist=False, cascade='all, delete-orphan')
    delivery = db.relationship('Delivery', backref='order', uselist=False, cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint("order_type IN ('Dine-In', 'Takeaway', 'Delivery')", name='ck_order_type'),
        CheckConstraint(
            "status IN ('Pending', 'In-Progress', 'Ready', 'Served', 'Completed', 'Cancelled')",
            name='ck_order_status'
        ),
        CheckConstraint('total_amount >= 0', name='ck_order_total_positive'),
    )

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'order_number': self.order_number,
            'order_type': self.order_type,
            'status': self.status,
            'table_id': self.table_id,
            'table_number': self.table.table_number if self.table else None,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name if self.customer else 'Guest',
            'customer_phone': self.customer.phone if self.customer else None,
            'staff_id': self.staff_id,
            'staff_name': self.staff.full_name if self.staff else None,
            'order_time': self.order_time.strftime('%Y-%m-%d %H:%M:%S'),
            'closed_at': self.closed_at.strftime('%Y-%m-%d %H:%M:%S') if self.closed_at else None,
            'total_amount': round(float(self.total_amount), 2),
            'notes': self.notes,
            'is_active': self.is_active,
            'has_bill': bool(self.bill),
            'bill_id': self.bill.id if self.bill else None,
            'bill_status': self.bill.status if self.bill else 'Unbilled'
        }
        if include_items:
            data['items'] = [item.to_dict() for item in self.order_items]
            if self.delivery:
                data['delivery'] = self.delivery.to_dict()
        return data


class OrderItem(db.Model):
    """
    Order Item Table: Line item details for an order.
    Stores historical price charged at moment of sale (3NF requirement).
    """
    __tablename__ = 'order_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending', nullable=False)

    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_order_item_qty_positive'),
        CheckConstraint('unit_price >= 0', name='ck_order_item_price_positive'),
        CheckConstraint('subtotal >= 0', name='ck_order_item_subtotal_positive'),
        CheckConstraint("status IN ('Pending', 'Preparing', 'Ready', 'Served')", name='ck_order_item_status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'menu_item_id': self.menu_item_id,
            'item_name': self.menu_item.name if self.menu_item else None,
            'quantity': self.quantity,
            'unit_price': round(float(self.unit_price), 2),
            'subtotal': round(float(self.subtotal), 2),
            'notes': self.notes,
            'status': self.status
        }


class Bill(db.Model):
    """
    Bill Table: Financial invoice generated from an order.
    Total amount strictly adheres to: subtotal + tax_amount + delivery_fee - discount_amount.
    Balance strictly equals: total_amount - paid_amount.
    """
    __tablename__ = 'bill'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), unique=True, nullable=False)
    subtotal = db.Column(db.Float, default=0.0, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0, nullable=False)
    delivery_fee = db.Column(db.Float, default=0.0, nullable=False)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0, nullable=False)
    balance = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='Unpaid', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    payments = db.relationship('Payment', backref='bill', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('subtotal >= 0', name='ck_bill_subtotal_positive'),
        CheckConstraint('tax_amount >= 0', name='ck_bill_tax_positive'),
        CheckConstraint('discount_amount >= 0', name='ck_bill_discount_positive'),
        CheckConstraint('delivery_fee >= 0', name='ck_bill_delivery_fee_positive'),
        CheckConstraint('total_amount >= 0', name='ck_bill_total_positive'),
        CheckConstraint('paid_amount >= 0', name='ck_bill_paid_positive'),
        CheckConstraint('balance >= 0', name='ck_bill_balance_positive'),
        CheckConstraint("status IN ('Unpaid', 'Partially_Paid', 'Paid')", name='ck_bill_status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'bill_number': self.bill_number,
            'order_id': self.order_id,
            'order_number': self.order.order_number if self.order else None,
            'subtotal': round(float(self.subtotal), 2),
            'tax_amount': round(float(self.tax_amount), 2),
            'discount_amount': round(float(self.discount_amount), 2),
            'delivery_fee': round(float(self.delivery_fee), 2),
            'total_amount': round(float(self.total_amount), 2),
            'paid_amount': round(float(self.paid_amount), 2),
            'balance': round(float(self.balance), 2),
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'payments': [p.to_dict() for p in self.payments]
        }


class Payment(db.Model):
    """
    Payment Table: Financial transactions applied against a Bill.
    Enforces DBMS Business Rule: Payment cannot exceed the remaining bill balance.
    """
    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_reference = db.Column(db.String(40), unique=True, nullable=False, index=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    transaction_ref = db.Column(db.String(100), nullable=True)
    payment_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_by_staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)

    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_payment_amount_positive'),
        CheckConstraint(
            "payment_method IN ('Cash', 'Credit Card', 'Debit Card', 'Mobile Payment', 'Online')",
            name='ck_payment_method'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'payment_reference': self.payment_reference,
            'bill_id': self.bill_id,
            'bill_number': self.bill.bill_number if self.bill else None,
            'amount': round(float(self.amount), 2),
            'payment_method': self.payment_method,
            'transaction_ref': self.transaction_ref,
            'payment_time': self.payment_time.strftime('%Y-%m-%d %H:%M:%S'),
            'processed_by': self.processed_by.full_name if self.processed_by else 'System'
        }


# ==============================================================================
# 7. DELIVERY DISPATCH & TRACKING
# ==============================================================================

class Delivery(db.Model):
    """
    Delivery Table: Manages the lifecycle of delivery orders.
    Enforces delivery status flow: Pending -> Assigned -> Out for delivery -> Delivered (or Cancelled).
    """
    __tablename__ = 'delivery'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), unique=True, nullable=False)
    rider_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    delivery_zone_id = db.Column(db.Integer, db.ForeignKey('delivery_zone.id'), nullable=False)
    address_id = db.Column(db.Integer, db.ForeignKey('address.id'), nullable=False)
    status = db.Column(db.String(30), default='Pending', nullable=False)
    estimated_time = db.Column(db.DateTime, nullable=True)
    actual_time = db.Column(db.DateTime, nullable=True)
    delivery_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('Pending', 'Assigned', 'Out for delivery', 'Delivered', 'Cancelled')",
            name='ck_delivery_status'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'order_number': self.order.order_number if self.order else None,
            'order_total': round(float(self.order.total_amount), 2) if self.order else 0.0,
            'rider_id': self.rider_id,
            'rider_name': self.rider.full_name if self.rider else 'Unassigned',
            'delivery_zone_id': self.delivery_zone_id,
            'zone_name': self.delivery_zone.name if self.delivery_zone else None,
            'delivery_fee': round(float(self.delivery_zone.delivery_fee), 2) if self.delivery_zone else 0.0,
            'address_id': self.address_id,
            'street': self.delivery_address.street if self.delivery_address else None,
            'city': self.delivery_address.city if self.delivery_address else None,
            'customer_name': self.order.customer.name if self.order and self.order.customer else None,
            'customer_phone': self.order.customer.phone if self.order and self.order.customer else None,
            'status': self.status,
            'estimated_time': self.estimated_time.strftime('%Y-%m-%d %H:%M') if self.estimated_time else None,
            'actual_time': self.actual_time.strftime('%Y-%m-%d %H:%M') if self.actual_time else None,
            'delivery_notes': self.delivery_notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ==============================================================================
# 8. AUDIT LOGGING (DBMS Course Practice: Full System Traceability)
# ==============================================================================

class AuditLog(db.Model):
    """
    Audit Log Table: Central immutable audit trail for security, financial transactions,
    order closures, stock deductions, and administrative operations.
    """
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id', ondelete='SET NULL'), nullable=True)
    username = db.Column(db.String(60), nullable=True)
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.String(50), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username or 'System/Anonymous',
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
