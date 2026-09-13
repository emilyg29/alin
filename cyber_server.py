import socket
import threading
import tkinter as tk
from tkinter import Label, scrolledtext, Toplevel, Listbox, Button
from constants import IP, PORT
from db_manager import DatabaseManager
from create_tables import create_all_tables, populate_media_menu
from hide_png import DataHider
from decode_png import ImageExtractor
from datetime import datetime
from PIL import Image, ImageTk
import os
import pygame
import time
import hashlib
import secrets
from encrypt import Encryption

class Server:
    def __init__(self):
        # Initialize database connection
        self.db_manager = DatabaseManager("localhost", "root", "emilygrois29", "mysql")
        create_all_tables(self.db_manager)
        populate_media_menu(self.db_manager)
        
        # Initialize encryption
        self.encryptor = Encryption()
        
        # Initialize GUI components
        self.root = tk.Tk()
        self.root.withdraw()
        self.log_text = None
        self.client_listbox = None
        self.all_clients_listbox = None
        self.bg_image = None
        self.client_details_images = {}
        self.connected_users = {}
        self.connected_users_lock = threading.Lock()

    def play_audio(self):
        pygame.mixer.init()
        audio_dir = os.path.dirname(os.path.abspath(__file__))
        personal_audio = os.path.join(audio_dir, "emily_audio.mp3")
        pygame.mixer.music.load(personal_audio)
        pygame.mixer.music.play()
        
    def update_gui_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.yview(tk.END)

    def update_client_list(self):
        self.client_listbox.delete(0, tk.END)

        with self.connected_users_lock:
            connected_client_ids = list(self.connected_users.keys())

        for client_id in connected_client_ids:
            client_rows = self.db_manager.get_rows_with_value(
                "clients",
                "client_id",
                client_id
            )

            if not client_rows:
                continue

            client = client_rows[0]
            self.client_listbox.insert(
                tk.END,
                f"{client_id} | CONNECTED | "
                f"uploaded: {client[6]} | "
                f"hidden data: {client[7]} | "
                f"decoded: {client[8]}"
            )

    def update_all_clients_list(self):
        self.all_clients_listbox.delete(0, tk.END)

        with self.connected_users_lock:
            connected_client_ids = set(self.connected_users.keys())

        clients = self.db_manager.get_all_rows("clients")

        for client in clients:
            client_id = str(client[0])
            status = (
                "CONNECTED"
                if client_id in connected_client_ids
                else "OFFLINE"
            )

            self.all_clients_listbox.insert(
                tk.END,
                f"{client_id} | {status} | "
                f"uploaded: {client[6]} | "
                f"hidden data: {client[7]} | "
                f"decoded: {client[8]}"
            )

    def show_selected_client_details(self):
        selection = self.client_listbox.curselection()
        if selection:
            client_id = self.client_listbox.get(selection[0]).split(" | ", 1)[0]
            self.show_client_details(client_id)

    def show_client_details(self, client_id):
        client_data = self.db_manager.get_rows_with_value("clients", "client_id", client_id)
        if not client_data:
            return
        client = client_data[0]

        details_window = Toplevel()
        details_window.title(f"Client {client_id} Details")
        details_window.geometry("400x350")

        # Create and store image reference in the window itself to prevent garbage collection
        bg_image = ImageTk.PhotoImage(Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_cyber.jpeg")))
        bg_label = Label(details_window, image=bg_image)
        bg_label.image = bg_image  # Keep a reference to prevent garbage collection
        bg_label.place(relwidth=1, relheight=1)

        details = [
            f"ID: {client[0]}",
            f"IP: {client[1]}",
            f"Port: {client[2]}",
            f"Last Seen: {client[3]}",
            f"Total Uploaded Files: {client[6]}",
            f"Files With Hidden Data: {client[7]}",
            f"Status: {'Connected' if str(client_id) in self.connected_users else 'Offline'}"
        ]

        for detail in details:
            lbl = Label(details_window, text=detail, fg='white', bg='black')
            lbl.pack(anchor="w", padx=10, pady=2)

        history_button = Button(details_window, text="History", command=lambda: self.show_client_history(client_id), bg='gray', fg='white')
        history_button.pack(pady=10)

    def authenticate_client(self, client_socket):
        while True:
            action = self.encryptor.receive_encrypted_message(client_socket)
            username = self.encryptor.receive_encrypted_message(client_socket).strip()
            password = self.encryptor.receive_encrypted_message(client_socket)

            if not username or not password:
                self.encryptor.send_encrypted_message(client_socket, "ERROR|Username and password are required.")
                continue
            username_hash = hashlib.sha256(
                username.strip().lower().encode("utf-8")
            ).hexdigest()

            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT user_id, password_hash FROM users WHERE username_hash = %s", (username_hash,))
            user = cursor.fetchone()

            if action == "REGISTER":
                if user:
                    self.encryptor.send_encrypted_message(client_socket, "ERROR|Username already exists. Please choose Login.")
                    continue
                salt = secrets.token_hex(16)
                password_hash = hashlib.pbkdf2_hmac(
                    "sha256", password.encode(), salt.encode(), 120000
                ).hex()
                cursor.execute(
                    "INSERT INTO users (username_hash, password_hash) VALUES (%s, %s)",
                    (username_hash, f"{salt}${password_hash}")
                )
                self.db_manager.conn.commit()
                self.encryptor.send_encrypted_message(
                    client_socket,
                    "REGISTERED|Registration successful. Please choose Login."
                )
            elif action == "LOGIN":
                if not user:
                    self.encryptor.send_encrypted_message(client_socket, "ERROR|User does not exist. Please choose Register first.")
                    continue
                salt, saved_hash = user[1].split("$", 1)
                password_hash = hashlib.pbkdf2_hmac(
                    "sha256", password.encode(), salt.encode(), 120000
                ).hex()
                if not secrets.compare_digest(password_hash, saved_hash):
                    self.encryptor.send_encrypted_message(client_socket, "ERROR|Incorrect password.")
                    continue
                self.encryptor.send_encrypted_message(client_socket, "LOGIN_SUCCESS|Login successful.")
                return str(user[0])
            else:
                self.encryptor.send_encrypted_message(client_socket, "ERROR|Choose Register or Login.")

    def show_client_history(self, client_id):
        history_window = Toplevel()
        history_window.title(f"Client {client_id} - History")
        history_window.geometry("600x400")

        # Create and store image reference in the window itself
        bg_image = ImageTk.PhotoImage(Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_cyber.jpeg")))
        bg_label = Label(history_window, image=bg_image)
        bg_label.image = bg_image  # Keep a reference to prevent garbage collection
        bg_label.place(relwidth=1, relheight=1)

        history_label = Label(history_window, text=f"Client {client_id} Image History", font=("Arial", 12, "bold"), fg="white", bg="black")
        history_label.pack(pady=5)

        image_listbox = Listbox(history_window, height=15, width=80, bg="black", fg="white", selectbackground="gray")
        image_listbox.pack(padx=10, pady=5, expand=True, fill="both")

        images = self.db_manager.get_rows_with_value("decrypted_media", "user_id", client_id)

        if not images:
            image_listbox.insert(tk.END, "No images found for this client.")
        else:
            media_dir = os.path.dirname(os.path.abspath(__file__))
            image_paths = [os.path.join(media_dir, img[2]) for img in images]
            for path in image_paths:
                image_listbox.insert(tk.END, path)

            def open_selected_image(event):
                selected_index = image_listbox.curselection()
                if selected_index:
                    selected_path = image_paths[selected_index[0]]
                    os.system(f'"{selected_path}"')

            image_listbox.bind("<Double-Button-1>", open_selected_image)

    def handle_client(self, client_socket):
        client_id = 'unknown'
        login_id = None
        try:
            client_id = self.authenticate_client(client_socket)
            client_ip, client_port = client_socket.getpeername()

            existing_client = self.db_manager.get_rows_with_value("clients", "client_id", client_id)

            if existing_client:
                db_ip, db_port, _, _, total_actions, total_uploaded_files, hidden_data_files, decoded_files = existing_client[0][1:9]
                if db_ip == client_ip and db_port == str(client_port):
                    self.db_manager.update_row(
                        "clients", "client_id", client_id,
                        ["last_seen"],
                        [datetime.now()]
                    )
                    self.encryptor.send_encrypted_message(client_socket, "WELCOME BACK")
                    client_status = "EXISTING"
                else:
                    self.db_manager.update_row("clients", "client_id", client_id,
                               ["client_ip", "client_port", "last_seen"],
                               [client_ip, client_port, datetime.now()])
                    self.encryptor.send_encrypted_message(client_socket, "WELCOME BACK (Updated Info)")
                    client_status = "EXISTING (Updated IP/Port)"
            else:
                self.db_manager.insert_row("clients",
                           "(client_id, client_ip, client_port, last_seen, ddos_status, total_sent_media, total_uploaded_files, hidden_data_files)",
                           "(%s, %s, %s, %s, %s, %s, %s, %s)",
                           (client_id, client_ip, client_port, datetime.now(), False, 0, 0, 0))
                self.encryptor.send_encrypted_message(client_socket, "WELCOME TO MASKER SERVER!")
                client_status = "NEW"
                total_actions = 0
                total_uploaded_files = 0
                hidden_data_files = 0
                decoded_files = 0
            login_id = self.db_manager.start_login_session(client_id)

            with self.connected_users_lock:
                self.connected_users[client_id] = {
                    "socket": client_socket,
                    "ip": client_ip,
                    "port": client_port,
                    "login_id": login_id
                }
            self.update_gui_log(f"Client {client_id} connected - Status: {client_status}")
            self.update_client_list()
            self.update_all_clients_list()

            while True:
                self.encryptor.send_encrypted_message(client_socket, "\n1: Hide Data\n2: Decode Data\n3: Logout")
                option = self.encryptor.receive_encrypted_message(client_socket)

                if option == "1":
                    hider = DataHider(client_socket, self.db_manager, client_id)
                    result = hider.run()
                    if result:
                        media_id, media_type_id, path = result
                        total_actions += 1
                        total_uploaded_files += 1
                        hidden_data_files += 1
                        self.db_manager.update_row("clients", "client_id", client_id,
                                                   ["total_sent_media", "total_uploaded_files", "hidden_data_files"],
                                                   [total_actions, total_uploaded_files, hidden_data_files])
                        self.update_client_list()
                        self.update_all_clients_list()
                elif option == "2":
                    extractor = ImageExtractor(client_socket, self.db_manager, client_id)
                    media_id, media_type, path = extractor.run()

                    total_actions += 1
                    total_uploaded_files += 1

                    decoded_count = len(extractor.found_images)
                    if decoded_count > 0:
                        hidden_data_files += 1
                        decoded_files += decoded_count

                    self.db_manager.update_row(
                        "clients",
                        "client_id",
                        client_id,
                        [
                            "total_sent_media",
                            "total_uploaded_files",
                            "hidden_data_files",
                            "decoded_files"
                        ],
                        [
                            total_actions,
                            total_uploaded_files,
                            hidden_data_files,
                            decoded_files
                        ]
                    )
                    self.update_client_list()
                    self.update_all_clients_list()
                elif option == "3":
                    self.update_gui_log(f"Client {client_id} disconnected.")
                    break
                else:
                    self.encryptor.send_encrypted_message(client_socket, "Invalid option.")
        except Exception as e:
            self.update_gui_log(f"Error handling client {client_id}: {e}")
        finally:
            if client_id != 'unknown':
                with self.connected_users_lock:
                    current_user = self.connected_users.get(client_id)
                    if current_user and current_user["socket"] is client_socket:
                        del self.connected_users[client_id]

            if login_id is not None:
                self.db_manager.end_login_session(login_id)

            client_socket.close()
            self.update_client_list()
            self.update_all_clients_list()

    def start_server(self):
        server_socket = socket.socket()
        server_socket.bind((IP, PORT))
        server_socket.listen()
        self.update_gui_log("Server started...")
        while True:
            client_socket, _ = server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()

    def create_gui(self):
        self.play_audio()
        
        # Create splash screen
        splash = Toplevel()
        splash.geometry("500x350")
        splash.configure(bg="#101820")
        splash.overrideredirect(True)

        Label(
            splash,
            text="MASKER",
            font=("Arial", 30, "bold"),
            fg="#00d9ff",
            bg="#101820"
        ).pack(pady=(45, 10))

        Label(
            splash,
            text="Secure Media Hiding System",
            font=("Arial", 15),
            fg="white",
            bg="#101820"
        ).pack(pady=5)

        Label(
            splash,
            text="Submitted by: Emily Groisman",
            font=("Arial", 11),
            fg="#b8c7d9",
            bg="#101820"
        ).pack(pady=20)

        Label(
            splash,
            text="Version 1.0",
            font=("Arial", 10),
            fg="#00d9ff",
            bg="#101820"
        ).pack(pady=5)

        splash.update()
        time.sleep(4)
        splash.destroy()

        # Destroy the initial withdrawn root and create a new one
        self.root.destroy()
        self.root = tk.Tk()
        self.root.title("Server GUI")
        self.root.geometry("500x500")

        # Load and keep reference to background image
        self.bg_image = ImageTk.PhotoImage(Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mizperamon1.png")))
        bg_label = Label(self.root, image=self.bg_image)
        bg_label.place(relwidth=1, relheight=1)

        # Create scrolled text for logs
        self.log_text = scrolledtext.ScrolledText(self.root, state=tk.DISABLED, wrap=tk.WORD, height=10, bg='black', fg='white')
        self.log_text.pack(expand=True, fill='both', padx=10, pady=5)

        # Create clients label
        # Clients connected right now
        Label(
            self.root,
            text="Connected Clients",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="black"
        ).pack(pady=5)

        self.client_listbox = Listbox(
            self.root,
            height=6,
            bg="black",
            fg="white"
        )
        self.client_listbox.pack(
            expand=True,
            fill="both",
            padx=10,
            pady=5
        )
        self.client_listbox.bind(
            "<Double-Button-1>",
            lambda event: self.show_selected_client_details()
        )

        # Every client saved in MySQL
        Label(
            self.root,
            text="All Clients",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="black"
        ).pack(pady=5)

        self.all_clients_listbox = Listbox(
            self.root,
            height=6,
            bg="black",
            fg="white"
        )
        self.all_clients_listbox.pack(
            expand=True,
            fill="both",
            padx=10,
            pady=5
        )
        self.update_client_list()
        self.update_all_clients_list()

        # Start server in a separate thread
        threading.Thread(target=self.start_server, daemon=True).start()
        self.root.mainloop()

if __name__ == "__main__":
    server = Server()
    server.create_gui()
