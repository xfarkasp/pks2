import os
import socket
import struct
import threading
import time
from queue import Queue

# Create a lock
message_lock = threading.Lock()
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
                # Start listener for messages
                keep_alive_thread = threading.Thread(target=keep_alive_sender, args=(s, 5))
                keep_alive_thread.start()
                receive_thread = threading.Thread(target=receive, args=(s,))
                receive_thread.start()


    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)

def wait_for_syn(host, port):
    try:
        # Create a socket for communication
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Bind the socket to a specific address and port
        s.bind((host, port))

        # Listen for incoming connections
        s.listen()

        print("Waiting for a connection...")

        # Accept a connection from a client
        conn, addr = s.accept()
        client_ip, client_port = addr

        header = conn.recv(1)
        syn_type = struct.unpack('!B', header)[0]

        if syn_type == 0:
            print(f"SYN received from {client_ip}:{client_port}")

            # Send the acknowledgment (SYN-ACK)
            ack_header = struct.pack('!B', 1)
            conn.sendall(ack_header)
            print(f"ACK to SYN from {client_ip}:{client_port} sent.")
            connection_queue.put(conn)  # Put the connection in the queue
            # Start listener for messages
            receive_thread = threading.Thread(target=receive, args=(conn,))
            receive_thread.start()

    except ConnectionRefusedError:
        print(f"Connection refused from the host: {host}")


def send_file(conn ,filename, save_path):
    try:
        header = struct.pack('!B', 5)
        conn.sendall(header)
        # Open the file in binary mode
        with open(filename, 'rb') as file:
            header = struct.pack('!BQ', 5, 0)
            conn.sendall(header)

            # Get the file size
            file_size = os.path.getsize(filename)
            # Encode the file path into bytes using UTF-8
            file_path_bytes = os.path.join(save_path, filename).encode('utf-8')
            # Send the file size and any other metadata in the header
            header = struct.pack(f'!B{256}sQ', 5, file_path_bytes, file_size)
            conn.sendall(header)

            # Define the chunk size (adjust according to your needs)
            chunk_size = 1400

            # Read and send file data in chunks along with the header
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                conn.sendall(chunk)

        print("File sent successfully and saved to: " + save_path + filename)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + host)


def receive(conn):
    try:

        file_size = 0
        while conn:
            signal_received = False
            #print("Waiting for data")
            #message_lock.acquire()


            while not signal_received:
                header_recieved = conn.recv(9)
                if header_recieved and len(header_recieved) == 9:
                    #print(len(header_recieved))
                    type = struct.unpack('!BQ', header_recieved)[0]
                    #print(type)
                    signal_received = True


            if type == 1:
                ack = True

            if type == 3:
                #print("TTL")
                keep_alive_ack_header = struct.pack('!BQ', 1, 0)
                conn.sendall(keep_alive_ack_header)

            if type == 5:
                init_header = conn.recv(265)
                type, received_file_path_bytes, received_file_size = struct.unpack(
                    f'!B{256}sQ', init_header)

                if file_size == 0:
                    # Decode the file path from bytes using UTF-8
                    received_file_path = received_file_path_bytes.decode('utf-8').rstrip('\x00')
                    print("File being saved to: " + received_file_path)
                    print("Size: " + str(received_file_size))
                # Open a new file for writing
                with open(received_file_path, 'wb') as file:
                    # Receive and write file data in chunks
                    remaining_bytes = received_file_size
                    chunk_size = 1400

                    while remaining_bytes > 0:
                        print(remaining_bytes)
                        chunk = conn.recv(min(chunk_size, remaining_bytes))
                        if not chunk:
                            continue
                        file.write(chunk)
                        remaining_bytes -= len(chunk)

                print("File received successfully to " +  received_file_path)

            #message_lock.release()
    except socket.gaierror as e:
        print(f"Error: {e}")
        print("Hostname resolution failed. Check the hostname or IP address.")


def keep_alive_sender(conn, interval):
    try:
        while True:
            time.sleep(interval)
            #print("Sending keep alive")
            keep_alive_header = struct.pack('!BQ', 3, 0)
            conn.sendall(keep_alive_header)

    except AttributeError:
        print("Error: Invalid socket object")


def gui():

    host = '192.168.1.14'
    port = 12345;
    conn = None

    while (1):
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
            wait_for_syn_thread = threading.Thread(target=wait_for_syn, args=('localhost', port))
            wait_for_syn_thread.start()
            wait_for_syn_thread.join()  # Wait for the thread to finish
            conn = connection_queue.get()

        elif user_input == '1':
            # Server (receiver) side
            host = input("Select IP to connect to: ")
            port = int(input("Select the PORT of the receiver: "))
            create_connection(host, port)
            conn = connection_queue.get()

        elif user_input == '3':
            # Retrieve the connection from the queue
            print(type(conn))
            if conn:
                file = input("Path to file: ")
                save_path = input("enter path to save on remote: ")
                # Server (receiver) side
                send_file(conn, file, save_path)

        else:
            continue

if __name__ == "__main__":
    # Create connection que, to pass established connection from threads
    connection_queue = Queue()
    gui_thread = threading.Thread(target=gui)
    gui_thread.start()
    gui_thread.join()