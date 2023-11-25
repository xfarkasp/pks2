import os
import socket
import struct
import threading
import time

def createConnection(filename, host, port):
    try:
            # Create a socket for communication
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Connect to the server
                s.connect((host, port))

                # Send the file size and any other metadata in the header
                header = struct.pack('!B', 0)
                s.sendall(header)
                print("Syn sent.")

                # Bind the socket to a specific address and port
                s.bind((host, port))

                # Listen for incoming connections
                s.listen()

                print("Waiting for a connection...")

                # Accept a connection from a client
                conn, addr = s.accept()
                with conn:

                    # Receive the header containing file size
                    header = conn.recv(8)
                    type = struct.unpack('!B', header)[0]
                    if type == 1:
                        print("connection established")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)

def waitForSyn(host, port):
    try:
            # Create a socket for communication
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Connect to the server
                s.connect((host, port))

                # Bind the socket to a specific address and port
                s.bind((host, port))

                # Listen for incoming connections
                s.listen()

                print("Waiting for a connection...")

                # Accept a connection from a client
                conn, addr = s.accept()
                with conn:
                    # Receive the header containing file size
                    header = conn.recv(8)
                    type = struct.unpack('!B', header)[0]
                    if(type == 0):
                        print("SYN RECIEVED FORM: " + host)
                        # Send the file size and any other metadata in the header
                        header = struct.pack('!B', 1)
                        s.sendall(header)
                        print("ACK to SYN from: " + host +" sent.")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)


def send_file(filename, host, port):
    try:
        # Open the file in binary mode
        with open(filename, 'rb') as file:
            # Get the file size
            file_size = os.path.getsize(filename)

            # Create a socket for communication
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Connect to the server
                s.connect((host, port))

                # Send the file size and any other metadata in the header
                header = struct.pack('!Q', file_size)
                s.sendall(header)

                # Define the chunk size (adjust according to your needs)
                chunk_size = 1024

                # Read and send file data in chunks along with the header
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    s.sendall(chunk)

        print("File sent successfully.")
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)

def receive_file(filename, host, port):
    try:
        # Create a socket for communication
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Bind the socket to a specific address and port
            s.bind((host, port))

            # Listen for incoming connections
            s.listen()

            print("Waiting for a connection...")

            # Accept a connection from a client
            conn, addr = s.accept()
            with conn:
                print("Connected by", addr)

                # Receive the header containing file size
                header = conn.recv(8)
                file_size = struct.unpack('!Q', header)[0]

                # Open a new file for writing
                with open(filename, 'wb') as file:
                    # Receive and write file data in chunks
                    remaining_bytes = file_size
                    chunk_size = 1024

                    while remaining_bytes > 0:
                        print(remaining_bytes)
                        chunk = conn.recv(min(chunk_size, remaining_bytes))
                        if not chunk:
                            break
                        file.write(chunk)
                        remaining_bytes -= len(chunk)

        print("File received successfully.")

    except socket.gaierror as e:
        print(f"Error: {e}")
        print("Hostname resolution failed. Check the hostname or IP address.")

def keep_alive_thread(s, interval):
    while True:
        time.sleep(interval)
        try:
            s.sendall(b'Keep alive message')
        except AttributeError:
            print("Error: Invalid socket object")

# Example usage:
if __name__ == "__main__":
    # host = 'localhost'
    host = '192.168.1.14'
    port = 12345;

    while(1):
        print("0 = set up config")
        print("1 = start connection")
        print("2 = send text")
        print("3 = send file")
        print("4 = end connection")
        print("5 = change fragment size")

        user_input = input("Select function: ")
        print(user_input)
        if user_input == '0':
            host = input("Input reciever ip: ")
            port = int(input("Select port to operate on: "))
            folder = input("Path to save data: ")

            # Server (receiver) side
            receiver_thread = threading.Thread(target=receive_file, args=('C:\\Users\\pedro\\PycharmProjects\\pks2\\', host, port));
            receiver_thread.start();

        if user_input == '3':
            host = input("Input reciever ip: ")
            port = int(input("Select port to operate on: "))
            folder = input("Path to send data: ")

            # Server (receiver) side
            sender_thread = threading.Thread(target=send_file, args=(
            'C:\\Users\\pedro\\PycharmProjects\\pks2\\piculkovia.jpeg', host, port));
            sender_thread.start();

    # Client (sender) side with keep-alive thread
    #
    # keep_alive_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # keep_alive_socket.connect((host, port))  # Connect to the server
    # keep_alive_thread = threading.Thread(target=keep_alive_thread, args=(keep_alive_socket, 5))  # 5 seconds interval
    #sender_thread.start();
    # keep_alive_thread.start()

    # Wait for both threads to finish
    #
    # keep_alive_thread.join()

