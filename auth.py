import firebase_admin
from firebase_admin import credentials, auth
from flask import Flask, request, redirect, render_template, session, jsonify
import mysql.connector as mc
import os

app = Flask(__name__)

app.secret_key = "cheeseBurgerMonzafera"


# Firebase init
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)


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

    print("RAW TOKEN:", id_token)
    print("TOKEN TYPE:", type(id_token))
    print("TOKEN LENGTH:", len(id_token) if id_token else None)

    try:
        decoded = auth.verify_id_token(id_token, clock_skew_seconds=10)
        print("DECODED EMAIL:", decoded.get("email"))

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

    connection = mc.connect(
        host="localhost",
        user="root",
        password="",

    )
    cursor = connection.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS 4towers;")
    cursor.execute("USE 4towers;")
    cursor.execute("CREATE TABLE IF NOT EXISTS markers (text VARCHAR(255), lat VARCHAR(255), lon VARCHAR(255), user VARCHAR(255), url VARCHAR(255), id int PRIMARY KEY);")
    cursor.execute("SELECT MAX(id) FROM markers")
    result = cursor.fetchone()
    max_id = result[0] if result else None
    new_id = 100000 if max_id is None else max_id + 1

    if(image):
        if not os.path.exists("/Users/aman/Desktop/4towers/images/"):
             os.makedirs("/Users/aman/Desktop/4towers/images/")
        image.save(f"/Users/aman/Desktop/4towers/images/{user + str(new_id)}.jpg")
        image_url = f"/Users/aman/Desktop/4towers/images/{user + str(new_id)}.jpg"
    
    cursor.execute("INSERT INTO markers (text, lat, lon, user, url, id) VALUES (%s, %s, %s, %s, %s, %s);", (text, lat, lng, user, image_url, new_id))
    connection.commit()
    print(f"\n\n\nlatitude: {lat}\nlongitude: {lng}\nmarker title: {text}\nimage: {image_url}\nuser: {user}\nid: {new_id}\n\n")
    
    connection.close()
    
    return jsonify({
        "text": text,
        "lat": lat,
        "lon": lng,
        "user": user,
        "url": image_url,
        "id": new_id
    })



@app.route("/get_markers")
def get_markers():
    try:
        connection = mc.connect(
            host="localhost",
            user="root",
            password="",
            database="4towers"
        )
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM markers")
        rows = cursor.fetchall()
        column_names = [i[0] for i in cursor.description]
        
        markers = []
        for row in rows:
            marker = dict(zip(column_names, row))
            markers.append(marker)
            
        connection.close()
        return jsonify(markers)
    except Exception as e:
        print("GET MARKERS ERROR:", e)
        return jsonify([])

@app.route("/delete", methods=["POST"])
def delete_marker():
    try:
        marker_id = request.form.get("id")
        print("DELETING MARKER ID:", marker_id)
        
        connection = mc.connect(
            host="localhost",
            user="root",
            password="",
            database="4towers"
        )
        cursor = connection.cursor()
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


if __name__ == "__main__":
    app.run(port=5000, debug=True)
