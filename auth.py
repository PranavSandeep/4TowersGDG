import os
import json
import firebase_admin
from firebase_admin import credentials, auth
from flask import (
    Flask, request, redirect, render_template,
    session, jsonify, send_from_directory
)
import mysql.connector as mc

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

# -------------------- DATABASE HELPER --------------------

def get_db():
    return mc.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", 3306))
    )

def init_db():
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markers (
            text VARCHAR(255),
            lat VARCHAR(255),
            lon VARCHAR(255),
            user VARCHAR(255),
            url VARCHAR(255),
            id INT PRIMARY KEY
        )
    """)
    connection.commit()
    connection.close()

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
def getData():
    text = request.form.get("text")
    lat = request.form.get("lat")
    lng = request.form.get("lng")
    user = request.form.get("user")

    image = request.files.get("image")
    image_url = None

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT MAX(id) FROM markers")
    result = cursor.fetchone()
    max_id = result[0] if result and result[0] else None
    new_id = 100000 if max_id is None else max_id + 1

    if image:
        filename = f"{user}{new_id}.jpg"
        image_path = os.path.join(IMAGE_DIR, filename)
        image.save(image_path)
        image_url = f"/images/{filename}"

    cursor.execute(
        "INSERT INTO markers (text, lat, lon, user, url, id) VALUES (%s, %s, %s, %s, %s, %s)",
        (text, lat, lng, user, image_url, new_id)
    )

    connection.commit()
    connection.close()

    return jsonify({
        "text": text,
        "lat": lat,
        "lon": lng,
        "user": user,
        "url": image_url,
        "id": new_id
    })


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)


@app.route("/get_markers")
def get_markers():
    try:
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM markers")
        rows = cursor.fetchall()
        column_names = [i[0] for i in cursor.description]

        markers = [dict(zip(column_names, row)) for row in rows]

        connection.close()
        return jsonify(markers)

    except Exception as e:
        print("GET MARKERS ERROR:", e)
        return jsonify([])


@app.route("/delete", methods=["POST"])
def delete_marker():
    try:
        marker_id = request.form.get("id")

        connection = get_db()
        cursor = connection.cursor()

        cursor.execute("SELECT url FROM markers WHERE id = %s", (marker_id,))
        result = cursor.fetchone()

        if result and result[0]:
            filename = result[0].replace("/images/", "")
            image_path = os.path.join(IMAGE_DIR, filename)
            if os.path.exists(image_path):
                os.remove(image_path)

        cursor.execute("DELETE FROM markers WHERE id = %s", (marker_id,))
        connection.commit()
        connection.close()

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
