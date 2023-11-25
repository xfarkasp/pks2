import os
import socket
import struct
import threading
import time
from queue import Queue

def create_connection(host, port):
    try:
            # Create a socket for communication
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Connect to the server
            s.connect((host, port))

            # Send the file size and any other metadata in the header
            header = struct.pack('!B', 0)
            s.sendall(header)
            print("Syn sent.")

            print("Waiting for ACK message...")

            # Receive the acknowledgment
            ack_header = s.recv(1)
            if not ack_header:
                print("Error: No data received or connection closed.")
            else:
                ack_type = struct.unpack('!B', ack_header)[0]
                print(f"Acknowledgment type: {ack_type}")

            if ack_type == 1:
                print("ACK received. Connection established.")
                connection_queue.put(s)  # Put the connection in the queue

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)

def wait_for_syn(host, port):
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
            client_ip, client_port = addr
            with conn:
                header = conn.recv(1)
                syn_type = struct.unpack('!B', header)[0]

                if syn_type == 0:
                    print(f"SYN received from {client_ip}:{client_port}")

                    # Send the acknowledgment (SYN-ACK)
                    ack_header = struct.pack('!B', 1)
                    conn.sendall(ack_header)
                    print(f"ACK to SYN from {client_ip}:{client_port} sent.")
                    # Start file transfer listner
                    receive(conn)

    except ConnectionRefusedError:
        print(f"Connection refused from the host: {host}")


def send_file(conn ,filename):
    try:
        header = struct.pack('!B', 5)
        conn.sendall(header)
        # Open the file in binary mode
        with open(filename, 'rb') as file:
            # Get the file size
            file_size = os.path.getsize(filename)

            # Create a socket for communication
            with conn:
                # Send the file size and any other metadata in the header
                header = struct.pack('!BQ', 5, file_size)
                conn.sendall(header)

                # Define the chunk size (adjust according to your needs)
                chunk_size = 1024

                # Read and send file data in chunks along with the header
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    conn.sendall(chunk)

        print("File sent successfully.")
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)

def receive(conn):
    try:
        with conn:
            file_size = 0
            while conn:
                signal_received = False
                print("Waiting for data")
                while not signal_received:
                    header_recieved = conn.recv(9)
                    if header_recieved and len(header_recieved) == 9:
                        print(len(header_recieved))
                        type = struct.unpack('!BQ', header_recieved)[0]
                        signal_received = True

                if type == 5:
                    if file_size == 0:
                        file_size = struct.unpack('!BQ', header_recieved)[1]

                    # Open a new file for writing
                    with open("file.jpeg", 'wb') as file:
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
    # Create connection que, to pass established connection from threads
    connection_queue = Queue()
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
            port = int(input("Select port to operate on: "))
            # Start listener for connection
            wait_for_syn = threading.Thread(target=wait_for_syn, args=('localhost', port))
            wait_for_syn.start()

        if user_input == '1':

            # Server (receiver) side
            host = input("Select IP to connect to: ")
            port = int(input("Select the PORT of the receiver: "))
            connection_thread = threading.Thread(target=create_connection, args=(host, port));
            connection_thread.start();

        if user_input == '3':
            # Retrieve the connection from the queue
            conn = connection_queue.get()
            print(type(conn))
            if conn:
                file = input("Path to file ")
                # Server (receiver) side
                sender_thread = threading.Thread(target=send_file, args=(conn , file));
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

