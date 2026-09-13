import base64
import os
import secrets
from Crypto.Cipher import AES
from constants import CHUNK_SIZE

class Encryption:
    """Encrypt socket messages and binary payloads with AES-GCM."""

    def __init__(self):
        key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "personal.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as key_file:
                self.AES_KEY = key_file.read()
        else:
            self.AES_KEY = secrets.token_bytes(32)
            with open(key_path, "wb") as key_file:
                key_file.write(self.AES_KEY)

        if len(self.AES_KEY) not in (16, 24, 32):
            raise ValueError("personal.key must contain a valid AES key")

    def encrypt_data(self, data: bytes) -> str:
        """
        Encrypts binary data using AES-GCM
        
        Documentation:
        This function receives binary data and encrypts it using AES-GCM.
        It appends the authentication tag to the ciphertext and returns a base64 encoded string.
        
        Args:
            data (bytes): The binary data to encrypt
            
        Returns:
            str: Base64 encoded encrypted data with authentication tag
        """
        nonce = secrets.token_bytes(12)
        cipher = AES.new(self.AES_KEY, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return base64.b64encode(nonce + ciphertext + tag).decode()

    def decrypt_data(self, data: str) -> bytes:
        """
        Decrypts a base64 encoded string of encrypted data
        
        Documentation:
        This function receives a base64 encoded string, decodes it, and decrypts using AES-GCM.
        It separates the ciphertext from the authentication tag and verifies the integrity.
        
        Args:
            data (str): Base64 encoded encrypted data with authentication tag
            
        Returns:
            bytes: Decrypted binary data
            
        Raises:
            ValueError: If the authentication tag verification fails
        """
        raw_data = base64.b64decode(data)
        nonce = raw_data[:12]
        ciphertext, tag = raw_data[12:-16], raw_data[-16:]
        cipher = AES.new(self.AES_KEY, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    @staticmethod
    def _receive_exact(sock, size):
        data = b""
        while len(data) < size:
            chunk = sock.recv(min(CHUNK_SIZE, size - len(data)))
            if not chunk:
                raise ConnectionError("Socket closed before receiving the full payload")
            data += chunk
        return data

    def _receive_frame(self, sock):
        raw_length = sock.recv(4)
        if not raw_length:
            return b""
        while len(raw_length) < 4:
            raw_length += self._receive_exact(sock, 4 - len(raw_length))
        message_length = int.from_bytes(raw_length, byteorder="big")
        return self._receive_exact(sock, message_length)

    def send_encrypted_data(self, sock, data):
        """Encrypt and send arbitrary binary data with a length prefix."""
        encrypted_bytes = self.encrypt_data(data).encode()
        sock.sendall(len(encrypted_bytes).to_bytes(4, byteorder="big"))
        sock.sendall(encrypted_bytes)

    def receive_encrypted_data(self, sock):
        """Receive and decrypt arbitrary binary data with a length prefix."""
        encrypted_bytes = self._receive_frame(sock)
        if not encrypted_bytes:
            return b""
        return self.decrypt_data(encrypted_bytes.decode())

    def send_encrypted_message(self, sock, message):
        """
        Encrypts and sends a message through a socket
        
        Documentation:
        This function encrypts the given message and sends it through the provided socket.
        It first sends the length of the encrypted message as 4 bytes, then the encrypted message.
        
        Args:
            sock: Socket object to send data through
            message (str/bytes): Message to encrypt and send
        """
        if isinstance(message, str):
            message = message.encode()
        self.send_encrypted_data(sock, message)

    def receive_encrypted_message(self, sock) -> str:
        """
        Receives and decrypts a message from a socket
        
        Documentation:
        This function receives an encrypted message from the provided socket,
        decrypts it, and returns the original message as a string.
        It first reads 4 bytes to determine the message length, then reads the encrypted message.
        
        Args:
            sock: Socket object to receive data from
            
        Returns:
            str: Decrypted message
            
        Returns empty string if no data is received
        """
        return self.receive_encrypted_data(sock).decode()

# Example usage:
# encryptor = Encryption()
# encryptor.send_encrypted_message(socket_object, "Hello, world!")
# received_message = encryptor.receive_encrypted_message(socket_object)