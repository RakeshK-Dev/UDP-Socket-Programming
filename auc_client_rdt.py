"""Module Name: auc_client_rdt.py
Description: This script implements a client that can either act as a seller or a buyer. Sellers submit auction requests, while buyers submit bids. Reliable data transfer is implemented using a stop-and-wait protocol with optional packet loss simulation.

Developer Information:
-----------------------
- Author: Rakesh Kannan, Sharmila Reddy Anugula 
- Email: rkannan3@ncsu.edu, sanugul@ncsu.edu
- GitHub: https://github.com/RakeshK-Dev
- Created Date: 2024-11-01
- Last Modified: 2024-11-18
- Version: 2.0.0

Features:
---------
- Operates as a seller or buyer based on the server's initial response.
- Implements bidding logic for buyers and auction request logic for sellers.
- Uses a stop-and-wait protocol for reliable data transfer over UDP.
- Simulates packet loss to test the robustness of the communication.

Usage:
------
Run this script to connect to the auction server as either a seller or buyer. The server must be running for this client to connect.

Example:
--------
$ python3 auc_client_rdt.py <Server IP Address> <ServerPort> <RDT Port> <rate>

Where:
'<Server IP Address>' - the IP address of the auction server that the client will connect to
'<ServerPort>' - the TCP port number on which the auction server is listening for incoming connections
'<RDT Port>' - the UDP port number that will be used for the reliable data transfer (RDT) protocol implementation
'<rate>' - the packet loss rate to be simulated for testing the RDT protocol. It's a value between [0.0, 1.0], where: 0.0 means no packet loss"""


import socket
import sys
import time
import random

class AuctionClient:
    def __init__(self, host, port, udp_port, packet_loss_prob=None):
        """Initialize the client with the server's host, port, UDP port, and optional packet loss probability."""
        self.host = host
        self.port = port
        self.udp_port = udp_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP socket
        self.packet_loss_prob = packet_loss_prob  # Probability of packet drop for RDT with loss simulation
        self.item_name = None  # Track the item name for the seller
        self.payment = None  # Track the payment for the item
        self.expected_seller_ip = None  # To store the expected seller's IP

    def connect_to_server(self):
        """Attempt to connect to the auctioneer server."""
        try:
            self.client_socket.connect((self.host, self.port))  # Connect to the server
            print(f"Connected to the Auctioneer server.\n")
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
        return True

    def send_message(self, message):
        """Send a message to the server."""
        try:
            self.client_socket.sendall(message.encode())  # Ensure full message is sent
        except (BrokenPipeError, ConnectionResetError):
            # Handle server disconnection or broken connection
            print("Server connection lost.")
            self.client_socket.close()

    def receive_message(self):
        """Receive a message from the server."""
        try:
            return self.client_socket.recv(1024).decode()  # Receive data from the server
        except (ConnectionResetError, socket.error):
            # Return None in case of a connection error
            return None

    def run(self):
        """Main method to start the client, determine role, and handle the auction process."""
        if not self.connect_to_server():  # Connect to the server
            return

        response = self.receive_message()  # Wait for a message from the server

        if response is None:
            print("Server is busy. Try to connect again later.")
            self.client_socket.close()  # Close the connection if the server is busy
            return

        # Determine if the client is a seller or a buyer based on server response
        if "submit an auction request" in response:
            print("Your role is: [Seller]")
            self.seller_mode()  # Start seller mode
        elif "waiting for other Buyers" in response:
            print("Your role is: [Buyer]")
            print("The Auctioneer is still waiting for other Buyers to connect...\n")
            self.wait_for_bidding()  # Wait for bidding to start
        else:
            print("Server is busy. Try to connect again later.")
            self.client_socket.close()  # Close the connection if no valid response is received
            return

    def seller_mode(self):
        """Handle seller operations for initiating an auction."""
        while True:
            print("Please submit auction request:")
            auction_details = input()  # Get auction details from the seller

            try:
                # Parse auction details from input
                auction_type, lowest_price, num_bids, item_name = auction_details.split(maxsplit=3)
                message = f"{auction_type.strip()} {lowest_price.strip()} {num_bids.strip()} {item_name.strip()}"
                self.item_name = item_name  # Store the item name
                self.send_message(message)  # Send auction request to the server

                response = self.receive_message()  # Wait for server response
                if response is None:
                    print("Server is busy. Try to connect again later.")
                    break

                print("Server: Auction start.\n")

                # Wait for further server response to indicate auction results
                response = self.receive_message()

                if response:
                    # Parse and print auction result if the item is sold
                    if "sold for $" in response and "Winning buyer IP" in response:
                        parts = response.split()
                        price_index = parts.index("sold") + 2
                        ip_index = parts.index("IP:") + 1
                        self.payment = parts[price_index].replace("$", "")
                        winning_buyer_ip = parts[ip_index]

                        print("Auction finished!")
                        print(f"Success! Your item {self.item_name} has been sold for ${self.payment} Buyer IP: {winning_buyer_ip}")
                        print("Disconnecting from the Auctioneer server. Auction is over!")

                        # Start the UDP file transfer to the winning buyer
                        self.initiate_udp_transfer(winning_buyer_ip)

                    elif "Item not sold" in response:
                        # Print the result if the item was not sold
                        print("Auction finished!")
                        print("Unfortunately, your item was not sold as all bids were below the minimum price.")
                        print("Disconnecting from the Auctioneer server. Auction is over!")

                else:
                    print("Server did not respond with auction results.")
                break
            except ValueError:
                # Handle input parsing errors
                print("Server: Invalid auction request!")

    def is_valid_ip(self, ip):
        """Validate the IP address format."""
        try:
            socket.inet_aton(ip)  # Check if the IP format is valid
            return True
        except socket.error:
            return False

    def send_file_over_udp(self, seller_ip, buyer_ip, udp_port, file_path="tosend.file"):
        """Send a file over UDP using a reliable stop-and-wait protocol with packet loss simulation."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.settimeout(2)  # Timeout for retransmission

        try:
            print("UDP socket opened for RDT.\nStart sending file.")
            with open(file_path, "rb") as file:
                data = file.read()
            
            total_size = len(data)
            if total_size == 0:  # Handle empty file case
                print("Error: File is empty. Nothing to send.")
                udp_socket.close()
                return

            chunk_size = 2000
            seq_num = 0  # Start sequence number at 0
            bytes_sent = 0  # Track total bytes sent

            # Send control packet
            control_packet = f"start {total_size}".encode()
            udp_socket.sendto(bytes([seq_num, 0]) + control_packet, (buyer_ip, udp_port))
            print(f"Sending control seq {seq_num}: start {total_size}")
            is_first_send = True
            # Wait for acknowledgment of the control packet
            while True:
                try:
                    ack, addr = udp_socket.recvfrom(1024)
                    if addr[0] == buyer_ip and ack == bytes([seq_num, 0]):
                        # Simulate acknowledgment drop
                        if self.packet_loss_prob and random.random() < self.packet_loss_prob:
                            print(f"Ack dropped: {seq_num}")
                            continue  # Simulate acknowledgment drop

                        print(f"Ack received: {seq_num}")
                        seq_num = 1 - seq_num  # Toggle sequence number for next packet
                        break
                except socket.timeout:
                    if is_first_send:
                        udp_socket.sendto(bytes([seq_num, 0]) + control_packet, (buyer_ip, udp_port))
                        is_first_send = False
                    else:
                        print(f"Msg re-sent: {seq_num}")
                        udp_socket.sendto(bytes([seq_num, 0]) + control_packet, (buyer_ip, udp_port))

            # Send data packets
            for i in range(0, total_size, chunk_size):
                chunk = data[i:i + chunk_size]  # Initialize `chunk` properly within the loop
                packet = bytes([seq_num, 1]) + chunk  # Create packet with sequence number and type flag
                is_first_send = True  # Track if this is the first send of the packet

                while True:
                    if is_first_send:
                        print(f"Sending data seq {seq_num}: {bytes_sent + len(chunk)} / {total_size}")
                        is_first_send = False  # Mark as sent for the first time
                    else:
                        print(f"Msg re-sent: {seq_num}")

                    udp_socket.sendto(packet, (buyer_ip, udp_port))

                    try:
                        ack, addr = udp_socket.recvfrom(1024)
                        if addr[0] == buyer_ip and ack == bytes([seq_num, 0]):
                            # Simulate acknowledgment drop
                            if self.packet_loss_prob and random.random() < self.packet_loss_prob:
                                print(f"Ack dropped: {seq_num}")
                                continue  # Simulate acknowledgment drop

                            print(f"Ack received: {seq_num}")
                            seq_num = 1 - seq_num  # Toggle sequence number for next packet
                            bytes_sent += len(chunk)  # Increment bytes_sent after a successful send
                            break  # Exit loop and move to the next packet
                    except socket.timeout:
                        # Timeout handling - stay in the loop to resend the packet
                        continue

            # Send the end-of-transmission signal
            udp_socket.sendto(bytes([seq_num, 0]) + b"fin", (buyer_ip, udp_port))
            print(f"Sending control seq {seq_num}: fin")

            # Wait for acknowledgment of the `fin` packet
            while True:
                try:
                    ack, addr = udp_socket.recvfrom(1024)
                    if addr[0] == buyer_ip and ack == bytes([seq_num, 0]):
                        print(f"Ack received: {seq_num}")
                        break  # Break after receiving acknowledgment for the `fin`
                except socket.timeout:
                    print(f"Msg re-sent: {seq_num}")
                    udp_socket.sendto(bytes([seq_num, 0]) + b"fin", (buyer_ip, udp_port))

        finally:
            udp_socket.close()
            print("UDP socket closed after transfer.")


    def initiate_udp_transfer(self, winning_buyer_ip):
        """Initiate the UDP transfer after a successful auction."""
        # Start the file transfer over UDP to the winning buyer
        self.send_file_over_udp(seller_ip=self.host, buyer_ip=winning_buyer_ip, udp_port=self.udp_port)

    def wait_for_bidding(self):
        """Wait for the bidding phase to start."""
        response = self.receive_message()
        if response and "Bidding start!" in response:
            print("The bidding has started!")
            self.buyer_mode()  # Start the bidding process

    def buyer_mode(self):
        """Handle the bidding process for the buyer."""
        self.expected_seller_ip = None  # Initialize to store the seller's IP

        while True:
            print("Please submit your bid:")
            bid = input()  # Get the bid from the buyer
            self.send_message(bid)  # Send the bid to the server
            response = self.receive_message()  # Wait for the server response

            if response is None:
                print("Server is busy. Try to connect again later.")
                break

            print(f"Server: {response}")

            # If the response indicates an invalid bid, prompt the user again without closing the connection
            if "Invalid bid" in response:
                continue  # Loop back to allow the user to submit a valid input

            if "Bid received" in response:
                response = self.receive_message()  # Wait for the auction result
                if response is None:
                    print("Server is busy. Try to connect again later.")
                    break
                print(f"Server: {response}")

                if "You won the item" in response:  # If the buyer wins the auction
                    # Read all remaining messages to find the seller's IP
                    while True:
                        seller_ip_message = self.receive_message()
                        if not seller_ip_message:
                            break

                        # Split the response into lines and find the seller's IP
                        lines = seller_ip_message.strip().split("\n")
                        for line in lines:
                            if line.startswith("SELLER_IP"):
                                parts = line.split()
                                if len(parts) == 2:
                                    self.expected_seller_ip = parts[1]  # Store the seller IP
                                    break  # Exit loop once IP is found

                        if self.expected_seller_ip:
                            break  # Stop reading once the IP is found

                    if not self.expected_seller_ip:
                        print("Error: Did not receive seller's IP for UDP transfer.")
                        return  # Exit if the seller IP is not found

            # Ensure the TCP connection is gracefully closed before starting the UDP connection
            self.client_socket.close()

            # If we have the seller IP, initiate the UDP file reception
            if self.expected_seller_ip:
                self.receive_file_over_udp(self.udp_port)
            else:
                print("")
            break  # Exit after processing the auction result

    def receive_file_over_udp(self, udp_port, expected_file_path="recved.file"):
        """Receive a file over UDP using a reliable stop-and-wait protocol with packet loss simulation."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(("", udp_port))
        udp_socket.settimeout(2)  # Timeout set according to specifications

        try:
            print("UDP socket opened for RDT.\nStart receiving file.")
            buffer = b""  # Initialize the buffer for storing data
            expected_seq = 0
            total_bytes_received = 0
            expected_size = None  # Initialize expected size
            first_packet_received = False  # Flag to track if the first packet has been received

            # Start time tracking for BPS calculation
            start_time = time.time()

            while True:
                try:
                    packet, addr = udp_socket.recvfrom(2048)
                    if not packet or len(packet) < 2:
                        continue

                    seq_num, type_flag = packet[0], packet[1]

                    # Ensure packet drop simulation only runs after the first packet is received
                    if first_packet_received and self.packet_loss_prob and random.random() < self.packet_loss_prob:
                        print(f"Pkt dropped: {seq_num}")
                        continue  # Simulate packet drop and skip processing

                    # Process only if packet is from the expected sender
                    if addr[0] == self.expected_seller_ip:
                        first_packet_received = True  # Mark that the first packet has been received

                    if seq_num == expected_seq:
                        print(f"Msg received: {seq_num}")
                        if type_flag == 0:  # Control packet
                            if packet[2:].decode().startswith("start"):
                                expected_size = int(packet[2:].decode().split()[1])
                                print(f"Ack sent: {seq_num}")
                                udp_socket.sendto(bytes([seq_num, 0]), addr)
                                expected_seq = 1  # Set for next packet
                                continue
                            elif packet[2:].decode() == "fin":
                                print(f"Ack sent: {seq_num}")
                                udp_socket.sendto(bytes([seq_num, 0]), addr)  # Send final ACK for fin
                                break  # Exit after acknowledging the 'fin' signal

                        if type_flag == 1:  # Data packet
                            buffer += packet[2:]
                            total_bytes_received += len(packet) - 2
                            print(f"Ack sent: {seq_num}")
                            print(f"Received data seq {seq_num}: {total_bytes_received} / {expected_size}") 
                            udp_socket.sendto(bytes([seq_num, 0]), addr)
                            expected_seq = 1 - expected_seq  # Toggle expected sequence

                            if expected_size and total_bytes_received >= expected_size:
                                continue  # Wait for 'fin' packet after receiving the complete data
                    else:
                        # Handle sequence mismatch case
                        print(f"Msg received with mismatched sequence number {seq_num}. Expecting {expected_seq}")
                        udp_socket.sendto(bytes([1 - expected_seq, 0]), addr)
                        print(f"Ack re-sent: {1 - expected_seq}")


                except socket.timeout:
                    continue  # Handle timeout for waiting for packets

                except Exception as e:
                    print(f"Error: {e}")
                    break

            # End time tracking and calculate BPS
            end_time = time.time()
            duration = end_time - start_time
            if duration > 0:
                bps = (total_bytes_received * 8) / duration  # Convert bytes to bits and divide by time
                print(f"All data received! Exiting...")
                print(f"Transmission finished: {total_bytes_received} bytes / {duration:.6f} seconds = {bps:,.6f} bps")
            else:
                print("Error: Transmission duration is zero or negative, cannot calculate BPS.")
            
            # Write the received buffer to a file
            if buffer:
                with open(expected_file_path, "wb") as f:
                    f.write(buffer)
                #print(f"File saved as '{expected_file_path}'")

        finally:
            udp_socket.close()
            print("UDP socket closed after receiving.")



if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 auc_client_rdt.py <server_ip> <port> <udp_port> [packet_loss_prob]")
        sys.exit(1)

    # Parse command-line arguments
    server_ip = sys.argv[1]
    port = int(sys.argv[2])
    udp_port = int(sys.argv[3])
    packet_loss_prob = float(sys.argv[4]) if len(sys.argv) == 5 else None

    # Create and run the auction client
    client = AuctionClient(server_ip, port, udp_port, packet_loss_prob)
    client.run()
