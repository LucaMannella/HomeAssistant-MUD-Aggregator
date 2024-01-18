import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import socket

def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """

    # Option for the number of packets as a function of
    param = '-n' if platform.system().lower()=='windows' else '-c'

    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', param, '1', host]

    return subprocess.call(command) == 0

def traceroute(host):
    param = '-m 3'  # number of hops
    command = ['traceroute', param, host]
    return subprocess.call(command) == 0

def curl(host, filename):
    param = '-o '+filename
    command = ["curl", param, host]
    return subprocess.call(command) == 0


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(('8.8.8.8', 1))  # doesn't even have to be reachable
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def mac_to_bytes(mac_addr: str) -> bytes:
    """ Converts a MAC address string to bytes. """
    return int(mac_addr.replace(":", ""), 16).to_bytes(6, "big")
