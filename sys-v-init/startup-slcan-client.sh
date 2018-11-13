#!/bin/sh

CONNECTOR=connectify
HOST="192.168.23.17"
PORT="6160"

if [ -h "$0" ]; then
	. $(dirname $(readlink $0))/startup-slcan-server.sh
else
	. $(dirname $0)/startup-slcan-server.sh
fi

