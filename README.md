# **UDP-Socket-Programming**

A robust auction system utilizing reliable UDP socket programming with a stop-and-wait protocol. This project allows users to connect as sellers or buyers. Sellers can create auctions with item details, and buyers place bids in real-time. The server manages the auction process, determines winners based on first-price or second-price rules, and facilitates reliable file transfers between the seller and winning buyer.

---

## **Project Overview**

The auction system consists of two main components:
1. **Auction Server (`auc_server_rdt.py`)**:  
   - Manages the entire auction lifecycle.
   - Handles seller and buyer connections, processes bids, determines auction winners, and facilitates reliable file transfer from seller to buyer.
   - Supports first-price and second-price auction types.

2. **Auction Client (`auc_client_rdt.py`)**:  
   - Acts as a seller or buyer.
   - Sellers submit auction requests with item details, and buyers place bids.
   - Includes reliable UDP communication for transferring item details after auction completion.

---

## **How to Run the Code**

### **Module Name**: `auc_server_rdt.py`

**Description**:  
This script implements the auction server to manage the auction process. It handles connections from sellers and buyers, processes auction requests, and determines winners. The server also facilitates reliable UDP file transfer to send item details from the seller to the winning buyer.

**Usage**:  
Run this script on the server to host auctions. The first client connection is treated as a seller, and subsequent connections as buyers.

**Example**:  
```bash
$ python3 auc_server_rdt.py <port>
