import os
import socket
import struct
import threading
import time
from queue import Queue

local_port = 666

remote_addr = 'localhost'
remote_port = 0

def create_connection(host, port):
    try:
            # Create a socket for communication
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connect to the server
            s.connect((host, port))

            peer = (host, port)

            header = create_header(0, 0, 0)

            s.sendto(header, peer)
            print("Syn sent.")

            print("Waiting for ACK message...")

            # Receive the acknowledgment
            ack_header = s.recv(22)
            if not ack_header:
                print("Error: No data received or connection closed.")
            else:
                #ack_type = struct.unpack('!B', ack_header)[0]
                ack_type = decode_header(ack_header)
                print(f"Acknowledgment type: {ack_type}")

            if ack_type[0] == 1:
                print("ACK received. Connection established.")
                connection_queue.put(s)  # Put the connection in the queue

                # Get the address and port from the socket object
                peer_address, peer_port = s.getpeername()
                global remote_addr, remote_port
                remote_addr = peer_address
                remote_port = peer_port
                print(f"remote_addr{remote_addr}:{remote_port}")

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
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind the socket to a specific address and port
        s.bind((host, port))


        print("Waiting for a connection...")
        # Listen for incoming connections
        # Receive data from the server
        header, addr = s.recvfrom(22)

        global remote_addr, remote_port
        remote_addr = addr[0]
        remote_port = addr[1]
        print(f"remote_addr{remote_addr}:{remote_port}")


        #syn_type = struct.unpack('!B', header)[0]
        syn_type = decode_header(header)
        print(syn_type[0])
        if syn_type[0] == 0:
            print(f"SYN received from {addr}")
            # Send the acknowledgment (SYN-ACK)
            #ack_header = struct.pack('!B', 1)
            ack_header = create_header(1, 0, 0)
            s.sendto(ack_header, addr)
            print(f"ACK to SYN from {addr} sent.")
            connection_queue.put(s)  # Put the connection in the queue
            # Start listener for messages
            receive_thread = threading.Thread(target=receive, args=(s,))
            receive_thread.start()

    except ConnectionRefusedError:
        print(f"Connection refused from the host: {host}")


def send_file(conn ,filename, save_path):
    try:
        peer_address, local_port = conn.getsockname()
        print(f"local port: {local_port}")
        print(f"remote port: {remote_port}")
        peer = (remote_addr, remote_port)

        header = create_header(5, 0, 0, str(os.path.getsize(filename)) + "|" + save_path + filename)
        print(f"send header: {header}")
        conn.sendto(header, peer)
        #Open the file in binary mode
        with open(filename, 'rb') as file:

            # Define the chunk size (adjust according to your needs)
            frag_size = 1400

            # Read and send file data in chunks along with the header
            while True:
                chunk = file.read(frag_size)
                if not chunk:
                    break
                conn.sendto(chunk, peer)

        print("File sent successfully and saved to: " + save_path + filename)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + remote_addr)


def receive(conn):
    try:
        file_size = 0
        peer_address, peer_port = conn.getsockname()
        peer = (peer_address, peer_port)
        while conn:
            signal_received = False

            while not signal_received:
                header_recieved = conn.recvfrom(1400)

                if header_recieved and len(header_recieved[0]) > 2:
                    header = decode_header(header_recieved[0])
                    type = header[0]
                    signal_received = True


            if type == 1:
                ack = True

            if type == 3:
                #print("TTL")
                keep_alive_ack_header = create_header(1, 0, 0)
                conn.sendto(keep_alive_ack_header, peer)

            if type == 5:
                #init_header = conn.recv(265)
                #data_header = decode_header(init_header)
                data = header[3]
                print(f"Recived data: {data}")
                # Split the string into two parts using the | character
                parser = data.split('|')

                if file_size == 0:
                    # Decode the file path from bytes using UTF-8
                    received_file_path = parser[1]
                    print("File being saved to: " + received_file_path)
                    print("Size: " + str(parser[0]))
                # Open a new file for writing
                with open(received_file_path, 'wb') as file:
                    # Receive and write file data in chunks
                    remaining_bytes = int(parser[0])
                    frag_size = 1400

                    while remaining_bytes > 0 and type != 1:
                        print(remaining_bytes)
                        chunk = conn.recv(min(frag_size, int(remaining_bytes)))
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
        # Get the address and port from the socket object
        peer_address, local_port = conn.getpeername()
        peer = (peer_address, local_port)
        print(f"Peer {peer[0]}:{peer[1]} ")
        while True:

            time.sleep(interval)

            keep_alive_header = create_header(3, 0, 0)
            conn.sendto(keep_alive_header, peer)

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


def create_header(type, seq, crc, data = None):
    header = format(type, '03b')
    header += format(seq, '03b')
    header += format(crc, '016b')

    header_to_send = int(header, 2).to_bytes(3, byteorder='big')
    if data is not None:
        data = data.encode('utf-8')
        header_to_send += data

    # print(f"encoded set: {int(header, 2).to_bytes(3, byteorder='big')}")
    return header_to_send


def decode_header(encoded_header):
    # Ensure the length of the encoded header is correct
    if len(encoded_header) < 3:
        print("header to short")
        return

    # Extracting the components from the encoded header
    bits = ''.join(format(byte, '08b') for byte in encoded_header[:3])
    type_bits = bits[:5]
    seq_bits = bits[5:8]
    crc_bits = bits[8:24]
    data_bytes = b''
    if len(encoded_header) > 3:
        data_bits = ''.join(format(byte, '08b') for byte in encoded_header[3:])
        data_bytes = bytes([int(data_bits[i:i + 8], 2) for i in range(0, len(data_bits), 8)])
        data_bytes = data_bytes.decode('utf-8')


    # Decoding each component
    decoded_type = int(type_bits, 2)
    decoded_seq = int(seq_bits, 2)
    decoded_crc = int(crc_bits, 2)

    return decoded_type, decoded_seq, decoded_crc, data_bytes


if __name__ == "__main__":

    # Create connection que, to pass established connection from threads
    connection_queue = Queue()
    gui_thread = threading.Thread(target=gui)
    gui_thread.start()
    gui_thread.join()