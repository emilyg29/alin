import socket
import os
from PIL import Image
from constants import IP, PORT, CHUNK_SIZE
from encrypt import Encryption
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog

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
            messagebox.showerror(
                "Connection Error",
                "Could not connect to the server. Please start the server and try again."
            )
            self.client_socket = None

    def choose_authentication(self):
        credentials = {}

        window = tk.Tk()
        window.title("Image hiding system - Authentication")
        window.geometry("350x230")
        window.resizable(False, False)

        tk.Label(
            window,
            text="Image hiding system",
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
            if "|" not in response:
                messagebox.showerror(
                    "Authentication Error",
                    "The server returned an invalid authentication response."
                )
                return False

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


    def choose_main_option(self):
        """Show the main actions in a graphical window."""
        selected = {"option": None}

        window = tk.Tk()
        window.title("Image hiding system - Main Menu")
        window.geometry("420x330")
        window.configure(bg="#101820")
        window.resizable(False, False)

        def choose(option):
            selected["option"] = option
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", lambda: choose("3"))

        tk.Label(
            window,
            text="Image hiding system",
            font=("Arial", 26, "bold"),
            fg="#00d9ff",
            bg="#101820"
        ).pack(pady=(25, 5))

        tk.Label(
            window,
            text="Choose an action",
            font=("Arial", 14),
            fg="white",
            bg="#101820"
        ).pack(pady=(0, 20))

        tk.Button(
            window,
            text="Hide Data",
            width=24,
            height=2,
            command=lambda: choose("1")
        ).pack(pady=7)

        tk.Button(
            window,
            text="Decode Data",
            width=24,
            height=2,
            command=lambda: choose("2")
        ).pack(pady=7)

        tk.Button(
            window,
            text="Logout",
            width=24,
            height=2,
            command=lambda: choose("3")
        ).pack(pady=7)

        window.mainloop()
        return selected["option"]
    
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
            messagebox.showinfo(
                "Hide Data",
                "No cover images are available."
            )
            return

        print("\nAvailable media to hide data in:\n")
        print(media_menu)

        valid_media_ids = {
            line.split(":", 1)[0].strip()
            for line in media_menu.splitlines()
            if ":" in line
        }

        while True:
            selected_media_id = simpledialog.askstring(
                "Choose Cover Image",
                f"Choose the cover image that will hide the secret image:\n\n{media_menu}\n\nEnter cover image ID:"
            )

            if selected_media_id is None:
                self.encryptor.send_encrypted_message(
                    self.client_socket,
                    "CANCEL"
                )
                messagebox.showinfo(
                    "Hide Data",
                    "Operation cancelled."
                )
                return

            selected_media_id = selected_media_id.strip()

            if selected_media_id in valid_media_ids:
                break

            messagebox.showerror(
                "Invalid Selection",
                "Please choose a valid media ID from the list."
            )

        data_to_hide_path = filedialog.askopenfilename(
            title="Choose the secret JPEG image to hide inside the cover",
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
            messagebox.showinfo(
                "Hide Data",
                "Operation cancelled."
            )
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

        messagebox.showinfo(
            "Hide Data Completed",
            response
        )

    def handle_decode_option(self):
        print("\nYou chose to decode data.")
        media_path = filedialog.askopenfilename(
            title="Choose a hidden JPEG file to decode",
            initialdir=os.path.dirname(os.path.abspath(__file__)),
            filetypes=[
                ("JPEG images", "*.jpg *.jpeg")
            ]
        )

        if not media_path:
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "CANCEL"
            )
            messagebox.showinfo(
                "Decode Data",
                "No file was selected. Operation cancelled."
            )
            return

        print("File chosen for decoding:", media_path)

        if not os.path.exists(media_path):
            self.encryptor.send_encrypted_message(
                self.client_socket,
                "CANCEL"
            )
            messagebox.showerror(
                "Decode Data",
                "The selected file does not exist."
            )
            return

        with open(media_path, "rb") as file:
            data = file.read()

        # Send length encrypted
        self.encryptor.send_encrypted_message(self.client_socket, str(len(data)))
        
        # Send binary data through the encrypted connection
        self.encryptor.send_encrypted_data(self.client_socket, data)

        # Receive results
        num_images = int(self.encryptor.receive_encrypted_message(self.client_socket))
        print(f"Found {num_images} hidden images.")

        decoded_paths = []

        for i in range(num_images):
            image_size = int(self.encryptor.receive_encrypted_message(self.client_socket))
            self.encryptor.send_encrypted_message(self.client_socket, "ACK")

            image_data = self.encryptor.receive_encrypted_data(self.client_socket)

            decoded_file_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"decoded_image_{i + 1}.jpg"
            )
            with open(decoded_file_path, "wb") as file:
                file.write(image_data)

            print(f"Decoded image saved at {decoded_file_path}")
            decoded_paths.append(decoded_file_path)

        if not decoded_paths:
            messagebox.showwarning(
                "Decode Data",
                "No hidden JPEG image was found in the selected file."
            )
            return

        messagebox.showinfo(
            "Decode Completed",
            f"Successfully decoded {len(decoded_paths)} hidden image(s)."
        )

        for decoded_file_path in decoded_paths:
            try:
                Image.open(decoded_file_path).show()
            except Exception as e:
                messagebox.showerror(
                    "Decode Data",
                    f"The decoded image was saved, but could not be opened:\n{e}"
                )

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

            option = self.choose_main_option()
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
