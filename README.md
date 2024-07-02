# Simple Ping Alert

This is a super simple script to check the availability of a specified IP address via ping. If the server becomes unreachable for a specified amount of time, the script will send an alert message via Telegram, including the source IP and BGP Subnet information for further checking by the NOC.

## Configuration

1. **Target Host**: The IP address of the server to monitor.
2. **Telegram Info**: Add your Telegram info on the telegram-info file Line 1 is your Bot Token, Line 2 is the chat ID.
