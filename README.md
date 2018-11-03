<!-- vim: fo=a tw=80 colorcolumn=80 syntax=markdown :
-->

SLCAN over TCP tunnel
=====================

Simple SLCAN implementation that tunnels the SLCAN protocol over TCP. Has a lot
of overhead and miserable timing, but is super easy to deploy.


How to forward an existing CAN netdev over network
--------------------------------------------------

To forward an interface `can0` from `SRC` to an interface `slcan0` on `DST`,
create an SLCAN tunnel server on one side and a client on the other, such, that
they are connected and `slcan0` is the corresponding interface on `SRC`. Then
bridge the slcan interface on SRC with the interface to be forwarded: 

		SRC:~# modprobe can_gw
		SRC:~# cangw -A -s can0 -d slcan0 -f 0:0 -e
		SRC:~# cangw -A -d can0 -s slcan0 -f 0:0 -e

This will copy all CAN frames between `can0` and `slcan0` on `SRC`. The slcan
connection takes care to copy all frames between `slcan0` on `SRC` and `slcan0`
on `DST`. Thus you can use `slcan0` on `DST`, as if it was `can0` on `SRC`. With
quite a performance impact, though.


How to reduce the network overhead
----------------------------------

Running SLCAN over TCP roughly has factor 5 of overhead. I.e. for a 100000kbaud
CAN bus that is saturated, we get ~500KBit of network traffic. Thats a lot.

To reduce the overhead, the slcan-tcp-tunnel script has option '-x' for simple
compression. This is OFF by default, as it is not SLCAN standard conform.

The majority of the transmitted traffic will be 't' and 'T' lines of the SLCAN
protocol. The easiest way to reduce overhead is to recompress these lines in the
most simple way:

		tiiil[dd...]\r
		is translated into:
		t\x0i\xii\x0l[\xdd...]\r

		e.g.:
		t012188\r becomes t\x00\x12\x01\x88\r

Same for extended ID frames:

		Tiiiiiiiil[dd...]\r
		is translated into:
		T\xii\xii\xii\xii\x0l[\xdd...]\r

All other commands of the SLCAN protocol stay as-is. This reduces the overhead
of the bulk, i.e. all can frames, by almost half - while keeping the complexity
very low. Sadly, as the data in CAN frames can be arbitrary data, we loose the
line-basedness of the SLCAN protocoll, as CAN frames can contain the \r byte.


Authors
-------

David R. Piegdon <dgit@piegdon.de>


License
-------

All files in this repository are released unter the GNU General Public License
Version 3 or later. See the file COPYING for more information.

