"""
AI-Powered Restaurant Management System
---------------------------------------
Built with Python, Streamlit, SQLite and Google Gemini (Google AI Studio).

Everything lives in this one file. It is split into clear sections:
  1. Settings            - names, currency, delivery fee, restaurant info
  2. Database helpers    - create tables, run queries, add sample data
  3. Validation helpers  - check what the customer types
  4. Cart + order logic  - shopping cart, bill, receipt
  5. Gemini AI helpers   - talk to the Gemini API safely
  6. Pages               - Dashboard, Menu, Order, AI pages, Feedback, Admin
  7. Main                - sidebar navigation that opens each page
"""

import hmac
import os
import re
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

# The Gemini library is optional at import time so the app still opens
# (with AI disabled) if it is not installed.
try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None


# ----------------------------------------------------------------------------
# 1. SETTINGS  (change these to match your own restaurant)
# ----------------------------------------------------------------------------
DB_PATH = "restaurant.db"
RESTAURANT_NAME = "Spice Garden Restaurant"
CURRENCY = "Rs."
DELIVERY_FEE = 150  # flat delivery charge added to every order
MAX_QTY_PER_ITEM = 20
DEFAULT_MODEL = "gemini-2.5-flash"  # can be overridden with GEMINI_MODEL secret

ORDER_STATUSES = ["Pending", "Preparing", "Out for Delivery", "Delivered", "Cancelled"]

# The AI chatbot may ONLY use this text and the menu from the database.
RESTAURANT_INFO = """
Restaurant name: Spice Garden Restaurant
Opening hours: Every day, 11:00 AM to 11:00 PM.
Services: Online food ordering and home delivery.
Delivery fee: Rs. 150 flat per order.
Payment method: Cash on delivery only.
Order status steps: Pending, Preparing, Out for Delivery, Delivered.
"""

DEFAULT_CATEGORIES = [
    "Fast Food", "Pizza", "Burgers", "BBQ", "Chinese Food", "Drinks", "Desserts",
]

CATEGORY_EMOJI = {
    "Fast Food": "🍟", "Pizza": "🍕", "Burgers": "🍔", "BBQ": "🍖",
    "Chinese Food": "🥡", "Drinks": "🥤", "Desserts": "🍰",
}

# (name, category, description, ingredients, price, is_vegetarian)
SAMPLE_FOODS = [
    ("Crispy Chicken Wrap", "Fast Food", "Crispy chicken, lettuce and garlic mayo in a warm wrap.", "Chicken, flour tortilla, lettuce, garlic mayo", 450, 0),
    ("Loaded Fries", "Fast Food", "Golden fries topped with cheese sauce and jalapenos.", "Potato, cheese sauce, jalapenos", 350, 1),
    ("Chicken Tikka Pizza", "Pizza", "Spicy tikka chicken, onions and mozzarella.", "Dough, chicken tikka, onion, mozzarella, tomato sauce", 1200, 0),
    ("Margherita Pizza", "Pizza", "Classic pizza with tomato sauce and fresh mozzarella.", "Dough, tomato sauce, mozzarella, basil", 950, 1),
    ("Classic Beef Burger", "Burgers", "Juicy beef patty, cheddar, pickles and house sauce.", "Beef patty, bun, cheddar, pickles, lettuce, sauce", 650, 0),
    ("Veggie Burger", "Burgers", "Crunchy vegetable patty with fresh salad.", "Vegetable patty, bun, lettuce, tomato, mayo", 500, 1),
    ("Chicken Seekh Kebab", "BBQ", "Minced chicken kebabs grilled over charcoal.", "Minced chicken, onion, green chili, spices", 700, 0),
    ("Chicken Malai Boti", "BBQ", "Creamy, tender chicken pieces cooked on the grill.", "Chicken, cream, yogurt, spices", 850, 0),
    ("Chicken Chow Mein", "Chinese Food", "Stir-fried noodles with chicken and vegetables.", "Noodles, chicken, cabbage, carrot, soy sauce", 600, 0),
    ("Vegetable Fried Rice", "Chinese Food", "Wok-fried rice with mixed vegetables.", "Rice, carrot, peas, spring onion, soy sauce", 480, 1),
    ("Fresh Mint Lemonade", "Drinks", "Cool lemonade blended with fresh mint.", "Lemon, mint, sugar, water, ice", 220, 1),
    ("Mango Shake", "Drinks", "Thick shake made with ripe mangoes and milk.", "Mango, milk, sugar, ice", 300, 1),
    ("Chocolate Brownie", "Desserts", "Warm fudge brownie with chocolate sauce.", "Flour, cocoa, butter, eggs, sugar", 380, 1),
    ("Kheer", "Desserts", "Traditional rice pudding with cardamom and nuts.", "Rice, milk, sugar, cardamom, almonds", 320, 1),
]


# ----------------------------------------------------------------------------
# 2. DATABASE HELPERS
# ----------------------------------------------------------------------------
def get_conn():
    """Open a new SQLite connection that returns rows like dictionaries."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, params=()):
    """Run a SELECT and return a list of dictionaries."""
    conn = get_conn()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def execute(sql, params=()):
    """Run INSERT / UPDATE / DELETE and return the new row id."""
    conn = get_conn()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    """Create all tables (if missing) and add sample data on the first run."""
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER,
                description TEXT,
                ingredients TEXT,
                price REAL NOT NULL,
                image_url TEXT,
                is_veg INTEGER NOT NULL DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            );
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                subtotal REAL NOT NULL,
                delivery_fee REAL NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                food_id INTEGER,
                food_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                rating INTEGER NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        # Add sample data only when the tables are empty.
        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            for cat in DEFAULT_CATEGORIES:
                conn.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
        if conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 0:
            for name, cat, desc, ingredients, price, is_veg in SAMPLE_FOODS:
                row = conn.execute("SELECT id FROM categories WHERE name = ?", (cat,)).fetchone()
                if row:
                    conn.execute(
                        "INSERT INTO foods (name, category_id, description, ingredients, "
                        "price, image_url, is_veg, available) VALUES (?, ?, ?, ?, ?, '', ?, 1)",
                        (name, row[0], desc, ingredients, price, is_veg),
                    )
        conn.commit()
    finally:
        conn.close()


@st.cache_resource
def setup_database():
    """Runs init_db only once per server start."""
    init_db()
    return True


def get_categories():
    return query("SELECT id, name FROM categories ORDER BY name")


def get_foods(only_available=True):
    sql = (
        "SELECT f.*, c.name AS category FROM foods f "
        "LEFT JOIN categories c ON c.id = f.category_id"
    )
    if only_available:
        sql += " WHERE f.available = 1"
    sql += " ORDER BY c.name, f.name"
    return query(sql)


def money(value):
    return f"{CURRENCY} {value:,.0f}"


# ----------------------------------------------------------------------------
# 3. VALIDATION HELPERS
# ----------------------------------------------------------------------------
def clean_text(text, max_len):
    """Remove extra spaces and cut the text to a safe length."""
    return re.sub(r"\s+", " ", (text or "")).strip()[:max_len]


def validate_customer(name, phone, address):
    """Return (clean_values, list_of_errors)."""
    errors = []
    name = clean_text(name, 60)
    address = clean_text(address, 200)
    phone = re.sub(r"[\s\-()]", "", phone or "")
    if not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,59}", name):
        errors.append("Please enter a valid name (letters and spaces only, 2-60 characters).")
    if not re.fullmatch(r"\+?[0-9]{10,15}", phone):
        errors.append("Please enter a valid phone number (10-15 digits, e.g. 03001234567).")
    if len(address) < 10:
        errors.append("Please enter a full delivery address (at least 10 characters).")
    return (name, phone, address), errors


# ----------------------------------------------------------------------------
# 4. CART + ORDER LOGIC
# ----------------------------------------------------------------------------
def init_session():
    """Create the values we keep between button clicks."""
    defaults = {
        "cart": {},            # {food_id: quantity}
        "receipt": None,       # text of the last receipt
        "chat_messages": [],   # AI assistant chat history
        "admin_ok": False,
        "review_summary": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cart_add(food_id):
    cart = st.session_state.cart
    cart[food_id] = min(cart.get(food_id, 0) + 1, MAX_QTY_PER_ITEM)
    st.toast("Added to cart 🛒")


def cart_change(food_id, delta):
    cart = st.session_state.cart
    new_qty = cart.get(food_id, 0) + delta
    if new_qty <= 0:
        cart.pop(food_id, None)
    else:
        cart[food_id] = min(new_qty, MAX_QTY_PER_ITEM)


def cart_remove(food_id):
    st.session_state.cart.pop(food_id, None)


def cart_details():
    """Return cart lines using the CURRENT prices from the database."""
    cart = st.session_state.cart
    if not cart:
        return []
    ids = list(cart.keys())
    marks = ",".join("?" * len(ids))
    rows = query(f"SELECT id, name, price FROM foods WHERE available = 1 AND id IN ({marks})", ids)
    found = {row["id"]: row for row in rows}
    for food_id in ids:  # drop items that were deleted or hidden by the admin
        if food_id not in found:
            cart.pop(food_id, None)
    lines = []
    for food_id, qty in cart.items():
        food = found[food_id]
        lines.append({
            "id": food_id, "name": food["name"], "price": food["price"],
            "qty": qty, "line_total": food["price"] * qty,
        })
    return lines


def bill_totals(lines):
    subtotal = sum(line["line_total"] for line in lines)
    fee = DELIVERY_FEE if lines else 0
    return subtotal, fee, subtotal + fee


def place_order(name, phone, address, lines):
    """Save customer, order and order items in ONE database transaction."""
    subtotal, fee, total = bill_totals(lines)
    created = now_text()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES (?, ?, ?, ?)",
            (name, phone, address, created),
        )
        customer_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO orders (customer_id, subtotal, delivery_fee, total, status, created_at) "
            "VALUES (?, ?, ?, ?, 'Pending', ?)",
            (customer_id, subtotal, fee, total, created),
        )
        order_id = cur.lastrowid
        for line in lines:
            conn.execute(
                "INSERT INTO order_items (order_id, food_id, food_name, quantity, unit_price) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, line["id"], line["name"], line["qty"], line["price"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return order_id, created


def build_receipt(order_id, created, name, phone, address, lines):
    subtotal, fee, total = bill_totals(lines)
    out = [
        "=" * 44,
        RESTAURANT_NAME.center(44),
        "ORDER RECEIPT".center(44),
        "=" * 44,
        f"Order No : #{order_id}",
        f"Date     : {created}",
        f"Customer : {name}",
        f"Phone    : {phone}",
        f"Address  : {address}",
        "-" * 44,
    ]
    for line in lines:
        out.append(f"{line['qty']} x {line['name']}")
        out.append(f"{'':>26}{money(line['line_total']):>18}")
    out += [
        "-" * 44,
        f"{'Subtotal':<26}{money(subtotal):>18}",
        f"{'Delivery fee':<26}{money(fee):>18}",
        f"{'TOTAL':<26}{money(total):>18}",
        "=" * 44,
        "Payment: Cash on delivery".center(44),
        "Thank you for ordering with us!".center(44),
    ]
    return "\n".join(out)


# ----------------------------------------------------------------------------
# 5. GEMINI AI HELPERS
# ----------------------------------------------------------------------------
def get_secret(name):
    """Read a value from Streamlit Secrets, or from environment variables."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass  # no secrets file found - fall back to environment variables
    return os.environ.get(name, "")


def ai_available():
    return genai is not None and bool(get_secret("GEMINI_API_KEY"))


def ask_gemini(system_rules, prompt):
    """Send a prompt to Gemini and return the answer text (never crashes)."""
    if genai is None:
        return "⚠️ The AI library is not installed. Run: pip install -r requirements.txt"
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ AI is not set up yet. Add GEMINI_API_KEY to your Streamlit secrets (see README)."
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=get_secret("GEMINI_MODEL") or DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system_rules, temperature=0.4),
        )
        return response.text or "Sorry, I could not create an answer. Please try again."
    except Exception as error:
        return f"⚠️ The AI service is not available right now ({type(error).__name__}). Please try again later."


def menu_context():
    """Turn the available menu into plain text that Gemini can read."""
    foods = get_foods(only_available=True)
    if not foods:
        return "The menu is currently empty."
    lines = []
    for f in foods:
        diet = "Vegetarian" if f["is_veg"] else "Non-vegetarian"
        lines.append(
            f"- {f['name']} | Category: {f['category']} | Price: {money(f['price'])} | {diet} | "
            f"Description: {f['description']} | Ingredients: {f['ingredients']}"
        )
    return "\n".join(lines)


def assistant_rules():
    return (
        f"You are the friendly AI assistant of {RESTAURANT_NAME}. "
        "Use ONLY the restaurant information and menu given below. "
        "Never invent dishes, prices, ingredients, offers or services. "
        "If the answer is not in the data, say you do not have that information and suggest "
        "contacting the restaurant. Keep answers short, clear and polite. "
        "Never ask for or reveal any customer personal data.\n\n"
        f"RESTAURANT INFORMATION:\n{RESTAURANT_INFO}\n"
        f"CURRENT MENU:\n{menu_context()}"
    )


# ----------------------------------------------------------------------------
# 6. PAGES
# ----------------------------------------------------------------------------
def apply_style():
    st.markdown(
        """
        <style>
        .stApp { background-color: #FFF8F0; }
        [data-testid="stSidebar"] { background-color: #3B1F1A; }
        [data-testid="stSidebar"] * { color: #FFF8F0 !important; }
        .hero { background: linear-gradient(90deg, #B03A2E, #E67E22); color: white;
                padding: 1.1rem 1.4rem; border-radius: 14px; margin-bottom: 1rem; }
        .hero h1 { color: white; margin: 0; font-size: 1.8rem; }
        .hero p { margin: 0.2rem 0 0 0; opacity: 0.95; }
        .food-emoji { font-size: 3.4rem; text-align: center; background: #FDEBD0;
                      border-radius: 10px; padding: 0.6rem 0; margin-bottom: 0.4rem; }
        .price { color: #B03A2E; font-weight: 700; font-size: 1.1rem; }
        [data-testid="stMetric"] { background: white; border-radius: 12px;
                                   padding: 0.8rem 1rem; border: 1px solid #F5CBA7; }
        .stButton > button, .stFormSubmitButton > button { border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title, subtitle):
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


# ---------------------------- A. Dashboard ----------------------------------
def page_dashboard():
    page_header(f"🍽️ {RESTAURANT_NAME}", "Restaurant dashboard and performance overview")

    total_orders = query("SELECT COUNT(*) AS n FROM orders")[0]["n"]
    total_sales = query("SELECT COALESCE(SUM(total), 0) AS s FROM orders WHERE status != 'Cancelled'")[0]["s"]
    items = query("SELECT COUNT(*) AS n FROM foods WHERE available = 1")[0]["n"]
    avg_rating = query("SELECT AVG(rating) AS r FROM feedback")[0]["r"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Orders", total_orders)
    c2.metric("Total Sales", money(total_sales))
    c3.metric("Available Food Items", items)
    c4.metric("Average Rating", f"{avg_rating:.1f} ⭐" if avg_rating else "No ratings yet")

    valid_orders = query("SELECT COUNT(*) AS n FROM orders WHERE status != 'Cancelled'")[0]["n"]
    delivered = query("SELECT COUNT(*) AS n FROM orders WHERE status = 'Delivered'")[0]["n"]
    pending = query("SELECT COUNT(*) AS n FROM orders WHERE status IN ('Pending', 'Preparing', 'Out for Delivery')")[0]["n"]
    avg_order = total_sales / valid_orders if valid_orders else 0

    st.subheader("Performance statistics")
    p1, p2, p3 = st.columns(3)
    p1.metric("Average Order Value", money(avg_order))
    p2.metric("Delivered Orders", delivered)
    p3.metric("Active Orders", pending)

    left, right = st.columns(2)
    with left:
        st.subheader("🔥 Popular dishes")
        popular = query(
            "SELECT oi.food_name AS Dish, SUM(oi.quantity) AS Sold FROM order_items oi "
            "JOIN orders o ON o.id = oi.order_id WHERE o.status != 'Cancelled' "
            "GROUP BY oi.food_name ORDER BY Sold DESC LIMIT 5"
        )
        if popular:
            st.bar_chart(pd.DataFrame(popular).set_index("Dish"))
        else:
            st.info("Popular dishes will appear after the first orders.")
    with right:
        st.subheader("📈 Sales by day")
        daily = query(
            "SELECT date(created_at) AS Day, SUM(total) AS Sales FROM orders "
            "WHERE status != 'Cancelled' GROUP BY Day ORDER BY Day"
        )
        if daily:
            st.line_chart(pd.DataFrame(daily).set_index("Day"))
        else:
            st.info("Sales chart will appear after the first orders.")

    st.subheader("🧾 Recent orders")
    recent = query(
        "SELECT o.id AS 'Order No', o.created_at AS 'Date', "
        "(SELECT SUM(quantity) FROM order_items WHERE order_id = o.id) AS 'Items', "
        "o.total AS 'Total', o.status AS 'Status' FROM orders o ORDER BY o.id DESC LIMIT 8"
    )
    if recent:
        st.dataframe(pd.DataFrame(recent), hide_index=True)
        st.caption("Customer details are private and only visible in the admin panel.")
    else:
        st.info("No orders yet. Visit the Menu page to place the first order!")


# ---------------------------- B. Digital Menu -------------------------------
def food_card(food):
    with st.container(border=True):
        if food["image_url"]:
            st.image(food["image_url"])
        else:
            emoji = CATEGORY_EMOJI.get(food["category"], "🍽️")
            st.markdown(f'<div class="food-emoji">{emoji}</div>', unsafe_allow_html=True)
        st.markdown(f"**{food['name']}**  " + ("🌱" if food["is_veg"] else ""))
        st.caption(f"{food['category']}")
        st.write(food["description"])
        st.markdown(f'<span class="price">{money(food["price"])}</span>', unsafe_allow_html=True)
        st.button("Add to cart", key=f"add_{food['id']}", on_click=cart_add, args=(food["id"],))


def page_menu():
    page_header("📖 Digital Food Menu", "Browse our dishes, search, and add your favourites to the cart")

    foods = get_foods(only_available=True)
    categories = ["All"] + [c["name"] for c in get_categories()]

    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("🔍 Search food", placeholder="e.g. pizza, chicken, mango")
    category = f2.selectbox("Category", categories)
    veg_only = f3.checkbox("🌱 Vegetarian only")
    max_price = st.slider("Maximum price", 0, 3000, 3000, step=50)

    results = []
    for f in foods:
        text = f"{f['name']} {f['description']} {f['ingredients']}".lower()
        if search and search.strip().lower() not in text:
            continue
        if category != "All" and f["category"] != category:
            continue
        if veg_only and not f["is_veg"]:
            continue
        if f["price"] > max_price:
            continue
        results.append(f)

    if not results:
        st.warning("No food items match your search. Try changing the filters.")
        return
    st.caption(f"Showing {len(results)} item(s). 🌱 = vegetarian")
    columns = st.columns(3)
    for index, food in enumerate(results):
        with columns[index % 3]:
            food_card(food)


# ---------------------------- C. Ordering -----------------------------------
def page_order():
    page_header("🛒 Your Cart & Checkout", "Check your items, enter delivery details and confirm your order")

    if st.session_state.receipt:
        st.success("✅ Your order has been confirmed! Our team will prepare it now.")
        st.code(st.session_state.receipt, language=None)
        st.download_button("⬇️ Download receipt", st.session_state.receipt, file_name="receipt.txt")
        if st.button("Start a new order"):
            st.session_state.receipt = None
            st.rerun()
        return

    lines = cart_details()
    if not lines:
        st.info("Your cart is empty. Go to the Menu page and add some delicious food!")
        return

    st.subheader("Items in your cart")
    for line in lines:
        c1, c2, c3, c4, c5, c6 = st.columns([4, 1, 1, 1, 2, 1])
        c1.markdown(f"**{line['name']}**  \n{money(line['price'])} each")
        c2.button("➖", key=f"minus_{line['id']}", on_click=cart_change, args=(line["id"], -1))
        c3.markdown(f"<div style='text-align:center;padding-top:0.4rem'><b>{line['qty']}</b></div>", unsafe_allow_html=True)
        c4.button("➕", key=f"plus_{line['id']}", on_click=cart_change, args=(line["id"], 1))
        c5.markdown(f"<div style='padding-top:0.4rem'>{money(line['line_total'])}</div>", unsafe_allow_html=True)
        c6.button("🗑️", key=f"del_{line['id']}", on_click=cart_remove, args=(line["id"],))

    subtotal, fee, total = bill_totals(lines)
    st.divider()
    b1, b2, b3 = st.columns(3)
    b1.metric("Subtotal", money(subtotal))
    b2.metric("Delivery fee", money(fee))
    b3.metric("Total bill", money(total))

    st.subheader("Delivery details")
    with st.form("checkout_form"):
        name = st.text_input("Full name", max_chars=60)
        phone = st.text_input("Phone number", max_chars=20, placeholder="03001234567")
        address = st.text_area("Delivery address", max_chars=200)
        confirm = st.form_submit_button("✅ Confirm order")

    if confirm:
        (name, phone, address), errors = validate_customer(name, phone, address)
        if errors:
            for message in errors:
                st.error(message)
            return
        lines = cart_details()  # read prices again to be safe
        if not lines:
            st.error("Your cart is empty or some items are no longer available.")
            return
        order_id, created = place_order(name, phone, address, lines)
        st.session_state.receipt = build_receipt(order_id, created, name, phone, address, lines)
        st.session_state.cart = {}
        st.rerun()


# ---------------------------- D. AI Recommendation --------------------------
def page_recommend():
    page_header("✨ AI Food Recommendation", "Tell us what you like and Gemini will pick meals from our menu")
    if not ai_available():
        st.warning("AI is not configured yet. Add GEMINI_API_KEY to the secrets (see README).")

    with st.form("recommend_form"):
        c1, c2 = st.columns(2)
        diet = c1.selectbox("Diet", ["No preference", "Vegetarian only", "Non-vegetarian"])
        budget = c2.number_input(f"Budget ({CURRENCY})", min_value=0, max_value=100000, value=1500, step=100)
        people = st.number_input("Number of people", min_value=1, max_value=20, value=2)
        likes = st.text_input("Your taste / mood (optional)", max_chars=200, placeholder="e.g. spicy, light, something sweet")
        go = st.form_submit_button("Get recommendations")

    if go:
        prompt = (
            f"A customer wants meal suggestions.\nDiet: {diet}\nTotal budget: {budget} {CURRENCY}\n"
            f"People: {people}\nPreferences: {clean_text(likes, 200) or 'none'}\n\n"
            "Suggest a meal combination from the menu. For each dish give the name, price and one "
            "short reason. Show the total price and make sure it stays within the budget. "
            "Respect the diet choice strictly."
        )
        with st.spinner("Gemini is choosing the best meals for you..."):
            st.markdown(ask_gemini(assistant_rules(), prompt))

    st.divider()
    st.subheader("Ask a question about the menu")
    with st.form("menu_question_form"):
        question = st.text_input("Your question", max_chars=300, placeholder="Which burger has no beef?")
        ask = st.form_submit_button("Ask")
    if ask:
        question = clean_text(question, 300)
        if len(question) < 3:
            st.error("Please type a question first.")
        else:
            with st.spinner("Thinking..."):
                st.markdown(ask_gemini(assistant_rules(), f"Customer question: {question}"))


# ---------------------------- E. AI Assistant (chatbot) ---------------------
def page_assistant():
    page_header("🤖 AI Restaurant Assistant", "Ask about the menu, ingredients, popular meals or our services")
    if not ai_available():
        st.warning("AI is not configured yet. Add GEMINI_API_KEY to the secrets (see README).")

    if st.button("🧹 Clear chat"):
        st.session_state.chat_messages = []
        st.rerun()

    if not st.session_state.chat_messages:
        st.info("Try: “What are your most popular dishes?” or “What is in the Margherita Pizza?”")

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_text = st.chat_input("Type your question here...")
    if user_text:
        user_text = clean_text(user_text, 500)
        st.session_state.chat_messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)

        popular = query(
            "SELECT food_name, SUM(quantity) AS qty FROM order_items GROUP BY food_name "
            "ORDER BY qty DESC LIMIT 3"
        )
        popular_text = ", ".join(p["food_name"] for p in popular) or "No sales data yet"
        history = st.session_state.chat_messages[-7:-1]  # last few messages for context
        history_text = "\n".join(f"{m['role'].title()}: {m['content']}" for m in history)
        prompt = (
            f"Most ordered dishes so far: {popular_text}\n\n"
            f"Conversation so far:\n{history_text or '(new conversation)'}\n\n"
            f"Customer: {user_text}\nAnswer the customer's last message."
        )
        with st.chat_message("assistant"):
            with st.spinner("Typing..."):
                answer = ask_gemini(assistant_rules(), prompt)
            st.markdown(answer)
        st.session_state.chat_messages.append({"role": "assistant", "content": answer})


# ---------------------------- G. Feedback -----------------------------------
def page_feedback():
    page_header("⭐ Customer Feedback", "Tell us about your experience")

    with st.form("feedback_form", clear_on_submit=True):
        name = st.text_input("Your name (optional)", max_chars=40)
        rating = st.slider("Rating (1 = poor, 5 = excellent)", 1, 5, 5)
        comment = st.text_area("Your review", max_chars=500)
        send = st.form_submit_button("Submit feedback")

    if send:
        name = clean_text(name, 40)
        comment = clean_text(comment, 500)
        if name and not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{0,39}", name):
            st.error("Name can only contain letters and spaces.")
        elif len(comment) < 5:
            st.error("Please write a review of at least 5 characters.")
        else:
            execute(
                "INSERT INTO feedback (customer_name, rating, comment, created_at) VALUES (?, ?, ?, ?)",
                (name or "Anonymous", rating, comment, now_text()),
            )
            st.session_state.review_summary = None
            st.success("Thank you! Your feedback was saved.")

    reviews = query("SELECT * FROM feedback ORDER BY id DESC LIMIT 30")
    st.divider()
    if not reviews:
        st.info("No reviews yet. Be the first to share your experience!")
        return

    stats = query("SELECT AVG(rating) AS avg_r, COUNT(*) AS n FROM feedback")[0]
    m1, m2 = st.columns(2)
    m1.metric("Average rating", f"{stats['avg_r']:.1f} ⭐")
    m2.metric("Total reviews", stats["n"])

    st.subheader("🤖 AI summary of reviews")
    if st.button("Summarize reviews with Gemini"):
        text = "\n".join(f"- {r['rating']}/5: {r['comment']}" for r in reviews)
        rules = (
            "You summarize restaurant customer reviews. Use only the reviews given. "
            "Write: a 2-sentence overall summary, then 'What customers like' and "
            "'What can be improved' as short bullet points. Do not invent details."
        )
        with st.spinner("Reading reviews..."):
            st.session_state.review_summary = ask_gemini(rules, f"Reviews:\n{text}")
    if st.session_state.review_summary:
        st.markdown(st.session_state.review_summary)

    st.subheader("Latest reviews")
    for r in reviews[:10]:
        with st.container(border=True):
            st.markdown(f"{'⭐' * r['rating']}  **{r['customer_name']}**  ·  {r['created_at'][:10]}")
            st.text(r["comment"])  # st.text shows plain text only (safe)


# ---------------------------- F. Admin Panel --------------------------------
def admin_login():
    expected = get_secret("ADMIN_PASSWORD")
    if not expected:
        st.error("Admin password is not set. Add ADMIN_PASSWORD to your secrets (see README).")
        return
    with st.form("admin_login"):
        password = st.text_input("Admin password", type="password")
        go = st.form_submit_button("Log in")
    if go:
        if hmac.compare_digest(password.encode(), expected.encode()):
            st.session_state.admin_ok = True
            st.rerun()
        else:
            st.error("Wrong password.")


def food_form_fields(prefix, cat_names, food=None):
    """Shared input fields for adding and editing a food item."""
    food = food or {}
    name = st.text_input("Food name", value=food.get("name", ""), max_chars=80, key=f"{prefix}_name")
    default_index = cat_names.index(food["category"]) if food.get("category") in cat_names else 0
    category = st.selectbox("Category", cat_names, index=default_index, key=f"{prefix}_cat")
    description = st.text_area("Description", value=food.get("description") or "", max_chars=300, key=f"{prefix}_desc")
    ingredients = st.text_input("Ingredients (comma separated)", value=food.get("ingredients") or "", max_chars=300, key=f"{prefix}_ing")
    price = st.number_input(f"Price ({CURRENCY})", min_value=0.0, max_value=100000.0,
                            value=float(food.get("price", 0.0)), step=10.0, key=f"{prefix}_price")
    image_url = st.text_input("Image URL (optional, starts with https://)", value=food.get("image_url") or "", key=f"{prefix}_img")
    is_veg = st.checkbox("Vegetarian", value=bool(food.get("is_veg", 0)), key=f"{prefix}_veg")
    available = st.checkbox("Available on the menu", value=bool(food.get("available", 1)), key=f"{prefix}_avail")
    return name, category, description, ingredients, price, image_url, is_veg, available


def check_food_values(name, price, image_url):
    errors = []
    if len(clean_text(name, 80)) < 2:
        errors.append("Food name must have at least 2 characters.")
    if price <= 0:
        errors.append("Price must be greater than 0.")
    if image_url.strip() and not image_url.strip().startswith(("https://", "http://")):
        errors.append("Image URL must start with https:// or http://")
    return errors


def admin_menu_tab():
    categories = get_categories()
    if not categories:
        st.warning("Please add a category first (Categories tab).")
        return
    cat_names = [c["name"] for c in categories]
    cat_ids = {c["name"]: c["id"] for c in categories}

    st.subheader("➕ Add new food item")
    with st.form("add_food_form", clear_on_submit=True):
        name, category, desc, ing, price, img, veg, avail = food_form_fields("add", cat_names)
        add = st.form_submit_button("Add food item")
    if add:
        errors = check_food_values(name, price, img)
        if errors:
            for e in errors:
                st.error(e)
        else:
            execute(
                "INSERT INTO foods (name, category_id, description, ingredients, price, image_url, is_veg, available) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (clean_text(name, 80), cat_ids[category], clean_text(desc, 300), clean_text(ing, 300),
                 price, img.strip(), int(veg), int(avail)),
            )
            st.success(f"“{clean_text(name, 80)}” was added to the menu.")

    st.divider()
    st.subheader("✏️ Update or delete a food item")
    foods = get_foods(only_available=False)
    if not foods:
        st.info("There are no food items yet.")
        return
    labels = {f["id"]: f"{f['name']}  ({f['category']}) - {money(f['price'])}" for f in foods}
    chosen = st.selectbox("Select item", list(labels.keys()), format_func=lambda i: labels[i])
    food = next(f for f in foods if f["id"] == chosen)

    with st.form(f"edit_food_form_{chosen}"):
        name, category, desc, ing, price, img, veg, avail = food_form_fields(f"edit{chosen}", cat_names, food)
        confirm_delete = st.checkbox("Yes, I want to delete this item permanently", key=f"confirm_{chosen}")
        c1, c2 = st.columns(2)
        save = c1.form_submit_button("💾 Save changes")
        delete = c2.form_submit_button("🗑️ Delete item")

    if save:
        errors = check_food_values(name, price, img)
        if errors:
            for e in errors:
                st.error(e)
        else:
            execute(
                "UPDATE foods SET name=?, category_id=?, description=?, ingredients=?, price=?, "
                "image_url=?, is_veg=?, available=? WHERE id=?",
                (clean_text(name, 80), cat_ids[category], clean_text(desc, 300), clean_text(ing, 300),
                 price, img.strip(), int(veg), int(avail), chosen),
            )
            st.success("Food item updated.")
            st.rerun()
    if delete:
        if confirm_delete:
            execute("DELETE FROM foods WHERE id = ?", (chosen,))
            st.success("Food item deleted.")
            st.rerun()
        else:
            st.warning("Tick the confirmation box first.")


def admin_categories_tab():
    st.subheader("Manage categories")
    categories = query(
        "SELECT c.id, c.name, COUNT(f.id) AS items FROM categories c "
        "LEFT JOIN foods f ON f.category_id = c.id GROUP BY c.id ORDER BY c.name"
    )
    if categories:
        st.dataframe(pd.DataFrame(categories).rename(columns={"id": "ID", "name": "Category", "items": "Items"}), hide_index=True)

    with st.form("add_cat_form", clear_on_submit=True):
        new_name = st.text_input("New category name", max_chars=40)
        add = st.form_submit_button("Add category")
    if add:
        new_name = clean_text(new_name, 40)
        if len(new_name) < 2:
            st.error("Category name must have at least 2 characters.")
        elif query("SELECT id FROM categories WHERE lower(name) = lower(?)", (new_name,)):
            st.error("This category already exists.")
        else:
            execute("INSERT INTO categories (name) VALUES (?)", (new_name,))
            st.success("Category added.")
            st.rerun()

    if categories:
        names = {c["id"]: c["name"] for c in categories}
        chosen = st.selectbox("Select category", list(names.keys()), format_func=lambda i: names[i])
        with st.form("edit_cat_form"):
            rename = st.text_input("Rename to", value=names[chosen], max_chars=40, key=f"rename_{chosen}")
            c1, c2 = st.columns(2)
            do_rename = c1.form_submit_button("Rename")
            do_delete = c2.form_submit_button("Delete category")
        if do_rename:
            rename = clean_text(rename, 40)
            clash = query("SELECT id FROM categories WHERE lower(name) = lower(?) AND id != ?", (rename, chosen))
            if len(rename) < 2:
                st.error("Category name must have at least 2 characters.")
            elif clash:
                st.error("Another category already uses this name.")
            else:
                execute("UPDATE categories SET name = ? WHERE id = ?", (rename, chosen))
                st.success("Category renamed.")
                st.rerun()
        if do_delete:
            if query("SELECT id FROM foods WHERE category_id = ?", (chosen,)):
                st.error("This category still has food items. Move or delete them first.")
            else:
                execute("DELETE FROM categories WHERE id = ?", (chosen,))
                st.success("Category deleted.")
                st.rerun()


def admin_orders_tab():
    st.subheader("Customer orders")
    status_filter = st.selectbox("Show orders with status", ["All"] + ORDER_STATUSES)
    sql = (
        "SELECT o.id, o.created_at, c.name, c.phone, c.address, o.total, o.status "
        "FROM orders o JOIN customers c ON c.id = o.customer_id"
    )
    params = ()
    if status_filter != "All":
        sql += " WHERE o.status = ?"
        params = (status_filter,)
    orders = query(sql + " ORDER BY o.id DESC", params)
    if not orders:
        st.info("No orders found.")
        return
    df = pd.DataFrame(orders).rename(columns={
        "id": "Order No", "created_at": "Date", "name": "Customer", "phone": "Phone",
        "address": "Address", "total": "Total", "status": "Status"})
    st.dataframe(df, hide_index=True)

    st.subheader("Order details and status")
    order_ids = [o["id"] for o in orders]
    chosen = st.selectbox("Select order number", order_ids)
    order = next(o for o in orders if o["id"] == chosen)
    items = query("SELECT food_name AS Item, quantity AS Qty, unit_price AS Price FROM order_items WHERE order_id = ?", (chosen,))
    st.dataframe(pd.DataFrame(items), hide_index=True)
    with st.form(f"status_form_{chosen}"):
        new_status = st.selectbox("New status", ORDER_STATUSES, index=ORDER_STATUSES.index(order["status"]))
        update = st.form_submit_button("Update status")
    if update:
        execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, chosen))
        st.success(f"Order #{chosen} is now “{new_status}”.")
        st.rerun()


def admin_reports_tab():
    st.subheader("Sales reports")
    total_sales = query("SELECT COALESCE(SUM(total), 0) AS s FROM orders WHERE status != 'Cancelled'")[0]["s"]
    orders_n = query("SELECT COUNT(*) AS n FROM orders WHERE status != 'Cancelled'")[0]["n"]
    cancelled = query("SELECT COUNT(*) AS n FROM orders WHERE status = 'Cancelled'")[0]["n"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Total sales", money(total_sales))
    m2.metric("Valid orders", orders_n)
    m3.metric("Cancelled orders", cancelled)

    daily = query("SELECT date(created_at) AS Day, SUM(total) AS Sales FROM orders WHERE status != 'Cancelled' GROUP BY Day ORDER BY Day")
    by_category = query(
        "SELECT COALESCE(c.name, 'Deleted item') AS Category, SUM(oi.quantity * oi.unit_price) AS Sales "
        "FROM order_items oi JOIN orders o ON o.id = oi.order_id "
        "LEFT JOIN foods f ON f.id = oi.food_id LEFT JOIN categories c ON c.id = f.category_id "
        "WHERE o.status != 'Cancelled' GROUP BY Category ORDER BY Sales DESC"
    )
    top_items = query(
        "SELECT oi.food_name AS Dish, SUM(oi.quantity) AS Sold, SUM(oi.quantity * oi.unit_price) AS Revenue "
        "FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE o.status != 'Cancelled' "
        "GROUP BY oi.food_name ORDER BY Sold DESC LIMIT 10"
    )
    if not daily:
        st.info("Reports will appear after customers place orders.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Sales per day**")
        st.line_chart(pd.DataFrame(daily).set_index("Day"))
    with c2:
        st.markdown("**Sales per category**")
        st.bar_chart(pd.DataFrame(by_category).set_index("Category"))
    st.markdown("**Top 10 dishes**")
    st.dataframe(pd.DataFrame(top_items), hide_index=True)

    all_orders = query(
        "SELECT o.id, o.created_at, c.name, c.phone, c.address, o.subtotal, o.delivery_fee, o.total, o.status "
        "FROM orders o JOIN customers c ON c.id = o.customer_id ORDER BY o.id"
    )
    csv = pd.DataFrame(all_orders).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download all orders (CSV)", csv, file_name="orders.csv", mime="text/csv")


def page_admin():
    page_header("🔐 Admin Panel", "Manage menu, categories, orders and reports")
    if not st.session_state.admin_ok:
        admin_login()
        return
    if st.button("Log out"):
        st.session_state.admin_ok = False
        st.rerun()
    tab1, tab2, tab3, tab4 = st.tabs(["🍕 Menu items", "🗂️ Categories", "📦 Orders", "📊 Reports"])
    with tab1:
        admin_menu_tab()
    with tab2:
        admin_categories_tab()
    with tab3:
        admin_orders_tab()
    with tab4:
        admin_reports_tab()


# ----------------------------------------------------------------------------
# 7. MAIN
# ----------------------------------------------------------------------------
PAGES = {
    "🏠 Dashboard": page_dashboard,
    "📖 Menu": page_menu,
    "🛒 Cart & Order": page_order,
    "✨ AI Recommendations": page_recommend,
    "🤖 AI Assistant": page_assistant,
    "⭐ Feedback": page_feedback,
    "🔐 Admin Panel": page_admin,
}


def main():
    st.set_page_config(page_title=RESTAURANT_NAME, page_icon="🍽️", layout="wide")
    apply_style()
    setup_database()
    init_session()

    st.sidebar.title(f"🍽️ {RESTAURANT_NAME}")
    choice = st.sidebar.radio("Navigation", list(PAGES.keys()))
    cart_count = sum(st.session_state.cart.values())
    st.sidebar.markdown(f"**🛒 Cart items: {cart_count}**")
    st.sidebar.caption("AI: " + ("connected ✅" if ai_available() else "not configured ⚠️"))

    PAGES[choice]()


main()
