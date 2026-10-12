from flask import Flask, render_template, request, jsonify
import sqlite3, os, math, random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "evsmart.db"
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

SEED_STATIONS = [
    ("Pune Hinjawadi Tech Park", "Hinjawadi, Pune", 6, 22, 0.18, 1.0),
    ("Wakad Mobility Hub", "Wakad, Pune", 4, 30, 0.22, 0.9),
    ("Baner Green Charge", "Baner, Pune", 5, 60, 0.15, 1.1),
    ("Pimpri Central Station", "Pimpri, Pune", 3, 22, 0.25, 0.8),
]
SEED_CHARGERS = [
    ("PUN-HW-01", 1, "CCS2", 60, "available"), ("PUN-HW-02", 1, "CCS2", 60, "occupied"),
    ("PUN-HW-03", 1, "Type2", 22, "available"), ("PUN-HW-04", 1, "CCS2", 120, "available"),
    ("PUN-HW-05", 1, "Type2", 22, "offline"), ("PUN-HW-06", 1, "CCS2", 60, "available"),
    ("WAK-01", 2, "CCS2", 60, "occupied"), ("WAK-02", 2, "Type2", 22, "available"),
    ("WAK-03", 2, "CCS2", 120, "available"), ("WAK-04", 2, "Type2", 22, "available"),
    ("BAN-01", 3, "CCS2", 60, "available"), ("BAN-02", 3, "CCS2", 120, "available"),
    ("BAN-03", 3, "Type2", 22, "occupied"), ("BAN-04", 3, "CCS2", 60, "available"),
    ("BAN-05", 3, "Type2", 22, "available"),
    ("PIM-01", 4, "CCS2", 60, "available"), ("PIM-02", 4, "Type2", 22, "available"),
    ("PIM-03", 4, "CCS2", 60, "offline"),
]

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS stations(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, location TEXT NOT NULL,
          charger_count INTEGER NOT NULL, max_kw REAL NOT NULL, tariff REAL NOT NULL, solar_share REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS chargers(
          id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
          station_id INTEGER NOT NULL REFERENCES stations(id), connector TEXT NOT NULL,
          power_kw REAL NOT NULL, status TEXT NOT NULL CHECK(status IN ('available','occupied','offline','reserved'))
        );
        CREATE TABLE IF NOT EXISTS vehicles(
          id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, model TEXT NOT NULL,
          connector TEXT NOT NULL, battery_kwh REAL NOT NULL, soc REAL NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, booking_code TEXT UNIQUE NOT NULL,
          vehicle_id INTEGER NOT NULL REFERENCES vehicles(id), charger_id INTEGER NOT NULL REFERENCES chargers(id),
          start_soc REAL NOT NULL, target_soc REAL NOT NULL, energy_kwh REAL NOT NULL,
          estimated_minutes INTEGER NOT NULL, estimated_cost REAL NOT NULL, priority TEXT NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL, ended_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
        if count == 0:
            for s in SEED_STATIONS:
                con.execute("INSERT INTO stations(name,location,charger_count,max_kw,tariff,solar_share) VALUES(?,?,?,?,?,?)", s)
            for c in SEED_CHARGERS:
                con.execute("INSERT INTO chargers(code,station_id,connector,power_kw,status) VALUES(?,?,?,?,?)", c)
            now = datetime.now().isoformat(timespec="seconds")
            seed_vehicles = [
                ("Aarav Shah","Tata Nexon EV","CCS2",40.5,32),
                ("Meera Kulkarni","MG ZS EV","CCS2",50,21),
                ("Kabir Patil","Ather 450X","Type2",3.7,28),
                ("Riya Deshmukh","Hyundai Kona Electric","CCS2",39.2,55),
                ("Ishaan Joshi","Mahindra XUV400","CCS2",39.4,18),
            ]
            for v in seed_vehicles:
                con.execute("INSERT INTO vehicles(owner,model,connector,battery_kwh,soc,created_at) VALUES(?,?,?,?,?,?)", (*v, now))
            con.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)", ("INFO","Demo environment initialized with simulated station telemetry.",now))

def log_event(level, message):
    with connect() as con:
        con.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)",
                    (level, message, datetime.now().isoformat(timespec="seconds")))

def rowdict(row):
    return dict(row) if row is not None else None

def get_dashboard():
    with connect() as con:
        station_count = con.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
        charger_rows = con.execute("SELECT status, COUNT(*) n FROM chargers GROUP BY status").fetchall()
        statuses = {r["status"]: r["n"] for r in charger_rows}
        active = con.execute("SELECT COUNT(*) FROM bookings WHERE status IN ('queued','charging','reserved')").fetchone()[0]
        completed = con.execute("SELECT COUNT(*) FROM bookings WHERE status='completed'").fetchone()[0]
        energy = con.execute("SELECT COALESCE(SUM(energy_kwh),0) FROM bookings WHERE status='completed'").fetchone()[0]
        revenue = con.execute("SELECT COALESCE(SUM(estimated_cost),0) FROM bookings WHERE status='completed'").fetchone()[0]
        station_data = con.execute("""
          SELECT s.*, COUNT(c.id) total_chargers,
          SUM(CASE WHEN c.status='available' THEN 1 ELSE 0 END) available,
          SUM(CASE WHEN c.status='occupied' THEN 1 ELSE 0 END) occupied,
          SUM(CASE WHEN c.status='offline' THEN 1 ELSE 0 END) offline
          FROM stations s LEFT JOIN chargers c ON c.station_id=s.id GROUP BY s.id ORDER BY s.id
        """).fetchall()
        recent = con.execute("""
          SELECT b.*, v.model, v.owner, c.code charger_code, s.name station_name
          FROM bookings b JOIN vehicles v ON v.id=b.vehicle_id
          JOIN chargers c ON c.id=b.charger_id JOIN stations s ON s.id=c.station_id
          ORDER BY b.id DESC LIMIT 8
        """).fetchall()
        events = con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 6").fetchall()
        vehicles = con.execute("SELECT * FROM vehicles ORDER BY id DESC").fetchall()
        chargers = con.execute("SELECT c.*,s.name station_name FROM chargers c JOIN stations s ON s.id=c.station_id ORDER BY c.id").fetchall()
    return {
      "kpis":{"stations":station_count,"chargers":sum(statuses.values()),"available":statuses.get("available",0),
              "occupied":statuses.get("occupied",0),"offline":statuses.get("offline",0),
              "active":active,"completed":completed,"energy":round(energy,1),"revenue":round(revenue,2)},
      "stations":[rowdict(x) for x in station_data],
      "bookings":[rowdict(x) for x in recent],
      "events":[rowdict(x) for x in events],
      "vehicles":[rowdict(x) for x in vehicles],
      "chargers":[rowdict(x) for x in chargers]
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify({"status":"ok","service":"EVSmart demo API","mode":"simulation","timestamp":datetime.now().isoformat()})

@app.get("/api/dashboard")
def api_dashboard():
    return jsonify(get_dashboard())

@app.get("/api/stations")
def api_stations():
    return jsonify(get_dashboard()["stations"])

@app.get("/api/vehicles")
def api_vehicles():
    return jsonify(get_dashboard()["vehicles"])

@app.post("/api/vehicles")
def add_vehicle():
    data = request.get_json(silent=True) or request.form
    try:
        owner = str(data.get("owner","")).strip()
        model = str(data.get("model","")).strip()
        connector = str(data.get("connector","CCS2")).strip()
        battery = float(data.get("battery_kwh",40))
        soc = float(data.get("soc",20))
        if not owner or not model or battery <= 0 or not 0 <= soc <= 100:
            return jsonify({"error":"Enter owner, model, positive battery capacity and SOC from 0 to 100."}), 400
        if connector not in ("CCS2","Type2","CHAdeMO"):
            return jsonify({"error":"Unsupported connector type."}), 400
        with connect() as con:
            cur = con.execute("INSERT INTO vehicles(owner,model,connector,battery_kwh,soc,created_at) VALUES(?,?,?,?,?,?)",
                              (owner,model,connector,battery,soc,datetime.now().isoformat(timespec="seconds")))
            vid = cur.lastrowid
        log_event("INFO", f"Vehicle registered: {model} ({owner})")
        return jsonify({"ok":True,"vehicle_id":vid,"message":"Vehicle registered successfully."}), 201
    except (ValueError, TypeError):
        return jsonify({"error":"Battery capacity and SOC must be numeric."}), 400

def compute_recommendation(vehicle_id, target_soc=80, priority="normal", method="smart"):
    with connect() as con:
        vehicle = con.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if not vehicle:
            return None, "Vehicle not found."
        target_soc = float(target_soc)
        if not (vehicle["soc"] < target_soc <= 100):
            return None, "Target SOC must be greater than current SOC and at most 100%."
        needed = vehicle["battery_kwh"] * (target_soc - vehicle["soc"]) / 100.0
        stations = con.execute("""
          SELECT s.*, c.id charger_id, c.code charger_code, c.connector, c.power_kw, c.status charger_status
          FROM stations s JOIN chargers c ON c.station_id=s.id
          WHERE c.status='available' AND c.connector=? ORDER BY s.id,c.id
        """, (vehicle["connector"],)).fetchall()
        if not stations:
            return None, "No available charger currently matches this vehicle's connector."
        candidates=[]
        for s in stations:
            minutes = max(1, math.ceil(needed / max(s["power_kw"]*0.90, 0.1) * 60))
            # Simple explicit scoring model: travel/queue proxy + duration + price + renewable share.
            # It is a deterministic decision-support heuristic, not a trained AI model.
            queue_proxy = max(0, s["occupied"] if "occupied" in s.keys() else 0)
            score = (s["tariff"] * needed) + (minutes * 0.035) - (s["solar_share"] * needed * 0.20)
            if priority.lower() == "urgent":
                score += minutes * 0.08
            elif priority.lower() == "flexible":
                score += minutes * 0.005
            if method == "fcfs":
                score = s["charger_id"]  # baseline: first available compatible charger
            candidates.append({"station_id":s["id"],"station":s["name"],"location":s["location"],
                "charger_id":s["charger_id"],"charger_code":s["charger_code"],"power_kw":s["power_kw"],
                "tariff":s["tariff"],"solar_share":s["solar_share"],"energy_kwh":round(needed,2),
                "minutes":minutes,"cost":round(needed*s["tariff"],2),"score":round(score,3)})
        candidates.sort(key=lambda x:x["score"])
        best=candidates[0]
        return {"vehicle":rowdict(vehicle),"target_soc":target_soc,"priority":priority,"method":method,
                "recommendation":best,"alternatives":candidates,"explanation":[
                  f"Connector compatibility checked: {vehicle['connector']}.",
                  f"Estimated energy needed: {needed:.2f} kWh.",
                  f"Estimated charging time uses 90% effective-power assumption.",
                  f"Ranking considers estimated tariff, charging duration and simulated solar share." if method=="smart" else "Baseline selects the first available compatible charger."
                ]}, None

@app.post("/api/recommend")
def api_recommend():
    data = request.get_json(silent=True) or request.form
    try:
        vehicle_id=int(data.get("vehicle_id"))
        target=float(data.get("target_soc",80))
        priority=str(data.get("priority","normal"))
        method=str(data.get("method","smart"))
        result, err=compute_recommendation(vehicle_id,target,priority,method)
        if err: return jsonify({"error":err}), 400
        return jsonify(result)
    except (ValueError,TypeError):
        return jsonify({"error":"Choose a valid vehicle and target SOC."}), 400

@app.post("/api/bookings")
def create_booking():
    data = request.get_json(silent=True) or request.form
    try:
        vehicle_id=int(data.get("vehicle_id"))
        target=float(data.get("target_soc",80))
        priority=str(data.get("priority","normal")).lower()
        method=str(data.get("method","smart")).lower()
        result, err=compute_recommendation(vehicle_id,target,priority,method)
        if err: return jsonify({"error":err}), 400
        rec=result["recommendation"]
        booking_code="EV"+datetime.now().strftime("%y%m%d%H%M%S")+str(random.randint(10,99))
        with connect() as con:
            # Re-check availability within transaction to avoid stale recommendation booking.
            charger=con.execute("SELECT status FROM chargers WHERE id=?", (rec["charger_id"],)).fetchone()
            if not charger or charger["status"] != "available":
                return jsonify({"error":"That charger was just taken. Refresh and recommend again."}), 409
            con.execute("UPDATE chargers SET status='reserved' WHERE id=?", (rec["charger_id"],))
            con.execute("""INSERT INTO bookings(booking_code,vehicle_id,charger_id,start_soc,target_soc,energy_kwh,
              estimated_minutes,estimated_cost,priority,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (booking_code,vehicle_id,rec["charger_id"],result["vehicle"]["soc"],target,rec["energy_kwh"],
               rec["minutes"],rec["cost"],priority,"reserved",datetime.now().isoformat(timespec="seconds")))
        log_event("SUCCESS", f"Booking {booking_code} reserved {rec['charger_code']} at {rec['station']}")
        return jsonify({"ok":True,"booking_code":booking_code,"recommendation":rec,"message":"Charger reserved. Start the session from Bookings."}), 201
    except (ValueError,TypeError):
        return jsonify({"error":"Invalid booking request."}), 400

@app.get("/api/bookings")
def list_bookings():
    with connect() as con:
        rows=con.execute("""SELECT b.*,v.model,v.owner,c.code charger_code,s.name station_name
          FROM bookings b JOIN vehicles v ON v.id=b.vehicle_id JOIN chargers c ON c.id=b.charger_id
          JOIN stations s ON s.id=c.station_id ORDER BY b.id DESC""").fetchall()
    return jsonify([rowdict(x) for x in rows])

@app.post("/api/bookings/<int:booking_id>/action")
def booking_action(booking_id):
    data=request.get_json(silent=True) or {}
    action=data.get("action")
    with connect() as con:
        b=con.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if not b: return jsonify({"error":"Booking not found."}),404
        if action=="start":
            if b["status"]!="reserved": return jsonify({"error":"Only reserved bookings can be started."}),400
            con.execute("UPDATE bookings SET status='charging' WHERE id=?", (booking_id,))
            con.execute("UPDATE chargers SET status='occupied' WHERE id=?", (b["charger_id"],))
            msg=f"Charging started for {b['booking_code']}."
        elif action=="complete":
            if b["status"] not in ("charging","reserved"): return jsonify({"error":"Only active bookings can be completed."}),400
            con.execute("UPDATE bookings SET status='completed',ended_at=? WHERE id=?",
                        (datetime.now().isoformat(timespec="seconds"),booking_id))
            con.execute("UPDATE chargers SET status='available' WHERE id=?", (b["charger_id"],))
            con.execute("UPDATE vehicles SET soc=? WHERE id=?", (b["target_soc"],b["vehicle_id"]))
            msg=f"Session {b['booking_code']} completed; vehicle SOC updated."
        elif action=="cancel":
            if b["status"] not in ("reserved","queued"): return jsonify({"error":"Only reserved or queued bookings can be cancelled."}),400
            con.execute("UPDATE bookings SET status='cancelled',ended_at=? WHERE id=?",
                        (datetime.now().isoformat(timespec="seconds"),booking_id))
            con.execute("UPDATE chargers SET status='available' WHERE id=?", (b["charger_id"],))
            msg=f"Booking {b['booking_code']} cancelled."
        else:
            return jsonify({"error":"Action must be start, complete or cancel."}),400
    log_event("INFO",msg)
    return jsonify({"ok":True,"message":msg})

@app.post("/api/simulation/tick")
def simulation_tick():
    # Explicit demo simulation: moves active sessions forward and occasionally flips a charger status.
    with connect() as con:
        active=con.execute("SELECT * FROM bookings WHERE status='charging'").fetchall()
        completed_codes=[]
        for b in active:
            remaining=max(0,b["estimated_minutes"]-5)
            if remaining <= 0:
                con.execute("UPDATE bookings SET status='completed',ended_at=? WHERE id=?",
                            (datetime.now().isoformat(timespec="seconds"),b["id"]))
                con.execute("UPDATE chargers SET status='available' WHERE id=?", (b["charger_id"],))
                con.execute("UPDATE vehicles SET soc=? WHERE id=?", (b["target_soc"],b["vehicle_id"]))
                completed_codes.append(b["booking_code"])
        # Simulated load event, no external hardware is contacted.
        if random.random() < 0.25:
            available=con.execute("SELECT id,code FROM chargers WHERE status='available' ORDER BY RANDOM() LIMIT 1").fetchone()
            if available:
                con.execute("UPDATE chargers SET status='offline' WHERE id=?", (available["id"],))
                con.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)",
                    ("WARNING",f"Simulated telemetry: {available['code']} went offline.",datetime.now().isoformat(timespec="seconds")))
        con.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)",
                    ("INFO",f"Simulation tick completed. Sessions auto-completed: {len(completed_codes)}.",datetime.now().isoformat(timespec="seconds")))
    return jsonify({"ok":True,"completed":completed_codes,"message":"Simulation advanced. Demo telemetry may change charger state."})

@app.post("/api/chargers/<int:charger_id>/status")
def set_charger_status(charger_id):
    data=request.get_json(silent=True) or {}
    status=data.get("status")
    if status not in ("available","offline"):
        return jsonify({"error":"Manual status can be set to available or offline."}),400
    with connect() as con:
        ch=con.execute("SELECT * FROM chargers WHERE id=?", (charger_id,)).fetchone()
        if not ch: return jsonify({"error":"Charger not found."}),404
        if ch["status"] in ("occupied","reserved") and status=="offline":
            return jsonify({"error":"Cannot take an active or reserved charger offline."}),409
        con.execute("UPDATE chargers SET status=? WHERE id=?", (status,charger_id))
    log_event("INFO",f"Charger {ch['code']} marked {status} by demo operator.")
    return jsonify({"ok":True})

@app.get("/api/analytics")
def analytics():
    with connect() as con:
        completed=con.execute("SELECT COUNT(*) FROM bookings WHERE status='completed'").fetchone()[0]
        total_energy=con.execute("SELECT COALESCE(SUM(energy_kwh),0) FROM bookings WHERE status='completed'").fetchone()[0]
        total_cost=con.execute("SELECT COALESCE(SUM(estimated_cost),0) FROM bookings WHERE status='completed'").fetchone()[0]
        station=con.execute("""SELECT s.name,COUNT(b.id) sessions,COALESCE(SUM(CASE WHEN b.status='completed' THEN b.energy_kwh ELSE 0 END),0) energy
            FROM stations s LEFT JOIN chargers c ON c.station_id=s.id LEFT JOIN bookings b ON b.charger_id=c.id
            GROUP BY s.id ORDER BY energy DESC""").fetchall()
        status=con.execute("SELECT status,COUNT(*) n FROM chargers GROUP BY status").fetchall()
        daily=con.execute("""SELECT substr(created_at,1,10) day, COUNT(*) sessions,
            COALESCE(SUM(energy_kwh),0) energy FROM bookings GROUP BY substr(created_at,1,10) ORDER BY day""").fetchall()
    return jsonify({"completed_sessions":completed,"energy_kwh":round(total_energy,2),"revenue_inr":round(total_cost,2),
                    "by_station":[rowdict(x) for x in station],"charger_status":[rowdict(x) for x in status],"daily": [rowdict(x) for x in daily]})

@app.get("/api/forecast")
def forecast():
    # Forecasting baseline uses recent completed sessions if available; otherwise a transparent synthetic profile.
    with connect() as con:
        recent=con.execute("SELECT energy_kwh,created_at FROM bookings WHERE status='completed' ORDER BY id DESC LIMIT 30").fetchall()
    if len(recent)>=5:
        values=[float(r["energy_kwh"]) for r in recent]
        avg=sum(values)/len(values)
        method="recent completed-session moving average"
        confidence="low-to-moderate; small demo dataset"
    else:
        # Synthetic hourly profile is for demonstration only, not real-world prediction.
        hours=[0.35,0.25,0.2,0.2,0.3,0.45,0.7,0.85,0.8,0.65,0.6,0.65,0.7,0.72,0.68,0.75,0.9,1.0,0.95,0.85,0.7,0.6,0.5,0.4]
        avg=round(sum(hours)/len(hours)*30,2)
        method="synthetic hourly demand profile (demo data)"
        confidence="illustrative only; replace with real charging history"
    hours_labels=["06","08","10","12","14","16","18","20","22"]
    multipliers=[0.42,0.55,0.7,0.72,0.68,0.82,1.0,0.92,0.64]
    points=[{"time":h+":00","demand_kwh":round(avg*m,1)} for h,m in zip(hours_labels,multipliers)]
    peak=max(points,key=lambda x:x["demand_kwh"])
    return jsonify({"model":"transparent baseline forecast","method":method,"confidence":confidence,
      "forecast":points,"peak_window":peak["time"],"peak_demand_kwh":peak["demand_kwh"],
      "note":"This demo forecast is not a trained ML model. It uses a moving average when sufficient completed sessions exist; otherwise it uses a synthetic profile."})

@app.post("/api/reset-demo")
def reset_demo():
    # Deletes transactional records but preserves station/charger inventory and vehicle records.
    with connect() as con:
        con.execute("DELETE FROM bookings")
        con.execute("UPDATE chargers SET status=CASE WHEN id IN (2,7,13) THEN 'occupied' WHEN id IN (5,18) THEN 'offline' ELSE 'available' END")
        con.execute("DELETE FROM events")
    log_event("INFO","Demo transactions reset.")
    return jsonify({"ok":True,"message":"Bookings and events reset. Station inventory and vehicles preserved."})

init_db()
if __name__ == "__main__":

    print("\\nEVSmart Enterprise Demo")
    print("Local dashboard: http://127.0.0.1:5000")
    print("API health:      http://127.0.0.1:5000/health")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT",5000)), debug=False)
