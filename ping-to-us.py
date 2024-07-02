import subprocess
import time
import datetime
import requests
import threading
import os
import json
from bs4 import BeautifulSoup

# Configuration
LOSS_THRESHOLD = 3  # seconds
TARGET_HOST = "95.179.139.97"  # Replace with the IP you want to ping
ENABLE_LOGGING = True  # Set to False to disable logging
LOG_ONLY_ON_LOSS = False  # Set to True to log only on packet loss

# File to store the IP and subnet information
INFO_FILE = '/mnt/data/server_info.json'

# Function to read Telegram credentials from the file
def read_telegram_credentials(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        return lines[0].strip(), lines[1].strip()

# Read the Telegram credentials
TELEGRAM_TOKEN, CHAT_ID = read_telegram_credentials('../../telegram-token-dev')

def ping(ip):
    try:
        output = subprocess.check_output(['ping', '-c', '1', '-W', '1', ip], stderr=subprocess.STDOUT, universal_newlines=True)
        return "1 packets transmitted, 1 received" in output
    except subprocess.CalledProcessError:
        return False

def traceroute(ip):
    try:
        output = subprocess.check_output(['traceroute', '-n', '-m', '10', '-w', '1', '-q', '1', ip], stderr=subprocess.STDOUT, universal_newlines=True)
        # Process output to show only the hop and the IP
        lines = output.strip().split('\n')
        processed_lines = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                hop = parts[0]
                ip_address = parts[1]
                processed_lines.append(f"{hop} {ip_address}")
        return "\n".join(processed_lines)
    except subprocess.CalledProcessError as e:
        return str(e.output)

def log_message(message):
    if ENABLE_LOGGING and (not LOG_ONLY_ON_LOSS or (LOG_ONLY_ON_LOSS and "loss" in message.lower())):
        with open("ping_monitor_log-us.txt", "a") as log_file:
            log_file.write(f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')} - {message}\n")

def log_loss(ip):
    log_message(f"{LOSS_THRESHOLD}-second packet loss detected for IP: {ip}")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message
    }
    requests.post(url, data=payload)

def async_traceroute_and_notify(ip):
    traceroute_info = traceroute(ip)
    public_ip, bgp_subnet = get_public_ip_and_bgp_subnet()
    message = (
        f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')} - {LOSS_THRESHOLD}-second packet loss detected for IP: {ip}\n"
        f"Source Public IP & Subnet: {public_ip} | {bgp_subnet}\n"
        "Traceroute:\n"
        f"{traceroute_info}"
    )
    send_telegram_message(message)
    log_loss(ip)
    log_message("Packet loss detected, sent notification.")

def monitor_ip(ip):
    loss_start_time = None
    loss_detected = False

    while True:
        if ping(ip):
            if loss_detected:
                message = f"{datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')} - Packet loss for IP {ip} has recovered."
                send_telegram_message(message)
                log_message("Packet loss recovered, sent recovery message.")
                loss_detected = False
            loss_start_time = None
            log_message("Ping successful.")
        else:
            if loss_start_time is None:
                loss_start_time = time.time()
                log_message("Ping failed, starting loss timer.")
            log_message(f"Ping failed, duration: {time.time() - loss_start_time:.2f} seconds")

        if loss_start_time and time.time() - loss_start_time >= LOSS_THRESHOLD and not loss_detected:
            # Run traceroute and notification asynchronously
            threading.Thread(target=async_traceroute_and_notify, args=(ip,)).start()
            loss_detected = True

        time.sleep(1)  # Ping every second

def get_public_ip_and_bgp_subnet():
    # Ensure the directory exists
    os.makedirs(os.path.dirname(INFO_FILE), exist_ok=True)
    
    if os.path.exists(INFO_FILE):
        with open(INFO_FILE, 'r') as file:
            info = json.load(file)
            return info['public_ip'], info['bgp_subnet']
    else:
        public_ip = requests.get('https://api.ipify.org?format=json').json()['ip']
        bgp_subnet = get_bgp_subnet(public_ip)
        info = {'public_ip': public_ip, 'bgp_subnet': bgp_subnet}
        with open(INFO_FILE, 'w') as file:
            json.dump(info, file)
        return public_ip, bgp_subnet

def get_bgp_subnet(ip):
    try:
        url = f"https://bgp.he.net/ip/{ip}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        subnet = soup.find_all('a', href=lambda href: href and "/net/" in href)[0].text.strip()
        return subnet
    except Exception as e:
        return f"Unknown (Error: {e})"

if __name__ == "__main__":
    public_ip, bgp_subnet = get_public_ip_and_bgp_subnet()
    print(f"Public IP: {public_ip}")
    print(f"BGP Subnet: {bgp_subnet}")
    monitor_ip(TARGET_HOST)
