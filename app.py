"""
Restaurant Management System - Flask Application
Full-Featured Backend with RBAC, DBMS Business Rules, and RESTful APIs
"""

import os
import shutil
from datetime import datetime, timedelta, date
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, send_file, g
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db, UserAccount, Staff, DeliveryZone, Customer, Address,
    DiningTable, Reservation, MenuCategory, MenuItem, Ingredient,
    Recipe, Supplier, PurchaseOrder, PurchaseOrderItem, StockTransaction,
    Orders, OrderItem, Bill, Payment, Delivery, AuditLog
)

def create_app(test_config=None):
    app = Flask(__name__)

    # Configuration
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'restaurant.db')

    app.config['SECRET_KEY'] = 'restaurant-secret-key-system-rms-2026'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    # Initialize Database on Start
    with app.app_context():
        db.create_all()

    # --------------------------------------------------------------------------
    # Helper: Audit Logger
    # --------------------------------------------------------------------------
    def log_audit(action, entity_type=None, entity_id=None, details=None):
        try:
            user_id = session.get('user_id')
            username = session.get('username') or 'Anonymous'
            ip_address = request.remote_addr or '127.0.0.1'

            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                details=details,
                ip_address=ip_address,
                timestamp=datetime.utcnow()
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Audit log error: {e}")

    # --------------------------------------------------------------------------
    # Helper: RBAC Decorator
    # --------------------------------------------------------------------------
    def role_required(allowed_roles):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({'error': 'Authentication required. Please log in.'}), 401
                    return redirect(url_for('login_page'))

                user_role = session.get('role')
                if user_role != 'Admin' and user_role not in allowed_roles:
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({'error': f'Forbidden: Role {user_role} not authorized for this action.'}), 403
                    return render_template('login.html', error="Insufficient privileges for requested page.")

                return f(*args, **kwargs)
            return decorated_function
        return decorator

    # --------------------------------------------------------------------------
    # Authentication Routes
    # --------------------------------------------------------------------------
    @app.route('/login', methods=['GET', 'POST'])
    def login_page():
        if request.method == 'GET':
            if 'user_id' in session:
                return redirect(url_for('index_page'))
            return render_template('login.html')

        # POST login request
        data = request.get_json() if request.is_json else request.form
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'}), 400

        user = UserAccount.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            log_audit('LOGIN_FAILED', 'UserAccount', None, f"Failed login attempt for username '{username}'")
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

        if not user.is_active:
            log_audit('LOGIN_REJECTED', 'UserAccount', user.id, f"Inactive user '{username}' attempted login")
            return jsonify({'success': False, 'message': 'This account has been deactivated'}), 403

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        staff = user.staff_profile
        session['staff_id'] = staff.id if staff else None
        session['full_name'] = staff.full_name if staff else user.username

        log_audit('LOGIN_SUCCESS', 'UserAccount', user.id, f"User '{username}' logged in successfully as {user.role}")

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'full_name': session['full_name']
            }
        })

    @app.route('/logout', methods=['GET', 'POST'])
    def logout():
        username = session.get('username')
        user_id = session.get('user_id')
        if user_id:
            log_audit('LOGOUT', 'UserAccount', user_id, f"User '{username}' logged out")
        session.clear()
        if request.is_json:
            return jsonify({'success': True, 'message': 'Logged out successfully'})
        return redirect(url_for('login_page'))

    @app.route('/api/auth/current_user')
    def current_user():
        if 'user_id' not in session:
            return jsonify({'authenticated': False}), 200
        return jsonify({
            'authenticated': True,
            'user_id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'staff_id': session.get('staff_id'),
            'full_name': session.get('full_name')
        })

    # --------------------------------------------------------------------------
    # Main App View
    # --------------------------------------------------------------------------
    @app.route('/')
    def index_page():
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('index.html', user={
            'username': session.get('username'),
            'role': session.get('role'),
            'full_name': session.get('full_name')
        })

    # --------------------------------------------------------------------------
    # Dashboard API
    # --------------------------------------------------------------------------
    @app.route('/api/dashboard/stats')
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef', 'Delivery Rider'])
    def dashboard_stats():
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Today's Revenue (from completed payments today)
        today_payments = db.session.query(db.func.sum(Payment.amount)).filter(Payment.payment_time >= today_start).scalar() or 0.0

        # 2. Today's Total Orders
        today_orders_count = Orders.query.filter(Orders.order_time >= today_start).count()

        # 3. Active Orders (Pending or In-Progress)
        active_orders_count = Orders.query.filter(Orders.status.in_(['Pending', 'In-Progress', 'Ready', 'Served'])).count()

        # 4. Table Occupancy Rate
        total_tables = DiningTable.query.filter_by(is_active=True).count()
        occupied_tables = DiningTable.query.filter_by(is_active=True, status='Occupied').count()
        occupancy_rate = round((occupied_tables / total_tables * 100), 1) if total_tables > 0 else 0.0

        # 5. Pending / Active Deliveries
        pending_deliveries = Delivery.query.filter(Delivery.status.in_(['Pending', 'Assigned', 'Out for delivery'])).count()

        # 6. Low stock alert count
        low_stock_count = Ingredient.query.filter(
            Ingredient.is_active == True,
            Ingredient.current_stock <= Ingredient.minimum_stock
        ).count()

        # 7. Recent 5 orders
        recent_orders = [o.to_dict(include_items=True) for o in Orders.query.order_by(Orders.order_time.desc()).limit(6).all()]

        # 8. Weekly Revenue trend (past 7 days)
        revenue_trend = []
        for i in range(6, -1, -1):
            day_dt = datetime.utcnow().date() - timedelta(days=i)
            day_start = datetime.combine(day_dt, datetime.min.time())
            day_end = datetime.combine(day_dt, datetime.max.time())
            rev = db.session.query(db.func.sum(Payment.amount)).filter(
                Payment.payment_time >= day_start,
                Payment.payment_time <= day_end
            ).scalar() or 0.0
            revenue_trend.append({
                'date': day_dt.strftime('%b %d'),
                'revenue': round(float(rev), 2)
            })

        return jsonify({
            'today_revenue': round(float(today_payments), 2),
            'today_orders_count': today_orders_count,
            'active_orders_count': active_orders_count,
            'occupancy_rate': occupancy_rate,
            'occupied_tables': occupied_tables,
            'total_tables': total_tables,
            'pending_deliveries': pending_deliveries,
            'low_stock_count': low_stock_count,
            'recent_orders': recent_orders,
            'revenue_trend': revenue_trend
        })

    # --------------------------------------------------------------------------
    # Menu Categories & Menu Items API
    # --------------------------------------------------------------------------
    @app.route('/api/menu/categories', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef'])
    def menu_categories():
        if request.method == 'GET':
            cats = MenuCategory.query.filter_by(is_active=True).order_by(MenuCategory.display_order.asc(), MenuCategory.name.asc()).all()
            return jsonify([c.to_dict() for c in cats])

        # POST: Create category (Admin/Manager only)
        if session.get('role') not in ['Admin', 'Manager']:
            return jsonify({'error': 'Unauthorized to modify categories'}), 403

        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'Category name is required'}), 400

        if MenuCategory.query.filter_by(name=name).first():
            return jsonify({'error': f"Category '{name}' already exists"}), 400

        cat = MenuCategory(
            name=name,
            description=data.get('description'),
            display_order=int(data.get('display_order', 0)),
            is_active=True
        )
        db.session.add(cat)
        db.session.commit()
        log_audit('CATEGORY_CREATE', 'MenuCategory', cat.id, f"Created menu category '{name}'")
        return jsonify(cat.to_dict()), 201

    @app.route('/api/menu/categories/<int:cat_id>', methods=['PUT', 'DELETE'])
    @role_required(['Admin', 'Manager'])
    def menu_category_detail(cat_id):
        cat = MenuCategory.query.get_or_404(cat_id)
        if request.method == 'PUT':
            data = request.get_json() or {}
            if 'name' in data:
                cat.name = data['name'].strip()
            if 'description' in data:
                cat.description = data['description']
            if 'display_order' in data:
                cat.display_order = int(data['display_order'])
            db.session.commit()
            log_audit('CATEGORY_UPDATE', 'MenuCategory', cat.id, f"Updated category '{cat.name}'")
            return jsonify(cat.to_dict())

        # DELETE: Soft-delete (DBMS rule: Deactivate instead of delete)
        cat.is_active = False
        db.session.commit()
        log_audit('CATEGORY_DEACTIVATE', 'MenuCategory', cat.id, f"Deactivated category '{cat.name}'")
        return jsonify({'message': f"Category '{cat.name}' deactivated successfully"})

    @app.route('/api/menu/items', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef'])
    def menu_items():
        if request.method == 'GET':
            cat_id = request.args.get('category_id')
            query = MenuItem.query.filter_by(is_active=True)
            if cat_id:
                query = query.filter_by(category_id=int(cat_id))
            items = query.order_by(MenuItem.name.asc()).all()
            return jsonify([i.to_dict() for i in items])

        # POST: Create menu item (Admin/Manager only)
        if session.get('role') not in ['Admin', 'Manager']:
            return jsonify({'error': 'Unauthorized to modify menu items'}), 403

        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        price = data.get('price')
        category_id = data.get('category_id')

        if not name or price is None or not category_id:
            return jsonify({'error': 'Item name, price, and category are required'}), 400

        try:
            price_val = float(price)
            if price_val < 0:
                raise ValueError()
        except ValueError:
            return jsonify({'error': 'Price must be a positive number'}), 400

        if MenuItem.query.filter_by(name=name).first():
            return jsonify({'error': f"Menu item '{name}' already exists"}), 400

        item = MenuItem(
            name=name,
            category_id=int(category_id),
            price=price_val,
            description=data.get('description'),
            is_available=bool(data.get('is_available', True)),
            is_active=True
        )
        db.session.add(item)
        db.session.commit()
        log_audit('MENU_ITEM_CREATE', 'MenuItem', item.id, f"Added menu item '{name}' at ${price_val:.2f}")
        return jsonify(item.to_dict()), 201

    @app.route('/api/menu/items/<int:item_id>', methods=['GET', 'PUT', 'DELETE'])
    @role_required(['Admin', 'Manager', 'Chef'])
    def menu_item_detail(item_id):
        item = MenuItem.query.get_or_404(item_id)
        if request.method == 'GET':
            data = item.to_dict()
            data['recipes'] = [r.to_dict() for r in item.recipes]
            return jsonify(data)

        if session.get('role') not in ['Admin', 'Manager']:
            return jsonify({'error': 'Unauthorized to edit menu items'}), 403

        if request.method == 'PUT':
            data = request.get_json() or {}
            if 'name' in data:
                item.name = data['name'].strip()
            if 'price' in data:
                item.price = float(data['price'])
            if 'category_id' in data:
                item.category_id = int(data['category_id'])
            if 'description' in data:
                item.description = data['description']
            if 'is_available' in data:
                item.is_available = bool(data['is_available'])
            db.session.commit()
            log_audit('MENU_ITEM_UPDATE', 'MenuItem', item.id, f"Updated menu item '{item.name}'")
            return jsonify(item.to_dict())

        # DELETE: Soft-delete (DBMS rule: Deactivate instead of delete)
        item.is_active = False
        db.session.commit()
        log_audit('MENU_ITEM_DEACTIVATE', 'MenuItem', item.id, f"Deactivated menu item '{item.name}'")
        return jsonify({'message': f"Menu item '{item.name}' deactivated successfully"})

    # --------------------------------------------------------------------------
    # Tables & Reservations (DBMS Rule: No Double-Booking Overlap)
    # --------------------------------------------------------------------------
    @app.route('/api/tables', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter'])
    def dining_tables():
        if request.method == 'GET':
            tables = DiningTable.query.filter_by(is_active=True).order_by(DiningTable.table_number.asc()).all()
            return jsonify([t.to_dict() for t in tables])

        # POST: Create Table (Admin/Manager only)
        if session.get('role') not in ['Admin', 'Manager']:
            return jsonify({'error': 'Unauthorized to create tables'}), 403

        data = request.get_json() or {}
        table_number = (data.get('table_number') or '').strip().upper()
        capacity = data.get('capacity')
        location_area = data.get('location_area', 'Main Dining')

        if not table_number or not capacity:
            return jsonify({'error': 'Table number and capacity are required'}), 400

        if DiningTable.query.filter_by(table_number=table_number).first():
            return jsonify({'error': f"Table '{table_number}' already exists"}), 400

        t = DiningTable(
            table_number=table_number,
            capacity=int(capacity),
            location_area=location_area,
            status='Available',
            is_active=True
        )
        db.session.add(t)
        db.session.commit()
        log_audit('TABLE_CREATE', 'DiningTable', t.id, f"Created table {table_number} with capacity {capacity}")
        return jsonify(t.to_dict()), 201

    @app.route('/api/tables/<int:table_id>/status', methods=['PUT'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter'])
    def update_table_status(table_id):
        t = DiningTable.query.get_or_404(table_id)
        data = request.get_json() or {}
        new_status = data.get('status')
        if new_status not in ['Available', 'Occupied', 'Reserved']:
            return jsonify({'error': 'Invalid status. Must be Available, Occupied, or Reserved'}), 400

        old_status = t.status
        t.status = new_status
        db.session.commit()
        log_audit('TABLE_STATUS_CHANGE', 'DiningTable', t.id, f"Changed table {t.table_number} status from {old_status} to {new_status}")
        return jsonify(t.to_dict())

    @app.route('/api/reservations', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter'])
    def reservations_list():
        if request.method == 'GET':
            res_list = Reservation.query.order_by(Reservation.reservation_time.desc()).limit(50).all()
            return jsonify([r.to_dict() for r in res_list])

        # POST: Create Reservation with Strict Conflict Prevention Rule
        data = request.get_json() or {}
        customer_id = data.get('customer_id')
        table_id = data.get('dining_table_id')
        res_time_str = data.get('reservation_time')
        party_size = data.get('party_size')

        if not customer_id or not table_id or not res_time_str or not party_size:
            return jsonify({'error': 'Customer, table, reservation time, and party size are required'}), 400

        try:
            res_dt = datetime.strptime(res_time_str, '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                res_dt = datetime.fromisoformat(res_time_str)
            except Exception:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD HH:MM'}), 400

        table = DiningTable.query.get_or_404(table_id)
        if int(party_size) > table.capacity:
            return jsonify({'error': f"Party size ({party_size}) exceeds table capacity ({table.capacity})"}), 400

        # DBMS Business Rule: NO DOUBLE-BOOKING A TABLE
        # A 2-hour window is reserved per booking. Table cannot have conflicting active reservations.
        window_start = res_dt - timedelta(hours=2)
        window_end = res_dt + timedelta(hours=2)

        conflict = Reservation.query.filter(
            Reservation.dining_table_id == table_id,
            Reservation.status.in_(['Confirmed', 'Seated']),
            Reservation.reservation_time >= window_start,
            Reservation.reservation_time <= window_end
        ).first()

        if conflict:
            conf_time = conflict.reservation_time.strftime('%Y-%m-%d %H:%M')
            return jsonify({
                'error': f"Double-Booking conflict: Table {table.table_number} is already booked around {conf_time}. Please select another table or time."
            }), 409

        reservation = Reservation(
            customer_id=int(customer_id),
            dining_table_id=table.id,
            reservation_time=res_dt,
            party_size=int(party_size),
            status='Confirmed',
            special_requests=data.get('special_requests')
        )
        db.session.add(reservation)
        # Update table status to Reserved if reservation is within 1 hour
        if abs((res_dt - datetime.utcnow()).total_seconds()) < 3600:
            table.status = 'Reserved'

        db.session.commit()
        log_audit('RESERVATION_CREATE', 'Reservation', reservation.id, f"Booked Table {table.table_number} for {res_dt.strftime('%Y-%m-%d %H:%M')} (Party: {party_size})")
        return jsonify(reservation.to_dict()), 201

    @app.route('/api/reservations/<int:res_id>/status', methods=['PUT'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter'])
    def update_reservation_status(res_id):
        res = Reservation.query.get_or_404(res_id)
        data = request.get_json() or {}
        new_status = data.get('status')
        if new_status not in ['Confirmed', 'Seated', 'Cancelled', 'Completed']:
            return jsonify({'error': 'Invalid reservation status'}), 400

        res.status = new_status
        if new_status == 'Seated':
            res.table.status = 'Occupied'
        elif new_status in ['Cancelled', 'Completed']:
            res.table.status = 'Available'

        db.session.commit()
        log_audit('RESERVATION_STATUS', 'Reservation', res.id, f"Reservation status updated to {new_status}")
        return jsonify(res.to_dict())

    # --------------------------------------------------------------------------
    # Orders API (Dine-in / Takeaway / Delivery)
    # --------------------------------------------------------------------------
    @app.route('/api/orders', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef', 'Delivery Rider'])
    def orders_endpoint():
        if request.method == 'GET':
            status_filter = request.args.get('status')
            type_filter = request.args.get('type')
            query = Orders.query.filter_by(is_active=True)

            if status_filter:
                query = query.filter_by(status=status_filter)
            if type_filter:
                query = query.filter_by(order_type=type_filter)

            orders_list = query.order_by(Orders.order_time.desc()).limit(100).all()
            return jsonify([o.to_dict(include_items=True) for o in orders_list])

        # POST: Create Order (Dine-in, Takeaway, Delivery)
        data = request.get_json() or {}
        order_type = data.get('order_type')
        items_data = data.get('items', [])
        notes = data.get('notes')

        if order_type not in ['Dine-In', 'Takeaway', 'Delivery']:
            return jsonify({'error': "Order type must be 'Dine-In', 'Takeaway', or 'Delivery'"}), 400

        if not items_data or len(items_data) == 0:
            return jsonify({'error': 'Order must contain at least one menu item'}), 400

        # Generate unique order number
        order_number = f"ORD-{datetime.utcnow().strftime('%y%m%d')}-{Orders.query.count() + 101}"

        table_id = None
        customer_id = data.get('customer_id')
        address_id = data.get('address_id')
        delivery_zone = None
        delivery_fee = 0.0

        if order_type == 'Dine-In':
            table_id = data.get('table_id')
            if not table_id:
                return jsonify({'error': 'Dine-In orders require a dining table'}), 400
            table = DiningTable.query.get(table_id)
            if not table or not table.is_active:
                return jsonify({'error': 'Selected table is invalid or inactive'}), 400
            table.status = 'Occupied'

        elif order_type == 'Delivery':
            # DBMS Business Rule: Delivery orders need an address in a delivery zone and meet its minimum order
            if not customer_id or not address_id:
                return jsonify({'error': 'Delivery orders require a customer and delivery address'}), 400

            address = Address.query.get(address_id)
            if not address or not address.is_active:
                return jsonify({'error': 'Selected delivery address is invalid'}), 400

            delivery_zone = address.delivery_zone
            if not delivery_zone or not delivery_zone.is_active:
                return jsonify({'error': 'Address delivery zone is inactive or not found'}), 400

            delivery_fee = float(delivery_zone.delivery_fee)

        # Calculate line items & subtotal
        subtotal = 0.0
        line_items_to_create = []

        for item_entry in items_data:
            m_id = item_entry.get('menu_item_id')
            qty = item_entry.get('quantity', 1)
            item_notes = item_entry.get('notes')

            menu_item = MenuItem.query.get(m_id)
            if not menu_item or not menu_item.is_active or not menu_item.is_available:
                return jsonify({'error': f"Menu item #{m_id} is unavailable"}), 400

            if int(qty) <= 0:
                return jsonify({'error': 'Quantity must be greater than 0'}), 400

            item_subtotal = float(menu_item.price) * int(qty)
            subtotal += item_subtotal

            line_items_to_create.append({
                'menu_item_id': menu_item.id,
                'quantity': int(qty),
                'unit_price': float(menu_item.price),
                'subtotal': item_subtotal,
                'notes': item_notes,
                'status': 'Pending'
            })

        # Validate minimum delivery order requirement
        if order_type == 'Delivery' and delivery_zone:
            if subtotal < float(delivery_zone.min_order_amount):
                return jsonify({
                    'error': f"Minimum order for zone '{delivery_zone.name}' is ${delivery_zone.min_order_amount:.2f}. Current items subtotal is ${subtotal:.2f}."
                }), 400

        # Tax calculation (standard 8% restaurant tax)
        tax_amount = round(subtotal * 0.08, 2)
        total_amount = round(subtotal + tax_amount + delivery_fee, 2)

        # Create Order entity
        order = Orders(
            order_number=order_number,
            order_type=order_type,
            status='Pending',
            table_id=table_id,
            customer_id=customer_id,
            staff_id=session.get('staff_id'),
            order_time=datetime.utcnow(),
            total_amount=total_amount,
            notes=notes,
            is_active=True
        )
        db.session.add(order)
        db.session.flush()

        # Add Order Items
        for li in line_items_to_create:
            oi = OrderItem(
                order_id=order.id,
                menu_item_id=li['menu_item_id'],
                quantity=li['quantity'],
                unit_price=li['unit_price'],
                subtotal=li['subtotal'],
                notes=li['notes'],
                status='Pending'
            )
            db.session.add(oi)

        # Automatically Create Bill entity (DBMS rule: Bill total includes delivery fee)
        bill_number = f"BILL-{order.order_number}"
        bill = Bill(
            bill_number=bill_number,
            order_id=order.id,
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=0.00,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            paid_amount=0.00,
            balance=total_amount,
            status='Unpaid',
            created_at=datetime.utcnow()
        )
        db.session.add(bill)

        # If Delivery order: Create Delivery tracking entry
        if order_type == 'Delivery':
            delivery_record = Delivery(
                order_id=order.id,
                rider_id=None,
                delivery_zone_id=delivery_zone.id,
                address_id=address_id,
                status='Pending',
                estimated_time=datetime.utcnow() + timedelta(minutes=delivery_zone.estimated_delivery_minutes),
                delivery_notes=data.get('delivery_notes') or notes,
                created_at=datetime.utcnow()
            )
            db.session.add(delivery_record)

        db.session.commit()
        log_audit('ORDER_CREATE', 'Orders', order.id, f"Created {order_type} order {order_number} for total ${total_amount:.2f}")

        return jsonify(order.to_dict(include_items=True)), 201

    @app.route('/api/orders/<int:order_id>')
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef', 'Delivery Rider'])
    def get_order_detail(order_id):
        order = Orders.query.get_or_404(order_id)
        return jsonify(order.to_dict(include_items=True))

    # --------------------------------------------------------------------------
    # DBMS Rule: Order Status & Closing Deducts Stock via Recipe in One Transaction
    # --------------------------------------------------------------------------
    @app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef'])
    def update_order_status(order_id):
        order = Orders.query.get_or_404(order_id)
        data = request.get_json() or {}
        new_status = data.get('status')

        valid_transitions = ['Pending', 'In-Progress', 'Ready', 'Served', 'Completed', 'Cancelled']
        if new_status not in valid_transitions:
            return jsonify({'error': f'Invalid status transition. Allowed: {valid_transitions}'}), 400

        old_status = order.status
        order.status = new_status

        # If order is Cancelled
        if new_status == 'Cancelled':
            if order.table:
                order.table.status = 'Available'
            if order.delivery:
                order.delivery.status = 'Cancelled'
            db.session.commit()
            log_audit('ORDER_CANCELLED', 'Orders', order.id, f"Order {order.order_number} was cancelled")
            return jsonify(order.to_dict(include_items=True))

        # DBMS Business Rule: CLOSING AN ORDER DEDUCTS INGREDIENT STOCK VIA RECIPE IN ONE TRANSACTION
        if new_status == 'Completed' and old_status != 'Completed':
            order.closed_at = datetime.utcnow()

            # Release table if Dine-In
            if order.table:
                order.table.status = 'Available'

            # Deduct ingredient inventory atomically via recipes
            try:
                for item in order.order_items:
                    # Find all ingredients linked in the recipe for this menu item
                    recipes = Recipe.query.filter_by(menu_item_id=item.menu_item_id).all()
                    for r in recipes:
                        qty_to_deduct = float(r.quantity_required) * int(item.quantity)
                        ingredient = r.ingredient

                        # Deduct stock (ensure non-negative or floor at 0)
                        ingredient.current_stock = max(0.0, float(ingredient.current_stock) - qty_to_deduct)

                        # Write immutable ledger record into stock_transaction
                        ledger_entry = StockTransaction(
                            ingredient_id=ingredient.id,
                            transaction_type='Order_Deduction',
                            quantity=-qty_to_deduct,
                            unit_cost=ingredient.cost_per_unit,
                            reference_id=order.order_number,
                            notes=f"Recipe deduction for {item.quantity}x {item.menu_item.name}",
                            created_by_staff_id=session.get('staff_id'),
                            timestamp=datetime.utcnow()
                        )
                        db.session.add(ledger_entry)

                db.session.commit()
                log_audit('ORDER_CLOSED', 'Orders', order.id, f"Order {order.order_number} closed. Stock deducted via recipe in transaction.")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error during order close inventory deduction: {e}")
                return jsonify({'error': f"Failed to close order: {str(e)}"}), 500

            return jsonify(order.to_dict(include_items=True))

        db.session.commit()
        log_audit('ORDER_STATUS_UPDATE', 'Orders', order.id, f"Order {order.order_number} status changed from {old_status} to {new_status}")
        return jsonify(order.to_dict(include_items=True))

    # --------------------------------------------------------------------------
    # Kitchen Display System (KDS) Screen API
    # --------------------------------------------------------------------------
    @app.route('/api/kitchen/tickets')
    @role_required(['Admin', 'Manager', 'Chef', 'Waiter'])
    def kitchen_tickets():
        # Get active orders: Pending or In-Progress
        tickets = Orders.query.filter(
            Orders.is_active == True,
            Orders.status.in_(['Pending', 'In-Progress'])
        ).order_by(Orders.order_time.asc()).all()

        ticket_data = []
        for t in tickets:
            elapsed_minutes = int((datetime.utcnow() - t.order_time).total_seconds() / 60)
            ticket_data.append({
                'order_id': t.id,
                'order_number': t.order_number,
                'order_type': t.order_type,
                'table_number': t.table.table_number if t.table else None,
                'status': t.status,
                'order_time': t.order_time.strftime('%H:%M'),
                'elapsed_minutes': elapsed_minutes,
                'notes': t.notes,
                'items': [item.to_dict() for item in t.order_items]
            })
        return jsonify(ticket_data)

    @app.route('/api/kitchen/items/<int:item_id>/status', methods=['PUT'])
    @role_required(['Admin', 'Manager', 'Chef'])
    def update_kitchen_item_status(item_id):
        item = OrderItem.query.get_or_404(item_id)
        data = request.get_json() or {}
        new_status = data.get('status')
        if new_status not in ['Pending', 'Preparing', 'Ready', 'Served']:
            return jsonify({'error': 'Invalid item status'}), 400

        item.status = new_status

        # If any item is preparing, set order status to In-Progress
        order = item.order
        if new_status == 'Preparing' and order.status == 'Pending':
            order.status = 'In-Progress'

        # Check if all items in the order are ready
        all_ready = all(i.status in ['Ready', 'Served'] for i in order.order_items)
        if all_ready and order.status != 'Ready':
            order.status = 'Ready'

        db.session.commit()
        log_audit('KITCHEN_ITEM_STATUS', 'OrderItem', item.id, f"Item '{item.menu_item.name}' status set to {new_status}")
        return jsonify(item.to_dict())

    # --------------------------------------------------------------------------
    # Billing & Payments (DBMS Rule: Payment cannot exceed bill balance)
    # --------------------------------------------------------------------------
    @app.route('/api/bills/<int:bill_id>')
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter'])
    def get_bill_detail(bill_id):
        bill = Bill.query.get_or_404(bill_id)
        return jsonify(bill.to_dict())

    @app.route('/api/bills/<int:bill_id>/pay', methods=['POST'])
    @role_required(['Admin', 'Manager', 'Cashier'])
    def process_payment(bill_id):
        bill = Bill.query.get_or_404(bill_id)
        data = request.get_json() or {}

        try:
            amount = round(float(data.get('amount', 0)), 2)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            return jsonify({'error': 'Payment amount must be greater than 0'}), 400

        # DBMS Business Rule: PAYMENT CANNOT EXCEED THE BILL BALANCE
        current_balance = round(float(bill.balance), 2)
        if amount > current_balance:
            return jsonify({
                'error': f"Payment amount (${amount:.2f}) cannot exceed current bill balance (${current_balance:.2f})."
            }), 400

        payment_method = data.get('payment_method')
        if payment_method not in ['Cash', 'Credit Card', 'Debit Card', 'Mobile Payment', 'Online']:
            return jsonify({'error': 'Invalid payment method selected'}), 400

        # Create unique payment reference
        pmt_ref = f"PMT-{datetime.utcnow().strftime('%y%m%d%H%M')}-{Payment.query.count() + 101}"

        payment = Payment(
            payment_reference=pmt_ref,
            bill_id=bill.id,
            amount=amount,
            payment_method=payment_method,
            transaction_ref=data.get('transaction_ref') or f"POS-{session.get('username')}",
            payment_time=datetime.utcnow(),
            processed_by_staff_id=session.get('staff_id')
        )
        db.session.add(payment)

        # Update Bill balances
        bill.paid_amount = round(float(bill.paid_amount) + amount, 2)
        bill.balance = round(float(bill.total_amount) - float(bill.paid_amount), 2)

        if bill.balance <= 0.001:
            bill.balance = 0.00
            bill.status = 'Paid'
        else:
            bill.status = 'Partially_Paid'

        db.session.commit()
        log_audit('PAYMENT_PROCESSED', 'Payment', payment.id, f"Payment of ${amount:.2f} applied to {bill.bill_number}. Remaining: ${bill.balance:.2f}")

        return jsonify({
            'success': True,
            'message': f"Payment of ${amount:.2f} received successfully.",
            'bill': bill.to_dict(),
            'payment': payment.to_dict()
        }), 201

    # --------------------------------------------------------------------------
    # Delivery Management (DBMS Rule: Pending -> Assigned -> Out for delivery -> Delivered)
    # --------------------------------------------------------------------------
    @app.route('/api/delivery/zones', methods=['GET', 'POST', 'PUT'])
    @role_required(['Admin', 'Manager', 'Cashier'])
    def delivery_zones():
        if request.method == 'GET':
            zones = DeliveryZone.query.filter_by(is_active=True).all()
            return jsonify([z.to_dict() for z in zones])

        if session.get('role') not in ['Admin', 'Manager']:
            return jsonify({'error': 'Unauthorized to modify zones'}), 403

        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        fee = data.get('delivery_fee', 0.0)
        min_ord = data.get('min_order_amount', 0.0)
        est_min = data.get('estimated_delivery_minutes', 30)

        zone = DeliveryZone(
            name=name,
            delivery_fee=float(fee),
            min_order_amount=float(min_ord),
            estimated_delivery_minutes=int(est_min),
            is_active=True
        )
        db.session.add(zone)
        db.session.commit()
        log_audit('ZONE_CREATE', 'DeliveryZone', zone.id, f"Created delivery zone '{name}'")
        return jsonify(zone.to_dict()), 201

    @app.route('/api/delivery/list')
    @role_required(['Admin', 'Manager', 'Cashier', 'Delivery Rider'])
    def deliveries_list():
        status_filter = request.args.get('status')
        rider_filter = request.args.get('rider_id')

        query = Delivery.query

        # If user is a Delivery Rider, restrict to their deliveries unless explicitly Admin/Manager
        user_role = session.get('role')
        if user_role == 'Delivery Rider':
            staff_id = session.get('staff_id')
            query = query.filter_by(rider_id=staff_id)
        elif rider_filter:
            query = query.filter_by(rider_id=int(rider_filter))

        if status_filter:
            query = query.filter_by(status=status_filter)

        deliveries = query.order_by(Delivery.created_at.desc()).limit(50).all()
        return jsonify([d.to_dict() for d in deliveries])

    @app.route('/api/delivery/<int:delivery_id>/assign', methods=['POST'])
    @role_required(['Admin', 'Manager', 'Cashier'])
    def assign_delivery_rider(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)
        data = request.get_json() or {}
        rider_id = data.get('rider_id')

        rider = Staff.query.get_or_404(rider_id)
        if rider.role != 'Delivery Rider' or not rider.is_active:
            return jsonify({'error': 'Selected staff member is not an active delivery rider'}), 400

        delivery.rider_id = rider.id
        delivery.status = 'Assigned'
        db.session.commit()

        log_audit('DELIVERY_ASSIGNED', 'Delivery', delivery.id, f"Delivery for {delivery.order.order_number} assigned to {rider.full_name}")
        return jsonify(delivery.to_dict())

    @app.route('/api/delivery/<int:delivery_id>/status', methods=['PUT'])
    @role_required(['Admin', 'Manager', 'Delivery Rider'])
    def update_delivery_status(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)
        data = request.get_json() or {}
        new_status = data.get('status')

        # DBMS Business Rule: DELIVERY STATUS FLOWS: Pending -> Assigned -> Out for delivery -> Delivered (or Cancelled)
        flow = {
            'Pending': ['Assigned', 'Cancelled'],
            'Assigned': ['Out for delivery', 'Cancelled'],
            'Out for delivery': ['Delivered', 'Cancelled'],
            'Delivered': [],
            'Cancelled': []
        }

        current_status = delivery.status
        allowed_next = flow.get(current_status, [])

        # Admin override or strict flow enforcement
        if session.get('role') != 'Admin' and new_status not in allowed_next:
            return jsonify({
                'error': f"Invalid delivery transition: Cannot change from '{current_status}' to '{new_status}'. Allowed: {allowed_next}"
            }), 400

        delivery.status = new_status
        if new_status == 'Delivered':
            delivery.actual_time = datetime.utcnow()
            # If order is ready or served, set order status to Completed
            if delivery.order.status != 'Completed':
                delivery.order.status = 'Completed'
                delivery.order.closed_at = datetime.utcnow()

        db.session.commit()
        log_audit('DELIVERY_STATUS_UPDATE', 'Delivery', delivery.id, f"Delivery for {delivery.order.order_number} changed to {new_status}")
        return jsonify(delivery.to_dict())

    # --------------------------------------------------------------------------
    # Inventory, Recipes, Suppliers & Purchase Orders
    # --------------------------------------------------------------------------
    @app.route('/api/inventory/ingredients', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Chef'])
    def inventory_ingredients():
        if request.method == 'GET':
            low_stock_only = request.args.get('low_stock') == 'true'
            query = Ingredient.query.filter_by(is_active=True)
            if low_stock_only:
                query = query.filter(Ingredient.current_stock <= Ingredient.minimum_stock)
            ings = query.order_by(Ingredient.name.asc()).all()
            return jsonify([i.to_dict() for i in ings])

        # POST: Create new Ingredient (Admin/Manager only)
        if session.get('role') not in ['Admin', 'Manager']:
            return jsonify({'error': 'Unauthorized to create ingredients'}), 403

        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        unit = (data.get('unit') or '').strip()
        stock = data.get('current_stock', 0.0)
        min_stk = data.get('minimum_stock', 5.0)
        cost = data.get('cost_per_unit', 0.0)

        if not name or not unit:
            return jsonify({'error': 'Name and measurement unit are required'}), 400

        if Ingredient.query.filter_by(name=name).first():
            return jsonify({'error': f"Ingredient '{name}' already exists"}), 400

        ing = Ingredient(
            name=name,
            unit=unit,
            current_stock=float(stock),
            minimum_stock=float(min_stk),
            cost_per_unit=float(cost),
            is_active=True
        )
        db.session.add(ing)
        db.session.commit()
        log_audit('INGREDIENT_CREATE', 'Ingredient', ing.id, f"Created ingredient '{name}' ({unit})")
        return jsonify(ing.to_dict()), 201

    @app.route('/api/inventory/adjust', methods=['POST'])
    @role_required(['Admin', 'Manager', 'Chef'])
    def adjust_stock():
        data = request.get_json() or {}
        ingredient_id = data.get('ingredient_id')
        adj_type = data.get('transaction_type')  # Restock, Waste, Adjustment
        quantity = data.get('quantity')
        notes = data.get('notes')

        if not ingredient_id or not adj_type or quantity is None:
            return jsonify({'error': 'Ingredient, transaction type, and quantity are required'}), 400

        if adj_type not in ['Restock', 'Waste', 'Adjustment']:
            return jsonify({'error': 'Invalid transaction type'}), 400

        try:
            qty_val = float(quantity)
        except ValueError:
            return jsonify({'error': 'Quantity must be numeric'}), 400

        ing = Ingredient.query.get_or_404(ingredient_id)

        # Calculate new stock
        delta = qty_val if adj_type == 'Restock' else -abs(qty_val)
        new_stock = max(0.0, float(ing.current_stock) + delta)
        ing.current_stock = new_stock

        # Add Ledger record
        ledger = StockTransaction(
            ingredient_id=ing.id,
            transaction_type=adj_type,
            quantity=delta,
            unit_cost=ing.cost_per_unit,
            reference_id=f"MANUAL-{session.get('username')}",
            notes=notes or f"Manual {adj_type} performed by {session.get('username')}",
            created_by_staff_id=session.get('staff_id'),
            timestamp=datetime.utcnow()
        )
        db.session.add(ledger)
        db.session.commit()

        log_audit('STOCK_ADJUSTMENT', 'Ingredient', ing.id, f"{adj_type} of {qty_val} {ing.unit} for '{ing.name}'. New stock: {new_stock}")
        return jsonify({'message': 'Stock updated successfully', 'ingredient': ing.to_dict()})

    @app.route('/api/inventory/recipes', methods=['GET', 'POST', 'DELETE'])
    @role_required(['Admin', 'Manager', 'Chef'])
    def manage_recipes():
        if request.method == 'GET':
            item_id = request.args.get('menu_item_id')
            query = Recipe.query
            if item_id:
                query = query.filter_by(menu_item_id=int(item_id))
            recipes = query.all()
            return jsonify([r.to_dict() for r in recipes])

        if request.method == 'POST':
            data = request.get_json() or {}
            item_id = data.get('menu_item_id')
            ing_id = data.get('ingredient_id')
            qty_req = data.get('quantity_required')

            if not item_id or not ing_id or not qty_req:
                return jsonify({'error': 'Menu item, ingredient, and quantity required are mandatory'}), 400

            # Check if composite pair already exists
            existing = Recipe.query.filter_by(menu_item_id=int(item_id), ingredient_id=int(ing_id)).first()
            if existing:
                existing.quantity_required = float(qty_req)
                db.session.commit()
                return jsonify(existing.to_dict())

            recipe = Recipe(
                menu_item_id=int(item_id),
                ingredient_id=int(ing_id),
                quantity_required=float(qty_req)
            )
            db.session.add(recipe)
            db.session.commit()
            log_audit('RECIPE_CREATE', 'Recipe', recipe.id, f"Linked ingredient #{ing_id} ({qty_req}) to menu item #{item_id}")
            return jsonify(recipe.to_dict()), 201

        # DELETE: Remove recipe link
        data = request.get_json() or {}
        recipe_id = data.get('id')
        rec = Recipe.query.get_or_404(recipe_id)
        db.session.delete(rec)
        db.session.commit()
        return jsonify({'message': 'Recipe ingredient removed successfully'})

    @app.route('/api/inventory/suppliers', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager'])
    def suppliers_list():
        if request.method == 'GET':
            sups = Supplier.query.filter_by(is_active=True).all()
            return jsonify([s.to_dict() for s in sups])

        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        phone = (data.get('phone') or '').strip()
        if not name or not phone:
            return jsonify({'error': 'Supplier name and phone are required'}), 400

        sup = Supplier(
            name=name,
            contact_person=data.get('contact_person'),
            phone=phone,
            email=data.get('email'),
            address=data.get('address'),
            is_active=True
        )
        db.session.add(sup)
        db.session.commit()
        log_audit('SUPPLIER_CREATE', 'Supplier', sup.id, f"Created supplier '{name}'")
        return jsonify(sup.to_dict()), 201

    @app.route('/api/inventory/purchase-orders', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager'])
    def purchase_orders():
        if request.method == 'GET':
            pos = PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc()).all()
            return jsonify([p.to_dict() for p in pos])

        data = request.get_json() or {}
        supplier_id = data.get('supplier_id')
        items = data.get('items', [])

        if not supplier_id or not items:
            return jsonify({'error': 'Supplier and purchase items are required'}), 400

        po_num = f"PO-{datetime.utcnow().strftime('%y%m%d')}-{PurchaseOrder.query.count() + 101}"

        total_cost = 0.0
        po_items_to_add = []
        for itm in items:
            ing_id = itm.get('ingredient_id')
            qty = float(itm.get('quantity', 0))
            cost = float(itm.get('unit_cost', 0))
            sub = round(qty * cost, 2)
            total_cost += sub
            po_items_to_add.append((ing_id, qty, cost, sub))

        po = PurchaseOrder(
            po_number=po_num,
            supplier_id=supplier_id,
            order_date=datetime.utcnow(),
            status='Draft',
            total_cost=total_cost,
            created_by_staff_id=session.get('staff_id')
        )
        db.session.add(po)
        db.session.flush()

        for ing_id, qty, cost, sub in po_items_to_add:
            poi = PurchaseOrderItem(
                purchase_order_id=po.id,
                ingredient_id=ing_id,
                quantity=qty,
                unit_cost=cost,
                subtotal=sub
            )
            db.session.add(poi)

        db.session.commit()
        log_audit('PO_CREATE', 'PurchaseOrder', po.id, f"Created purchase order {po_num} for total ${total_cost:.2f}")
        return jsonify(po.to_dict()), 201

    @app.route('/api/inventory/purchase-orders/<int:po_id>/receive', methods=['POST'])
    @role_required(['Admin', 'Manager'])
    def receive_purchase_order(po_id):
        po = PurchaseOrder.query.get_or_404(po_id)
        if po.status == 'Received':
            return jsonify({'error': 'Purchase order has already been received'}), 400

        po.status = 'Received'
        po.received_date = datetime.utcnow()

        # Automatically increment ingredient stock and record in stock_transaction ledger
        for item in po.items:
            ing = item.ingredient
            ing.current_stock = float(ing.current_stock) + float(item.quantity)
            ing.cost_per_unit = float(item.unit_cost)

            ledger = StockTransaction(
                ingredient_id=ing.id,
                transaction_type='Restock',
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                reference_id=po.po_number,
                notes=f"Receipt from PO {po.po_number} ({po.supplier.name})",
                created_by_staff_id=session.get('staff_id'),
                timestamp=datetime.utcnow()
            )
            db.session.add(ledger)

        db.session.commit()
        log_audit('PO_RECEIVED', 'PurchaseOrder', po.id, f"Received PO {po.po_number}. Inventory replenished.")
        return jsonify(po.to_dict())

    @app.route('/api/inventory/ledger')
    @role_required(['Admin', 'Manager', 'Chef'])
    def stock_ledger():
        limit = int(request.args.get('limit', 50))
        txs = StockTransaction.query.order_by(StockTransaction.timestamp.desc()).limit(limit).all()
        return jsonify([t.to_dict() for t in txs])

    # --------------------------------------------------------------------------
    # Customers & Addresses API
    # --------------------------------------------------------------------------
    @app.route('/api/customers', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager', 'Cashier', 'Waiter'])
    def customers_list():
        if request.method == 'GET':
            search = request.args.get('q', '').strip()
            query = Customer.query.filter_by(is_active=True)
            if search:
                query = query.filter((Customer.name.ilike(f'%{search}%')) | (Customer.phone.ilike(f'%{search}%')))
            custs = query.order_by(Customer.name.asc()).limit(30).all()

            results = []
            for c in custs:
                c_dict = c.to_dict()
                c_dict['addresses'] = [a.to_dict() for a in c.addresses.filter_by(is_active=True).all()]
                results.append(c_dict)
            return jsonify(results)

        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        phone = (data.get('phone') or '').strip()
        if not name or not phone:
            return jsonify({'error': 'Customer name and phone are required'}), 400

        existing = Customer.query.filter_by(phone=phone).first()
        if existing:
            return jsonify({'error': f"Customer with phone '{phone}' already registered ({existing.name})"}), 400

        cust = Customer(
            name=name,
            phone=phone,
            email=data.get('email'),
            is_active=True
        )
        db.session.add(cust)
        db.session.flush()

        # If initial address provided
        street = data.get('street')
        zone_id = data.get('delivery_zone_id')
        if street and zone_id:
            addr = Address(
                customer_id=cust.id,
                delivery_zone_id=int(zone_id),
                street=street.strip(),
                city=data.get('city', 'Metropolis').strip(),
                postal_code=data.get('postal_code'),
                notes=data.get('notes'),
                is_active=True
            )
            db.session.add(addr)

        db.session.commit()
        log_audit('CUSTOMER_CREATE', 'Customer', cust.id, f"Created customer profile for '{name}'")
        return jsonify(cust.to_dict()), 201

    # --------------------------------------------------------------------------
    # Staff & User Management (Role-based Administration)
    # --------------------------------------------------------------------------
    @app.route('/api/staff', methods=['GET', 'POST'])
    @role_required(['Admin', 'Manager'])
    def staff_list():
        if request.method == 'GET':
            role_filter = request.args.get('role')
            query = Staff.query.filter_by(is_active=True)
            if role_filter:
                query = query.filter_by(role=role_filter)
            staff_members = query.order_by(Staff.first_name.asc()).all()
            return jsonify([s.to_dict() for s in staff_members])

        if session.get('role') != 'Admin':
            return jsonify({'error': 'Only Admin can register new staff members'}), 403

        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        role = data.get('role')
        fname = (data.get('first_name') or '').strip()
        lname = (data.get('last_name') or '').strip()
        phone = (data.get('phone') or '').strip()

        if not username or not password or not role or not fname or not lname or not phone:
            return jsonify({'error': 'All user and staff fields are required'}), 400

        if role not in ['Admin', 'Manager', 'Cashier', 'Waiter', 'Chef', 'Delivery Rider']:
            return jsonify({'error': 'Invalid role specified'}), 400

        if UserAccount.query.filter_by(username=username).first():
            return jsonify({'error': f"Username '{username}' is already taken"}), 400

        # Create UserAccount with Salted Hash
        user = UserAccount(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            is_active=True
        )
        db.session.add(user)
        db.session.flush()

        # Create Staff Profile
        staff = Staff(
            user_account_id=user.id,
            first_name=fname,
            last_name=lname,
            phone=phone,
            role=role,
            hire_date=date.today(),
            is_active=True
        )
        db.session.add(staff)
        db.session.commit()

        log_audit('STAFF_CREATE', 'Staff', staff.id, f"Registered new staff member {fname} {lname} as {role}")
        return jsonify(staff.to_dict()), 201

    @app.route('/api/users')
    @role_required(['Admin'])
    def users_list():
        users = UserAccount.query.all()
        return jsonify([u.to_dict() for u in users])

    @app.route('/api/users/<int:user_id>/toggle-active', methods=['PUT'])
    @role_required(['Admin'])
    def toggle_user_active(user_id):
        user = UserAccount.query.get_or_404(user_id)
        if user.id == session.get('user_id'):
            return jsonify({'error': 'Cannot deactivate your own active session account'}), 400

        user.is_active = not user.is_active
        if user.staff_profile:
            user.staff_profile.is_active = user.is_active

        db.session.commit()
        state = 'activated' if user.is_active else 'deactivated'
        log_audit('USER_TOGGLE', 'UserAccount', user.id, f"User '{user.username}' was {state}")
        return jsonify(user.to_dict())

    # --------------------------------------------------------------------------
    # Reports & Analytics (Delivery Performance, Sales, Inventory Usage)
    # --------------------------------------------------------------------------
    @app.route('/api/reports/sales')
    @role_required(['Admin', 'Manager'])
    def sales_report():
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)

        bills = Bill.query.filter(Bill.created_at >= start_date).all()

        total_sales = sum(b.total_amount for b in bills)
        total_tax = sum(b.tax_amount for b in bills)
        total_delivery_fees = sum(b.delivery_fee for b in bills)
        total_discounts = sum(b.discount_amount for b in bills)
        total_collected = sum(b.paid_amount for b in bills)

        # Breakdown by order type
        type_counts = {'Dine-In': 0, 'Takeaway': 0, 'Delivery': 0}
        type_revenue = {'Dine-In': 0.0, 'Takeaway': 0.0, 'Delivery': 0.0}

        for b in bills:
            if b.order:
                otype = b.order.order_type
                if otype in type_counts:
                    type_counts[otype] += 1
                    type_revenue[otype] += float(b.total_amount)

        return jsonify({
            'period_days': days,
            'total_sales': round(total_sales, 2),
            'total_tax': round(total_tax, 2),
            'total_delivery_fees': round(total_delivery_fees, 2),
            'total_discounts': round(total_discounts, 2),
            'total_collected': round(total_collected, 2),
            'order_type_counts': type_counts,
            'order_type_revenue': {k: round(v, 2) for k, v in type_revenue.items()}
        })

    @app.route('/api/reports/top-dishes')
    @role_required(['Admin', 'Manager'])
    def top_dishes_report():
        # Group order items by menu item
        items = db.session.query(
            MenuItem.name,
            db.func.sum(OrderItem.quantity).label('total_qty'),
            db.func.sum(OrderItem.subtotal).label('total_rev')
        ).join(OrderItem, MenuItem.id == OrderItem.menu_item_id)\
         .group_by(MenuItem.id)\
         .order_by(db.desc('total_qty')).limit(10).all()

        return jsonify([{
            'name': row[0],
            'quantity_sold': int(row[1] or 0),
            'revenue': round(float(row[2] or 0), 2)
        } for row in items])

    @app.route('/api/reports/delivery-performance')
    @role_required(['Admin', 'Manager'])
    def delivery_performance_report():
        riders = Staff.query.filter_by(role='Delivery Rider', is_active=True).all()
        report = []

        for r in riders:
            deliveries = Delivery.query.filter_by(rider_id=r.id).all()
            total = len(deliveries)
            completed = [d for d in deliveries if d.status == 'Delivered']
            completed_count = len(completed)

            # Average delivery time calculation
            durations = []
            for d in completed:
                if d.actual_time and d.created_at:
                    mins = (d.actual_time - d.created_at).total_seconds() / 60
                    durations.append(mins)

            avg_time = round(sum(durations) / len(durations), 1) if durations else 0.0

            report.append({
                'rider_id': r.id,
                'rider_name': r.full_name,
                'phone': r.phone,
                'total_assigned': total,
                'delivered_count': completed_count,
                'completion_rate': round((completed_count / total * 100), 1) if total > 0 else 0.0,
                'average_delivery_minutes': avg_time
            })

        return jsonify(report)

    # --------------------------------------------------------------------------
    # Audit Logs API
    # --------------------------------------------------------------------------
    @app.route('/api/audit-logs')
    @role_required(['Admin', 'Manager'])
    def get_audit_logs():
        limit = int(request.args.get('limit', 100))
        action_filter = request.args.get('action')
        query = AuditLog.query

        if action_filter:
            query = query.filter_by(action=action_filter)

        logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        return jsonify([log.to_dict() for log in logs])

    # --------------------------------------------------------------------------
    # Database Backup API
    # --------------------------------------------------------------------------
    @app.route('/api/system/backup')
    @role_required(['Admin'])
    def system_backup():
        """Creates an immediate snapshot backup of the SQLite database file."""
        if not os.path.exists(db_path):
            return jsonify({'error': 'Database file not found'}), 404

        backup_filename = f"restaurant_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(base_dir, backup_filename)

        try:
            shutil.copyfile(db_path, backup_path)
            log_audit('SYSTEM_BACKUP', 'Database', None, f"Created database backup snapshot: {backup_filename}")
            return send_file(backup_path, as_attachment=True, download_name=backup_filename)
        except Exception as e:
            return jsonify({'error': f"Backup creation failed: {str(e)}"}), 500

    return app

if __name__ == '__main__':
    application = create_app()
    # Runs development server on port 5000
    print("==================================================================")
    print(" Restaurant Management System - Ready")
    print(" Local Server: http://127.0.0.1:5000")
    print("==================================================================")
    application.run(host='0.0.0.0', port=5000, debug=True)
