#!/usr/bin/python2
# this script is a hack to work around ancient service management...

import sys
import os
import signal
import subprocess
import time

def log(message, newline="\n"):
    sys.stderr.write("{0}:{1}{2}".format(os.getpid(), message, newline))

process = None
terminate = False

def stop_process():
    global process
    global terminate
    terminate = True
    if process is not None:
        try:
            process.send_signal(signal.SIGCHLD)
            time.sleep(2)
            if process.poll() is None:
                process.terminate()
        except OSError:
            pass

def sig_term_handler(signum, frame):
    stop_process()

def main(args):
    if len(args) < 1:
        log("repeat <command and parameters")
        log("will repeat given command until a SIGTERM is received (or keyboard interrupt).")
        log("then command process will be send a SIGCHLD, then a SIGTERM.")
        sys.exit(1)

    signal.signal(signal.SIGTERM, sig_term_handler)
    
    global terminate

    while not terminate:
        global process
        process = subprocess.Popen(args, close_fds=True)
        try:
            while process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_process()

if __name__ == "__main__":
    main(sys.argv[1:])

