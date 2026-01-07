import os
import json
import psycopg2
import psycopg2.extras
import firebase_admin
from firebase_admin import credentials, auth
from flask import (
    Flask, request, redirect, render_template,
    session, jsonify, send_from_directory
)

# -------------------- APP SETUP --------------------

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# -------------------- FIREBASE INIT --------------------

service_account = json.loads(
    os.environ["FIREBASE_SERVICE_ACCOUNT"]
)

cred = credentials.Certificate(service_account)
firebase_admin.initialize_app(cred)

# -------------------- DATABASE HELPERS --------------------

def get_db():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 5432))
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS markers (
            id INTEGER PRIMARY KEY,
            text TEXT,
            lat TEXT,
            lon TEXT,
            "user" TEXT,
            url TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# -------------------- ROUTES --------------------

@app.route("/")
def login():
    return render_template("login.html")


@app.route("/guest")
def guest():
    session["user"] = "Guest"
    return redirect("/dashboard")


@app.route("/verify", methods=["POST"])
def verify():
    id_token = request.form.get("idToken")
    try:
        decoded = auth.verify_id_token(id_token, clock_skew_seconds=10)
        session["user"] = decoded.get("name", decoded.get("email"))
        return redirect("/dashboard")
    except Exception as e:
        print("VERIFY ERROR:", e)
        return "Invalid token", 401


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("index.html", user=session["user"])


@app.route("/data", methods=["POST"])
def add_marker():
    text = request.form.get("text")
    lat = request.form.get("lat")
    lng = request.form.get("lng")
    user = request.form.get("user")

    image = request.files.get("image")
    image_url = None

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT MAX(id) FROM markers")
    max_id = cur.fetchone()[0]
    new_id = 100000 if max_id is None else max_id + 1

    if image:
        filename = f"{user}{new_id}.jpg"
        path = os.path.join(IMAGE_DIR, filename)
        image.save(path)
        image_url = f"/images/{filename}"

    cur.execute(
        """
        INSERT INTO markers (id, text, lat, lon, "user", url)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (new_id, text, lat, lng, user, image_url)
    )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "id": new_id,
        "text": text,
        "lat": lat,
        "lon": lng,
        "user": user,
        "url": image_url
    })


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)


@app.route("/get_markers")
def get_markers():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM markers")
        markers = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(markers)
    except Exception as e:
        print("GET MARKERS ERROR:", e)
        return jsonify([])


@app.route("/delete", methods=["POST"])
def delete_marker():
    try:
        marker_id = request.form.get("id")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT url FROM markers WHERE id = %s", (marker_id,))
        row = cur.fetchone()
        if row and row[0]:
            filename = row[0].replace("/images/", "")
            path = os.path.join(IMAGE_DIR, filename)
            if os.path.exists(path):
                os.remove(path)

        cur.execute("DELETE FROM markers WHERE id = %s", (marker_id,))
        conn.commit()
        cur.close()
        conn.close()

        return "Deleted", 200
    except Exception as e:
        print("DELETE ERROR:", e)
        return "Error", 500


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# -------------------- START SERVER --------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
