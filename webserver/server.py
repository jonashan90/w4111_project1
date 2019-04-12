#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
Example webserver

To run locally

  python server.py

Go to http://localhost:8111 in your browser


A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

from operator import itemgetter
from geopy import distance
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, flash, url_for
import random
import datetime
from datetime import timedelta

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
app.secret_key = os.urandom(24)
DB_USER = "jh3877"
DB_PASSWORD = "Vy8Dx3Dc04"
DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.com"
DATABASEURI = "postgresql://"+DB_USER+":"+DB_PASSWORD+"@"+DB_SERVER+"/w4111"

engine = create_engine(DATABASEURI)


@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request 
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request

    The variable g is globally accessible
    """
    try:
        g.conn = engine.connect()
    except:
        print "uh oh, problem connecting to database"
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass


#
# @app.route is a decorator around index() that means:
#     run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to e.g., localhost:8111/foobar/ with POST or GET then you could use
#
#             @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/')
def index():
    return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if "user" in session:
        return redirect(url_for('user_profile'))
    else:
        return render_template("login.html")


@app.route('/user_profile', methods=['GET', 'POST'])
def user_profile():
    if "user" in session:
        username = session["user"]
    else:
        username = request.form["username"].lower().capitalize()
        session["user"] = username
    if "user_type" in session:
        user_type = session["user_type"]
    else:
        user_type = request.form["user_type"]
        session["user_type"] = user_type

    print(user_type)
    print(username)
    results_dict = dict()
    trip_history = []
    bike_history = []

    if user_type == "user":

        # Query for user information.
        query = 'SELECT * FROM users WHERE UPPER(users.username) = (:username)'
        cursor = g.conn.execute(text(query), username=username.upper())
        for results in cursor:
            results_dict["email"] = results[0]
            results_dict["age"] = results[1]
            results_dict["cc"] = results[2]
            results_dict["first_name"] = results[3]
            results_dict["last_name"] = results[4]
        cursor.close()

        # Query for trip history.
        query = """SELECT T.trip_id, T.request_time, T.begin_trip_time, T.dropoff_time, T.begin_trip_lat, 
        T.begin_trip_lng, T.dropoff_lat, T.dropoff_lng, T.distance_m, T.fare, T.duration,
        D.first_name, D.last_name, D.license_num, initcap(T.status)
        FROM trips T INNER JOIN schedules S ON T.trip_id = S.trip_id
        INNER JOIN accepts A ON A.trip_id = T.trip_id
        INNER JOIN drivers D ON D.license_num = A.license_num
        WHERE UPPER(S.username) = (:username) 
        ORDER BY T.request_time DESC"""
        cursor = g.conn.execute(text(query), username=username.upper())
        for results in cursor:
            trip_history.append(results)
        cursor.close()

        # Query for bike history.
        query = """SELECT R.rent_id, B.bike_id, B.battery, B.latitude, B.longitude
                   FROM bikes B INNER JOIN rents R ON B.bike_id = R.bike_id
                   WHERE UPPER(R.username) = (:username)"""
        cursor = g.conn.execute(text(query), username=username.upper())
        for results in cursor:
            bike_history.append(results)
        cursor.close()

        # Query for promotion.
        query = """SELECT P.establishment FROM receives R INNER JOIN promotions P ON R.promotion_id = P.promotion_id
                WHERE UPPER(R.username) = (:username)"""
        cursor = g.conn.execute(text(query), username=username.upper())
        for results in cursor:
            promotion = results[0].encode("utf-8")
        cursor.close()

        return render_template("user_template.html", results_dict=results_dict, trip_history=trip_history,
                               bike_history=bike_history, promotion=promotion)

    if user_type == "driver":

        # Query for driver information.
        query = 'SELECT * FROM drivers WHERE UPPER(drivers.username) = (:username)'
        cursor = g.conn.execute(text(query), username=username.upper())
        for results in cursor:
            results_dict["license_num"] = results[0]
            results_dict["first_name"] = results[1]
            results_dict["last_name"] = results[2]
            results_dict["email"] = results[3]
            results_dict["lat"] = results[4]
            results_dict["long"] = results[5]
        cursor.close()

        # Query for trip history.
        query = """SELECT T.trip_id, T.request_time, T.begin_trip_time, T.dropoff_time, T.begin_trip_lat, 
                T.begin_trip_lng, T.dropoff_lat, T.dropoff_lng, T.distance_m, T.fare, T.duration,
                U.first_name, U.last_name, initcap(T.status)
                FROM trips T INNER JOIN schedules S ON T.trip_id = S.trip_id
                INNER JOIN users U ON U.username = S.username
                INNER JOIN accepts A ON A.trip_id = T.trip_id
                INNER JOIN drivers D ON D.license_num = A.license_num
                WHERE UPPER(D.username) = (:username) 
                ORDER BY T.request_time DESC"""
        cursor = g.conn.execute(text(query), username=username.upper())
        for results in cursor:
            trip_history.append(results)
        cursor.close()

        car_info = dict()
        # Query for car information.
        query = """SELECT vin_number, plate_number, make_model, color, year, state
                FROM drive_cars WHERE license_num = '{}'""".format(results_dict["license_num"])
        cursor = g.conn.execute(text(query))
        for results in cursor:
            car_info["vin_num"] = results[0]
            car_info["plate_num"] = results[1]
            car_info["make_model"] = results[2]
            car_info["color"] = results[3]
            car_info["year"] = results[4]
            car_info["state"] = results[5]
        cursor.close()
        return render_template("driver_template.html", results_dict=results_dict,
                               trip_history=trip_history, car_info=car_info)


@app.route('/find_drivers', methods=['POST'])
def find_drivers():
    trip_info = dict()
    trip_info["current_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trip_info["pickup_lat"] = float(request.form["pickup_lat"].encode("utf-8"))
    trip_info["pickup_long"] = float(request.form["pickup_long"].encode("utf-8"))
    trip_info["dropoff_lat"] = float(request.form["dropoff_lat"].encode("utf-8"))
    trip_info["dropoff_long"] = float(request.form["dropoff_long"].encode("utf-8"))
    trip_info["distance"] = distance.distance((trip_info["pickup_lat"], trip_info["pickup_long"]),
                                              (trip_info["dropoff_lat"], trip_info["dropoff_long"])).miles
    trip_info["duration"] = timedelta(hours=(trip_info["distance"]/25))
    trip_info["fare"] = round((trip_info["distance"]*2.5), 2)

    # Query for drivers.
    query = """SELECT D.first_name, D.last_name, D.license_num, C.plate_number, C.make_model, C.color, C.year,
                      C.state, D.lat, D.lng
               FROM drivers D INNER JOIN drive_cars C ON D.license_num = C.license_num"""
    cursor = g.conn.execute(text(query))
    drivers = []
    for results in cursor:
        row = []
        for attr in results:
            row.append(attr)
        # Calculate additional columns.
        driver_distance = distance.distance((row[-2], row[-1]), (trip_info["pickup_lat"], trip_info["pickup_long"])).miles
        pickup_time = datetime.datetime.now() + timedelta(hours=(driver_distance/25))
        dropoff_time = pickup_time + trip_info["duration"]
        pickup_time = pickup_time.strftime("%Y-%m-%d %H:%M:%S")
        dropoff_time = dropoff_time.strftime("%Y-%m-%d %H:%M:%S")
        row.append(pickup_time)
        row.append(dropoff_time)
        drivers.append(row)
    cursor.close()

    drivers = sorted(drivers, key=itemgetter(-2))

    return render_template("find_drivers.html", trip_info=trip_info, drivers=drivers)


@app.route('/driver_selection', methods=['POST'])
def driver_selection():
    results = str(request.form["driver_select"]).strip("()")
    print(results)
    driver_license_num, pickup_lat, pickup_long, dropoff_lat, dropoff_long, distance, fare, current_time,\
    pickup_time, dropoff_time, days, seconds, microseconds = results.split(", ")
    days = days.split("(")[-1]
    duration = timedelta(int(days), int(seconds), int(microseconds))
    driver_license_num = driver_license_num.strip("'")

    print(driver_license_num)
    print(type(driver_license_num))

    print(pickup_lat)
    print(type(pickup_lat))

    print("days: ", days, "seconds: ", seconds, "microseconds: ", microseconds)
    print("duration: ", duration)
    print("duration type: ", type(duration))

    print("pickup_time: ", pickup_time)

    # Insert pending trip into trips table.
    trip_id = random.randint(100, 999999999999)
    query = "INSERT INTO trips VALUES({},{},{},{},{},{},{},{},{},{},'{}','Pending')".\
        format(trip_id, current_time, pickup_time, dropoff_time,
               pickup_lat, pickup_long, dropoff_lat, dropoff_long,
               distance, fare, duration)
    cursor = g.conn.execute(text(query))
    cursor.close()

    # Insert into schedules.
    query = "INSERT INTO schedules VALUES('{}',{})".format(session["user"], trip_id)
    cursor = g.conn.execute(text(query))
    cursor.close()

    # Insert into accepts.
    query = "INSERT INTO accepts VALUES('{}','{}')".format(trip_id, driver_license_num)
    cursor = g.conn.execute(text(query))
    cursor.close()

    return redirect(url_for("user_profile"))


@app.route('/accept_trip', methods=['POST'])
def accept_trip():
    trip_id = request.form["trip_id"]
    print("in accept trip, trip_id: ", trip_id)

    # Update status in trips table.
    query = "UPDATE trips SET status = 'Completed' WHERE trip_id = '{}'".format(trip_id)
    cursor = g.conn.execute(text(query))
    cursor.close()
    return redirect(url_for("user_profile"))


@app.route('/cancel_trip', methods=['POST'])
def cancel_trip():
    trip_id = request.form["trip_id"]
    print("in cancel trip, trip_id: ", trip_id)

    # Update status in trips table.
    query = "UPDATE trips SET status = 'Canceled' WHERE trip_id = '{}'".format(trip_id)
    cursor = g.conn.execute(text(query))
    cursor.close()
    return redirect(url_for("user_profile"))


@app.route('/bike_rental', methods=['POST'])
def bike_rental():
    user_lat = request.form["latitude"]
    user_long = request.form["longitude"]
    user_position = (float(user_lat.encode("utf-8")), float(user_long.encode("utf-8")))
    print("user latitude: ", user_lat)
    print("user longitude: ", user_long)
    print(session["user"])
    query = "SELECT * FROM bikes"
    cursor = g.conn.execute(text(query))

    bikes = []
    for results in cursor:
        row = []
        for attr in results:
            row.append(attr)
        bikes.append(row)

    for bike in bikes:
        bike_lat = bike[2]
        bike_long = bike[3]
        bike_position = (bike_lat, bike_long)
        print(bike)
        print("distance(miles): ", distance.distance(user_position, bike_position).miles)
        bike.append(distance.distance(user_position, bike_position).miles)

    bikes = sorted(bikes, key=itemgetter(-1))
    return render_template("bike_rental.html", bikes=bikes, user_position=user_position)


@app.route('/bike_rental_confirm', methods=['GET', 'POST'])
def bike_rental_confirm():
    query = "INSERT INTO rents VALUES({},'{}',{})".format(random.randint(100, 999999999999), session["user"],
                                                          request.form["bike_selection"].encode("utf-8"))
    cursor = g.conn.execute(text(query))
    return redirect(url_for("user_profile"))


@app.route('/logout', methods=['POST'])
def logout():
    session.pop("user")
    session.pop("user_type")
    return redirect(url_for("login"))


if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using

                python server.py

        Show the help text using

                python server.py --help

        """

        HOST, PORT = host, port
        print "running on %s:%d" % (HOST, PORT)
        app.run(host=HOST, port=PORT, debug=True, threaded=threaded)


    run()
