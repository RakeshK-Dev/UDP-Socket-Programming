"""Module Name: auc_server_rdt.py
Description: This script implements the server-side logic for hosting auctions. It manages the auctioneer's operations, including handling seller requests, managing buyers, processing bids, and determining auction results. Reliable data transfer is implemented using a stop-and-wait protocol with optional packet loss simulation.

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
- Handles seller and buyer connections sequentially.
- Processes auction requests and determines the winning bidder based on auction rules.
- Simulates network packet loss for testing the reliability of the communication.
- Uses a stop-and-wait protocol for reliable data transfer over UDP.

Usage:
------
Run this script to start the auction server. The server listens for incoming seller and buyer connections.

Example:
--------
$ python3 auc_server_rdt.py <IP Address> <Port Number>

Where 
'<IP Address>' - the IP address on which you want the server to listen for incoming connections
'<Port Number>' - the TCP port number on which the server will listen for incoming connections. """

import socket
import threading
import sys
import time
import random

class AuctioneerServer:
    def __init__(self, host='localhost', port=65432):
        # Initialize the auctioneer server with given host and port
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen()
        print(f"Auctioneer is ready for hosting auctions!\n")

        # Auction status and data structures to manage the process
        self.status = 0  # 0: Waiting for Seller, 1: Waiting for Buyers
        self.seller = None
        self.seller_address = None
        self.buyer_threads = []
        self.buyers = []
        self.buyer_bids = {}
        self.auction_details = {}
        self.bid_order = []
        self.buyer_count = 0
        self.buyer_number_map = {}
        self.lock = threading.Lock()
        self.seller_request_received = False

    def handle_client(self, client_socket, address):
        # Handle new client connections (either seller or buyers)
        if self.seller is None:
            # Assign the first client as the seller
            self.seller = client_socket
            self.seller_address = address
            self.status = 1  # Change status to waiting for buyers
            ip, port = address
            print(f"Seller is connected from {ip}:{port}")
            print(f">> New Seller Thread spawned")

            # Ask the seller to submit an auction request
            client_socket.send(b"submit an auction request")
            self.process_seller_request(client_socket)
        elif self.status == 1 and not self.seller_request_received:
            # Prevent buyers from joining before the auction request is submitted
            print("Buyer tried to connect before auction request submission.")
            client_socket.sendall(b"Server is busy. Try to connect again later.")
            client_socket.shutdown(socket.SHUT_WR)
            client_socket.close()
        elif self.status == 1 and self.seller_request_received:
            # Process buyer connections once the seller's request is submitted
            self.process_buyer(client_socket, address)

    def process_seller_request(self, client_socket):
        # Process the seller's auction request
        while True:
            try:
                message = client_socket.recv(1024).decode()
                auction_data = message.split()

                if len(auction_data) != 4:
                    # Validate auction request format
                    client_socket.send(b"Invalid auction request!")
                    continue

                # Parse and store auction details
                type_of_auction, lowest_price, number_of_bids, item_name = auction_data
                self.auction_details = {
                    "type": int(type_of_auction),
                    "lowest_price": int(lowest_price),
                    "num_bids": int(number_of_bids),
                    "item_name": item_name,
                }
                self.seller_request_received = True
                client_socket.send(f"Auction request received: {message}".encode())
                print(f"Auction request received. Now waiting for Buyers.\n")
                break
            except Exception as e:
                print(f"Error processing seller request: {e}")

    def process_buyer(self, client_socket, address):
        # Handle the buyer's connection and add them to the auction
        if len(self.buyers) < self.auction_details["num_bids"]:
            self.buyer_count += 1
            ip, port = address
            print(f"Buyer {self.buyer_count} is connected from {ip}:{port}")
            self.buyer_number_map[client_socket] = self.buyer_count
            self.buyers.append(client_socket)
            client_socket.send(b"waiting for other Buyers")

            # Start bidding when the required number of buyers have connected
            if len(self.buyers) == self.auction_details["num_bids"]:
                print("Requested number of bidders arrived. Let's start bidding!\n")
                print(">> New Bidding Thread spawned")
                self.start_bidding()
        else:
            # Reject extra buyers if the auction is full
            print(f"Extra Buyer tried to join. Informing that the auction is full.")
            client_socket.send(b"Server busy, auction in progress!")
            client_socket.close()

    def start_bidding(self):
        # Notify all buyers that bidding has started
        for buyer in self.buyers:
            buyer.send(b"Bidding start! Please submit your bid.")

        # Create threads for handling each buyer's bid
        for buyer in self.buyers:
            threading.Thread(target=self.handle_bidding, args=(buyer, buyer.getpeername())).start()

    def handle_bidding(self, client_socket, address):
        # Handle the bidding process for each buyer
        buyer_number = self.buyer_number_map[client_socket]
        while True:
            try:
                bid = client_socket.recv(1024).decode()
                if bid.isdigit() and int(bid) > 0:
                    # Store valid bids and maintain order
                    with self.lock:
                        if client_socket not in self.buyer_bids:
                            self.buyer_bids[client_socket] = int(bid)
                            self.bid_order.append(client_socket)
                            print(f">> Buyer {buyer_number} bid ${bid}")
                            client_socket.send(b"Bid received. Please wait...\n")
                            break
                else:
                    # Inform buyer of invalid input and allow them to submit again
                    client_socket.send(b"Invalid bid. Please submit a positive integer!")
            except Exception as e:
                print(f"Error handling bid from Buyer {buyer_number}: {e}")
                break

        # Check if all buyers have submitted their bids
        with self.lock:
            if len(self.buyer_bids) == self.auction_details["num_bids"]:
                self.process_auction_results()

    def process_auction_results(self):
        # Determine the outcome of the auction
        highest_bid = max(self.buyer_bids.values())
        lowest_price = self.auction_details["lowest_price"]

        if highest_bid < lowest_price:
            # Handle the case where no bids meet the minimum price
            print(f">> All bids are below the minimum price of ${lowest_price}. The item is not sold.")
            self.notify_seller(f"Item not sold. All bids were below the minimum price of ${lowest_price}.")
            self.notify_all_buyers("Auction finished!")
            self.notify_all_buyers("\nUnfortunately you did not win in the last round.")
            self.notify_all_buyers("\nDisconnecting from the Auctioneer server. Auction is over!")
        else:
            # Process the winner if a valid bid is found
            self.process_winner(highest_bid)

        # Reset auction state for a new round
        self.reset_auction()

    def process_winner(self, highest_bid):
        # Identify the winning buyer
        winning_buyer = None
        for buyer in self.bid_order:
            if self.buyer_bids[buyer] == highest_bid:
                winning_buyer = buyer
                break

        lowest_price = self.auction_details["lowest_price"]
        item_name = self.auction_details["item_name"]

        # Determine the payment for the item based on auction type
        if highest_bid >= lowest_price:
            if self.auction_details["type"] == 1:
                winning_price = highest_bid
                print(f">> Item sold! The highest bid is ${highest_bid}. The actual payment is ${winning_price}")
                self.notify_winner(winning_buyer, winning_price)
            else:
                # Second-price auction logic (Vickrey auction)
                all_bids = list(self.buyer_bids.values()) + [lowest_price]
                all_bids.sort(reverse=True)
                winning_price = all_bids[1] if len(all_bids) > 1 else lowest_price

                print(f">> Item sold! The highest bid is ${highest_bid}. The actual payment is ${winning_price}")
                self.notify_winner(winning_buyer, winning_price)

            # Share IPs for further communication between buyer and seller
            self.handle_auction_end(self.server_socket, self.seller_address, winning_buyer.getpeername())

    def notify_winner(self, winning_buyer, payment):
        # Notify the winning buyer and the seller about the auction result
        item_name = self.auction_details["item_name"]

        try:
            # Send result to the seller
            seller_message = f"Auction finished! Item '{item_name}' sold for ${payment}. Winning buyer IP: {winning_buyer.getpeername()[0]}"
            self.seller.sendall(seller_message.encode())

            # Send winning notification to the buyer
            winning_message = f"Auction finished!\nYou won the item '{item_name}'! Your payment due is ${payment}. Seller IP: {self.seller_address[0]}\nDisconnecting from the Auctioneer server. Auction is over!"
            winning_buyer.sendall(winning_message.encode())

            time.sleep(0.1)  # Delay to ensure messages are processed

            end_message = "Disconnecting from the Auctioneer server. Auction is over!\n"
            winning_buyer.sendall(end_message.encode())

            time.sleep(0.1)

            # Send seller IP to the winning buyer
            seller_ip_message = f"SELLER_IP {self.seller_address[0]}\n"
            winning_buyer.sendall(seller_ip_message.encode())

            time.sleep(0.1)

            # Send winning buyer's IP to the seller
            buyer_ip_message = f"WINNING_BUYER_IP {winning_buyer.getpeername()[0]}\n"
            self.seller.sendall(buyer_ip_message.encode())
        except Exception as e:
            print(f"Error sending messages to winning buyer or seller: {e}")

        # Notify all losing buyers
        for buyer, bid in self.buyer_bids.items():
            if buyer != winning_buyer:
                try:
                    losing_message = "Auction finished!\nUnfortunately you did not win in the last round.\nDisconnecting from the Auctioneer server. Auction is over!\n"
                    buyer.sendall(losing_message.encode())
                except Exception as e:
                    print(f"Error notifying losing buyer {self.buyer_number_map[buyer]}: {e}")

        try:
            # Final notification to the seller
            self.notify_seller(f"Item '{item_name}' sold for ${payment}.")
        except Exception as e:
            print(f"Error notifying the seller: {e}")

    def notify_seller(self, message):
        # Send a message to the seller and close their connection
        self.seller.send(message.encode())
        self.seller.close()

    def notify_all_buyers(self, message):
        # Notify all buyers with a given message
        for buyer in self.buyer_bids:
            try:
                buyer.send(message.encode())
            except OSError:
                print(f"Error: Unable to send message to a buyer (bad file descriptor).")
                continue

    def reset_auction(self):
        # Reset the auction state to allow for a new auction
        self.status = 0
        self.seller = None
        self.seller_address = None
        self.buyers.clear()
        self.buyer_bids.clear()
        self.buyer_number_map.clear()
        self.bid_order.clear()
        self.auction_details.clear()
        self.seller_request_received = False

    def share_ips(self, seller_address, winning_buyer_address):
        # Share the seller's and winning buyer's IP addresses for UDP communication
        if self.seller:
            try:
                seller_msg = f"WINNING_BUYER_IP {winning_buyer_address[0]}"
                buyer_msg = f"SELLER_IP {seller_address[0]}"
                self.seller.send(seller_msg.encode())
                print(f"Sent winning buyer's IP ({winning_buyer_address[0]}) to the seller.")
                
                for buyer in self.buyers:
                    if buyer.getpeername() == winning_buyer_address:
                        buyer.send(buyer_msg.encode())
                        print(f"Sent seller's IP ({seller_address[0]}) to the winning buyer.")
                        break
            except OSError as e:
                print("")
        else:
            print("Error: Seller socket is invalid or closed.")

    def handle_auction_end(self, server_socket, seller_address, winning_buyer_address):
        # Handle end-of-auction operations and share IPs
        self.share_ips(seller_address, winning_buyer_address)

    def start(self):
        # Start the server and accept new client connections
        while True:
            client_socket, address = self.server_socket.accept()
            threading.Thread(
                target=self.handle_client, args=(client_socket, address)
            ).start()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 auc_server_rdt.py <port>")
        sys.exit(1)

    # Start the auctioneer server on the specified port
    port = int(sys.argv[1])
    auctioneer_server = AuctioneerServer(port=port)
    auctioneer_server.start()
