import os
import socket
import threading
import time
import random
from queue import Queue
from colorama import Fore, init
init()

local_port = 666

remote_addr = 'localhost'
remote_port = 0


frag_size = 1469


data_ack = threading.Event()
fyn = threading.Event()
keep_alive_event = threading.Event()


error_detected = False
was_listening = False
data_transfer = False
data_ack_time_out = False


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
            # ack_type = struct.unpack('!B', ack_header)[0]
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


def terminate_connection(conn):
    try:
        if conn:
            peer = (remote_addr, remote_port)

            fyn_header = create_header(7, 3, 0)
            conn.sendto(fyn_header, peer)

            print("Fyn message sent, Waiting for ACK message...")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + remote_addr)


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

        # syn_type = struct.unpack('!B', header)[0]
        syn_type = decode_header(header)
        print(syn_type[0])
        if syn_type[0] == 0:
            print(f"SYN received from {addr}")
            # Send the acknowledgment (SYN-ACK)
            # ack_header = struct.pack('!B', 1)
            ack_header = create_header(1, 0, 0)
            s.sendto(ack_header, addr)
            print(f"ACK to SYN from {addr} sent.")
            connection_queue.put(s)  # Put the connection in the queue
            # Start listener for messages
            receive_thread = threading.Thread(target=receive, args=(s,))
            receive_thread.start()

    except ConnectionRefusedError:
        print(f"Connection refused from the host: {host}")


def data_ack_timer():
    global data_ack_time_out, data_ack
    start_time = time.time()
    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time

        if data_ack.wait(timeout=max(0, 2 - elapsed_time)):
            # Keep-alive event is set
            start_time = time.time()

        else:
            print("data ack timeout")
            data_ack_time_out = True
            data_ack.set()


def send_text(conn, message):
    peer_address, local_port = conn.getsockname()
    print(f"local port: {local_port}")
    print(f"remote port: {remote_port}")
    peer = (remote_addr, remote_port)

    header = create_header(6, 0, 0, str(frag_size) + "|" + str(len(message)))

    print(f"send header: {header}")
    conn.sendto(header, peer)
    tmp_message = message
    global error_detected, data_ack

    time_out_thread = threading.Thread(target = data_ack_timer)
    time_out_thread.start()

    while tmp_message:
        string_buffer = tmp_message[:frag_size]
        # Update the source string by removing the characters that were read
        tmp_message = tmp_message[frag_size:]
        message_header = create_header(6, 0, 0, string_buffer)
        try:
            conn.sendto(message_header, peer)
        except OSError:
            print("connection was closed during transfer")
            return
        print("chunk sent, waiting for ack/nack")
        data_ack.wait()
        if error_detected is not True:
            print(Fore.GREEN + "continue sending" + Fore.RESET)
        else:
            print(Fore.YELLOW +"ERROR DETECTED, resending last fragment" + Fore.RESET)
            conn.sendto(message_header, peer)
            error_detected = False

    time_out_thread.join()

def send_file(conn, filename):
    try:
        peer_address, local_port = conn.getsockname()
        print(f"local port: {local_port}")
        print(f"remote port: {remote_port}")
        peer = (remote_addr, remote_port)

        header = create_header(5, 0, 0, str(frag_size) + "|" + str(os.path.getsize(filename)) + "|" + filename)
        print(f"send header: {header}")
        conn.sendto(header, peer)
        global error_detected, data_ack, data_ack_time_out

        time_out_thread = threading.Thread(target=data_ack_timer)
        time_out_thread.start()
        # Open the file in binary mode
        with open(filename, 'rb') as file:

            # Read and send file data in chunks along with the header
            while True:
                chunk = file.read(frag_size)
                if not chunk:
                    break
                data_header = create_header(5, 0, 0, chunk)
                try:
                    conn.sendto(data_header, peer)
                except OSError:
                    print("connection was closed during transfer")
                    return
                print("chunk sent, waiting for ack/nack")
                data_ack.wait()
                if error_detected is not True:
                    print("continue sending")
                elif data_ack_time_out is True:
                    print(Fore.YELLOW + "DATA ACK TIMEOUT, resending last fragment" + Fore.RESET)
                    conn.sendto(data_header, peer)
                else:
                    print(Fore.YELLOW + "ERROR DETECTED, resending last fragment" + Fore.RESET)
                    conn.sendto(data_header, peer)
                    error_detected = False

                data_ack.clear()

        print(f"File {filename} sent successfully: ")

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")

    except ConnectionRefusedError:
        print(f"Connection refused from the host: " + remote_addr)


def receive(conn):
    try:
        keep_alive_lis_thread = threading.Thread(target=keep_alive_handler)
        keep_alive_lis_thread.start()

        file_size = 0
        peer_address, peer_port = conn.getsockname()
        peer = (peer_address, peer_port)
        peer_sender = (remote_addr, remote_port)
        global error_detected, data_ack, keep_alive_event
        start_time = time.time()
        while conn:

            signal_received = False

            while not signal_received:
                try:
                    header_recieved = conn.recvfrom(1500)
                except OSError:
                    print("Connection was terminated")
                    return

                if header_recieved and len(header_recieved[0]) > 2:
                    header = decode_header(header_recieved[0])
                    type = header[0]
                    signal_received = True

            if type == 1:
                keep_alive_event.set()
                ack = True
                if header[1] == 3:
                    print("Fyn ACK received, terminating")
                    universal_termination()
                    return

            if type == 2:
                print(f"NACK recived")
                error_detected = True
                data_ack.set()

            if type == 3:
                keep_alive_event.set()
                start_time = time.time()
                keep_alive_ack_header = create_header(1, 0, 0)
                conn.sendto(keep_alive_ack_header, (remote_addr, remote_port))

            if type == 4:
                keep_alive_event.set()
                print("ack to data recv")
                data_ack.set()

            if type == 5:
                data = header[3].decode('utf-8')

                # Split the string into two parts using the | character
                parser = data.split('|')
                frag_size = int(parser[0])
                file_size = int(parser[1])
                file_name = parser[2]

                if file_size == 0:
                    # Decode the file path from bytes using UTF-8
                    print("Recived file: " + file_name)
                    print("Size: " + str(file_size))

                frag_counter = 0
                total_frags = round(file_size / frag_size)
                remaining_bytes = file_size
                recived_data_bytes = b''
                error_timer = 0
                while remaining_bytes > 0:
                    error_timer += 1
                    try:
                        data_header = conn.recv(min(frag_size + 31, remaining_bytes + 31))
                    except OSError:
                        print("connection timed out during data transfer")
                        return

                    decoded_header = decode_header(data_header)
                    keep_alive_event.set()
                    if error_timer == 6:
                        decoded_header = decode_header(data_header, True)

                    if decoded_header is not None:
                        if (decoded_header[0] == 5):
                            chunk = decoded_header[3]
                            if not chunk:
                                continue

                            frag_counter += 1
                            print(f"--------------------------\n"
                                  f"Fragmet: {frag_counter}/{total_frags}\n"
                                  f"Bytes recivded: {len(chunk)}\n"
                                  f"--------------------------")
                            recived_data_bytes += chunk
                            remaining_bytes -= len(chunk)
                            ack_header = create_header(4, 0, 0)

                            conn.sendto(ack_header, peer_sender)
                            print("ack sent to chunk")
                    else:
                        nack_header = create_header(2, 0, 0)
                        conn.sendto(nack_header, peer_sender)
                        print("NACK sent to chunk")
                save_thread = threading.Thread(target=save_file, args=(file_name, recived_data_bytes))
                save_thread.start()

            if type == 6:
                data = header[3].decode('utf-8')

                # Split the string into two parts using the | character
                parser = data.split('|')
                frag_size = int(parser[0])
                message_size = int(parser[1])

                frag_counter = 0
                total_frags = round(message_size / frag_size)
                remaining_bytes = message_size
                recived_data_bytes = b''
                error_timer = 0
                while remaining_bytes > 0:
                    error_timer += 1
                    data_header = conn.recv(min(frag_size + 31, remaining_bytes + 31))
                    decoded_header = decode_header(data_header)
                    if error_timer == 6:
                        decoded_header = decode_header(data_header, True)

                    if decoded_header is not None:
                        if (decoded_header[0] == 6):
                            chunk = decoded_header[3]
                            if not chunk:
                                continue

                            frag_counter += 1
                            print(f"--------------------------\n"
                                  f"Fragmet: {frag_counter}/{total_frags}\n"
                                  f"Bytes recivded: {len(chunk)}\n"
                                  f"--------------------------")

                            recived_data_bytes += chunk
                            remaining_bytes -= len(chunk)
                            ack_header = create_header(4, 0, 0)

                            conn.sendto(ack_header, peer_sender)
                            print("ack sent to chunk")
                    else:
                        nack_header = create_header(2, 0, 0)
                        conn.sendto(nack_header, peer_sender)
                        print("NACK sent to chunk")

                print(recived_data_bytes)

            if type == 7:
                print("Fyn received, sending ACK and terminating")
                nack_header = create_header(1, 3, 0)
                conn.sendto(nack_header, peer_sender)
                universal_termination()
                return



    except socket.gaierror as e:
        print(f"Error: {e}")
        print("Hostname resolution failed. Check the hostname or IP address.")

    except ConnectionResetError as e:
        print(f"Error: {e}")
        print("Hostname resolution failed. Check the hostname or IP address.")


def keep_alive_sender(conn, interval):
    try:
        # Get the address and port from the socket object
        peer_address, local_port = conn.getpeername()
        peer = (peer_address, local_port)
        print(f"Peer {peer[0]}:{peer[1]} ")
        global fyn
        fyn.clear()
        while True:
            if fyn.is_set():
                return

            keep_alive_header = create_header(3, 0, 0)
            conn.sendto(keep_alive_header, peer)

            time.sleep(interval)

    except AttributeError:
        print("Error: Invalid socket object")

    except OSError:
        print("socket was closed")
        return

def save_file(file_name, recived_data_bytes):
    save_path = input("path to save file: ")
    # Write the bytes to a file
    with open(save_path + file_name, 'wb') as file:
        file.write(recived_data_bytes)

    print("File received successfully to " + save_path + file_name)

def calculate_crc16(data):
    crc = 0xFFFF

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1

    return crc & 0xFFFF


def create_header(type, seq, crc, data=None):
    header = format(type, '03b')
    header += format(seq, '03b')

    crc_calculation = int(header, 2).to_bytes(1, byteorder='big')
    if data is not None:
        if isinstance(data, str):
            # Data is a string
            data = data.encode('utf-8')
            crc_calculation += data
        elif isinstance(data, bytes):
            # Data is already bytes
            crc_calculation += data
        else:
            # Handle other types or raise an exception
            raise ValueError("Unsupported data type")

    crc16 = calculate_crc16(crc_calculation)
    header += format(crc16, '016b')

    header_to_send = int(header, 2).to_bytes(3, byteorder='big')
    if data is not None:
        header_to_send += data

    # print(f"encoded set: {int(header, 2).to_bytes(3, byteorder='big')}")
    return header_to_send


def decode_header(encoded_header, simulate_error=False):
    # Ensure the length of the encoded header is correct
    if len(encoded_header) < 3:
        print("header to short")
        return

    # Extracting the components from the encoded header
    bits = ''.join(format(byte, '08b') for byte in encoded_header[:3])
    crc_check_bits = bits[:8]
    type_bits = bits[:5]
    seq_bits = bits[5:8]
    crc_bits = bits[8:24]
    data_bytes = b''
    if len(encoded_header) > 3:
        data_bits = ''.join(format(byte, '08b') for byte in encoded_header[3:])
        data_bytes = bytes([int(data_bits[i:i + 8], 2) for i in range(0, len(data_bits), 8)])
        if (simulate_error):
            # Randomly choose a position to change
            position_to_change = random.randint(0, len(data_bytes) - 1)
            # Randomly generate a new byte
            new_byte = bytes([random.randint(0, 255)])
            # Update the bytes at the chosen position
            data_bytes = data_bytes[:position_to_change] + new_byte + data_bytes[position_to_change + 1:]

    if (simulate_error):
        # Randomly choose a position to invert
        position_to_invert = random.randint(0, min(4, len(type_bits) - 1))
        # Invert the chosen bit
        type_bits = type_bits[:position_to_invert] + ('0' if type_bits[position_to_invert] == '1' else '1') + type_bits[position_to_invert + 1:]

    # Decoding each component
    decoded_type = int(type_bits, 2)
    decoded_seq = int(seq_bits, 2)
    decoded_crc = int(crc_bits, 2)

    if calculate_crc16(int(crc_check_bits, 2).to_bytes(1, byteorder='big') + data_bytes) != int(crc_bits, 2):
        print(f"corrupted datagram")
        return None

    return decoded_type, decoded_seq, decoded_crc, data_bytes


def keep_alive_handler():
    global keep_alive_event, fyn
    start_time = time.time()
    conn = None
    fyn.clear()
    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time

        if keep_alive_event.wait(timeout=max(0, 15 - elapsed_time)):
            # Keep-alive event is set
            start_time = time.time()
            keep_alive_event.clear()
        else:
            # 15 seconds passed without keep-alive
            if fyn.is_set():
                return
            print(Fore.RED + f"{current_time - start_time} seconds has passed from last keep alive/ACK terminating connection")
            universal_termination()
            return

def universal_termination():
    global fyn
    fyn.set()
    conn = connection_queue.get()
    conn.close()

    print(Fore.RED + f"Connection timeout, connection terminated" + Fore.RESET)
    if was_listening:
        try:
            hostname = socket.getfqdn()
            ip = socket.gethostbyname_ex(hostname)[2][1]
            print(f"local ip: {ip}")
        except IndexError:
            print("Media is not connected")
            return
        print(f"Hostname: {ip}")
        wait_for_syn_thread = threading.Thread(target=wait_for_syn, args=(ip, local_port))
        wait_for_syn_thread.start()


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
        print("5 = change fragment size(default = 1469)")
        print("6 = send text")

        user_input = input("Select function: ")
        print(user_input)
        if user_input == '0':
            hostname = socket.getfqdn()
            try:
                ip = socket.gethostbyname_ex(hostname)[2][1]
                print(f"local ip: {ip}")
                port = int(input("Select port to operate on: "))
                # Start listener for connection
                wait_for_syn_thread = threading.Thread(target=wait_for_syn, args=(ip, port))
                wait_for_syn_thread.start()
                wait_for_syn_thread.join()  # Wait for the thread to finish
                conn = connection_queue.get()
                connection_queue.put(conn)
                global was_listening
                was_listening = True
            except IndexError:
                print("Media is not connected")

        elif user_input == '1':
            # Server (receiver) side
            host = input("Select IP to connect to: ")
            port = int(input("Select the PORT of the receiver: "))
            create_connection(host, port)
            conn = connection_queue.get()
            connection_queue.put(conn)

        elif user_input == '3':
            # Retrieve the connection from the queue
            conn = connection_queue.get()
            connection_queue.put(conn)
            if conn:
                file = input("Path to file: ")
                send_thread = threading.Thread(target=send_file, args=(conn, file,))
                send_thread.start()
                send_thread.join()

        elif user_input == '4':
            conn = connection_queue.get()
            connection_queue.put(conn)
            if conn:
                terminate_connection(conn)
                conn = None

        elif user_input == '5':

            new_frag_size = int(input("Chose new frag_size: "))
            if new_frag_size <= 1469:
                global frag_size
                frag_size = new_frag_size
            else:
                print("frag size not supported, frag size set to default!")

        elif user_input == '6':

            # Retrieve the connection from the queue
            print(type(conn))
            if conn:
                message = input("Message to peer: ")
                send_thread = threading.Thread(target=send_text, args=(conn, message,))
                send_thread.start()

        else:
            continue


if __name__ == "__main__":
    # Create connection que, to pass established connection from threads
    connection_queue = Queue()
    gui_thread = threading.Thread(target=gui)
    gui_thread.start()
    gui_thread.join()
