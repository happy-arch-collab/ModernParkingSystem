import sqlite3

DATABASE = "parking.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():

    connection = get_db_connection()

    connection.executescript("""

        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Available'
        );


        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL UNIQUE,
            vehicle_type TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS parking_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            vehicle_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,

            entry_time TEXT NOT NULL,
            exit_time TEXT,

            fee REAL DEFAULT 0,

            status TEXT NOT NULL DEFAULT 'Parked',

            FOREIGN KEY (vehicle_id)
                REFERENCES vehicles(id),

            FOREIGN KEY (slot_id)
                REFERENCES parking_slots(id)
        );


        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            parking_record_id INTEGER NOT NULL,

            amount REAL NOT NULL,

            payment_method TEXT NOT NULL,

            transaction_reference TEXT,

            payment_time TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'Pending',

            FOREIGN KEY (parking_record_id)
                REFERENCES parking_records(id)
        );


        CREATE TABLE IF NOT EXISTS parking_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            duration_minutes INTEGER NOT NULL UNIQUE,

            amount REAL NOT NULL,

            description TEXT NOT NULL
        );
        

                CREATE TABLE IF NOT EXISTS barriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Closed',
            last_opened TEXT
        );
    """)

    connection.commit()
    connection.close()


def create_parking_slots():

    connection = get_db_connection()

    for number in range(1, 21):

        slot_number = f"A{number:02d}"

        connection.execute(
            """
            INSERT OR IGNORE INTO parking_slots
            (slot_number)
            VALUES (?)
            """,
            (slot_number,)
        )

    connection.commit()
    connection.close()


def create_default_rates():

    connection = get_db_connection()

    rates = [
        (30, 0, "Up to 30 minutes"),
        (120, 50, "Up to 2 hours"),
        (240, 100, "Up to 4 hours"),
        (360, 300, "Up to 6 hours"),
        (999999, 500, "Over 6 hours")
    ]

    for duration, amount, description in rates:

        connection.execute(
            """
            INSERT OR IGNORE INTO parking_rates
            (duration_minutes, amount, description)
            VALUES (?, ?, ?)
            """,
            (duration, amount, description)
        )

    connection.commit()
    connection.close()


def create_exit_barrier():

    connection = get_db_connection()

    connection.execute(
        """
        INSERT OR IGNORE INTO barriers
        (id, name, status)
        VALUES (1, 'Main Exit Barrier', 'Closed')
        """
    )

    connection.commit()
    connection.close()