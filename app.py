from flask import Flask, render_template, request, redirect, url_for, flash
from database import (
    initialize_database,
    create_parking_slots,
    create_default_rates,
    create_exit_barrier,
    get_db_connection
)
from datetime import datetime

def calculate_fee(duration_minutes):
    if duration_minutes <= 30:
        return 0
    elif duration_minutes <= 120:
        return 50
    elif duration_minutes <= 240:
        return 100
    elif duration_minutes <= 360:
        return 300
    else:
        return 500

app = Flask(__name__)
app.secret_key = "parking-system-secret-key"


# Initialize database
initialize_database()
create_parking_slots()
create_default_rates()
create_exit_barrier()


@app.route("/")
def dashboard():
    connection = get_db_connection()

    slots = connection.execute(
        "SELECT * FROM parking_slots ORDER BY id"
    ).fetchall()

    available_count = connection.execute(
        "SELECT COUNT(*) FROM parking_slots WHERE status = 'Available'"
    ).fetchone()[0]

    occupied_count = connection.execute(
        "SELECT COUNT(*) FROM parking_slots WHERE status = 'Occupied'"
    ).fetchone()[0]

    connection.close()

    return render_template(
        "dashboard.html",
        slots=slots,
        available_count=available_count,
        occupied_count=occupied_count
    )


@app.route("/vehicle-entry", methods=["GET", "POST"])
def vehicle_entry():

    if request.method == "POST":

        plate_number = request.form["plate_number"].strip().upper()
        vehicle_type = request.form["vehicle_type"]

        connection = get_db_connection()

        # Check whether the vehicle is already parked
        existing_vehicle = connection.execute(
            """
            SELECT parking_records.id
            FROM vehicles
            JOIN parking_records
                ON vehicles.id = parking_records.vehicle_id
            WHERE vehicles.plate_number = ?
            AND parking_records.status = 'Parked'
            """,
            (plate_number,)
        ).fetchone()

        if existing_vehicle:
            connection.close()
            flash("This vehicle is already parked.", "error")
            return redirect(url_for("vehicle_entry"))

        # Find the first available parking slot
        available_slot = connection.execute(
            """
            SELECT *
            FROM parking_slots
            WHERE status = 'Available'
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()

        if not available_slot:
            connection.close()
            flash("Sorry, all parking slots are occupied.", "error")
            return redirect(url_for("vehicle_entry"))

        # Check whether vehicle already exists
        vehicle = connection.execute(
            "SELECT * FROM vehicles WHERE plate_number = ?",
            (plate_number,)
        ).fetchone()

        if vehicle:
            vehicle_id = vehicle["id"]
        else:
            cursor = connection.execute(
                """
                INSERT INTO vehicles (plate_number, vehicle_type)
                VALUES (?, ?)
                """,
                (plate_number, vehicle_type)
            )

            vehicle_id = cursor.lastrowid

        # Record entry time
        entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create parking record
        connection.execute(
            """
            INSERT INTO parking_records
            (vehicle_id, slot_id, entry_time, status)
            VALUES (?, ?, ?, 'Parked')
            """,
            (vehicle_id, available_slot["id"], entry_time)
        )

        # Mark parking slot as occupied
        connection.execute(
            """
            UPDATE parking_slots
            SET status = 'Occupied'
            WHERE id = ?
            """,
            (available_slot["id"],)
        )

        connection.commit()
        connection.close()

        flash(
            f"Vehicle {plate_number} assigned to slot "
            f"{available_slot['slot_number']}.",
            "success"
        )

        return redirect(url_for("dashboard"))

    return render_template("vehicle_entry.html")


@app.route("/vehicle-exit", methods=["GET", "POST"])
def vehicle_exit():

    if request.method == "POST":

        plate_number = request.form["plate_number"].strip().upper()

        connection = get_db_connection()

        # First, check whether this vehicle is already
        # awaiting payment.
        parking_record = connection.execute(
            """
            SELECT
                parking_records.id,
                parking_records.entry_time,
                parking_records.exit_time,
                parking_records.fee,
                parking_records.slot_id,
                parking_records.status,
                vehicles.plate_number,
                parking_slots.slot_number
            FROM parking_records
            JOIN vehicles
                ON parking_records.vehicle_id = vehicles.id
            JOIN parking_slots
                ON parking_records.slot_id = parking_slots.id
            WHERE vehicles.plate_number = ?
            AND parking_records.status = 'Awaiting Payment'
            ORDER BY parking_records.id DESC
            LIMIT 1
            """,
            (plate_number,)
        ).fetchone()

        # If already awaiting payment, show payment page
        # without creating another exit record.
        if parking_record:

            connection.close()

            return render_template(
                "payment.html",
                parking_record_id=parking_record["id"],
                plate_number=parking_record["plate_number"],
                slot_number=parking_record["slot_number"],
                entry_time=parking_record["entry_time"],
                exit_time=parking_record["exit_time"],
                duration_minutes=0,
                fee=parking_record["fee"]
            )

        # Otherwise, find a vehicle that is still parked.
        parking_record = connection.execute(
            """
            SELECT
                parking_records.id,
                parking_records.entry_time,
                parking_records.slot_id,
                parking_records.status,
                vehicles.plate_number,
                parking_slots.slot_number
            FROM parking_records
            JOIN vehicles
                ON parking_records.vehicle_id = vehicles.id
            JOIN parking_slots
                ON parking_records.slot_id = parking_slots.id
            WHERE vehicles.plate_number = ?
            AND parking_records.status = 'Parked'
            ORDER BY parking_records.id DESC
            LIMIT 1
            """,
            (plate_number,)
        ).fetchone()

        if not parking_record:

            connection.close()

            flash(
                "No active parking or pending payment found for this vehicle.",
                "error"
            )

            return redirect(url_for("vehicle_exit"))

        # Calculate exit time and duration.
        exit_time = datetime.now()

        entry_time = datetime.strptime(
            parking_record["entry_time"],
            "%Y-%m-%d %H:%M:%S"
        )

        duration = exit_time - entry_time

        duration_minutes = int(
            duration.total_seconds() / 60
        )

        fee = calculate_fee(duration_minutes)

        # Save exit details and await payment.
        connection.execute(
            """
            UPDATE parking_records
            SET exit_time = ?,
                fee = ?,
                status = 'Awaiting Payment'
            WHERE id = ?
            """,
            (
                exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                fee,
                parking_record["id"]
            )
        )

        connection.commit()
        connection.close()

        return render_template(
            "payment.html",
            parking_record_id=parking_record["id"],
            plate_number=parking_record["plate_number"],
            slot_number=parking_record["slot_number"],
            entry_time=parking_record["entry_time"],
            exit_time=exit_time.strftime("%Y-%m-%d %H:%M:%S"),
            duration_minutes=duration_minutes,
            fee=fee
        )

    return render_template("vehicle_exit.html")

           

@app.route("/make-payment", methods=["POST"])
def make_payment():

    parking_record_id = request.form["parking_record_id"]

    payment_method = request.form["payment_method"]

    transaction_reference = request.form[
        "transaction_reference"
    ].strip()

    connection = get_db_connection()

    # Find the parking record
    parking_record = connection.execute(
        """
        SELECT *
        FROM parking_records
        WHERE id = ?
        AND status = 'Awaiting Payment'
        """,
        (parking_record_id,)
    ).fetchone()

    if not parking_record:

        connection.close()

        flash(
            "Invalid or already completed parking transaction.",
            "error"
        )

        return redirect(url_for("dashboard"))

    # For this academic project, payment is simulated
    # and immediately treated as confirmed.

    payment_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Record payment
    connection.execute(
        """
        INSERT INTO payments
        (
            parking_record_id,
            amount,
            payment_method,
            transaction_reference,
            payment_time,
            status
        )

        VALUES (?, ?, ?, ?, ?, 'Paid')
        """,
        (
            parking_record_id,
            parking_record["fee"],
            payment_method,
            transaction_reference,
            payment_time
        )
    )

    # Complete the parking record
    connection.execute(
        """
        UPDATE parking_records

        SET status = 'Completed'

        WHERE id = ?
        """,
        (parking_record_id,)
    )

    # Free the parking slot
    connection.execute(
        """
        UPDATE parking_slots

        SET status = 'Available'

        WHERE id = ?
        """,
        (parking_record["slot_id"],)
    )

    # Open exit barrier
    connection.execute(
        """
        UPDATE barriers

        SET status = 'Open',
            last_opened = ?

        WHERE id = 1
        """,
        (payment_time,)
    )

    connection.commit()

    # Get updated barrier
    barrier = connection.execute(
        """
        SELECT *
        FROM barriers
        WHERE id = 1
        """
    ).fetchone()

    connection.close()

    return render_template(
        "payment_success.html",
        amount=parking_record["fee"],
        payment_method=payment_method,
        transaction_reference=transaction_reference,
        payment_time=payment_time,
        barrier_status=barrier["status"]
    )
 
if __name__ == "__main__":
    app.run(debug=True)