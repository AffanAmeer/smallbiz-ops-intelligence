# Demo script (about 3 minutes)

Use this for a recorded Loom video, a screen share in an interview, or a live demo. Start the app with `streamlit run app.py` before you begin. Talk to the business problem first and the code second.

## 0:00 – The problem (20 seconds)

> "Small businesses like corner stores and cafés usually manage stock with spreadsheets and gut feel. They know what they sold, but they don't know what's about to run out, what's sitting on the shelf too long, or where their waste comes from. I built a dashboard that answers those questions from three CSV files they probably already have. The data here is simulated: it's a made-up grocery store, and the banner at the top says so."

## 0:20 – Overview tab (30 seconds)

- Point at the six KPI cards. "Last 28 days compared with the 28 before. Revenue is down about 3%, and the waste rate went up slightly."
- Point at the revenue chart. "The bars are daily revenue and the line is a 7-day average, which smooths out the weekly cycle."
- Point at the weekday chart. "Saturdays are the busiest day. That pattern matters for the forecast later."

## 0:50 – Inventory & reorder tab (45 seconds)

- "Four items need ordering now. Milk has a day and a half of stock left, and the supplier takes two days."
- Open **How the reorder numbers are calculated**. "The reorder point is average daily demand times lead time, plus safety stock for busier-than-normal days. Every number here can be checked with a calculator."
- Move the **Target service level** slider from 0.95 to 0.99. "If the owner wants to almost never run out, safety stock goes up and the order gets bigger. That's the trade-off between running out and holding too much stock."
- Point at the slow movers. "On the other side, the olive oil and gift baskets have $1,860 tied up in stock that won't sell for over 100 days."
- Click **Download order list**. "This is the part the owner actually uses."

## 1:35 – Demand forecast tab (40 seconds)

- "The forecast is simple on purpose: next Saturday is the average of the last four Saturdays."
- Point at the accuracy cards. "I tested it day by day on the last four weeks, using only data that would have been available at the time. It's 44% more accurate than just using last week's average."
- Switch the product to **Sourdough Loaf**. "For this product it doesn't beat the baseline, and the app says so instead of hiding it. A forecast is only useful if it beats the simple option."

## 2:15 – Waste tab (25 seconds)

- Read the key findings. "Three products cause half of the waste cost. Monday waste is almost double the average, which suggests over-ordering for the weekend. Most waste is expired stock, so the fix is smaller, more frequent orders, not better storage."

## 2:40 – Data quality (20 seconds)

- Switch to **Upload my own CSVs**, upload `data/sample/sales_with_errors.csv` and `inventory.csv`, and click **Validate and load**.
- "Real data is messy. Before anything is saved, every file is checked, and each problem points to the exact spreadsheet row, so a non-technical owner can fix it."

## Close (10 seconds)

> "It's Python, pandas, SQLite and Streamlit, with 38 automated tests that check the formulas against small examples I worked out by hand. The README lists the limitations, the biggest being that sales aren't the same as demand when something sells out."
