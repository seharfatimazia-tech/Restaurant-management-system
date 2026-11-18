"""
Restaurant Management System - Database Seed Script
Populates initial schema and realistic demo data for all roles, menu items,
tables, zones, recipes, inventory, orders, deliveries, and audit trails.
"""

from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash
from app import create_app
from models import (
    db, UserAccount, Staff, DeliveryZone, Customer, Address,
    DiningTable, Reservation, MenuCategory, MenuItem, Ingredient,
    Recipe, Supplier, PurchaseOrder, PurchaseOrderItem, StockTransaction,
    Orders, OrderItem, Bill, Payment, Delivery, AuditLog
)

def run_seed():
    app = create_app()
    with app.app_context():
        print("--> Dropping all tables (clean setup)...")
        db.drop_all()
        print("--> Creating all tables via SQLAlchemy ORM...")
        db.create_all()

        print("--> Seeding User Accounts & Staff profiles...")
        # Roles: Admin, Manager, Cashier, Waiter, Chef, Delivery Rider
        roles_data = [
            ("admin", "Admin@123", "Admin", "Alexander", "Wright", "555-0001", date(2023, 1, 15)),
            ("manager", "Manager@123", "Manager", "Maria", "Gomez", "555-0002", date(2023, 3, 1)),
            ("cashier", "Cashier@123", "Cashier", "David", "Chen", "555-0003", date(2023, 6, 10)),
            ("waiter", "Waiter@123", "Waiter", "Sarah", "Jenkins", "555-0004", date(2023, 8, 20)),
            ("chef", "Chef@123", "Chef", "Gordon", "Rossi", "555-0005", date(2023, 2, 1)),
            ("rider", "Rider@123", "Delivery Rider", "Marcus", "Taylor", "555-0006", date(2023, 9, 5)),
            ("rider2", "Rider@123", "Delivery Rider", "Elena", "Rostova", "555-0007", date(2023, 10, 1)),
        ]

        staff_map = {}
        for username, password, role, fname, lname, phone, hdate in roles_data:
            user = UserAccount(
                username=username,
                password_hash=generate_password_hash(password),
                role=role,
                is_active=True
            )
            db.session.add(user)
            db.session.flush()

            staff = Staff(
                user_account_id=user.id,
                first_name=fname,
                last_name=lname,
                phone=phone,
                role=role,
                hire_date=hdate,
                is_active=True
            )
            db.session.add(staff)
            db.session.flush()
            staff_map[username] = staff

        print("--> Seeding Delivery Zones...")
        zones_data = [
            ("Downtown Core", 3.50, 15.00, 25),
            ("Westside Suburbs", 5.00, 25.00, 40),
            ("University District", 2.50, 12.00, 20),
            ("North Metro", 6.00, 30.00, 45)
        ]
        zone_map = {}
        for name, fee, min_ord, est_mins in zones_data:
            zone = DeliveryZone(
                name=name,
                delivery_fee=fee,
                min_order_amount=min_ord,
                estimated_delivery_minutes=est_mins,
                is_active=True
            )
            db.session.add(zone)
            db.session.flush()
            zone_map[name] = zone

        print("--> Seeding Customers & Addresses...")
        customers_data = [
            ("John Doe", "555-0101", "john.doe@example.com", "101 Pine St", "Metropolis", "10001", "Apt 4B, ring bell", "Downtown Core"),
            ("Emily Watson", "555-0102", "emily.w@example.com", "452 Elm St", "Metropolis", "10002", "Leave at side porch", "University District"),
            ("Robert Johnson", "555-0103", "robert.j@example.com", "88 Sunset Blvd", "Metropolis", "10003", "Gate code #4490", "Westside Suburbs"),
            ("Sophia Patel", "555-0104", "sophia.p@example.com", "712 High St", "Metropolis", "10004", None, "North Metro"),
            ("Michael Brown", "555-0105", "michael.b@example.com", "33 Oak Ave", "Metropolis", "10001", "Suite 201", "Downtown Core")
        ]
        customer_map = {}
        for cname, cphone, cemail, street, city, postal, notes, zname in customers_data:
            cust = Customer(name=cname, phone=cphone, email=cemail, is_active=True)
            db.session.add(cust)
            db.session.flush()
            customer_map[cname] = cust

            addr = Address(
                customer_id=cust.id,
                delivery_zone_id=zone_map[zname].id,
                street=street,
                city=city,
                postal_code=postal,
                notes=notes,
                is_active=True
            )
            db.session.add(addr)
            db.session.flush()

        print("--> Seeding Dining Tables...")
        tables_data = [
            ("T-01", 2, "Main Dining", "Available"),
            ("T-02", 4, "Main Dining", "Occupied"),
            ("T-03", 4, "Main Dining", "Occupied"),
            ("T-04", 6, "Main Dining", "Available"),
            ("T-05", 8, "Private Dining", "Reserved"),
            ("T-06", 2, "Patio Terrace", "Available"),
            ("T-07", 4, "Patio Terrace", "Available"),
            ("T-08", 4, "Bar Lounge", "Available"),
        ]
        table_map = {}
        for tnum, cap, loc, st in tables_data:
            t = DiningTable(table_number=tnum, capacity=cap, location_area=loc, status=st, is_active=True)
            db.session.add(t)
            db.session.flush()
            table_map[tnum] = t

        print("--> Seeding Reservations...")
        # 1 confirmed reservation for tonight on Table T-05
        res_time = datetime.utcnow() + timedelta(hours=3)
        res = Reservation(
            customer_id=customer_map["Robert Johnson"].id,
            dining_table_id=table_map["T-05"].id,
            reservation_time=res_time,
            party_size=6,
            status="Confirmed",
            special_requests="Anniversary dinner; quiet corner requested."
        )
        db.session.add(res)

        print("--> Seeding Menu Categories & Items...")
        categories_data = [
            ("Appetizers & Starters", "Fresh starters to kick off your dining experience", 1),
            ("Artisan Pizzas", "Wood-fired stone oven pizzas with fresh mozzarella", 2),
            ("Gourmet Burgers & Mains", "Chef curated handcrafted burgers and hearty mains", 3),
            ("Fresh Pastas", "Traditional handmade pasta dishes", 4),
            ("Desserts", "Decadent house-made sweets", 5),
            ("Beverages & Cocktails", "Refreshing craft sodas, mocktails, and coffees", 6)
        ]
        category_map = {}
        for cat_name, desc, dorder in categories_data:
            cat = MenuCategory(name=cat_name, description=desc, display_order=dorder, is_active=True)
            db.session.add(cat)
            db.session.flush()
            category_map[cat_name] = cat

        menu_items_data = [
            ("Crispy Calamari", "Appetizers & Starters", 12.50, "Tender calamari with lemon garlic dip"),
            ("Truffle Fries", "Appetizers & Starters", 8.00, "Golden skin-on fries tossed in white truffle oil and parmesan"),
            ("Margherita Pizza", "Artisan Pizzas", 16.00, "San Marzano sauce, fresh buffalo mozzarella, and basil"),
            ("Pepperoni Diablo", "Artisan Pizzas", 18.50, "Spicy Italian pepperoni, crushed red pepper, and mozzarella"),
            ("Wagyu Bacon Burger", "Gourmet Burgers & Mains", 19.50, "1/2 lb Wagyu beef patty, aged cheddar, smoked bacon, brioche"),
            ("Fettuccine Alfredo", "Fresh Pastas", 17.00, "Rich parmesan cream sauce, garlic, and fresh cracked pepper"),
            ("Classic Tiramisu", "Desserts", 9.50, "Espresso soaked ladyfingers and mascarpone mousse"),
            ("Molten Lava Cake", "Desserts", 10.50, "Warm chocolate cake with molten center and vanilla gelato"),
            ("Craft Lemonade", "Beverages & Cocktails", 4.50, "House squeezed Meyer lemons with mint"),
            ("Espresso", "Beverages & Cocktails", 3.50, "Double shot of premium roasted Arabica beans")
        ]
        item_map = {}
        for iname, cat_name, iprice, idesc in menu_items_data:
            item = MenuItem(
                category_id=category_map[cat_name].id,
                name=iname,
                price=iprice,
                description=idesc,
                is_available=True,
                is_active=True
            )
            db.session.add(item)
            db.session.flush()
            item_map[iname] = item

        print("--> Seeding Raw Ingredients (Inventory)...")
        ingredients_data = [
            ("Pizza Dough", "kg", 45.0, 10.0, 1.80),
            ("Mozzarella Cheese", "kg", 28.0, 8.0, 6.50),
            ("San Marzano Tomato Sauce", "liters", 35.0, 10.0, 3.20),
            ("Pepperoni Slices", "kg", 18.0, 5.0, 8.50),
            ("Wagyu Beef Patty", "units", 40.0, 12.0, 4.50),
            ("Brioche Buns", "units", 50.0, 15.0, 0.75),
            ("Smoked Bacon", "kg", 15.0, 4.0, 7.00),
            ("Aged Cheddar Cheese", "kg", 14.0, 5.0, 6.00),
            ("Fettuccine Pasta", "kg", 25.0, 8.0, 2.00),
            ("Heavy Whipping Cream", "liters", 20.0, 6.0, 3.50),
            ("Parmesan Reggiano", "kg", 12.0, 4.0, 12.00),
            ("White Truffle Oil", "liters", 5.0, 1.5, 25.00),
            ("Skin-on Potato Fries", "kg", 60.0, 15.0, 1.50),
            ("Fresh Calamari", "kg", 16.0, 5.0, 9.00),
            ("Mascarpone Cheese", "kg", 10.0, 3.0, 8.00),
            ("Arabica Coffee Beans", "kg", 15.0, 4.0, 14.00),
            ("Fresh Meyer Lemons", "kg", 20.0, 5.0, 2.50),
            ("Pure Cane Sugar", "kg", 30.0, 8.0, 1.20)
        ]
        ingredient_map = {}
        for ing_name, unit, stock, min_stk, cost in ingredients_data:
            ing = Ingredient(
                name=ing_name,
                unit=unit,
                current_stock=stock,
                minimum_stock=min_stk,
                cost_per_unit=cost,
                is_active=True
            )
            db.session.add(ing)
            db.session.flush()
            ingredient_map[ing_name] = ing

        print("--> Seeding Recipes (Bill of Materials)...")
        # Format: (MenuItemName, [(IngredientName, quantity_required)])
        recipes_data = [
            ("Margherita Pizza", [
                ("Pizza Dough", 0.25),
                ("Mozzarella Cheese", 0.20),
                ("San Marzano Tomato Sauce", 0.15)
            ]),
            ("Pepperoni Diablo", [
                ("Pizza Dough", 0.25),
                ("Mozzarella Cheese", 0.20),
                ("San Marzano Tomato Sauce", 0.15),
                ("Pepperoni Slices", 0.10)
            ]),
            ("Wagyu Bacon Burger", [
                ("Wagyu Beef Patty", 1.0),
                ("Brioche Buns", 1.0),
                ("Smoked Bacon", 0.05),
                ("Aged Cheddar Cheese", 0.05)
            ]),
            ("Truffle Fries", [
                ("Skin-on Potato Fries", 0.30),
                ("White Truffle Oil", 0.02),
                ("Parmesan Reggiano", 0.03)
            ]),
            ("Crispy Calamari", [
                ("Fresh Calamari", 0.25),
                ("Fresh Meyer Lemons", 0.05)
            ]),
            ("Fettuccine Alfredo", [
                ("Fettuccine Pasta", 0.20),
                ("Heavy Whipping Cream", 0.15),
                ("Parmesan Reggiano", 0.05)
            ]),
            ("Classic Tiramisu", [
                ("Mascarpone Cheese", 0.12),
                ("Arabica Coffee Beans", 0.03),
                ("Pure Cane Sugar", 0.04)
            ]),
            ("Craft Lemonade", [
                ("Fresh Meyer Lemons", 0.15),
                ("Pure Cane Sugar", 0.05)
            ]),
            ("Espresso", [
                ("Arabica Coffee Beans", 0.02)
            ])
        ]
        for item_name, ing_list in recipes_data:
            m_item = item_map[item_name]
            for ing_name, qty in ing_list:
                rec = Recipe(
                    menu_item_id=m_item.id,
                    ingredient_id=ingredient_map[ing_name].id,
                    quantity_required=qty
                )
                db.session.add(rec)

        print("--> Seeding Suppliers & Purchase Orders...")
        suppliers_data = [
            ("Metro Dairy & Fresh Foods", "Marco Vane", "555-9001", "marco@metrodairy.com", "77 Distribution Way"),
            ("Prime Artisan Meats", "Lucas Thorne", "555-9002", "lucas@primemeats.com", "12 Industrial Pkwy"),
            ("Milano Specialty Imports", "Gianna Rossi", "555-9003", "gianna@milanofoods.com", "400 Harbor Blvd"),
            ("Citrus & Beverage Goods", "Terry Simmons", "555-9004", "terry@citrusgoods.com", "90 Orchard Lane")
        ]
        supplier_map = {}
        for sname, scontact, sphone, semail, saddr in suppliers_data:
            sup = Supplier(name=sname, contact_person=scontact, phone=sphone, email=semail, address=saddr, is_active=True)
            db.session.add(sup)
            db.session.flush()
            supplier_map[sname] = sup

        # Completed PO with initial stock ledger records
        po1 = PurchaseOrder(
            po_number="PO-2026-001",
            supplier_id=supplier_map["Metro Dairy & Fresh Foods"].id,
            order_date=datetime.utcnow() - timedelta(days=2),
            received_date=datetime.utcnow() - timedelta(days=1),
            status="Received",
            total_cost=256.00,
            created_by_staff_id=staff_map["manager"].id
        )
        db.session.add(po1)
        db.session.flush()

        po_item1 = PurchaseOrderItem(
            purchase_order_id=po1.id,
            ingredient_id=ingredient_map["Mozzarella Cheese"].id,
            quantity=20.0,
            unit_cost=6.50,
            subtotal=130.00
        )
        po_item2 = PurchaseOrderItem(
            purchase_order_id=po1.id,
            ingredient_id=ingredient_map["Heavy Whipping Cream"].id,
            quantity=15.0,
            unit_cost=3.50,
            subtotal=52.50
        )
        po_item3 = PurchaseOrderItem(
            purchase_order_id=po1.id,
            ingredient_id=ingredient_map["Parmesan Reggiano"].id,
            quantity=6.125,
            unit_cost=12.00,
            subtotal=73.50
        )
        db.session.add_all([po_item1, po_item2, po_item3])

        # Record Initial Restock transactions in stock ledger
        st1 = StockTransaction(
            ingredient_id=ingredient_map["Mozzarella Cheese"].id,
            transaction_type="Restock",
            quantity=20.0,
            unit_cost=6.50,
            reference_id="PO-2026-001",
            notes="Initial warehouse batch receipt",
            created_by_staff_id=staff_map["manager"].id
        )
        db.session.add(st1)

        print("--> Seeding Sample Operational Orders (Dine-in, Takeaway, Delivery)...")

        # ORDER 1: Completed Dine-in Order with Bill, full Payment, and Recipe Stock Deduction
        ord1 = Orders(
            order_number="ORD-1001",
            order_type="Dine-In",
            status="Completed",
            table_id=table_map["T-01"].id,
            staff_id=staff_map["waiter"].id,
            order_time=datetime.utcnow() - timedelta(hours=2),
            closed_at=datetime.utcnow() - timedelta(hours=1),
            total_amount=36.00,
            notes="Table 1 lunch session",
            is_active=True
        )
        db.session.add(ord1)
        db.session.flush()

        ord1_item1 = OrderItem(
            order_id=ord1.id,
            menu_item_id=item_map["Margherita Pizza"].id,
            quantity=1,
            unit_price=16.00,
            subtotal=16.00,
            status="Served"
        )
        ord1_item2 = OrderItem(
            order_id=ord1.id,
            menu_item_id=item_map["Wagyu Bacon Burger"].id,
            quantity=1,
            unit_price=19.50,
            subtotal=19.50,
            status="Served"
        )
        db.session.add_all([ord1_item1, ord1_item2])

        # Bill for Order 1: Subtotal: 35.50, Tax (8%): 2.84, Total: 38.34, Paid: 38.34, Balance: 0.00
        bill1 = Bill(
            bill_number="BILL-1001",
            order_id=ord1.id,
            subtotal=35.50,
            tax_amount=2.84,
            discount_amount=0.00,
            delivery_fee=0.00,
            total_amount=38.34,
            paid_amount=38.34,
            balance=0.00,
            status="Paid"
        )
        db.session.add(bill1)
        db.session.flush()

        pmt1 = Payment(
            payment_reference="PMT-1001",
            bill_id=bill1.id,
            amount=38.34,
            payment_method="Credit Card",
            transaction_ref="TXN-984210",
            processed_by_staff_id=staff_map["cashier"].id
        )
        db.session.add(pmt1)

        # Stock deduction ledger for closed Order 1
        st_deduct1 = StockTransaction(
            ingredient_id=ingredient_map["Pizza Dough"].id,
            transaction_type="Order_Deduction",
            quantity=-0.25,
            reference_id="ORD-1001",
            notes="Recipe stock deduction for Margherita Pizza",
            created_by_staff_id=staff_map["cashier"].id
        )
        st_deduct2 = StockTransaction(
            ingredient_id=ingredient_map["Wagyu Beef Patty"].id,
            transaction_type="Order_Deduction",
            quantity=-1.0,
            reference_id="ORD-1001",
            notes="Recipe stock deduction for Wagyu Bacon Burger",
            created_by_staff_id=staff_map["cashier"].id
        )
        db.session.add_all([st_deduct1, st_deduct2])

        # ORDER 2: Active Dine-in Order (Table T-02, In-Progress, Pending in Kitchen)
        ord2 = Orders(
            order_number="ORD-1002",
            order_type="Dine-In",
            status="In-Progress",
            table_id=table_map["T-02"].id,
            staff_id=staff_map["waiter"].id,
            order_time=datetime.utcnow() - timedelta(minutes=20),
            total_amount=48.00,
            notes="No onions on burger please",
            is_active=True
        )
        db.session.add(ord2)
        db.session.flush()

        ord2_item1 = OrderItem(
            order_id=ord2.id,
            menu_item_id=item_map["Pepperoni Diablo"].id,
            quantity=1,
            unit_price=18.50,
            subtotal=18.50,
            status="Preparing"
        )
        ord2_item2 = OrderItem(
            order_id=ord2.id,
            menu_item_id=item_map["Crispy Calamari"].id,
            quantity=1,
            unit_price=12.50,
            subtotal=12.50,
            status="Ready"
        )
        ord2_item3 = OrderItem(
            order_id=ord2.id,
            menu_item_id=item_map["Fettuccine Alfredo"].id,
            quantity=1,
            unit_price=17.00,
            subtotal=17.00,
            status="Preparing"
        )
        db.session.add_all([ord2_item1, ord2_item2, ord2_item3])

        bill2 = Bill(
            bill_number="BILL-1002",
            order_id=ord2.id,
            subtotal=48.00,
            tax_amount=3.84,
            discount_amount=0.00,
            delivery_fee=0.00,
            total_amount=51.84,
            paid_amount=0.00,
            balance=51.84,
            status="Unpaid"
        )
        db.session.add(bill2)

        # ORDER 3: Active Delivery Order (Customer: Emily Watson, Zone: University District)
        # Assigned to rider Marcus Taylor; status = 'Assigned'
        emily_cust = customer_map["Emily Watson"]
        emily_addr = emily_cust.addresses.first()

        ord3 = Orders(
            order_number="ORD-1003",
            order_type="Delivery",
            status="In-Progress",
            customer_id=emily_cust.id,
            staff_id=staff_map["cashier"].id,
            order_time=datetime.utcnow() - timedelta(minutes=15),
            total_amount=35.50,
            notes="Contactless drop-off at side porch",
            is_active=True
        )
        db.session.add(ord3)
        db.session.flush()

        ord3_item1 = OrderItem(
            order_id=ord3.id,
            menu_item_id=item_map["Margherita Pizza"].id,
            quantity=1,
            unit_price=16.00,
            subtotal=16.00,
            status="Ready"
        )
        ord3_item2 = OrderItem(
            order_id=ord3.id,
            menu_item_id=item_map["Classic Tiramisu"].id,
            quantity=1,
            unit_price=9.50,
            subtotal=9.50,
            status="Ready"
        )
        ord3_item3 = OrderItem(
            order_id=ord3.id,
            menu_item_id=item_map["Craft Lemonade"].id,
            quantity=2,
            unit_price=4.50,
            subtotal=9.00,
            status="Ready"
        )
        db.session.add_all([ord3_item1, ord3_item2, ord3_item3])

        # Delivery record
        delivery3 = Delivery(
            order_id=ord3.id,
            rider_id=staff_map["rider"].id,
            delivery_zone_id=emily_addr.delivery_zone_id,
            address_id=emily_addr.id,
            status="Assigned",
            estimated_time=datetime.utcnow() + timedelta(minutes=25),
            delivery_notes="Leave package on the wooden bench."
        )
        db.session.add(delivery3)
        db.session.flush()

        # Bill for Delivery Order 3 includes delivery_fee ($2.50)
        # Subtotal: 34.50, Tax (8%): 2.76, Delivery Fee: 2.50, Total: 39.76
        bill3 = Bill(
            bill_number="BILL-1003",
            order_id=ord3.id,
            subtotal=34.50,
            tax_amount=2.76,
            discount_amount=0.00,
            delivery_fee=2.50,
            total_amount=39.76,
            paid_amount=39.76,
            balance=0.00,
            status="Paid"
        )
        db.session.add(bill3)
        db.session.flush()

        pmt3 = Payment(
            payment_reference="PMT-1003",
            bill_id=bill3.id,
            amount=39.76,
            payment_method="Online",
            transaction_ref="ONL-WEB-55419",
            processed_by_staff_id=staff_map["cashier"].id
        )
        db.session.add(pmt3)

        print("--> Seeding Initial Audit Logs...")
        logs_data = [
            ("admin", "SYSTEM_INIT", "Database", "1", "Database schema initialized and seed execution started."),
            ("admin", "USER_CREATE", "UserAccount", "1", "Created Administrative account 'admin'."),
            ("manager", "MENU_CREATE", "MenuItem", str(item_map["Margherita Pizza"].id), "Added 'Margherita Pizza' to Artisan Pizzas."),
            ("cashier", "ORDER_CREATE", "Orders", "ORD-1001", "Created Dine-in order ORD-1001 for Table T-01."),
            ("cashier", "PAYMENT_PROCESSED", "Payment", "PMT-1001", "Received $38.34 via Credit Card for Bill BILL-1001."),
            ("chef", "ORDER_CLOSED", "Orders", "ORD-1001", "Order ORD-1001 finalized. Ingredients automatically deducted from inventory."),
            ("manager", "DELIVERY_ASSIGN", "Delivery", str(delivery3.id), f"Assigned delivery for ORD-1003 to rider {staff_map['rider'].full_name}.")
        ]
        for uname, act, etype, eid, dtl in logs_data:
            alog = AuditLog(
                username=uname,
                action=act,
                entity_type=etype,
                entity_id=eid,
                details=dtl,
                ip_address="127.0.0.1"
            )
            db.session.add(alog)

        db.session.commit()
        print("--> SUCCESS: Database seeded completely with all 21 models and realistic records!")

if __name__ == "__main__":
    run_seed()
