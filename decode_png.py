import os
from datetime import datetime
from encrypt import Encryption
from constants import HIDDEN_MARKER

class ImageExtractor:
    """
    A class responsible for receiving a media file from the client,
    extracting hidden JPEG images from it, saving them, and sending them back.
    """

    def __init__(self, client_socket, db_manager, user_id):
        """
        Initializes the extractor with the client's socket, DB manager, and user ID.
        
        """
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id
        self.jpeg_start = b'\xFF\xD8'
        self.jpeg_end = b'\xFF\xD9'
        self.found_images = []
        self.encryptor = Encryption()

    def receive_media(self):
        """
        Receives the media file size (encrypted) and raw binary media data from the client.

        :return: binary data of the received media file
        """
        size_message = self.encryptor.receive_encrypted_message(self.client_socket)
        if size_message == "CANCEL":
            return None

        media_size = int(size_message)
        media_data = b''

        while len(media_data) < media_size:
            media_data += self.encryptor.receive_encrypted_data(self.client_socket)

        return media_data

    def save_temp_file(self, data):
        """
        Saves the received media data to a temporary file.

        :param data: binary media data
        :return: path to the temporary file
        """
        temp_path = f"temp_{self.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        with open(temp_path, "wb") as temp_file:
            temp_file.write(data)
        return temp_path

    def extract_images(self, media_data):
            """
            Extracts the single JPEG file stored after HIDDEN_MARKER.
            """
            marker_index = media_data.find(HIDDEN_MARKER)

            if marker_index == -1:
                return

            payload_start = marker_index + len(HIDDEN_MARKER)
            hidden_image_data = media_data[payload_start:]

            if not hidden_image_data.startswith(self.jpeg_start):
                return

            end_index = hidden_image_data.rfind(self.jpeg_end)

            if end_index == -1:
                return

            hidden_image_data = hidden_image_data[:end_index + 2]

            media_dir = os.path.dirname(os.path.abspath(__file__))
            output_filename = (
                f"hidden_{self.user_id}_1_"
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            )
            output_file = os.path.join(media_dir, output_filename)

            with open(output_file, "wb") as hidden_file:
                hidden_file.write(hidden_image_data)

            self.found_images.append(output_file)

            self.db_manager.insert_decrypted_media(
                self.user_id,
                1,
                output_filename
            )
    def send_results(self):
        """
        Sends the number of found images to the client,
        then sends each image size (encrypted), waits for "ACK", and sends the image file.
        """
        self.encryptor.send_encrypted_message(self.client_socket, f"{len(self.found_images)}")

        for image_path in self.found_images:
            with open(image_path, "rb") as file:
                data = file.read()
                self.encryptor.send_encrypted_message(self.client_socket, f"{len(data)}")
                ack = self.encryptor.receive_encrypted_message(self.client_socket)
                if ack != "ACK":
                    break
                self.encryptor.send_encrypted_data(self.client_socket, data)

    def run(self):
        """
        Executes the full flow: receive, extract, send back hidden images.

        :return: (media_type_id, media_type, first_output_path) tuple
        """
        media_data = self.receive_media()
        if media_data is None:
            return None

        temp_path = self.save_temp_file(media_data)
        self.extract_images(media_data)
        self.send_results()
        os.remove(temp_path)

        if self.found_images:
            return 1, "image", self.found_images[0]
        else:
            return 1, "image", ""
