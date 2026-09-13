import socket
import os
from PIL import Image
from constants import IP, PORT, CHUNK_SIZE
from encrypt import Encryption
import tkinter as tk
from tkinter import messagebox, filedialog

class Client:
    def __init__(self):
        media_dir = os.path.dirname(os.path.abspath(__file__))
        self.decrypted_list_paths = sorted(
            os.path.join(media_dir, filename)
            for filename in os.listdir(media_dir)
            if filename.startswith("hidden_") and filename.lower().endswith(".jpg")
        )
        self.usual_images = [
            os.path.join(media_dir, "poke.jpg"),
            os.path.join(media_dir, "logo_cyber.jpeg"),
            os.path.join(media_dir, "mizperamon1.png")
        ]
        self.client_socket = None
        self.encryptor = Encryption()

    def connect_to_server(self):
        try:
            self.client_socket = socket.socket()
            self.client_socket.connect((IP, PORT))
            print("Connected to server")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            self.client_socket = None

    def choose_authentication(self):
        credentials = {}

        window = tk.Tk()
        window.title("MASKER Authentication")
        window.geometry("350x230")
        window.resizable(False, False)

        tk.Label(
            window,
            text="MASKER",
            font=("Arial", 20, "bold")
        ).pack(pady=10)

        tk.Label(window, text="Username").pack()
        username_entry = tk.Entry(window, width=30)
        username_entry.pack(pady=5)

        tk.Label(window, text="Password").pack()
        password_entry = tk.Entry(window, width=30, show="*")
        password_entry.pack(pady=5)
        show_password = tk.BooleanVar(value=False)
        
        def toggle_password():
            if show_password.get():
                password_entry.config(show="")
            else:
                password_entry.config(show="*")

        tk.Checkbutton(
            window,
            text="Show password",
            variable=show_password,
            command=toggle_password
        ).pack()

        def submit(action):
            username = username_entry.get().strip()
            password = password_entry.get()

            if not username or not password:
                messagebox.showerror(
                    "Authentication Error",
                    "Username and password are required.",
                    parent=window
                )
                return

            credentials["action"] = action
            credentials["username"] = username
            credentials["password"] = password
            window.destroy()

        buttons_frame = tk.Frame(window)
        buttons_frame.pack(pady=15)

        tk.Button(
            buttons_frame,
            text="Register",
            width=12,
            command=lambda: submit("REGISTER")
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            buttons_frame,
            text="Login",
            width=12,
            command=lambda: submit("LOGIN")
        ).pack(side=tk.LEFT, padx=5)

        username_entry.focus()
        window.mainloop()

        return credentials
    
    def authenticate(self):
        while True:
            credentials = self.choose_authentication()
            if not credentials:
                return False
            self.encryptor.send_encrypted_message(self.client_socket, credentials["action"])
            self.encryptor.send_encrypted_message(self.client_socket, credentials["username"])
            self.encryptor.send_encrypted_message(self.client_socket, credentials["password"])
            response = self.encryptor.receive_encrypted_message(
                self.client_socket
            )
            status, message = response.split("|", 1)

            if status == "LOGIN_SUCCESS":
                messagebox.showinfo(
                    "Login",
                    message
                )
                return True

            if status == "REGISTERED":
                messagebox.showinfo(
                    "Register",
                    message
                )
            else:
                messagebox.showerror(
                    "Authentication Error",
                    message
                )


    def receive_menu(self):
        try:
            menu = self.encryptor.receive_encrypted_message(self.client_socket)
            print("\nOptions from server:\n")
            print(menu)
            return menu
        except Exception as e:
            print(f"Error receiving menu: {e}")
            return None

    def handle_hide_option(self):
        print("\nYou chose to hide data.")

        media_menu = self.encryptor.receive_encrypted_message(
            self.client_socket
        )

        if "No media options available." in media_menu:
            print("No media options available. Returning to menu.")
            return

        print("\nAvailable media to hide data in:\n")
        print(media_menu)

        valid_media_ids = {
            line.split(":", 1)[0].strip()
            for line in media_menu.splitlines()
            if ":" in line
        }

        while True:
            selected_media_id = input(
                "Choose media ID: "
            ).strip()

            if selected_media_id in valid_media_ids:
                break

            print("Invalid media ID. Choose an option from the menu.")

        data_to_hide_path = filedialog.askopenfilename(
            title="Choose a JPEG image to hide",
            initialdir=os.path.dirname(os.path.abspath(__file__)),
            filetypes=[
                ("JPEG images", "*.jpg *.jpeg")
            ]
        )

        if (
            not data_to_hide_path
            or not os.path.exists(data_to_hide_path)
        ):
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "CANCEL"
            )
            print("Hide operation cancelled. Returning to menu.")
            return

        print("Data to hide:", data_to_hide_path)

        self.encryptor.send_encrypted_message(
            self.client_socket,
            selected_media_id
        )

        with open(data_to_hide_path, "rb") as file:
            data_to_hide = file.read()

        self.encryptor.send_encrypted_message(
            self.client_socket,
            str(len(data_to_hide))
        )

        self.encryptor.send_encrypted_data(
            self.client_socket,
            data_to_hide
        )

        response = self.encryptor.receive_encrypted_message(
            self.client_socket
        )
        print(response)

        hidden_media_path = response.split("in ")[-1].strip()

        if os.path.exists(hidden_media_path):
            try:
                img = Image.open(hidden_media_path)
                img.show()
            except Exception as e:
                print(f"Error opening the hidden media: {e}")

    def handle_decode_option(self):
        print("\nYou chose to decode data.")
        media_path = filedialog.askopenfilename(
            title="Choose a file to decode",
            initialdir=os.path.dirname(os.path.abspath(__file__)),
            filetypes=[
                ("JPEG images", "*.jpg *.jpeg")
            ]
        )

        if not media_path:
            print("No file was selected. Returning to menu.")
            return

        print("File chosen for decoding:", media_path)

        if not os.path.exists(media_path):
            print("File does not exist. Returning to menu.")
            return

        with open(media_path, "rb") as file:
            data = file.read()

        # Send length encrypted
        self.encryptor.send_encrypted_message(self.client_socket, str(len(data)))

        # Send raw binary data (unencrypted)
        self.encryptor.send_encrypted_message(self.client_socket, data)

        # Receive results
        num_images = int(self.encryptor.receive_encrypted_message(self.client_socket))
        print(f"Found {num_images} hidden images.")

        for i in range(num_images):
            image_size = int(self.encryptor.receive_encrypted_message(self.client_socket))
            self.encryptor.send_encrypted_message(self.client_socket, "ACK")

            image_data = self.encryptor.receive_encrypted_data(self.client_socket)

            decoded_file_path = f"decoded_image_{i + 1}.jpg"
            with open(decoded_file_path, "wb") as file:
                file.write(image_data)

            print(f"Decoded image saved at {decoded_file_path}")
            if os.path.exists(decoded_file_path):
                try:
                    img = Image.open(decoded_file_path)
                    img.show()
                except Exception as e:
                    print(f"Error opening the decoded image: {e}")

    def run(self):
        self.connect_to_server()
        if not self.client_socket:
            return

        if not self.authenticate():
            self.client_socket.close()
            return
        welcome_message = self.encryptor.receive_encrypted_message(
            self.client_socket
        )
        print(welcome_message)

        while True:
            menu = self.receive_menu()
            if not menu:
                break

            option = input(
                "Choose option (1 = Hide, 2 = Decode, 3 = Logout): "
            ).strip()
            self.encryptor.send_encrypted_message(self.client_socket, option)

            if option == "1":
                self.handle_hide_option()
            elif option == "2":
                self.handle_decode_option()
            elif option == "3":
                print("Logging out...")
                break
            else:
                print("Invalid option chosen.")

        self.client_socket.close()

if __name__ == "__main__":
    client = Client()
    client.run()