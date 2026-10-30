# 🍽️ AI-Powered Restaurant Management System

A beginner-friendly restaurant web app built with **Python**, **Streamlit**, **SQLite** and the **Google Gemini API**.
Customers can browse the menu, order food online, get AI meal recommendations, chat with an AI assistant and leave reviews. The restaurant owner can manage everything from a password-protected admin panel.

## Features

| Area | What it does |
|------|--------------|
| **Dashboard** | Total orders, total sales, available items, popular dishes, recent orders, average order value, sales chart |
| **Digital Menu** | 7 categories, food cards with image/description/price, search, category / vegetarian / price filters |
| **Online Ordering** | Cart, + / − quantities, automatic bill (with delivery fee), customer details, order confirmation, downloadable receipt |
| **AI Recommendation** | Gemini suggests meals by diet, budget, number of people and taste, and answers menu questions |
| **AI Assistant** | Chatbot that answers **only** from the menu and restaurant information |
| **Admin Panel** | Add / update / delete food, manage categories, view orders, update order status, sales reports, CSV export |
| **Feedback** | Star ratings, reviews, and an AI summary of all reviews |

## Technology Stack

- **Python 3.10+** – backend logic
- **Streamlit** – user interface
- **SQLite** – database (tables are created automatically on first start)
- **Google Gemini Flash** (Google AI Studio) – AI features
- **GitHub** – source code storage
- **Streamlit Community Cloud** – free online hosting

## Project Files

```
app.py            # the whole application
requirements.txt  # Python libraries
README.md         # this guide
```

## How the code is organised (for learning)

`app.py` is divided into numbered sections:

1. **Settings** – restaurant name, currency, delivery fee, restaurant info used by the AI.
2. **Database helpers** – `query()` reads data, `execute()` changes data, `init_db()` creates the tables and sample menu.
3. **Validation** – checks name, phone and address before saving.
4. **Cart and order logic** – the cart lives in `st.session_state`. When an order is placed, prices are read again from the database (so nobody can fake a price) and everything is saved in one transaction.
5. **Gemini helpers** – `ask_gemini()` sends a prompt plus strict rules ("use only this menu"). If anything fails it returns a friendly message instead of crashing.
6. **Pages** – one function per page.
7. **Main** – the sidebar menu that opens the selected page.

## Installation (local)

1. Install **Python 3.10 or newer** from <https://www.python.org/downloads/>.
2. Put the three files in one folder, e.g. `restaurant_app`.
3. Open a terminal in that folder and (optional but recommended) create a virtual environment:

   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # Mac / Linux
   ```
4. Install the libraries:

   ```bash
   pip install -r requirements.txt
   ```

## How to get a Gemini API key

1. Go to **<https://aistudio.google.com/apikey>** and sign in with your Google account.
2. Click **Create API key** and choose a project (or create one).
3. Copy the key. Keep it private – never post it online or put it inside `app.py`.

The free tier is enough for learning, but it has usage limits. If the AI says it is unavailable, wait a minute and try again.

## How to configure secrets

The app needs two secrets:

| Name | Meaning |
|------|---------|
| `GEMINI_API_KEY` | Your key from Google AI Studio |
| `ADMIN_PASSWORD` | A strong password you choose for the admin panel |

Optional: `GEMINI_MODEL` (default is `gemini-2.5-flash`). If Google retires that name, set a newer Flash model name here.

**Locally:** create a folder named `.streamlit` next to `app.py`, and inside it a file named `secrets.toml`:

```toml
GEMINI_API_KEY = "paste-your-key-here"
ADMIN_PASSWORD = "choose-a-strong-password"
```

> ⚠️ **Never upload `.streamlit/secrets.toml` to GitHub.** Only upload the three project files. If you use `git`, create a `.gitignore` file containing the lines `.streamlit/secrets.toml`, `restaurant.db` and `venv/`.

Alternatively, you can use environment variables with the same names.

## Run the application locally

```bash
streamlit run app.py
```

Your browser opens at `http://localhost:8501`. A file `restaurant.db` is created automatically with the 7 categories and 14 sample dishes.

## How to test the application

Follow this checklist:

1. **Dashboard** – opens with zeros and an "empty" message.
2. **Menu** – search "pizza"; filter by *Burgers*; tick *Vegetarian only*; click **Add to cart** on 2–3 items (the sidebar cart count increases).
3. **Cart & Order** – use ➕ ➖ 🗑️. Check: Subtotal = sum of (price × quantity), Total = Subtotal + delivery fee.
4. **Validation** – press *Confirm order* with an empty form (you should see errors), then with phone `abc` (error), then with valid details (name `Ali Khan`, phone `03001234567`, a full address). A receipt appears; download it.
5. **Dashboard** – order count, sales, popular dishes and recent orders now update. The recent-orders table shows no customer names or phone numbers.
6. **AI Recommendations** – try *Vegetarian only*, budget 1000, 2 people. Check that the dishes and prices match your menu. Ask: "Which dessert is vegetarian?"
7. **AI Assistant** – ask "What are your opening hours?" (answer from the restaurant info) and "Do you sell sushi?" (it should say it has no such information).
8. **Feedback** – submit a review, then click **Summarize reviews with Gemini**.
9. **Admin Panel** – try a wrong password, then the correct one. Add a food item; edit its price; hide it by unticking *Available*; delete it. Add/rename/delete a category (deleting is blocked when it still has food). Open *Orders*, change the status of your test order. Open *Reports*.

## Upload the project to GitHub

1. Create a free account at <https://github.com>.
2. Click **+** (top right) → **New repository**.
3. Name it, for example, `ai-restaurant-system`. Choose **Public** (Streamlit's free plan works easily with public repos) and click **Create repository**.
4. On the new repository page click **uploading an existing file**.
5. Drag and drop `app.py`, `requirements.txt` and `README.md`. **Do not upload `secrets.toml` or `restaurant.db`.**
6. Write a message like "First version" and click **Commit changes**.

## Deploy with Streamlit Community Cloud

1. Go to <https://share.streamlit.io> and sign in with **GitHub**; allow access to your repository.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Choose your repository, branch `main`, and main file path `app.py`.
4. Click **Advanced settings** → **Secrets**, and paste:

   ```toml
   GEMINI_API_KEY = "paste-your-key-here"
   ADMIN_PASSWORD = "choose-a-strong-password"
   ```
5. Click **Deploy**. Wait a few minutes while the libraries install.
6. When it finishes you get a public link like `https://your-app-name.streamlit.app`. Share it with anyone. You can change the name under **Settings → General**.

To update the app later, edit a file on GitHub and commit – Streamlit redeploys automatically. Secrets can be changed under **Settings → Secrets**.

## Limitations and things to know

- **Data may be lost on Streamlit Community Cloud.** SQLite stores data in a file on the server, and that file is reset when the app is rebuilt or restarted after sleeping. This is fine for learning and demos. For a real restaurant, move to a hosted database (for example Supabase/PostgreSQL).
- **Payment is cash on delivery only.** There is no online payment.
- **Customers have no accounts.** Orders are not linked to a login and customers cannot track an order by themselves. The admin updates the status.
- **Admin login is a single shared password.** It is good for a small project; it is not a full user-account system. Use a long password and keep it secret.
- **Customer data privacy.** Names, phones and addresses are visible only in the admin panel. They are never sent to Gemini. Menu text and review text are sent to Gemini to create AI answers.
- **Images:** food images are optional URLs. Without a URL the app shows a category emoji.
- **AI limits:** Gemini can still make mistakes. The app tells it to use only your menu data, but always check prices and ingredients. Free-tier API quotas apply.
- **Time zone:** order times use the server's clock (on Streamlit Cloud this is usually UTC).
- **Edit the restaurant details:** change `RESTAURANT_NAME`, `CURRENCY`, `DELIVERY_FEE` and `RESTAURANT_INFO` at the top of `app.py`. Keep `RESTAURANT_INFO` accurate, because the chatbot answers from it.# resturent
