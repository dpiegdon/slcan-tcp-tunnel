#!/bin/sh

CONNECTOR=${CONNECTOR:-hostify}
HOST=${HOST:-}
PORT=${PORT:-6160}
CONNECTION=${CONNECTION:-${HOST}:${PORT}}
NETDEV=${NETDEV:-can${PORT}}
COMPRESS=${COMPRESS:---compress}
SERVICE=slcan-${CONNECTOR}-${NETDEV}

PIDFILE=/tmp/.${SERVICE}-${NETDEV}-${CONNECTION}.pid

BINDIR=/root
CONNECTOR_BINARY=${BINDIR}/${CONNECTOR}.py

service_getpid() {
	cat $PIDFILE
}

service_is_running() {
	[ -e "$PIDFILE" ] && kill -0 "$(service_getpid)" > /dev/null 2>&1
}

case "$1" in
	start)
		if service_is_running; then
			echo "service ${SERVICE} already running at $(service_getpid)"
			exit 1
		else
			/usr/bin/python "$BINDIR/repeat.py" \
				/usr/bin/python "$CONNECTOR_BINARY" "$CONNECTION" \
					/usr/bin/python "$BINDIR/slcan-tunnel.py" $COMPRESS "$NETDEV" \
						> /dev/null 2>&1 &
			PID=$!
			echo "$PID" > "$PIDFILE"
			echo "service ${SERVICE} running at $PID"
		fi
		;;

	stop)
		if service_is_running; then
			while service_is_running; do
				echo "sending SIGTERM to ${SERVICE}"
				if kill -TERM "$(service_getpid)"; then
					:
				else
					echo "failed to terminated ${SERVICE}"
					break
				fi
				sleep 1.5
			done
			rm "$PIDFILE"
		else
			echo "service ${SERVICE} was not running."
			exit 1
		fi
		;;

	restart|reload|force-reload)
		$0 stop && $0 start
		;;

	status)
		if service_is_running; then
			echo "service running at ${SERVICE}."
		else
			echo "service not running."
		fi
		;;

	*)
		echo "unknown option."
		exit 1
		;;

esac

