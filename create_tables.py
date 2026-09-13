from db_manager import DatabaseManager
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_all_tables(db_manager):
    """Create all necessary database tables."""
    db_manager.create_table(
        "users",
        "(user_id INT AUTO_INCREMENT PRIMARY KEY, username_hash CHAR(64) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL)"
    )
    db_manager.create_table(
        "clients",
        "(client_id INT PRIMARY KEY, client_ip VARCHAR(255), client_port INT, last_seen DATETIME, ddos_status BOOLEAN, total_sent_media INT DEFAULT 0, total_uploaded_files INT DEFAULT 0, hidden_data_files INT DEFAULT 0, decoded_files INT DEFAULT 0)"
    )
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
        "(user_id VARCHAR(255), media_type_id INT, path_to_decrypted_media VARCHAR(255))"
    )
    db_manager.create_table(
        "media_menu",
        "(id_media INT PRIMARY KEY, image_path VARCHAR(255), audio_path VARCHAR(255), video_path VARCHAR(255))"
    )


def populate_media_menu(db_manager):
    """Populate the media menu table with predefined data if it is empty."""
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
