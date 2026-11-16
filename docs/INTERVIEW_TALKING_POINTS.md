# Interview talking points

Notes for talking about this project in co-op interviews (operations, business analyst, data, supply chain and consulting roles).

**Before any interview: be able to explain every file in `ops/` line by line, and be able to compute one reorder point and one forecast by hand.** Interviewers often ask you to walk through a formula. If you used AI tools while building this, say so plainly if asked, and show that you understand and can defend each decision. That is the part that counts.

## 30-second version

> "I built a dashboard for small businesses that takes their sales, inventory and waste spreadsheets and tells them what to reorder, what's sitting on the shelf too long, what they'll sell next week, and where their waste comes from. It's Python and pandas with a SQLite database and a Streamlit front end. I kept every calculation explainable, because a store owner won't trust a number they can't check. On simulated data, the forecast cut the error by 44% compared with a simple average, and the waste analysis showed three products driving half the waste cost."

## STAR story: building it

- **Situation:** In my meal program work I saw how much food gets wasted when production is planned by gut feel. Small businesses have the same problem with stock.
- **Task:** Build a tool that turns the data they already have into specific actions, without needing a data team.
- **Action:** Designed three simple CSV formats; wrote validation that names the exact bad row; stored clean data in SQLite; implemented reorder points with safety stock, a weekday forecast with a backtest against a baseline, and a Pareto analysis of waste; wrote 38 tests using small datasets whose answers I worked out by hand.
- **Result:** A working app that flags 4 items to reorder and $1,860 of slow stock in the sample data, and a forecast that beats the simple baseline by 44% overall. All of it is on simulated data, which I state clearly.

## Decisions you can defend

| Decision | Why |
|---|---|
| Same-weekday average instead of a machine learning model | Small businesses have strong weekly patterns. This captures them, an owner can check it by hand, and the backtest shows it beats a simple baseline. A complex model is only worth it if it beats this by a clear margin. |
| Backtest against a baseline | A forecast's error number means nothing alone. Comparing with "last week's average" shows whether the method adds value. |
| WAPE instead of MAPE | MAPE divides by each day's actual sales, so it breaks on zero-sale days. WAPE divides by total sales. |
| Fill missing days with zero | No sales row means zero sales. Skipping those days would overstate average demand and reorder points. |
| Validate everything before saving | A dashboard built on bad data is worse than none. All-or-nothing loading means the database only ever holds clean data. |
| Error messages with spreadsheet row numbers | The user is a store owner, not a developer. "Row 6" is something they can fix. |
| Calculations separate from the UI | `ops/` has no Streamlit code, so it can be tested on its own and reused elsewhere. |
| SQLite | A real SQL database with no server to install. Enough for one store's data. |

## Questions you should expect

**"How does safety stock work?"**
It is extra stock to cover the days when demand is higher than average while you wait for a delivery. Higher variability, longer lead times or a higher service level all mean more safety stock. Formula: z × daily standard deviation × √lead time. The square root comes from variance adding up over independent days.

**"What's the biggest weakness?"**
Sales are treated as demand. If milk sold out at 3pm, the data shows what was sold, not what customers wanted, so the forecast learns a demand level that is too low and keeps under-ordering. The fix is to detect likely stock-out days and exclude or adjust them.

**"Your forecast didn't beat the baseline for sourdough. Why?"**
Its daily sales are noisy compared with its weekly pattern, so averaging 4 values per weekday is noisier than averaging 7 recent days. It's a good example of why you test against a baseline rather than assume the fancier method wins.

**"How would you know if this works on a real business?"**
Run it alongside the owner's current ordering for a few weeks, then compare stock-outs and waste before and after. Also check the forecast's backtest on their real data, since the simulated data contains patterns I chose.

**"What would you do next?"**
Stock-out detection, holiday flags in the forecast, and tracking inventory over time so the app can measure actual stock-outs.

## Connecting it to the role

- **Operations / supply chain:** reorder points, safety stock, lead times, service level trade-offs, waste reduction.
- **Business / data analyst:** KPI definitions, period-over-period comparison, Pareto analysis, turning analysis into specific actions.
- **Consulting / strategy:** starting from the business question, stating assumptions and limitations, presenting findings an owner can act on.
- **Technical roles:** data validation, tests, separating logic from presentation, SQL.

## Honest framing

- Always say the data is **simulated**.
- Do not claim it has been used by a real business unless that becomes true. If you can get a local shop or your food program to try it, that becomes your strongest talking point.
