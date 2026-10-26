# UI changes — user-acceptance checklist

Sign in as an administrator, then repeat the starred (★) lines as the read-only client user. Record Pass / Fail and a note.

| # | Change | What to do | Expected | Pass / Fail | Notes |
|---|---|---|---|---|---|
| 1 | Conditional sidebar | Sign in (no company open) | Left menu shows only **All Companies · All Directors · Notifications**; opening a company shows the company menus and the three links are hidden ★ | | |
| 1 | All Directors | Open **All Directors**; search a name, a DIN and a PAN; click a role chip; export CSV | One row per person with companies and roles; search works; CSV downloads ★ | | |
| 1 | Notifications | Click the bell in the top bar | Count badge matches the cards on the Notifications screen; each card opens the matching list ★ | | |
| 2 | Filings column | Open **All Companies** | No "Filings" column; other columns unchanged; Overview still shows "Overdue filings" ★ | | |
| 3 | Top bar | Look at the top bar with a company open; then with none | Right side reads: status, Refresh, Print, bell, **FY selector**, Data, **user name**; FY hidden when no company is open ★ | | |
| 4 | Master Data tabs | Open **Master Data**; click all four tabs; refresh the page; press Back | Tabs: General Info & Registration · Capital Structure & Financials · Charges & Borrowings · Statutory Registers; the tab survives a refresh; edit a profile field and leave it → "✓ saved" (admin only) | | |
| 4 | Registers / charges | Open Statutory Registers and Charges & Borrowings | Composed registers with CSV export; clear "No charge register in the approved data model" message ★ | | |
| 5 | Calculated Values | Look through the whole menu | No "Calculated Values" entry; Overview and cap table still show figures ★ | | |
| 6 | Directors panel | Open **Directors**; use the six tabs and the segment buttons (All, Active in FY, Ceased, Independent, KMP, On a committee); try the keyboard arrows on the tabs | Counts on segments; committees inside Board Committees; tabs reachable by keyboard ★ | | |
| 7 | Shareholders panel | Open **Shareholders**; open the four tabs; click "Capital structure" | Cap table percentages equal the database figures; allotments / transfers can be added and edited (no Add buttons for the client) ★ | | |
| 8 | ODI / ECB / DI | Open **ODI / ECB / DI / Foreign Investments** (Financial & Legal) | Summary strip and four lists (ODI, step-down subsidiaries, ECB, DI); no Add buttons for the client ★ | | |
| 9 | Address / Phone | Open the Directors register and the Master Data Directors card | Address and Phone columns present; existing values show; blank ones leave the cell empty ★ | | |
| 10 | FY filtering | Pick a FY in the top bar; open the Directors register; tick **Show Historical / Ceased Directors** | Directors who left before the FY are hidden; the switch shows them with a "Ceased on dd-mm-yyyy" badge, no page reload ★ | | |
| — | Navigation | Paste a company/tab link into a new browser tab; use Back / Forward | The same screen and tab open; Back works | | |
| — | Security | As the client, try to add or edit anything | No Add / Save buttons; nothing can be changed ★ | | |
