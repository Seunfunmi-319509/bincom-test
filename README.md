# Bincom Test - Election Results (plain Python + MySQL)

No framework. Only the Python standard library plus `mysql-connector-python` (the package that lets Python talk to MySQL).

| Page | URL | What it does |
|---|---|---|
| Q1 | `/polling-unit` | Choose an LGA, then a polling unit, and see its party scores |
| Q2 | `/lga-total` | Choose an LGA and see the summed score of each party over all its polling units (does NOT use `announced_lga_results`) |
| Q3 | `/new-result` | Choose an LGA, then a ward, name a new polling unit and save the scores of all 9 parties |

## How it works
- Everything is in `app.py`. The function `application()` at the bottom receives every web request, looks at the address (`/polling-unit`, `/lga-total`, ...) and calls the matching page function.
- Each page function runs SQL with `run_query()`, then builds the HTML page as a string with loops.
- Q2: join `announced_pu_results.polling_unit_uniqueid` to `polling_unit.uniqueid`, keep one `lga_id`, then `SUM(party_score)` with `GROUP BY party_abbreviation`.
- Q3: insert a row in `polling_unit`, then one row per party in `announced_pu_results` using the new unit's `uniqueid`; `conn.commit()` saves them together.
- SQL uses `%s` placeholders and values are passed separately (prevents SQL injection). Text shown on pages goes through `escape()` (prevents HTML injection).

## Run on your computer
1. Install Python and MySQL (for example XAMPP, which has MySQL and phpMyAdmin).
2. Create a database `bincomphptest` and import `bincom_test.sql` (phpMyAdmin > Import).
3. In a terminal in this folder:
   ```
   pip install mysql-connector-python
   python app.py
   ```
4. Open http://127.0.0.1:8000

Database settings come from the environment variables `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Defaults are the XAMPP ones: `localhost`, `root`, no password, `bincomphptest`.

## Put it online (example: PythonAnywhere)
1. Databases tab: set a MySQL password, then import `bincom_test.sql` in the MySQL console.
2. Upload this folder (or `git clone` your repo in a Bash console) and run `pip install --user mysql-connector-python`.
3. Web tab: add a new web app (manual configuration), then edit the WSGI file to:
   ```python
   import os, sys
   sys.path.insert(0, "/home/<username>/bincom-plain")
   os.environ["DB_HOST"] = "<username>.mysql.pythonanywhere-services.com"
   os.environ["DB_USER"] = "<username>"
   os.environ["DB_PASSWORD"] = "<your mysql password>"
   os.environ["DB_NAME"] = "<username>$bincomphptest"
   from app import application
   ```
4. Press Reload.

## Notes
- Q3 uses the party codes of `announced_pu_results` (`LABO`, not `LABOUR` from the `party` table).
- Polling unit 10 already has two result entries in the data. Q1 shows both (with who entered them and when); Q2 adds both.
- Only polling units 8 to 27 had results in the given data, so the many blank `polling_unit` rows never appear in dropdowns.
