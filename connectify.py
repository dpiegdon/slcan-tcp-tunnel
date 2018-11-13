#!/usr/bin/python2
#
# connectify.py -- connect a TCP server to STDIO of a process.
# Part of https://github.com/dpiegdon/slcan-tcp-tunnel
#
# 2018 by David R. Piegdon
# Released under GPLv3 or later, see COPYING.

import socket
import sys
import os

def log(message, newline="\n"):
    sys.stderr.write("{0}:{1}{2}".format(os.getpid(), message, newline))

def main(args):
    def show_help():
        log("connectify.py <host:port> <command> [command params ...]")
        log("connects to <host:port> and runs <command> using the socket as STDIO.")
        sys.exit(1)

    if len(args) < 2:
        show_help()

    try:
        host = args[0].split(":")[0]
        port = int(args[0].split(":")[1])
    except Exception as e:
        log("Failed to parse <host:port>")
        show_help()
    command = args[1]
    command_args = [ command ] + args[2:]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sock < 0:
        log("Failed to create socket.")
        sys.exit(-1)

    log("Connecting to {0}:{1}...".format(host, port))
    sock.connect((host, port))

    os.close(sys.stdin.fileno())
    os.dup2(sock.fileno(), sys.stdin.fileno())

    os.close(sys.stdout.fileno())
    os.dup2(sock.fileno(), sys.stdout.fileno())

    sock.close()

    os.execv(command, command_args)

    log("Failed to execv: " + " ".join(command_args))
    sys.exit(-1)

if __name__ == "__main__":
    main(sys.argv[1:])

