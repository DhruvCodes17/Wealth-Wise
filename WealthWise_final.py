# paisa_path_app.py
import base64
import io
import json
import os
import random
import re
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from PIL import Image
import requests
import yfinance as yf
import tempfile
import json as _json

# --- Ollama integration ---
import requests, json

def query_ollama(prompt: str, model: str = "mistral") -> str:
    """
    Query local Ollama model (default: mistral).
    Make sure Ollama is running locally (ollama serve).
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt},
            stream=True,
            timeout=60
        )
        output = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                if "response" in data:
                    output += data["response"]
        return output.strip() if output else "⚠️ No response from Ollama."
    except Exception as e:
        return f"⚠️ Error connecting to Ollama: {e}"

# =========================
# CONFIG
# =========================
DATA_FILE = "data.json"

# Paths for images
LOGO_IMAGE = r"c:\Users\pasri\Desktop\Wealth Wise\Logo.jpg" # Place logo above the heading

# =========================
# UTILITY FUNCTIONS
# =========================
def fmt_money(amount):
    """Format money with commas for thousands and ₹ symbol"""
    if isinstance(amount, (int, float)):
        return f"₹{amount:,.0f}"
    return f"₹0"

def calc_emi(principal, rate, months):
    """Calculate EMI amount"""
    monthly_rate = rate / 12 / 100
    if monthly_rate == 0:
        return principal / months
    return principal * monthly_rate * (1 + monthly_rate)**months / ((1 + monthly_rate)**months - 1)

# =========================
# PERSISTENCE (JSON)
# =========================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "users": {},
        "profiles": {},
        "history": {},
        "records": {},
        "emis": {},
        "investments": {},
        "portfolio": {}
    }


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =========================
# AUTH VIEW
# =========================
def auth_view():
    # Display image above WealthWise title
    try:
        if os.path.exists(LOGO_IMAGE):
            logo = Image.open(LOGO_IMAGE)
            col1, col2, col3 = st.columns([3, 2, 3]) # Create columns for centering
            with col2:
                st.image(logo, width=200, use_container_width="auto")
    except:
        st.write("")

    # Title - MODIFIED THIS LINE
    st.markdown(
    "<h2 style='text-align:center; margin-left:45px;'>💰 Your Finance Pal</h2>",
    unsafe_allow_html=True)
    st.write("---")

    # Login/Register Tabs
    tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register"])

    # -------------------------
    # LOGIN TAB
    # -------------------------
    with tab_login:
        l_user = st.text_input("Username", key="login_user_input")
        l_pass = st.text_input("Password", type="password", key="login_pass_input")
        if st.button("Login", use_container_width=True, key="login_button"):
            users = st.session_state.data["users"]
            if l_user in users and users[l_user] == l_pass:
                st.session_state.auth_user = l_user
                st.success(f"✅ Welcome {l_user}, you are logged in!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

        # Forgot Password Section
        with st.expander("🔑 Forgot Password?"):
            fp_user = st.text_input("Enter your username", key="fp_user_input")
            fp_contact = st.text_input("Enter your registered Email/Phone", key="fp_contact_input")
            # A simple placeholder for the forgot password functionality
            if st.button("Reset Password", key="reset_button"):
                st.info("Password reset instructions would be sent here.")


    # -------------------------
    # REGISTER TAB
    # -------------------------
    with tab_register:
        r_user = st.text_input("Choose a Username", key="reg_user_input")
        r_pass = st.text_input("Create a Password", type="password", key="reg_pass_input")
        r_pass_conf = st.text_input("Confirm Password", type="password", key="reg_pass_conf_input")
        if st.button("Register", use_container_width=True, key="reg_button"):
            users = st.session_state.data["users"]
            if r_user in users:
                st.error("Username already exists.")
            elif not r_pass or r_pass != r_pass_conf:
                st.error("Passwords do not match.")
            else:
                st.session_state.data["users"][r_user] = r_pass
                save_data(st.session_state.data)
                st.success("✅ Registered successfully! Please log in.")


# =========================
# PROFILE VIEW
# =========================
def profile_view():
    user = st.session_state.auth_user
    st.subheader("👤 Your Profile")
    prof = st.session_state.data["profiles"].get(user, {"name": "", "city": "", "age": "", "risk": "Moderate"})
    c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
    with c1:
        prof["name"] = st.text_input("Full Name", value=prof.get("name", ""))
    with c2:
        prof["city"] = st.text_input("City", value=prof.get("city", ""))
    with c3:
        prof["age"] = st.text_input("Age", value=str(prof.get("age", "")))
    with c4:
        prof["risk"] = st.selectbox(
            "Risk Preference",
            ["Conservative", "Moderate", "Aggressive"],
            index=["Conservative", "Moderate", "Aggressive"].index(prof.get("risk", "Moderate"))
        )
    if st.button("💾 Save Profile"):
        st.session_state.data["profiles"][user] = prof
        save_data(st.session_state.data)
        st.success("Profile saved ✔️")
# =========================
# RECORDS VIEW
# =========================
def records_view():
    user = st.session_state.auth_user
    st.subheader("🧾 Records (Income & Expense)")
    records = st.session_state.data["records"].setdefault(user, {"incomes": [], "expenses": []})

    t1, t2 = st.tabs(["➕ Add Record", "📚 View Records"])

    # =======================
    # TAB 1: Add Record
    # =======================
    with t1:
        rec_type = st.radio("Type", ["Income", "Expense"], horizontal=True)
        colA, colB, colC = st.columns([2, 2, 2])
        with colA:
            title = st.text_input("Title", placeholder="Salary / Rent / Shopping")
        with colB:
            amount = st.number_input("Amount (₹)", min_value=0, step=100, value=0)
        with colC:
            date_str = st.date_input("Date", value=datetime.today()).strftime("%Y-%m-%d")

        if st.button("Add"):
            if title and amount > 0:
                item = {"title": title, "amount": int(amount), "date": date_str}
                if rec_type == "Income":
                    records["incomes"].append(item)
                else:
                    records["expenses"].append(item)
                st.session_state.data["records"][user] = records
                save_data(st.session_state.data)
                st.success("Record added ✔️")
            else:
                st.warning("Please enter a title and amount.")

    # =======================
    # TAB 2: View Records
    # =======================
    with t2:
        col1, col2 = st.columns(2)

        # Incomes
        with col1:
            st.markdown("### Incomes")
            if records["incomes"]:
                for i, r in enumerate(records["incomes"][::-1]):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"• {r['date']} — **{r['title']}**: {fmt_money(r['amount'])}")
                    with c2:
                        if st.button("❌", key=f"del_income_{i}"):
                            records["incomes"].pop(len(records["incomes"]) - 1 - i)
                            save_data(st.session_state.data)
                            st.rerun()
            else:
                st.info("No incomes added yet.")

        # Expenses
        with col2:
            st.markdown("### 💸 Expenses")

            # Expense form
            with st.form("expense_form", clear_on_submit=True):
                exp_cat = st.text_input("Category")
                exp_amt = st.number_input("Amount (₹)", min_value=0, step=100)
                exp_note = st.text_area("Note")
                exp_bill = st.file_uploader("Upload Bill/Receipt", type=["png", "jpg", "jpeg"])

                submitted = st.form_submit_button("➕ Add Expense")
                if submitted and exp_cat and exp_amt > 0:
                    bill_data = None
                    if exp_bill is not None:
                        bill_data = base64.b64encode(exp_bill.read()).decode("utf-8")

                    exp_record = {
                        "category": exp_cat,
                        "amount": exp_amt,
                        "note": exp_note,
                        "bill": bill_data
                    }

                    records["expenses"].append(exp_record)
                    st.session_state.data["records"][user] = records
                    save_data(st.session_state.data)
                    st.success("Expense added successfully!")

            # Show Expenses
            st.markdown("### 📜 Your Expenses")
            for exp in records.get("expenses", []):
                category = exp.get("category", exp.get("title", "Unknown"))
                amount = exp.get("amount", 0)
                note = exp.get("note", exp.get("date", ""))

                st.write(f"**{category}** - ₹{amount} ({note})")

                if exp.get("bill"):
                    st.image(base64.b64decode(exp["bill"]), caption="Bill/Receipt", use_container_width=True)
# =========================
# PLANNER VIEW
# =========================
def planner_view():
    st.subheader("🧭 Planner")
    c1, c2 = st.columns(2)
    with c1:
        income = st.number_input("📥 Monthly Income (₹)", min_value=1000, step=500, value=int(st.session_state.prefill_income) if isinstance(st.session_state.prefill_income,(int,float)) else 30000)
        goal_name = st.text_input("🎯 Your Goal (e.g., Buy a scooter)", value=st.session_state.prefill_goal_name or "", placeholder="E.g., Buy a scooter")
    with c2:
        goal_amount = st.number_input("💵 Goal Amount (₹)", min_value=1000, step=1000, value=int(st.session_state.prefill_goal_amount) if isinstance(st.session_state.prefill_goal_amount,(int,float)) else 100000)
        months = st.number_input("⏳ Timeline (months)", min_value=1, step=1, value=int(st.session_state.prefill_months) if isinstance(st.session_state.prefill_months,int) and st.session_state.prefill_months>=1 else 6)
    if income > 0 and goal_amount > 0 and months > 0:
        monthly_saving_required = goal_amount / months
        st.markdown("### 📊 Savings Summary")
        st.info(f"👉 To achieve **{goal_name or 'your goal'}** worth {fmt_money(goal_amount)}, you must save at least **{fmt_money(monthly_saving_required)}/month** for {months} months.")
        # Customization with st.expander("⚙️ Customize Your Plan", expanded=True):
        default_rate = max(5, min(70, int((monthly_saving_required / income) * 100)))
        saving_rate = st.slider("💵 Saving rate (% of income)", 5, 70, default_rate)
        invest_growth = st.slider("📈 Expected monthly growth (if invested %)", 0, 5, 1)
        actual_saving = (saving_rate / 100) * income
        st.success(f"✅ You plan to save **{fmt_money(actual_saving)}/month** with **{invest_growth}%** monthly growth.")
        # Visualization
        st.markdown("### 📈 Savings Visualization")
        view_option = st.radio("Choose a view:", ["Planned vs Goal","Realistic Simulation","Invested Growth"], horizontal=True)
        months_array = np.arange(1, months+1)
        fig, ax = plt.subplots()
        if view_option == "Planned vs Goal":
            ideal_savings = np.cumsum([monthly_saving_required] * months)
            ax.plot(months_array, ideal_savings, marker="o", label="Planned Savings")
        elif view_option == "Realistic Simulation":
            realistic_savings = np.cumsum([actual_saving * (1 + random.uniform(-0.2,0.2)) for _ in range(months)])
            ax.plot(months_array, realistic_savings, marker="x", linestyle="--", label="Realistic Savings")
        else:
            invested_savings = []
            total = 0.0
            for _ in range(months):
                total = (total + actual_saving) * (1 + invest_growth / 100.0)
                invested_savings.append(total)
            ax.plot(months_array, invested_savings, marker="s", linestyle=":", label="Invested Savings")
        ax.axhline(y=goal_amount, linestyle="--", label=f"Goal {fmt_money(goal_amount)}")
        ax.set_title("Savings Journey")
        ax.set_xlabel("Month"); ax.set_ylabel("Total Savings (₹)"); ax.legend()
        st.pyplot(fig)
        # Save Plan
        if st.button("💾 Save this plan to History"):
            user = st.session_state.auth_user
            entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "income": int(income),
                "goal": goal_name or "Unnamed goal",
                "goal_amount": int(goal_amount),
                "months": int(months),
                "saved_per_month_required": int(round(monthly_saving_required)),
                "plan_saving_rate_pct": int(saving_rate),
                "plan_monthly_saving": int(round(actual_saving)),
                "expected_growth_pct": int(invest_growth),
                "view": view_option,
            }
            st.session_state.data["history"].setdefault(user, []).append(entry)
            save_data(st.session_state.data)
            st.success("✅ Plan saved to history!")
        # Progress Tracker
        st.markdown("### 📅 Progress Tracker")
        progress_month = st.slider("Current Month", 1, months, 1) if months > 1 else 1
        st.progress(progress_month / months, text=f"{progress_month}/{months} months completed")
        # Rewards
        st.markdown("### 🏆 Rewards")
        if monthly_saving_required < income * 0.2:
            st.success("🥉 Bronze Saver – Easy goal, you’re on track!")
        elif monthly_saving_required < income * 0.4:
            st.info("🥈 Silver Saver – Good discipline required, keep going!")
        else:
            st.warning("🥇 Gold Saver – Big challenge! Stay consistent 🚀")
                  # AI Financial Coach
# =========================
# EMIS VIEW
# =========================
def emis_view():
    user = st.session_state.auth_user
    st.subheader("🏦 EMIs &amp; Loans")
    emis = st.session_state.data.setdefault("emis", {}).setdefault(user, [])
    t1, t2 = st.tabs(["➕ Add EMI/Loan", "📊 View EMIs"])
    with t1:
        name = st.text_input("Loan/EMI Name", placeholder="Car Loan")
        principal = st.number_input("Principal Amount (₹)", min_value=0, step=1000)
        rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, step=0.1)
        months = st.number_input("Tenure (Months)", min_value=1, step=1)
        if st.button("Add EMI"):
            emi_amount = calc_emi(principal, rate, months)
            emis.append({
                "name": name,
                "principal": principal,
                "rate": rate,
                "months": months,
                "emi_amount": round(emi_amount,0)
            })
            st.session_state.data["emis"][user] = emis
            save_data(st.session_state.data)
            st.success(f"Added {name} with EMI {fmt_money(emi_amount)}")
    with t2:
        if emis:
            for i, e in enumerate(emis):
                c1, c2 = st.columns([4,1])
                with c1:
                    st.write(f"• {e['name']} – EMI: {fmt_money(e['emi_amount'])}, " f"Principal: {fmt_money(e['principal'])}, Rate: {e['rate']}%, " f"Tenure: {e['months']} months")
                with c2:
                    if st.button("❌", key=f"del_emi_{i}"):
                        emis.pop(i)
                        st.session_state.data["emis"][user] = emis
                        save_data(st.session_state.data)
                        st.rerun()
        else:
            st.info("No EMIs added yet.")

# =========================
# INVESTMENTS VIEW
# =========================
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# --- Helper Functions ---
def get_nse_symbol_list():
    return [
        "ADANIPORTS.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS",
        "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
        "INFRATEL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS",
        "DRREDDY.NS", "EICHERMOT.NS", "GAIL.NS", "GRASIM.NS",
        "HCLTECH.NS", "HDFC.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
        "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
        "ITC.NS", "IOC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS",
        "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS",
        "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELAXO.NS", "RELIANCE.NS",
        "SBIN.NS", "SHREECEM.NS", "SUNPHARMA.NS", "TCS.NS", "TATAMOTORS.NS",
        "TATASTEEL.NS", "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS"
    ]

def fetch_live_price(symbol: str) -> float:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="1d")
    if not hist.empty:
        return float(hist["Close"].iloc[-1])
    return 0.0

# --- Main View ---
def get_live_market_data():
    """Fetch live NIFTY 50 and SENSEX data using yfinance"""
    indices = {
        "nifty": "^NSEI",   # NIFTY 50 Yahoo Finance symbol
        "sensex": "^BSESN"  # SENSEX Yahoo Finance symbol
    }
    data = {}
    for name, symbol in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[0])
                change_pct = ((current - prev_close) / prev_close) * 100
                data[name] = {"current": current, "change": change_pct}
        except Exception as e:
            st.error(f"⚠️ Error fetching {name.upper()} data: {e}")
            return None
    return data if data else None
def get_top_stocks(limit: int = 10):
    """
    Fetch top performing NSE stocks from the symbol list using yfinance.
    Returns a list of dicts: [{"Symbol": "...", "Current Price": ..., "Change (%)": ...}, ...]
    """
    symbols = get_nse_symbol_list()
    results = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")  # need at least 2 days to calculate change
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                current = float(hist["Close"].iloc[-1])
                change_pct = ((current - prev_close) / prev_close) * 100
                results.append({
                    "Symbol": symbol.replace(".NS", ""),
                    "Current Price": round(current, 2),
                    "Change (%)": round(change_pct, 2)
                })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            continue

    # Sort by daily change descending (top gainers first)
    results = sorted(results, key=lambda x: x["Change (%)"], reverse=True)

    return results[:limit] if results else None

def investments_view():
    """Enhanced investments view with NSE live stock picker & portfolio"""
    user = st.session_state.auth_user
    st.subheader("📈 Investments & Live Market Data")

    # --- Live Market Data Section ---
    st.markdown("### 🔴 Live Indian Stock Market")
    with st.spinner("Fetching live market data..."):
        market_data = get_live_market_data()

    if market_data:
        col1, col2 = st.columns(2)
        with col1:
            nifty_change = market_data['nifty']['change']
            nifty_color = "🟢" if nifty_change >= 0 else "🔴"
            st.metric(f"{nifty_color} NIFTY 50",
                      f"₹{market_data['nifty']['current']:.2f}",
                      f"{nifty_change:+.2f}%")
        with col2:
            sensex_change = market_data['sensex']['change']
            sensex_color = "🟢" if sensex_change >= 0 else "🔴"
            st.metric(f"{sensex_color} BSE SENSEX",
                      f"₹{market_data['sensex']['current']:.2f}",
                      f"{sensex_change:+.2f}%")
    else:
        st.warning("Unable to fetch live market data. Please check your internet connection.")

    # --- Top Stocks Section ---
    st.markdown("### 🏆 Top Stocks of the Day")
    with st.spinner("Fetching top stocks..."):
        top_stocks = get_top_stocks()

    if top_stocks:
        df = pd.DataFrame(top_stocks[:10])

        def highlight_gains_losses(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return 'background-color: #d4edda; color: #155724'
                elif val < 0:
                    return 'background-color: #f8d7da; color: #721c24'
            return ''
        styled_df = df.style.applymap(highlight_gains_losses, subset=['Change (%)'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        if len(top_stocks) >= 5:
            st.markdown("#### 📊 Top 5 Performers Chart")
            top_5 = df.head(5)
            fig, ax = plt.subplots(figsize=(10, 6))
            colors = ['green' if x >= 0 else 'red' for x in top_5['Change (%)']]
            bars = ax.bar(top_5['Symbol'], top_5['Change (%)'], color=colors, alpha=0.7)
            for bar, value in zip(bars, top_5['Change (%)']):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height >= 0 else -0.3),
                        f'{value:.1f}%', ha='center',
                        va='bottom' if height >= 0 else 'top')
            ax.set_title('Top 5 Stock Performers Today', fontsize=14, fontweight='bold')
            ax.set_ylabel('Change (%)'); ax.set_xlabel('Stock Symbol')
            ax.grid(axis='y', alpha=0.3); plt.xticks(rotation=45, ha='right')
            plt.tight_layout(); st.pyplot(fig)
    else:
        st.info("Unable to fetch live stock data. Please try again later.")

    st.markdown("---")

    # --- Educational Resources Section ---
    st.markdown("### 📚 Learn About Stock Market Investments")
    st.info("🎓 **New to investing?** Start with these educational resources to understand the basics!")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🇮🇳 हिंदी में सीखें")
        st.markdown("🎥 **[Hindi Tutorial देखें](https://www.youtube.com/watch?v=fzp02ud0AHc)**")
    with col2:
        st.markdown("#### 🇬🇧 Learn in English")
        st.markdown("🎥 **[English Tutorial](https://www.youtube.com/watch?v=iWBjHPFrwrM)**")
    with col3:
        st.markdown("#### 🇮🇳 ಕನ್ನಡದಲ್ಲಿ ಕಲಿಯಿರಿ")
        st.markdown("🎥 **[Kannada Tutorial](https://www.youtube.com/watch?v=bKmMYxgYl6E)**")

    # --- Quick Tips ---
    st.markdown("### 💡 Quick Investment Tips")
    col_a, col_b = st.columns(2)
    with col_a:
        st.success("""**✅ Do's:**
- Research before investing
- Diversify your portfolio
- Invest for long term
- Monitor market trends""")
    with col_b:
        st.error("""**❌ Don'ts:**
- Don't invest borrowed money
- Avoid panic selling
- Don't put all eggs in one basket
- Don't follow tips blindly""")

    st.markdown("---")

    # --- Portfolio Section ---
    st.markdown("### 💼 Your Investment Portfolio")
    investments = st.session_state.data.setdefault("investments", {}).setdefault(user, [])
    tab_add, tab_view = st.tabs(["➕ Add Investment", "📊 View Investments"])

    # --- Add Investment Tab (with yfinance integration) ---
    with tab_add:
        all_symbols = get_nse_symbol_list()
        sel = st.selectbox("Select NSE Stock", options=all_symbols,
                           format_func=lambda s: s.replace(".NS", ""))
        live_price = None
        if sel:
            live_price = fetch_live_price(sel)
            st.markdown(f"**Live Price** (as of {datetime.now().strftime('%Y-%m-%d %H:%M')}): ₹{live_price:,.2f}")

        units = st.number_input("Units/Quantity", min_value=1, step=1, value=1)
        submitted = st.button("💾 Add Investment")
        if submitted:
            if sel and units > 0 and live_price and live_price > 0:
                investments.append({
                    "name": sel.replace(".NS", ""),
                    "symbol": sel,
                    "units": units,
                    "purchase_price": live_price,
                    "current_price": live_price,
                    "purchase_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "added_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                st.session_state.data["investments"][user] = investments
                save_data(st.session_state.data)
                st.success(f"✅ Added {sel.replace('.NS','')} @ ₹{live_price:,.2f} to your portfolio")
                st.rerun()
            else:
                st.error("Unable to fetch live price or invalid units. Please try again.")

    # --- View Portfolio Tab ---
    with tab_view:
        if not investments:
            st.info("📝 No investments added yet. Start building your portfolio!")
        else:
            total_invested = sum(inv["units"] * inv["purchase_price"] for inv in investments)
            total_current = sum(inv["units"] * inv["current_price"] for inv in investments)
            total_pnl = total_current - total_invested
            pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Invested", f"₹{total_invested:,.0f}")
            col2.metric("Current Value", f"₹{total_current:,.0f}")
            col3.metric("P&L", f"₹{total_pnl:,.0f}", f"{pnl_pct:+.1f}%")
            col4.metric("Investments", len(investments))

            st.markdown("---")

            # Show table
            df = pd.DataFrame(investments)
            df["Invested Amount"] = df["units"] * df["purchase_price"]
            df["Current Value"] = df["units"] * df["current_price"]
            df["P&L (₹)"] = df["Current Value"] - df["Invested Amount"]
            df["P&L (%)"] = (df["P&L (₹)"] / df["Invested Amount"] * 100).round(1)
            st.dataframe(df[["name","symbol","units","purchase_price","current_price",
                             "Invested Amount","Current Value","P&L (₹)","P&L (%)"]],
                         use_container_width=True)

            # Remove investment
            for i, inv in enumerate(investments):
                col1, col2 = st.columns([8, 1])
                with col1:
                    st.markdown(f"**{inv['name']}** ({inv.get('symbol','')}) | Units: {inv['units']} | Buy: ₹{inv['purchase_price']:,.2f}")
                with col2:
                    if st.button("🗑️ Remove", key=f"del_inv_{i}"):
                        investments.pop(i)
                        st.session_state.data["investments"][user] = investments
                        save_data(st.session_state.data)
                        st.rerun()

            # Portfolio breakdown chart
            if len(investments) > 1:
                st.markdown("#### Portfolio Distribution")
                type_data = {}
                for inv in investments:
                    inv_type = inv.get('type', "Stock")
                    current_value = inv['units'] * inv['current_price']
                    type_data[inv_type] = type_data.get(inv_type, 0) + current_value

                if type_data:
                    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
                    ax1.pie(type_data.values(), labels=type_data.keys(), autopct='%1.1f%%', startangle=90)
                    ax1.set_title('Portfolio by Investment Type')
                    names = [inv['name'] for inv in investments]
                    values = [inv['units'] * inv['current_price'] for inv in investments]
                    ax2.bar(range(len(names)), values)
                    ax2.set_title('Individual Investment Values')
                    ax2.set_ylabel('Current Value (₹)')
                    ax2.set_xticks(range(len(names)))
                    ax2.set_xticklabels(names, rotation=45, ha='right')
                    plt.tight_layout()
                    st.pyplot(fig)
# =========================
# PORTFOLIO VIEW
# =========================
def portfolio_view():
    user = st.session_state.auth_user
    st.subheader("💹 Complete Portfolio Overview")
    records = st.session_state.data.get("records", {}).get(user, {"incomes": [], "expenses": []})
    emis = st.session_state.data.get("emis", {}).get(user, [])
    investments = st.session_state.data.get("investments", {}).get(user, [])
    portfolio = st.session_state.data.setdefault("portfolio", {}).setdefault(user, [])
    history = st.session_state.data.get("history", {}).get(user, [])
    total_income = sum(r.get("amount", 0) for r in records.get("incomes", []))
    total_expense = sum(r.get("amount", 0) for r in records.get("expenses", []))
    total_emi = sum(e.get("emi_amount", 0) for e in emis)
    total_investment_value = sum(inv.get("projected_values", [0])[-1] for inv in investments if inv.get("projected_values"))
    total_recent_savings = sum(h.get("plan_monthly_saving", 0) for h in history[-6:])
    total_portfolio_invested = sum(p.get("units", 0) * p.get("purchase_price", 0) for p in portfolio)
    total_portfolio_current = sum(p.get("units", 0) * p.get("current_price", 0) for p in portfolio)
    expected_returns = {"Share/Stock": 12, "Equity": 10, "Mutual Fund": 8, "Other": 5}
    total_portfolio_projected = sum( (p.get("units", 0) * p.get("current_price", 0)) * (1 + expected_returns.get(p.get("type"), 5) / 100) for p in portfolio )
    st.markdown("### 📊 Summary Metrics")
    col1, col2, col3 = st.columns(3)
    col1.metric("💵 Total Income", fmt_money(total_income))
    col1.metric("💸 Total Expenses", fmt_money(total_expense))
    col2.metric("🏦 Total EMIs", fmt_money(total_emi))
    col2.metric("📈 Total Investment Value", fmt_money(total_investment_value))
    col3.metric("💰 Recent Savings (last 6 plans)", fmt_money(total_recent_savings))
    col3.metric("💹 Portfolio Current Value", fmt_money(total_portfolio_current))
    st.markdown(f"**Projected Portfolio Value in 1 Year:** {fmt_money(total_portfolio_projected)}")
    # Pie chart (safe values only)
    labels = ["Expenses", "EMIs", "Investments", "Recent Savings", "Portfolio Current"]
    values = [total_expense, total_emi, total_investment_value, total_recent_savings, total_portfolio_current]
    filtered = [(l, v) for l, v in zip(labels, values) if v and not pd.isna(v) and v > 0]
    if filtered:
        labels, values = zip(*filtered)
        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140)
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No valid data to show distribution chart.")
    # Add portfolio item (keeps properties intact and allows populating portfolio)
    st.markdown("### ➕ Add to Portfolio")
    with st.form("add_portfolio", clear_on_submit=True):
        p_name = st.text_input("Name", placeholder="TCS / My Fund")
        p_type = st.selectbox("Type", ["Share/Stock", "Mutual Fund", "Equity", "Other"])
        p_units = st.number_input("Units", min_value=1, step=1, value=1)
        p_purchase_price = st.number_input("Purchase Price per Unit (₹)", min_value=1, step=1, value=100)
        p_current_price = st.number_input("Current Price per Unit (₹)", min_value=1, step=1, value=100)
        submitted = st.form_submit_button("Add to Portfolio")
        if submitted:
            portfolio.append({
                "name": p_name,
                "type": p_type,
                "units": p_units,
                "purchase_price": p_purchase_price,
                "current_price": p_current_price
            })
            st.session_state.data["portfolio"][user] = portfolio
            save_data(st.session_state.data)
            st.success("Portfolio item added.")
    # Portfolio Table + Charts
    if portfolio:
        st.markdown("### 📋 Portfolio Details")
        for i, p in enumerate(portfolio):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(f"• {p['name']} ({p['type']}) — Units: {p['units']}, " f"Buy @ {fmt_money(p['purchase_price'])}, Now @ {fmt_money(p['current_price'])}")
            with c2:
                if st.button("❌", key=f"del_port_{i}"):
                    portfolio.pop(i)
                    st.session_state.data["portfolio"][user] = portfolio
                    save_data(st.session_state.data)
                    st.rerun()
        df = pd.DataFrame(portfolio).fillna(0)
        if not df.empty:
            df["Invested Amount"] = df["units"] * df["purchase_price"]
            df["Current Value"] = df["units"] * df["current_price"]
            df["Profit/Loss"] = df["Current Value"] - df["Invested Amount"]
            df["Expected Annual Growth %"] = df["type"].map(expected_returns).fillna(5)
            df["Projected Value"] = df["Current Value"] * (1 + df["Expected Annual Growth %"] / 100)
            df["Projected Profit/Loss"] = df["Projected Value"] - df["Invested Amount"]
            st.dataframe(df[[ "type", "name", "units", "purchase_price", "current_price", "Invested Amount", "Current Value", "Profit/Loss", "Expected Annual Growth %", "Projected Value", "Projected Profit/Loss" ]])
            # Distribution chart
            type_summary = df.groupby("type")["Current Value"].sum()
            if type_summary.sum() > 0:
                fig2, ax2 = plt.subplots()
                ax2.pie(type_summary, labels=type_summary.index, autopct="%1.1f%%", startangle=90)
                ax2.set_title("Portfolio Distribution by Type")
                st.pyplot(fig2)
            # Profit/Loss chart
            fig3, ax3 = plt.subplots()
            names = df["name"].tolist()
            profits = df["Profit/Loss"].tolist()
            ax3.bar(range(len(names)), profits)
            ax3.set_xticks(range(len(names)))
            ax3.set_xticklabels(names, rotation=15, ha="right")
            ax3.set_ylabel("Profit / Loss (₹)")
            ax3.set_title("Profit/Loss per Investment")
            st.pyplot(fig3)
            # Projected Profit/Loss chart
            fig4, ax4 = plt.subplots()
            projected = df["Projected Profit/Loss"].tolist()
            ax4.bar(range(len(names)), projected)
            ax4.set_xticks(range(len(names)))
            ax4.set_xticklabels(names, rotation=15, ha="right")
            ax4.set_ylabel("Projected Profit / Loss (₹)")
            ax4.set_title("Projected Profit/Loss per Investment (1 yr)")
            st.pyplot(fig4)
    else:
        st.info("No portfolio investments yet.")
# NEW SIDEBAR CHATBOT
# =========================
import google.generativeai as genai

import streamlit as st
import requests
import json

import streamlit as st
from huggingface_hub import InferenceClient

import streamlit as st
import requests
import json

import requests
from bs4 import BeautifulSoup
import re

import requests
import json

# =========================
# ENHANCED FINANCE CHATBOT
# =========================
import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import quote_plus

def get_enhanced_web_summary(query):
    """
    Enhanced web scraping with multiple search engines and robust error handling
    """

    # Comprehensive headers to avoid detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

    # Multiple search engines as fallback
    search_engines = [
        {
            'name': 'DuckDuckGo',
            'url': f'https://html.duckduckgo.com/html/?q={quote_plus(query + " finance India")}',
            'result_selector': '.result__title a',
            'snippet_selector': '.result__snippet'
        },
        {
            'name': 'Startpage',
            'url': f'https://www.startpage.com/sp/search?query={quote_plus(query + " finance India")}&t=device&language=english&cat=web',
            'result_selector': '.w-gl__result-title',
            'snippet_selector': '.w-gl__description'
        }
    ]

    for engine in search_engines:
        try:
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))

            response = requests.get(
                engine['url'],
                headers=headers,
                timeout=10,
                allow_redirects=True
            )

            # Check if request was successful
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract search results
                results = []
                title_elements = soup.select(engine['result_selector'])

                for i, element in enumerate(title_elements[:5]):
                    title = element.get_text().strip()
                    if title:
                        results.append(title)

                if results:
                    summary = generate_finance_summary(query, results)
                    return summary

        except requests.exceptions.RequestException as e:
            continue  # Try next search engine
        except Exception as e:
            continue

    # If all search engines fail, return finance-specific fallback
    return get_finance_fallback_response(query)

def generate_finance_summary(query, results):
    """
    Generate intelligent finance summary from search results
    """
    summary = "**📊 Summary:**\n\n"

    # Add top 3 results
    for i, result in enumerate(results[:3], 1):
        summary += f"• {result}\n"

    summary += f"\n**Quick Finance Summary:**\n"

    # Enhanced keyword-based responses
    query_lower = query.lower()

    if any(term in query_lower for term in ['sip', 'systematic investment plan', 'mutual fund']):
        summary += """
**SIP (Systematic Investment Plan)** allows you to invest a fixed amount regularly in mutual funds. Key benefits:
- **Rupee Cost Averaging**: Buy more units when prices are low, fewer when high
- **Disciplined Investment**: Automated monthly investments
- **Compounding**: Long-term wealth creation through compounding
- **Flexible**: Can start with as low as ₹500/month
        """

    elif any(term in query_lower for term in ['tax', 'save tax', 'tax saving', '80c']):
        summary += """
**Tax Saving Investment Options in India:**
- **Section 80C**: ELSS, PPF, NSC, Tax-saving FDs (up to ₹1.5 lakh)
- **Section 80D**: Health insurance premiums (up to ₹25,000)
- **NPS**: Additional ₹50,000 deduction under 80CCD(1B)
- **Home Loan**: Interest deduction up to ₹2 lakh under 24(b)
        """

    elif any(term in query_lower for term in ['emi', 'loan', 'interest', 'home loan', 'personal loan']):
        summary += """
**EMI & Loan Information:**
- **EMI Formula**: Principal × Rate × (1+Rate)^Tenure / ((1+Rate)^Tenure-1)
- **Factors affecting EMI**: Principal amount, interest rate, loan tenure
- **Credit Score Impact**: Higher score = lower interest rates
- **Prepayment**: Reduces overall interest burden
        """

    elif any(term in query_lower for term in ['credit score', 'cibil', 'credit report']):
        summary += """
**Credit Score in India (300-900 range):**
- **750+**: Excellent - Best loan rates
- **700-749**: Good - Competitive rates
- **650-699**: Fair - Higher interest rates
- **Below 650**: Poor - Loan approval difficult
**Improvement Tips**: Pay on time, keep credit utilization low, maintain old accounts
        """

    elif any(term in query_lower for term in ['fd', 'fixed deposit', 'saving account', 'interest rates']):
        summary += """
**Current Bank Interest Rates (approx.):**
- **Savings Account**: 3-4% per annum
- **Fixed Deposits**: 5.5-7.5% (depending on tenure)
- **Senior Citizen FD**: Additional 0.5% interest
- **Tax**: Interest above ₹10,000 is taxable
        """

    else:
        summary += """
**General Finance Tips:**
- **Emergency Fund**: Maintain 6-12 months of expenses
- **Diversify**: Don't put all money in one investment
- **Start Early**: Power of compounding works best over time
- **Review Regularly**: Assess and rebalance your portfolio
        """

    summary += f"\n\n💡 **Need detailed advice?** Consider consulting a SEBI-registered financial advisor."

    return summary

def get_finance_fallback_response(query):
    """
    Fallback response when web scraping fails
    """
    query_lower = query.lower()

    fallback_responses = {
        'sip': """
**SIP (Systematic Investment Plan):**

**What is SIP?**
- Regular investment method for mutual funds
- Fixed amount invested monthly/quarterly
- Automatic debit from bank account

**Benefits:**
- Rupee cost averaging
- Disciplined investment habit
- Power of compounding
- Flexible - start/stop anytime

**How to Start:**
- Choose AMC (Asset Management Company)
- Select mutual fund scheme
- Complete KYC process
- Set up auto-debit mandate
        """,

        'tax': """
**Tax Saving in India - Key Options:**

**Section 80C (up to ₹1.5 lakh):**
- ELSS mutual funds (3-year lock-in)
- PPF (15-year lock-in, tax-free returns)
- NSC, Tax-saving FDs
- Life insurance premiums

**Other Deductions:**
- 80D: Health insurance (₹25,000-₹50,000)
- 80CCD(1B): NPS additional (₹50,000)
- 24(b): Home loan interest (₹2 lakh)
        """,

        'emi': """
**EMI Calculation & Tips:**

**EMI Components:**
- Principal amount
- Interest rate (fixed/floating)
- Loan tenure

**Tips to Reduce EMI:**
- Make higher down payment
- Choose longer tenure (but more interest)
- Compare rates across banks
- Maintain good credit score

**Prepayment Strategy:**
- Reduces total interest burden
- Check prepayment charges
        """
    }

    # Return specific fallback or general advice
    for key, response in fallback_responses.items():
        if key in query_lower:
            return f"**Helpful Information:**\n{response}"

    return """
**Popular Finance Topics:**
• SIP and mutual fund investments
• Tax saving options in India
• EMI calculations and loan tips
• Credit score improvement
• Fixed deposits and savings accounts
• Stock market basics

**Quick Finance Tip:** Always diversify your investments across different asset classes (equity, debt, gold) based on your risk appetite and financial goals.

*Try asking about specific topics mentioned above for detailed information.*
    """

def sidebar_chatbot():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## AI FINANCE ASSISTANT 🤖")
    st.sidebar.info("Ask any finance question")

    user_query = st.sidebar.text_area(
        "Your question:",
        placeholder="e.g., What is SIP? How to save tax in India?",
        key="chatbot_query"
    )

    if st.sidebar.button("Get Answer", key="chatbot_button"):
        if user_query and user_query.strip():
            with st.sidebar.container():
                with st.spinner("🤔 Thinking..."):
                    summary = query_ollama(user_query, model="mistral")
                    st.sidebar.success("✅ **Answer:**")
                    st.sidebar.markdown(summary)
        else:
            st.sidebar.warning("Please enter a question.")

# =========================
# AI FINANCIAL ADVISOR VIEW
# =========================
def ai_advisor_view():
    st.subheader("🤖 AI Financial Advisor")
    st.info("Get personalized financial advice based on your data from our AI, powered by Mistral.")

    user = st.session_state.auth_user

    # Fetch all user data
    profile = st.session_state.data.get("profiles", {}).get(user, {})
    records = st.session_state.data.get("records", {}).get(user, {"incomes": [], "expenses": []})
    emis = st.session_state.data.get("emis", {}).get(user, [])
    investments = st.session_state.data.get("investments", {}).get(user, [])
    portfolio = st.session_state.data.get("portfolio", {}).get(user, [])
    history = st.session_state.data.get("history", {}).get(user, [])

    # Summarize data for the prompt
    total_income = sum(r.get("amount", 0) for r in records.get("incomes", []))
    total_expense = sum(r.get("amount", 0) for r in records.get("expenses", []))
    total_emi = sum(e.get("emi_amount", 0) for e in emis)

    # Check if there is enough data
    if not profile and not records["incomes"] and not records["expenses"] and not emis and not investments and not portfolio:
        st.warning("⚠️ Please add some data to your Profile, Records, EMIs, or Investments to get personalized advice.")
        return

    if st.button("💡 Get My Financial Advice", use_container_width=True):
        with st.spinner("🧠 Your AI advisor is analyzing your finances..."):
            # Construct the detailed prompt for the Ollama model
            prompt = f"""
            You are an expert AI financial advisor for a user in India.
            Your task is to analyze the user's financial data and provide clear, actionable, and personalized recommendations.
            Do not give generic advice. Base your recommendations directly on the data provided.
            Structure your response with clear headings (e.g., ## Financial Health Overview, ## Investment Analysis, ## Loan Management, ## Recommendations).
            Use markdown for formatting.

            Here is the user's financial data:

            ---
            ### User Profile
            - **Name**: {profile.get("name", "N/A")}
            - **Age**: {profile.get("age", "N/A")}
            - **City**: {profile.get("city", "N/A")}
            - **Risk Preference**: {profile.get("risk", "Moderate")}

            ---
            ### Financial Summary
            - **Total Recorded Income**: {fmt_money(total_income)}
            - **Total Recorded Expenses**: {fmt_money(total_expense)}
            - **Total Monthly EMI Outflow**: {fmt_money(total_emi)}

            ---
            ### Loans & EMIs
            """
            if emis:
                for emi in emis:
                    prompt += f"- **{emi.get('name')}**: Principal {fmt_money(emi.get('principal'))}, Rate {emi.get('rate')}%, EMI {fmt_money(emi.get('emi_amount'))}\\n"
            else:
                prompt += "- No loans or EMIs recorded.\\n"

            prompt += """
            ---
            ### Stock Investments (from Live Market)
            """
            if investments:
                 for inv in investments:
                    purchase_value = inv.get('units', 0) * inv.get('purchase_price', 0)
                    current_value = inv.get('units', 0) * inv.get('current_price', 0)
                    pnl = current_value - purchase_value
                    prompt += f"- **{inv.get('name')}**: Units: {inv.get('units')}, Invested: {fmt_money(purchase_value)}, Current Value: {fmt_money(current_value)}, P&L: {fmt_money(pnl)}\\n"
            else:
                prompt += "- No stock investments recorded.\\n"

            prompt += """
            ---
            ### General Portfolio (Manual Entry)
            """
            if portfolio:
                for item in portfolio:
                    purchase_value = item.get('units', 0) * item.get('purchase_price', 0)
                    current_value = item.get('units', 0) * item.get('current_price', 0)
                    pnl = current_value - purchase_value
                    prompt += f"- **{item.get('name')} ({item.get('type')})**: Invested: {fmt_money(purchase_value)}, Current Value: {fmt_money(current_value)}, P&L: {fmt_money(pnl)}\\n"
            else:
                prompt += "- No general portfolio items recorded.\\n"

            prompt += """
            ---
            ### Financial Goals (from Planner)
            """
            if history:
                latest_goal = history[-1]
                prompt += f"- **Latest Goal**: To achieve '{latest_goal.get('goal')}' of {fmt_money(latest_goal.get('goal_amount'))} in {latest_goal.get('months')} months.\\n"
                prompt += f"- **Planned Monthly Saving**: {fmt_money(latest_goal.get('plan_monthly_saving'))}\\n"
            else:
                prompt += "- No financial goals recorded.\\n"

            prompt += """
            ---
            ### Your Task
            Based on all the data above, provide a comprehensive financial analysis and a set of prioritized, actionable recommendations.
            Consider the user's risk profile, income vs. expense ratio, debt, and investment diversification.
            Suggest specific actions they can take to improve their financial health and achieve their goals faster.
            Keep the advice relevant for India.
            """

            # Call the Ollama function
            advice = query_ollama(prompt, model="mistral")

            # Display the result
            st.markdown("### 📜 Here is your personalized financial advice:")
            st.markdown(advice)


def budget_optimizer_view():
    user = st.session_state.auth_user
    # Load user records
    records = st.session_state.data.get("records", {}).get(user, {"incomes": [], "expenses": []})
    total_income = sum(r.get("amount", 0) for r in records.get("incomes", []))
    total_expense = sum(r.get("amount", 0) for r in records.get("expenses", []))

    if total_income <= 0:
        st.warning("Please add income records first to use the AI Budget Optimizer.")
        return

    st.markdown(f"### 📊 Current Overview")
    st.info(f"**Total Income:** {fmt_money(total_income)} | **Total Expenses:** {fmt_money(total_expense)}")

    # Default allocation percentages (50-30-20 rule as baseline)
    default_alloc = {
        "Housing": 30,
        "Food & Essentials": 20,
        "Leisure": 10,
        "Investments": 20,
        "Others": 20
    }

    st.markdown("### 🛠 Customize Budget Allocation")
    alloc = {}
    total_pct = 0
    for cat, pct in default_alloc.items():
        alloc[cat] = st.slider(f"{cat} (%)", 0, 100, pct)
        total_pct += alloc[cat]

    if total_pct != 100:
        st.error("⚠️ Allocation percentages must add up to 100%.")
        return

    # Compute suggested allocations
    st.markdown("### 📑 Suggested Budget")
    budget_plan = {cat: (pct/100) * total_income for cat, pct in alloc.items()}

    for cat, amount in budget_plan.items():
        st.write(f"• **{cat}:** {fmt_money(amount)}")

    # Visualization
    fig, ax = plt.subplots()
    ax.pie(budget_plan.values(), labels=budget_plan.keys(), autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    st.pyplot(fig)

    # What-if Simulation
    st.markdown("### 🔮 What-if Simulation")
    goal_amount = st.number_input("Enter a savings goal (₹)", min_value=1000, step=1000, value=100000)
    months = st.number_input("Timeline (months)", min_value=1, step=1, value=12)
    current_saving = budget_plan.get("Investments", 0)

    if current_saving > 0:
        months_needed = goal_amount / current_saving
        st.info(f"With current saving of {fmt_money(current_saving)}/month, you will reach your goal in **{months_needed:.1f} months**.")

    extra_save_pct = st.slider("Increase savings by (%)", 0, 50, 10)
    improved_saving = current_saving * (1 + extra_save_pct/100)
    new_months_needed = goal_amount / improved_saving

    st.success(f"If you save **{extra_save_pct}%** more ({fmt_money(improved_saving)}/month), you can reach your goal in just **{new_months_needed:.1f} months** instead of {months_needed:.1f} months!")



# === AI Schemes Extension Added ===
import unicodedata
from datetime import datetime
import json
import pandas as pd

try:
    import streamlit as st
except Exception as e:
    raise RuntimeError("This module is meant to be run inside a Streamlit app. Install streamlit and run via `streamlit run`.") from e

# --------- Constants ---------
INDIAN_STATES = [
    "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana",
    "Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya",
    "Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura",
    "Uttar Pradesh","Uttarakhand","West Bengal",
    # UTs
    "Andaman and Nicobar Islands","Chandigarh","Dadra and Nagar Haveli and Daman and Diu","Delhi",
    "Jammu and Kashmir","Ladakh","Lakshadweep","Puducherry"
]

# --------- Hardcoded fallback schemes ---------
FALLBACK_SCHEMES = {
    "Uttar Pradesh": [
        {"title": "Kanya Vidya Dhan Yojana", "url": "https://myscheme.gov.in"},
        {"title": "Farmer Loan Waiver", "url": "https://myscheme.gov.in"},
        {"title": "Samajwadi Pension Yojana", "url": "https://myscheme.gov.in"},
    ],
    "Maharashtra": [
        {"title": "Chhatrapati Shivaji Maharaj Shetkari Sanman Yojana", "url": "https://myscheme.gov.in"},
        {"title": "Balasaheb Thackeray Accidental Insurance Scheme", "url": "https://myscheme.gov.in"},
        {"title": "Shiv Bhojan Thali", "url": "https://myscheme.gov.in"},
        {"title": "MahaDBT Scholarship", "url": "https://myscheme.gov.in"},
    ],
    "Delhi": [
        {"title": "Delhi Ladli Scheme", "url": "https://myscheme.gov.in"},
        {"title": "Mukhyamantri Teerth Yatra Yojana", "url": "https://myscheme.gov.in"},
        {"title": "Jahan Jhuggi Wahan Makan", "url": "https://myscheme.gov.in"},
        {"title": "Delhi Electric Vehicle Policy", "url": "https://myscheme.gov.in"},
    ],
    "Karnataka": [
        {"title": "Anna Bhagya Yojana", "url": "https://myscheme.gov.in"},
        {"title": "Vidya Siri Scholarship", "url": "https://myscheme.gov.in"},
        {"title": "Yeshasvini Health Insurance", "url": "https://myscheme.gov.in"},
        {"title": "Ksheera Bhagya", "url": "https://myscheme.gov.in"},
    ]
}

# --------- Helpers ---------
def _ensure_session_state():
    if "data" not in st.session_state:
        st.session_state.data = {}
    if "profiles" not in st.session_state.data:
        st.session_state.data["profiles"] = {}
    if "schemes" not in st.session_state.data:
        st.session_state.data["schemes"] = {}

def _fallback_save_data(data):
    try:
        with open("data_schemes.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Could not save data to disk: {e}")

def save_data_wrapper(data):
    try:
        save_data = globals().get("save_data", None)
        if callable(save_data):
            save_data(data)
            return
    except Exception:
        pass
    try:
        sd = st.session_state.get("save_data", None)
        if callable(sd):
            sd(data)
            return
    except Exception:
        pass
    _fallback_save_data(data)

# --------- Schemes view ---------
def schemes_view():
    _ensure_session_state()
    user = st.session_state.get("auth_user", None)
    if not user:
        st.info("No signed-in user found (set st.session_state['auth_user']).")
        return

    st.subheader("📜 Schemes")

    prof = st.session_state.data.get("profiles", {}).get(user, {})
    picked_state = prof.get("state", "")

    c1, c2 = st.columns([3, 1])
    with c1:
        options = ["(from profile)"] + INDIAN_STATES
        default_index = 0
        if picked_state in INDIAN_STATES:
            default_index = options.index(picked_state)
        sel = st.selectbox("State / UT", options=options, index=default_index)
        if sel == "(from profile)":
            picked_state = prof.get("state", "")
        else:
            picked_state = sel
    with c2:
        limit = st.number_input("Max results", min_value=5, max_value=100, value=20, step=5)

    if not picked_state:
        st.info("Please set your State in Profile or select here.")
        return

    if st.button("🔎 Show schemes for my state"):
        with st.spinner("Loading schemes..."):
            # Use hardcoded fallback
            schemes = FALLBACK_SCHEMES.get(picked_state, [])
            if not schemes:
                st.warning("No curated schemes available for this state.")
                schemes = []

            data = st.session_state.data
            data.setdefault("schemes", {}).setdefault(user, {})[picked_state] = {
                "fetched_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "items": schemes,
            }
            save_data_wrapper(data)
            st.success(f"Found {len(schemes)} scheme(s) for {picked_state}.")

    cache = st.session_state.data.get("schemes", {}).get(user, {}).get(picked_state)
    if cache:
        st.caption(f"Last fetched: {cache['fetched_on']}")
        df = pd.DataFrame(cache["items"])[: int(limit)]
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

        csv = pd.DataFrame(cache["items"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download schemes (CSV)", csv, file_name=f"schemes_{picked_state}.csv", mime="text/csv")


# START: CODE MODIFICATION TO FIX THE ERROR
def get_schemes_db_data():
    """
    Returns a hardcoded dictionary of government schemes.
    This replaces the need for an external 'schemes.json' file.
    """
    return {
        "central": [
            {
                "name": "Pradhan Mantri Jan Dhan Yojana (PMJDY)",
                "eligibility": "Any Indian citizen above 10 years of age without a bank account.",
                "benefits": "Zero-balance bank account, RuPay debit card, accident insurance cover of Rs. 2 lakh, and overdraft facility up to Rs. 10,000.",
                "apply": "Visit the nearest bank branch or Bank Mitra with ID proof."
            },
            {
                "name": "Sukanya Samriddhi Yojana (SSY)",
                "eligibility": "Parents or legal guardians of a girl child below 10 years of age.",
                "benefits": "High interest rate, tax benefits under Section 80C. Account matures after 21 years or on marriage after 18.",
                "apply": "Open an account in any authorized post office or bank branch."
            },
            {
                "name": "Atal Pension Yojana (APY)",
                "eligibility": "Any Indian citizen between 18 to 40 years with a bank account.",
                "benefits": "Guaranteed monthly pension of Rs. 1,000 to Rs. 5,000 after the age of 60. Government co-contributes 50% of the premium for 5 years.",
                "apply": "Through the bank or post office where the savings account is held."
            }
        ],
        "states": {
            "Karnataka": [
                {
                    "name": "Gruha Lakshmi Scheme",
                    "eligibility": "Woman head of a family identified in Antyodaya, BPL, and APL ration cards.",
                    "benefits": "Monthly financial assistance of Rs. 2,000.",
                    "apply": "Apply through Seva Sindhu portal or designated service centers."
                },
                {
                    "name": "Yuva Nidhi Scheme",
                    "eligibility": "Unemployed graduates and diploma holders who graduated in the academic year 2022-23.",
                    "benefits": "Monthly allowance of Rs. 3,000 for graduates and Rs. 1,500 for diploma holders for up to two years or until they find a job.",
                    "apply": "Register on the Seva Sindhu portal."
                }
            ],
            "Maharashtra": [
                {
                    "name": "Mahatma Jyotirao Phule Jan Arogya Yojana (MJPJAY)",
                    "eligibility": "Families with an annual income up to Rs. 1 lakh, holding specific ration cards.",
                    "benefits": "Cashless healthcare services up to Rs. 1.5 lakh per family per year for specified medical procedures.",
                    "apply": "Enroll at designated government hospitals and network hospitals."
                }
            ],
            "Delhi": [
                {
                    "name": "Mukhyamantri Mahila Samman Yojana",
                    "eligibility": "Women aged 18 and above, enrolled as a voter in Delhi.",
                    "benefits": "Monthly stipend of Rs. 1,000.",
                    "apply": "Through a form submission process announced by the Delhi government."
                }
            ],
            "Uttar Pradesh": [
                {
                    "name": "Kanya Sumangala Yojana",
                    "eligibility": "Families with a girl child, having an annual income up to Rs. 3 lakh.",
                    "benefits": "Financial assistance of Rs. 15,000 in total, given in six installments at various stages of the girl's life (birth, vaccination, school admission).",
                    "apply": "Online application through the official MKSY portal."
                }
            ]
        }
    }

def load_schemes_db():
    """
    Loads the schemes database from the hardcoded function.
    """
    db = get_schemes_db_data()
    # Ensure all states from INDIAN_STATES list are present in the db
    # to avoid errors when selecting a state with no schemes.
    for state in INDIAN_STATES:
        if state not in db["states"]:
            db["states"][state] = []
    return db

def explain_scheme_ai_text(scheme: dict, lang: str = "English"):
    """
    Uses local LLM (e.g., Mistral via Ollama) if available to simplify the scheme details.
    Falls back to plain text if query_ollama is not present.
    """
    text = f"Name: {scheme.get('name','')}\nEligibility: {scheme.get('eligibility','')}\nBenefits: {scheme.get('benefits','')}"
    try:
        # If the query_ollama function is available, use it.
        if 'query_ollama' in globals():
            prompt = f"Explain the following government scheme in very simple {lang}. Keep it under 6 short bullet points.\n\n{text}"
            return globals()['query_ollama'](prompt, model="mistral")
    except Exception as e:
        # If the AI call fails, log the error and fall back gracefully.
        print(f"AI explanation failed, falling back to plain text. Error: {e}")
        pass
    return text

def schemes_recommender_view_offline():
    st.subheader("📜 Personalized Government Schemes (Offline)")
    st.caption("Works without internet — curated national + state schemes.")
    db = load_schemes_db() # No longer needs a file path

    # Inputs
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Age", min_value=1, max_value=120, value=30)
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    with col2:
        occupation = st.selectbox("Occupation", ["Farmer", "Student", "Business", "Homemaker", "Worker", "Other"])
        state = st.selectbox("State/UT", sorted(list(db.get("states", {}).keys())))

    explain_in = st.selectbox("Explain in language", ["English", "Hindi", "Kannada"])
    show_ai = st.checkbox("Simplify with AI (if available)", value=True)
    st.markdown("---")

    # Very light filtering (you can expand with tags later)
    results = []
    results.extend(db.get("central", []))
    results.extend(db.get("states", {}).get(state, []))

    if not results:
        st.warning(f"No schemes found in the offline database for {state}. Please update the script to add them.")
        return

    st.success(f"Showing {len(results)} schemes for your selection.")
    for s in results:
        with st.container(border=True):
            st.markdown(f"### {s.get('name','(Unknown)')}")
            st.write(f"**Eligibility:** {s.get('eligibility','')}")
            st.write(f"**Benefits:** {s.get('benefits','')}")
            if s.get("apply"):
                st.write(f"**Apply:** {s['apply']}")
            if show_ai:
                with st.expander("🔎 Explain simply with AI"):
                    # This call will now work correctly
                    exp = explain_scheme_ai_text(s, lang=explain_in)
                    st.write(exp)
# END: CODE MODIFICATION

# =========================
# APP NAVIGATION (REMODELED)
# =========================
def main():
    st.session_state.data = load_data()

    # Initialize prefill variables if they don't exist
    if "prefill_income" not in st.session_state:
        st.session_state.prefill_income = 30000
    if "prefill_goal_name" not in st.session_state:
        st.session_state.prefill_goal_name = ""
    if "prefill_goal_amount" not in st.session_state:
        st.session_state.prefill_goal_amount = 100000
    if "prefill_months" not in st.session_state:
        st.session_state.prefill_months = 6

    # Initialize session state for page navigation if it doesn't exist
    if 'page' not in st.session_state:
        st.session_state.page = 'Planner' # Default page

    if not st.session_state.get("auth_user"):
        auth_view()
    else:
        # --- UI MODIFICATION START ---
        # Inject custom CSS for the new sidebar style
        st.markdown("""
        <style>
            /* Main sidebar styling */
            [data-testid="stSidebar"] {
                background-color: #0F172A; /* Dark blue-gray */
                border-right: 1px solid #334155;
            }
            [data-testid="stSidebar"] .st-emotion-cache-16txtl3 { /* Sidebar content */
                padding-top: 1rem;
            }
            /* Sidebar title */
            [data-testid="stSidebar"] h1 {
                color: #FFFFFF;
                padding: 0 1rem;
            }

            /* Sidebar button styling */
            [data-testid="stSidebar"] .stButton button {
                background-color: transparent;
                color: #CBD5E1; /* Lighter text */
                border: none;
                width: 100%;
                text-align: left;
                padding: 10px 20px;
                border-radius: 8px;
                margin-bottom: 5px;
                font-size: 16px;
                display: flex;
                align-items: center;
                gap: 12px; /* Space between icon and text */
            }

            /* Hover effect for sidebar buttons */
            [data-testid="stSidebar"] .stButton button:hover {
                background-color: #1E293B;
                color: #FFFFFF;
            }

            /* Remove focus outline */
            [data-testid="stSidebar"] .stButton button:focus {
                outline: none;
                box-shadow: none;
            }

             /* Main page top margin fix */
            .appview-container {
                margin-top: -75px;
            }
        </style>
        """, unsafe_allow_html=True)

        # --- Top Bar with Profile and Logout ---
        st.write(f"🎉 Welcome **{st.session_state.auth_user}**!")

        # Using columns to align buttons to the right
        _, col2, col3 = st.columns([6, 1.5, 1])
        with col2:
            if st.button("👤 View Profile"):
                 st.session_state.page = "Profile"
                 st.rerun()
        with col3:
            if st.button("Logout", use_container_width=True):
                # Clear relevant session state on logout
                if "auth_user" in st.session_state:
                    del st.session_state["auth_user"]
                if "page" in st.session_state:
                    del st.session_state["page"]
                st.rerun()

        # --- Sidebar Navigation ---
        with st.sidebar:
            st.title("WealthWise")
            st.write(f"Signed in as **{st.session_state.auth_user}**")
            st.markdown("---")

            # Page dictionary with emojis as icons
            pages = {
                "Planner": "🧭",
                "Records": "🧾",
                "EMIs": "🏦",
                "Investments": "📈",
                "Portfolio": "💹",
                "AI Financial Advisor": "🤖",
                "AI Budget Optimizer": "💡",
                "Save/Download Data": "💾",
                "Gov Schemes AI Analyzer": "💰"
            }

            for page, icon in pages.items():
                if st.button(f"{icon} {page}", use_container_width=True, key=f"nav_{page}"):
                    st.session_state.page = page
                    st.rerun()

            # Sidebar chatbot remains at the bottom
            sidebar_chatbot()

        # --- Page Routing ---
        current_page = st.session_state.page

        if current_page == "Planner":
            planner_view()
        elif current_page == "Records":
            records_view()
        elif current_page == "EMIs":
            emis_view()
        elif current_page == "Investments":
            investments_view()
        elif current_page == "Portfolio":
            portfolio_view()
        elif current_page == "AI Financial Advisor":
            ai_advisor_view()
        elif current_page == "Profile": # Route for the profile page
            profile_view()
        elif current_page == "AI Budget Optimizer":
            budget_optimizer_view()
        elif current_page == "Gov Schemes AI Analyzer":
            schemes_recommender_view_offline()
        elif current_page == "Save/Download Data":
            st.subheader("💾 Save & Export")
            if st.button("Save data now"):
                save_data(st.session_state.data)
                st.success("Data saved to disk.")
            st.markdown("Download a copy of your data:")
            data_bytes = json.dumps(
                st.session_state.data, indent=2, ensure_ascii=False
            ).encode("utf-8")
            st.download_button(
                "Download data.json",
                data=data_bytes,
                file_name="paisa_path_data.json",
                mime="application/json",
            )

def ensure_auth():
    if not st.session_state.get("auth_user"):
        st.warning("Please log in to access this section.")
        return False
    return True

if __name__ == "__main__":
    main()


# ===== Offline Schemes Database Loader =====

def explain_scheme_ai_text(scheme: dict, lang: str = "English"):
    """
    Uses local LLM (e.g., Mistral via Ollama) if available to simplify the scheme details.
    Falls back to plain text if query_ollama is not present.
    """
    text = f"Name: {scheme.get('name','')}\nEligibility: {scheme.get('eligibility','')}\nBenefits: {scheme.get('benefits','')}"
    try:
        # If user's code defines query_ollama(model="mistral"), use it.
        if 'query_ollama' in globals():
            prompt = f"Explain in very simple {lang}. Keep it under 6 short bullet points.\n\n{text}"
            return globals()['query_ollama'](prompt, model="mistral")
    except Exception:
        pass
    return text