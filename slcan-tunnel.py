#!/usr/bin/python2

import os
import sys
import subprocess
import time
import termios
import fcntl
import struct
import array
import socket
import signal
import signal
import errno


def log(message, newline="\n"):
    # python 2 variant:
    sys.stderr.write("{}:{}{}".format(os.getpid(), message, newline))


def pid_running(pid):
    # https://stackoverflow.com/questions/568271/how-to-check-if-there-exists-a-process-with-a-given-pid-in-python
    try:
        os.kill(pid, 0)
        return True
    except OSError as err:
        return (err.errno == errno.EPERM)


def ignore_children():
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def read_command(fd_in, compress):
    message = os.read(fd_in, 1)
    if message != 't' and message != 'T' or not compress:
        while True:
            c = os.read(fd_in, 1)
            message += c
            if c == '\r':
                return message
    else:
        log("SLCAN compression not implemented")
        raise NotImplemented()


def write_command(fd_out, compress, command):
    if command[0] != 't' and command[0] != 'T' or not compress:
        os.write(fd_out, command)
    else:
        log("SLCAN compression not implemented")
        raise NotImplemented()


def relay_single_stream(fd_in, decompress_in, fd_out, compress_out):
    while True:
        cmd = read_command(fd_in, decompress_in)
        write_command(fd_out, compress_out, cmd)


def worker_process(fun, *args, **kwargs):
    pid = os.fork()
    if pid > 0:
        return pid
    else:
        try:
            fun(*args, **kwargs)
        except (Exception, KeyboardInterrupt) as e:
            log(e)
        sys.exit(1)


TIOCSPTLCK = 0x40045431
N_SLCAN = 0x00000011
SIOCGIFNAME = 0x00008910
IFNAMSIZE=16

def slcan_relay(netdev, compress, fd_in, fd_out):
    """ create <netdev> as new (SL)CAN device
    and relay from fd_in to netdev and from netdev to fd_out. """

    def unlockpt(fd):
        ret = fcntl.ioctl(fd, TIOCSPTLCK, struct.pack('i', 0))
        if ret < 0:
            log("ERROR: failed to unlockpt. Error {}".format(ret))

    def tty_make_slcan(fd):
        ret = fcntl.ioctl(fd, termios.TIOCSETD, struct.pack('i', N_SLCAN))
        if ret < 0:
            log("ERROR: failed to set SLCAN serial line discipline. Error {}".format(ret))

    def netdev_name_for_slcan(fd):
        ifname = array.array('B', [0] * (IFNAMSIZE+1))
        ret = fcntl.ioctl(fd, SIOCGIFNAME, ifname, 1)
        if ret < 0:
            log("ERROR: failed to get netdev name")
        return ifname.tostring().rstrip('\0')

    def netdev_rename(old_name, new_name):
        os.system("ip link set {} name {}".format(old_name, new_name))
        log("SLCAN netdev: '{}'".format(new_name))

    def netdev_up(name):
        os.system("ip link set {} up".format(name))

    (master, slave) = os.openpty()

    unlockpt(master)
    tty_make_slcan(slave)
    old_name = netdev_name_for_slcan(slave)
    netdev_rename(old_name, netdev)
    netdev_up(netdev)

    ignore_children()

    relay_in  = worker_process(relay_single_stream, fd_in, compress, master, False)
    os.close(fd_in)
    log("SLCAN relay in: {}".format(relay_in))

    relay_out = worker_process(relay_single_stream, master, False, fd_out, compress)
    os.close(fd_out)
    log("SLCAN relay out: {}".format(relay_out))

    try:
        while pid_running(relay_in) and pid_running(relay_out):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass

    if pid_running(relay_in):
        os.kill(relay_in, signal.SIGKILL)

    if pid_running(relay_out):
        os.kill(relay_out, signal.SIGKILL)

    del slave
    del master

    log("SLCAN tunnel terminated")


def main(args):
    def show_help():
        log("slcan-tunnel.py [--compress] <netdev>")
        log("creates an SLCAN device on the host named <netdev>, while transceiving")
        log("SLCAN stream via STDIO, optionally compressing it.")
        sys.exit(1)

    if len(args) < 1:
        show_help()

    compress = False
    if args[0] == "--compress":
        compress = True
        args = args[1:]

    if len(args) != 1:
        show_help()

    netdev = args[0]

    slcan_relay(netdev, compress, sys.stdin.fileno(), sys.stdout.fileno())

    sys.exit(0)

if __name__ == "__main__":
    main(sys.argv[1:])

