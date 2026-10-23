"""
Bincom test - election results web app.
Plain Python only (no framework): standard library + the MySQL connector.

Pages:
  /               -> menu
  /polling-unit   -> Question 1: result of one polling unit
  /lga-total      -> Question 2: summed result of all polling units in an LGA
  /new-result     -> Question 3: save results for ALL parties of a new polling unit
"""
import os
from html import escape
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
import mysql.connector

# ---------- database settings (can be changed with environment variables) ----------
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "bincomphptest"),
}

# Party codes exactly as written in announced_pu_results
# (the `party` table says LABOUR, but the results use LABO)
PARTIES = ["PDP", "DPP", "ACN", "PPA", "CDC", "JP", "ANPP", "LABO", "CPP"]


# =====================================================================
# Small helper functions
# =====================================================================
def run_query(sql, params=()):
    """Run a SELECT and return the rows as a list of dictionaries."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_text(data, name):
    """Read one value from the form/URL data. Gives '' if it is missing."""
    values = data.get(name, [""])
    return values[0].strip()


def get_number(data, name):
    """Read one whole number from the form/URL data. Gives None if it is not a number."""
    text = get_text(data, name)
    if text.isdigit():
        return int(text)
    return None


def e(value):
    """Make a value safe to print inside HTML (stops HTML injection)."""
    return escape(str(value))


def make_page(title, body):
    """Put the menu and styling around the body of a page."""
    return """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>
 body { font-family: Arial, sans-serif; max-width: 760px; margin: 0 auto; padding: 16px; color: #222; }
 nav a { margin-right: 14px; }
 label { display: block; margin-top: 12px; font-weight: bold; }
 select, input[type=text], input[type=number] { width: 100%%; padding: 8px; margin-top: 4px; box-sizing: border-box; }
 button { margin-top: 16px; padding: 10px 18px; background: #305496; color: #fff; border: 0; border-radius: 4px; cursor: pointer; }
 table { border-collapse: collapse; width: 100%%; margin-top: 16px; }
 th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
 th { background: #305496; color: #fff; }
 .msg { padding: 10px; margin-top: 16px; border-radius: 4px; }
 .ok { background: #e3f6e3; border: 1px solid #8c8; }
 .error { background: #fde8e8; border: 1px solid #d88; }
 .info { background: #eef2fa; border: 1px solid #aac; }
 .scores { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
 .num { text-align: right; }
</style></head><body>
<nav>
 <a href="/">Home</a>
 <a href="/polling-unit">1. Polling unit result</a>
 <a href="/lga-total">2. LGA total</a>
 <a href="/new-result">3. Add new result</a>
</nav>
%s
</body></html>""" % (e(title), body)


def make_options(rows, value_name, label_name, chosen):
    """Build the <option> lines of a dropdown from database rows."""
    html = ""
    for row in rows:
        selected = ""
        if str(row[value_name]) == str(chosen):
            selected = " selected"
        html += '<option value="%s"%s>%s</option>\n' % (e(row[value_name]), selected, e(row[label_name]))
    return html


def get_lgas(only_with_results=False):
    """The LGAs for a dropdown."""
    if only_with_results:
        sql = """SELECT DISTINCT l.lga_id, l.lga_name
                 FROM lga l
                 JOIN polling_unit p ON p.lga_id = l.lga_id
                 JOIN announced_pu_results r ON r.polling_unit_uniqueid = p.uniqueid
                 ORDER BY l.lga_name"""
    else:
        sql = "SELECT lga_id, lga_name FROM lga ORDER BY lga_name"
    return run_query(sql)


# =====================================================================
# Home
# =====================================================================
def home_page():
    body = """<h1>Delta State 2011 Election Results</h1>
<p>Choose what you want to do:</p>
<ul>
 <li><a href="/polling-unit">See the result of one polling unit</a></li>
 <li><a href="/lga-total">See the summed total for a local government (LGA)</a></li>
 <li><a href="/new-result">Save the results of a new polling unit</a></li>
</ul>"""
    return make_page("Bincom Election Results", body)


# =====================================================================
# Question 1: result of one polling unit
# Chained dropdown: choose an LGA first, then a polling unit of that LGA
# =====================================================================
def polling_unit_page(query):
    lga_id = get_number(query, "lga_id")     # chosen in dropdown 1
    pu_id = get_number(query, "pu_id")       # chosen in dropdown 2

    body = "<h1>Result of a polling unit</h1>"
    if get_text(query, "saved"):
        body += '<div class="msg ok">The new polling unit and its results were saved. They are shown below.</div>'

    # dropdown 1: LGAs (the page reloads as soon as one is picked)
    body += '<form method="get">'
    body += '<label for="lga_id">Step 1: choose a local government (LGA)</label>'
    body += '<select name="lga_id" id="lga_id" onchange="this.form.pu_id.value=\'\'; this.form.submit()">'
    body += '<option value="">-- choose LGA --</option>'
    body += make_options(get_lgas(only_with_results=True), "lga_id", "lga_name", lga_id)
    body += "</select>"

    # dropdown 2: polling units of that LGA which have results
    if lga_id:
        units = run_query(
            """SELECT DISTINCT p.uniqueid, p.polling_unit_number, p.polling_unit_name
               FROM polling_unit p
               JOIN announced_pu_results r ON r.polling_unit_uniqueid = p.uniqueid
               WHERE p.lga_id = %s
               ORDER BY p.uniqueid""",
            (lga_id,),
        )
        # build a text for each option, like "DT1708006 - Sapele Ward 8 PU _"
        for unit in units:
            unit["label"] = "%s - %s" % (unit["polling_unit_number"] or "No number",
                                         unit["polling_unit_name"] or "No name")
        body += '<label for="pu_id">Step 2: choose a polling unit</label>'
        body += '<select name="pu_id" id="pu_id" onchange="this.form.submit()">'
        body += '<option value="">-- choose polling unit --</option>'
        body += make_options(units, "uniqueid", "label", pu_id)
        body += "</select>"
        if not units:
            body += '<div class="msg info">This LGA has no polling unit with results yet.</div>'
    else:
        body += '<input type="hidden" name="pu_id" value="">'
    body += "<noscript><button type=\"submit\">Show</button></noscript></form>"

    # the result table
    if pu_id:
        found = run_query(
            """SELECT p.polling_unit_number, p.polling_unit_name, w.ward_name, l.lga_name
               FROM polling_unit p
               LEFT JOIN ward w ON w.uniqueid = p.uniquewardid
               LEFT JOIN lga l ON l.lga_id = p.lga_id
               WHERE p.uniqueid = %s""",
            (pu_id,),
        )
        if found:
            unit = found[0]
            body += "<h2>%s</h2>" % e(unit["polling_unit_name"] or "Polling unit")
            body += "<p>Polling unit number: <b>%s</b><br>Ward: <b>%s</b><br>LGA: <b>%s</b></p>" % (
                e(unit["polling_unit_number"] or "-"), e(unit["ward_name"] or "-"), e(unit["lga_name"] or "-"))

            results = run_query(
                """SELECT party_abbreviation, party_score, entered_by_user, date_entered
                   FROM announced_pu_results
                   WHERE polling_unit_uniqueid = %s
                   ORDER BY date_entered, result_id""",
                (str(pu_id),),    # this column is text, so we pass text
            )
            if results:
                body += '<table><tr><th>Party</th><th class="num">Score</th><th>Entered by</th><th>Date entered</th></tr>'
                for row in results:
                    body += '<tr><td>%s</td><td class="num">%s</td><td>%s</td><td>%s</td></tr>' % (
                        e(row["party_abbreviation"]), e(row["party_score"]),
                        e(row["entered_by_user"] or "-"), e(row["date_entered"]))
                body += "</table>"
            else:
                body += '<div class="msg info">No result has been saved for this polling unit.</div>'

    return make_page("Polling unit result", body)


# =====================================================================
# Question 2: summed total of all polling units in an LGA
# (uses announced_pu_results only, NOT announced_lga_results)
# =====================================================================
def lga_total_page(query):
    lga_id = get_number(query, "lga_id")

    body = "<h1>Summed total for a local government (LGA)</h1>"
    body += '<form method="get">'
    body += '<label for="lga_id">Choose a local government (LGA)</label>'
    body += '<select name="lga_id" id="lga_id" onchange="this.form.submit()">'
    body += '<option value="">-- choose LGA --</option>'
    body += make_options(get_lgas(), "lga_id", "lga_name", lga_id)
    body += '</select><noscript><button type="submit">Show total</button></noscript></form>'

    if lga_id:
        names = run_query("SELECT lga_name FROM lga WHERE lga_id = %s", (lga_id,))
        if names:
            body += "<h2>%s</h2>" % e(names[0]["lga_name"])

        # join the scores to their polling unit, keep one LGA, add up per party
        totals = run_query(
            """SELECT r.party_abbreviation, SUM(r.party_score) AS total
               FROM announced_pu_results r
               JOIN polling_unit p ON r.polling_unit_uniqueid = p.uniqueid
               WHERE p.lga_id = %s
               GROUP BY r.party_abbreviation
               ORDER BY r.party_abbreviation""",
            (lga_id,),
        )
        if totals:
            counted = run_query(
                """SELECT COUNT(DISTINCT r.polling_unit_uniqueid) AS n
                   FROM announced_pu_results r
                   JOIN polling_unit p ON r.polling_unit_uniqueid = p.uniqueid
                   WHERE p.lga_id = %s""",
                (lga_id,),
            )
            body += "<p>Added up from the results of <b>%s</b> polling unit(s) in this LGA.</p>" % e(counted[0]["n"])
            body += '<table><tr><th>Party</th><th class="num">Total score</th></tr>'
            grand_total = 0
            for row in totals:
                total = int(row["total"])
                grand_total += total
                body += '<tr><td>%s</td><td class="num">%s</td></tr>' % (e(row["party_abbreviation"]), format(total, ","))
            body += '<tr><th>All parties</th><th class="num">%s</th></tr></table>' % format(grand_total, ",")
        else:
            body += '<div class="msg info">No polling unit result has been saved for this LGA yet.</div>'

    return make_page("LGA total", body)


# =====================================================================
# Question 3: save results of ALL parties for a NEW polling unit
# Chained dropdown: choose an LGA first, then a ward of that LGA
# =====================================================================
def new_result_page(query, errors=None, form=None):
    errors = errors or []
    form = form or {}
    lga_id = get_number(query, "lga_id")

    body = "<h1>Save the results of a new polling unit</h1>"
    if errors:
        body += '<div class="msg error"><b>Please fix this:</b><ul>'
        for message in errors:
            body += "<li>%s</li>" % e(message)
        body += "</ul></div>"

    # step 1: a small form on its own, it reloads the page with the wards of the LGA
    body += '<form method="get"><label for="lga_id">Step 1: choose a local government (LGA)</label>'
    body += '<select name="lga_id" id="lga_id" onchange="this.form.submit()">'
    body += '<option value="">-- choose LGA --</option>'
    body += make_options(get_lgas(), "lga_id", "lga_name", lga_id)
    body += '</select><noscript><button type="submit">Next</button></noscript></form>'

    if lga_id:
        wards = run_query(
            "SELECT uniqueid, ward_name FROM ward WHERE lga_id = %s ORDER BY ward_name", (lga_id,))
        body += '<form method="post">'
        body += '<input type="hidden" name="lga_id" value="%s">' % e(lga_id)
        body += '<label for="ward_uid">Step 2: choose the ward</label>'
        body += '<select name="ward_uid" id="ward_uid" required><option value="">-- choose ward --</option>'
        body += make_options(wards, "uniqueid", "ward_name", get_text(form, "ward_uid"))
        body += "</select>"
        body += '<label for="unit_name">Step 3: name of the new polling unit</label>'
        body += '<input type="text" name="unit_name" id="unit_name" maxlength="50" required value="%s" placeholder="e.g. Primary School, Ovie">' % e(get_text(form, "unit_name"))
        body += '<label for="entered_by">Your name</label>'
        body += '<input type="text" name="entered_by" id="entered_by" maxlength="50" required value="%s">' % e(get_text(form, "entered_by"))
        body += '<label>Step 4: score of each party</label><div class="scores">'
        for party in PARTIES:
            body += '<div><label for="score_%s">%s</label>' % (party, party)
            body += '<input type="number" name="score_%s" id="score_%s" min="0" step="1" required value="%s"></div>' % (
                party, party, e(get_text(form, "score_" + party)))
        body += '</div><button type="submit">Save result</button></form>'

    return make_page("Add new polling unit result", body)


def save_new_result(form):
    """Check the form, then save the polling unit and one row per party.
    Returns (page_html, None) if there is a problem, or (None, redirect_url) when saved."""
    lga_id = get_number(form, "lga_id")
    ward_uid = get_number(form, "ward_uid")
    unit_name = get_text(form, "unit_name")
    entered_by = get_text(form, "entered_by")

    # 1) check what the user typed
    errors = []
    if not ward_uid:
        errors.append("Please choose a ward.")
    if not unit_name:
        errors.append("Please type the polling unit name.")
    if not entered_by:
        errors.append("Please type your name.")
    scores = {}
    for party in PARTIES:
        score = get_number(form, "score_" + party)
        if score is None:
            errors.append("Score for %s must be a whole number (0 or more)." % party)
        else:
            scores[party] = score

    ward = None
    if ward_uid and lga_id:
        found = run_query("SELECT uniqueid, ward_id, lga_id FROM ward WHERE uniqueid = %s", (ward_uid,))
        if found and found[0]["lga_id"] == lga_id:
            ward = found[0]
        else:
            errors.append("That ward does not belong to the chosen LGA.")

    if errors:
        return new_result_page({"lga_id": [str(lga_id or "")]}, errors, form), None

    # 2) save to the database
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # the next polling_unit_id inside this ward
    cursor.execute(
        "SELECT COALESCE(MAX(polling_unit_id), 0) + 1 FROM polling_unit WHERE uniquewardid = %s",
        (ward_uid,),
    )
    next_id = cursor.fetchone()[0]
    number = "DT%02d%02d%03d" % (lga_id, ward["ward_id"], next_id)    # looks like DT1708006

    cursor.execute(
        """INSERT INTO polling_unit
           (polling_unit_id, ward_id, lga_id, uniquewardid, polling_unit_number,
            polling_unit_name, polling_unit_description, entered_by_user, date_entered)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
        (next_id, ward["ward_id"], lga_id, ward_uid, number, unit_name, unit_name, entered_by),
    )
    new_unit_id = cursor.lastrowid       # the uniqueid MySQL gave to the new polling unit

    for party in PARTIES:
        cursor.execute(
            """INSERT INTO announced_pu_results
               (polling_unit_uniqueid, party_abbreviation, party_score,
                entered_by_user, date_entered, user_ip_address)
               VALUES (%s, %s, %s, %s, NOW(), %s)""",
            (str(new_unit_id), party, scores[party], entered_by, ""),
        )

    conn.commit()        # save everything together
    cursor.close()
    conn.close()

    return None, "/polling-unit?lga_id=%s&pu_id=%s&saved=1" % (lga_id, new_unit_id)


# =====================================================================
# The "front door": every web request comes in here
# =====================================================================
def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    query = parse_qs(environ.get("QUERY_STRING", ""))      # data in the address bar

    form = {}
    if method == "POST":                                    # data sent by a form
        size = int(environ.get("CONTENT_LENGTH") or 0)
        form = parse_qs(environ["wsgi.input"].read(size).decode("utf-8"))

    status = "200 OK"
    headers = [("Content-Type", "text/html; charset=utf-8")]
    try:
        if path == "/":
            html = home_page()
        elif path == "/polling-unit":
            html = polling_unit_page(query)
        elif path == "/lga-total":
            html = lga_total_page(query)
        elif path == "/new-result":
            if method == "POST":
                html, redirect_to = save_new_result(form)
                if redirect_to:                              # saved: go and show the result
                    start_response("302 Found", [("Location", redirect_to)])
                    return [b""]
            else:
                html = new_result_page(query)
        else:
            status = "404 Not Found"
            html = make_page("Not found", "<h1>Page not found</h1>")
    except mysql.connector.Error as error:
        status = "500 Internal Server Error"
        html = make_page("Database error", '<h1>Database problem</h1><div class="msg error">%s</div>' % e(error))

    start_response(status, headers)
    return [html.encode("utf-8")]


if __name__ == "__main__":
    print("Open http://127.0.0.1:8000 in your browser (press Ctrl+C to stop)")
    make_server("127.0.0.1", 8000, application).serve_forever()
