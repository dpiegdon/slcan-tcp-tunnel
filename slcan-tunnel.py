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

import traceback    # XXX DEBUG
import functools    # XXX DEBUG
import binascii     # XXX DEBUG


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

__children_alive = False

def sig_child_handler(signum, frame):
    global __children_alive
    log("SLCAN SIGCHLD")
    __children_alive = False

def monitor_children():
    global __children_alive
    __children_alive = True
    signal.signal(signal.SIGCHLD, sig_child_handler)

def children_alive():
    return __children_alive

def read_command(fd_in, compress):
    try:
        payload = os.read(fd_in, 1)
        if 0 == len(payload):
            return ""

        if payload[0] != 't' and payload[0] != 'T' or not compress:
            while True:
                c = os.read(fd_in, 1)
                payload += c
                if c == '\r':
                    command = payload
                    break

        else:
            # decompress 't' and 'T' payloads only
            if 't' == payload[0]:
                payload += os.read(fd_in, 3)
                (dlc,) = struct.unpack('B', payload[3])
                payload += os.read(fd_in, dlc+1)
                if payload[-1] != '\r':
                    raise IndexError
                (id1, id2, dlc) = struct.unpack('BBB', payload[1:4])
                command = "t%1x%02x%1x" % (id1, id2, dlc)
                for i in range(dlc):
                    command += "%02x" % struct.unpack('B', payload[4+i])[0]
                command += '\r'

            elif 'T' == payload[0]:
                payload += os.read(fd_in, 5)
                (dlc,) = struct.unpack('B', payload[5])
                payload += os.read(fd_in, dlc+1)
                if payload[-1] != '\r':
                    raise IndexError
                (id1, id2, id3, id4, dlc) = struct.unpack('BBBBB', payload[1:6])
                command = "T%02x%02x%02x%02x%1x" % (id1, id2, id3, id4, dlc)
                for i in range(dlc):
                    command += "%02x" % struct.unpack('B', payload[6+i])[0]
                command += '\r'

        #log("SLCAN recv " + command) # XXX DEBUG
        return command

    except IndexError as e:
        # XXX DEBUG:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exc_text = functools.reduce(lambda x,y: x+y, traceback.format_exception(
                                        exc_type, exc_value, exc_traceback))
        log("SLCAN Malformed packet '{}' in RX path: {}".format(
                binascii.hexlify(payload), exc_text))
        return ""
        # <<< XXX DEBUG

def write_command(fd_out, compress, command):
    try:
        if command[0] != 't' and command[0] != 'T' or not compress:
            payload = command

        else:
            # compress 't' and 'T' commands only
            if 't' == command[0]:
                dlc = int(command[4], 16);
                if len(command) != (6+dlc*2):
                    raise IndexError
                if command[-1] != '\r':
                    raise IndexError
                fields = [ 't',
                           int(command[1], 16),
                           int(command[2:4], 16),
                           dlc
                         ]
                fields += [ int(command[5+i*2 : 7+i*2], 16) for i in range(dlc) ]
                fields.append('\r')
                payload = struct.pack('cBBB' + 'B'*dlc + 'c', *fields)

            elif 'T' == command[0]:
                dlc = int(command[9], 16);
                if len(command) != (11+dlc*2):
                    raise IndexError
                if command[-1] != '\r':
                    raise IndexError
                fields = [ 'T',
                           int(command[1:3], 16),
                           int(command[3:5], 16),
                           int(command[5:7], 16),
                           int(command[7:9], 16),
                           dlc
                         ]
                fields += [ int(command[10+i*2 : 12+i*2], 16) for i in range(dlc) ]
                fields.append('\r')
                payload = struct.pack('cBBBBB' + 'B'*dlc + 'c', *fields)

        #log("SLCAN TX => " + binascii.hexlify(payload))
        os.write(fd_out, payload);
    except IndexError:
        # XXX DEBUG:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exc_text = functools.reduce(lambda x,y: x+y, traceback.format_exception(
                                        exc_type, exc_value, exc_traceback))
        log("SLCAN Malformed packet '{}' in TX path: {}".format(
                binascii.hexlify(command), exc_text))
        # <<< XXX DEBUG


def relay_single_stream(fd_in, decompress_in, fd_out, compress_out):
    while True:
        cmd = read_command(fd_in, decompress_in)
        if cmd != "":
            write_commaed(fd_out, compress_out, cmd)
        else:
            log("SLCAN RX connection lost")
            break


def worker_process(fun, *args, **kwargs):
    pid = os.fork()
    if pid > 0:
        return pid
    else:
        try:
            fun(*args, **kwargs)
        except (Exception, KeyboardInterrupt) as e:
            if isinstance(e, OSError) and e.errno == errno.EPIPE:
                log("SLCAN Connection lost")
            else:
                # XXX DEBUG:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                exc_text = functools.reduce(lambda x,y: x+y, traceback.format_exception(
                                                exc_type, exc_value, exc_traceback))

                log("SLCAN Exception in worker: {}".format(exc_text))
                # <<< XXX DEBUG
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
            log("SLCAN Failed to unlockpt: Error {}".format(ret))

    def tty_make_slcan(fd):
        ret = fcntl.ioctl(fd, termios.TIOCSETD, struct.pack('i', N_SLCAN))
        if ret < 0:
            log("SLCAN Failed to set SLCAN serial line discipline: Error {}".format(ret))

    def netdev_name_for_slcan(fd):
        ifname = array.array('B', [0] * (IFNAMSIZE+1))
        ret = fcntl.ioctl(fd, SIOCGIFNAME, ifname, 1)
        if ret < 0:
            log("SLCAN Failed to get netdev name")
        return ifname.tostring().rstrip('\0')

    def netdev_rename(old_name, new_name):
        os.system("ip link set {} name {}".format(old_name, new_name))
        log("SLCAN Netdev: '{}'".format(new_name))

    def netdev_up(name):
        os.system("ip link set {} up".format(name))

    (master, slave) = os.openpty()

    unlockpt(master)
    tty_make_slcan(slave)
    old_name = netdev_name_for_slcan(slave)
    netdev_rename(old_name, netdev)
    netdev_up(netdev)

    monitor_children()

    relay_in  = worker_process(relay_single_stream, fd_in, compress, master, False)
    os.close(fd_in)
    log("SLCAN Relay in: {}".format(relay_in))

    relay_out = worker_process(relay_single_stream, master, False, fd_out, compress)
    os.close(fd_out)
    log("SLCAN Relay out: {}".format(relay_out))

    try:
        while children_alive():
            time.sleep(.5)
    except KeyboardInterrupt:
        pass

    if pid_running(relay_in):
        log("SLCAN Terminating RX side")
        os.kill(relay_in, signal.SIGTERM)

    if pid_running(relay_out):
        log("SLCAN Terminating TX side")
        os.kill(relay_out, signal.SIGTERM)

    del slave
    del master

    log("SLCAN Tunnel terminated")


def main(args):
    def show_help():
        log("slcan-tunnel.py [--compress] <netdev>")
        log("creates an SLCAN device on the host named <netdev>, while transceiving")
        log("an SLCAN stream via STDIO, optionally compressing it.")
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

