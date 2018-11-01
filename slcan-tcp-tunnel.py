#!/usr/bin/python2

import os
import sys
import subprocess
import time
import termios
import fcntl
import struct
import array

TIOCSPTLCK = 0x40045431
N_SLCAN = 0x00000011
SIOCGIFNAME = 0x00008910
IFNAMSIZE=16


def unlockpt(fd):
    ret = fcntl.ioctl(fd, TIOCSPTLCK, struct.pack('i', 0))
    if ret < 0:
        print("ERROR: failed to unlockpt. Error {}".format(ret))

def disable_echo(fd):
    (iflag, oflag, cflag, lflag, ispeed, ospeed, cc) = termios.tcgetattr(fd)
    lflag &= ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])

def tty_make_slcan(fd):
    ret = fcntl.ioctl(fd, termios.TIOCSETD, struct.pack('i', N_SLCAN))
    if ret < 0:
        print("ERROR: failed to set SLCAN serial line discipline. Error {}".format(ret))

def netdev_name_for_slcan(fd):
    ifname = array.array('B', [0] * (IFNAMSIZE+1))
    ret = fcntl.ioctl(fd, SIOCGIFNAME, ifname, 1)
    if ret < 0:
        print("ERROR: failed to get netdev name")
    return ifname.tostring().rstrip('\0')

def netdev_rename(old_name, new_name):
    os.system("ip link set {} name {}".format(old_name, new_name))
    print("SLCAN netdev: '{}'".format(new_name))

def netdev_up(name):
    os.system("ip link set {} up".format(name))
    
def slcan_over_tcp(netdev, host, port):
    """ create <netdev> as new (SL)CAN device, tunnel slcan over TCP.
    if host is not None, this will connect
    as a client to <host:port>. if it is None, this will listen on <port> """
    (master, slave) = os.openpty()

    # unlockpt() is platform specific, seemingly not needed on linux 4.9
    #unlockpt(master)
    # echo does not seem to make any trouble for now.
    #disable_echo(master)
    tty_make_slcan(slave)
    old_name = netdev_name_for_slcan(slave)
    netdev_rename(old_name, netdev)

    if host is not None:
        nc_call = ["nc", host, "{}".format(port)]
        print("Listening on TCP *:{}".format(port))
    else:
        nc_call = ["nc", "-l", "-p", "{}".format(port)]
        print("Connecting to TCP {}:{}".format(host, port))
    nc = subprocess.Popen(nc_call, close_fds=True, stdin=master, stdout=master)

    try:
        netdev_up(netdev)

        while(nc.poll() is None):
            time.sleep(1)
        print("nc terminated")
    except (Exception, KeyboardInterrupt):
        pass

    if nc.poll() is None:
        nc.kill()
        print("nc killed")


if __name__ == "__main__":
    def show_help():
        print("create <netdev> and connect as a client to <host:port>:")
        print("    <netdev> -c <host> <port>")
        print("or create <netdev> and listen as a server on <host:port>:")
        print("    <netdev> -s <port>")
        sys.exit(1)

    if len(sys.argv) < 3:
        show_help()

    netdev = sys.argv[1]

    if sys.argv[2] == "-c":
        if len(sys.argv) != 5:
            show_help()
        host = sys.argv[3]
        port = sys.argv[4]
            
    elif sys.argv[2] == "-s":
        if len(sys.argv) != 4:
            show_help()
        host = None
        port = sys.argv[3]
    else:
        show_help()

    try:
        port = int(port)
    except ValueError:
        show_help()

    slcan_over_tcp(netdev, host, port)

    print("terminated")
    sys.exit(0)

