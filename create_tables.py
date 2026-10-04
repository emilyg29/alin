from db_manager import DatabaseManager


def migrate_clients_table(db_manager):
    """
    Updates an older database:
    moves login information from users into clients,
    then removes the unnecessary users table.
    """
    cursor = db_manager.conn.cursor()

    cursor.execute("SHOW COLUMNS FROM clients")
    existing_columns = {row[0] for row in cursor.fetchall()}

    if "username_hash" not in existing_columns:
        cursor.execute(
            "ALTER TABLE clients "
            "ADD COLUMN username_hash CHAR(64) UNIQUE"
        )

    if "password_hash" not in existing_columns:
        cursor.execute(
            "ALTER TABLE clients "
            "ADD COLUMN password_hash VARCHAR(255)"
        )

    cursor.execute("SHOW TABLES LIKE 'users'")
    users_table_exists = cursor.fetchone() is not None

    if users_table_exists:
        cursor.execute(
            """
            INSERT INTO clients (
                client_id,
                username_hash,
                password_hash
            )
            SELECT
                user_id,
                username_hash,
                password_hash
            FROM users
            ON DUPLICATE KEY UPDATE
                username_hash = VALUES(username_hash),
                password_hash = VALUES(password_hash)
            """
        )

        cursor.execute("DROP TABLE users")

    try:
        cursor.execute(
            "ALTER TABLE clients "
            "MODIFY client_id INT AUTO_INCREMENT"
        )
    except Exception:
        pass

    db_manager.conn.commit()
    cursor.close()


def create_all_tables(db_manager):
    """Create all necessary database tables."""

    db_manager.create_table(
        "clients",
        """(
            client_id INT AUTO_INCREMENT PRIMARY KEY,
            client_ip VARCHAR(255),
            client_port INT,
            last_seen DATETIME,
            ddos_status BOOLEAN DEFAULT FALSE,
            total_sent_media INT DEFAULT 0,
            total_uploaded_files INT DEFAULT 0,
            hidden_data_files INT DEFAULT 0,
            decoded_files INT DEFAULT 0,
            username_hash CHAR(64) UNIQUE,
            password_hash VARCHAR(255)
        )"""
    )

    migrate_clients_table(db_manager)

    db_manager.create_table(
        "login_history",
        """(
            login_id INT AUTO_INCREMENT PRIMARY KEY,
            client_id INT NOT NULL,
            login_time DATETIME NOT NULL,
            logout_time DATETIME,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )"""
    )

    db_manager.create_table(
        "decrypted_media",
        """(
            user_id VARCHAR(255),
            media_type_id INT,
            path_to_decrypted_media VARCHAR(255)
        )"""
    )

    db_manager.create_table(
        "media_menu",
        """(
            id_media INT PRIMARY KEY,
            image_path VARCHAR(255),
            audio_path VARCHAR(255),
            video_path VARCHAR(255)
        )"""
    )


def populate_media_menu(db_manager):
    """Populate the media menu table only when it is empty."""

    predefined_media = [
        (1, "poke.jpg", None, None),
        (2, "logo_cyber.jpeg", None, None)
    ]

    existing_rows = db_manager.get_all_rows("media_menu")

    if not existing_rows:
        for media in predefined_media:
            db_manager.insert_row(
                "media_menu",
                "(id_media, image_path, audio_path, video_path)",
                "(%s, %s, %s, %s)",
                media
            )