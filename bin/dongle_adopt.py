#!/usr/bin/env python
#
# Original espota.py by Ivan Grokhotkov:
# https://gist.github.com/igrr/d35ab8446922179dc58c
#
# Modified since 2015-09-18 from Pascal Gollor (https://github.com/pgollor)
# Modified since 2015-11-09 from Hristo Gochkov (https://github.com/me-no-dev)
# Modified since 2016-01-03 from Matthew O'Gorman (https://githumb.com/mogorman)
# Modified to support ulnoiot dongle adopt by ulno starting 2019-02-35
#
# This script will push an initial OTA update through a ESP dongle in the
# ulnoiot environment
#
# Use it like this: python dongle_adopt.py -p <usbport> -f <firmware.bin>


from __future__ import print_function
import socket
import sys
import os
import optparse
import logging
import hashlib
import random

import serial
import time

# Commands
PROGRESS = False

# update_progress() : Displays or updates a console progress bar
## Accepts a float between 0 and 1. Any int will be converted to a float.
## A value under 0 represents a 'halt'.
## A value at 1 or bigger represents 100%
def update_progress(progress):
  if (PROGRESS):
    barLength = 40 # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
      progress = float(progress)
    if not isinstance(progress, float):
      progress = 0
      status = "error: progress var must be float\r\n"
    if progress < 0:
      progress = 0
      status = "Halt...\r\n"
    if progress >= 1:
      progress = 1
      status = "Done...\r\n"
    block = int(round(barLength*progress))
    text = "\rUploading: [{0}] {1}% {2}".format( "="*block + " "*(barLength-block), int(progress*100), status)
    sys.stderr.write(text)
    sys.stderr.flush()
  else:
    sys.stderr.write('.')
    sys.stderr.flush()

def serve(filename, port):
    # Create a serial connection
    ser = serial.Serial(port, 2000000, timeout=15);
    logging.info('Starting on %s.', port)
    ser.read_all()  # discard all
    ser.write(b"\n")
    ser.flush()
    answer = ser.read_until(b"CMD>").decode()
    if not answer.endswith("CMD>"):
        sys.stderr.write("Trouble communicating with dongle.")
        return 1

    content_size = os.path.getsize(filename)
    f = open(filename,'rb')
    file_md5 = hashlib.md5(f.read()).hexdigest()
    f.close()

    logging.info('Upload size: %d', content_size)

    # show options
    print("Scanning for devices that can be adopted... ", end='', flush=True)
    ser.write(b"scan\n")
    ser.flush()
    if not ser.read_until(b"!network_scan start\r\n"):
        sys.stderr.write("Network scan failed.\n")
        return 1

    node_list = []
    while(True):
        l = ser.readline().decode().strip()
        if (not " " in l) or (l == "!network_scan end"):
            break
        strength, name = l.split(" ", 1)
        strength = int(strength)  # TODO: catch potential error here
        if name.startswith("uiot-node-"):
            node_list.append((name[10:], strength))

    print(" done.")

    if len(node_list) == 0:
        sys.stderr.write("No nodes that can be adopted found.\n")
        return 1

    # sort by strength
    node_list.sort(key=lambda x: (x[1],x[0]))

    print("Following nodes found (ranked by strength):")
    n=1
    for name,s in node_list:
        print("%d. %s (%d)"%(n,name,s))
        n += 1

    while True:
        n = input("Which one should be adopted? (enter number, default=1) ")
        if not n:
            n = 1
        else:
            try:
                n = int(n)
            except ValueError:
                n = -1
        n -= 1

        if n>=0 and n<len(node_list):
            break

    ser.write(("adopt uiot-node-%s %d %s\n"%(node_list[n][0], content_size, file_md5)).encode())
    ser.flush()

    while(True):
        answer = ser.readline()
        if not answer:
            sys.stderr.write("Trouble with dongle communication.\n")
            return 1
        answer = answer.strip()
        if answer.startswith(b"!error"):
            sys.stderr.write("Error:%s\n", answer[7:].decode())
            return 1
        if answer.startswith(b"!upload"):
            break
        print(answer)

    received_ok = False

    f = open(filename, "rb")
    if (PROGRESS):
        update_progress(0)
    else:
        sys.stderr.write('Uploading')
        sys.stderr.flush()
        offset = 0
    while offset < content_size:
        chunk = f.read(1460)
        if not chunk: break
        offset += len(chunk)
        update_progress(offset/float(content_size))
        ser.write(chunk)
        answer = ser.readline()
        if not answer:
            sys.stderr.write('Error uploading')
            f.close()
            return 1
        answer = answer.strip()
        if answer.startswith(b"!error"):
            sys.stderr.write("Error:%s\n", answer[7:].decode())
            return 1

    f.close()
    sys.stderr.write('\n')
    answer = ser.readline()
    if not answer:
        sys.stderr.write('Error finishing upload\n')
        return 1
    answer = answer.strip()
    if answer.startswith(b"!success"):
        sys.stderr.write('Success uploading\n')
    else:
        if answer.startswith(b"!error"):
            sys.stderr.write("Error:%s\n", answer[7:].decode())
        else:
            sys.stderr.write('Error uploading\n')
        return 1

    logging.info('Result: OK')
    return 0

    # end serve


def parser(unparsed_args):
  parser = optparse.OptionParser(
    usage = "%prog [options]",
    description = "Transmit initial image over the air over a dongle to the esp8266 module with OTA support."
  )

  # usb port
  group = optparse.OptionGroup(parser, "Destination")
  group.add_option("-p", "--port",
    dest = "esp_port",
    type = "str",
    help = "ESP8266 serial port. Default /dev/ttyUSB0",
    default = "/dev/ttyUSB0"
  )
  parser.add_option_group(group)

  # image
  group = optparse.OptionGroup(parser, "Image")
  group.add_option("-f", "--file",
    dest = "image",
    help = "Image file.",
    metavar="FILE",
    default = None
  )
  parser.add_option_group(group)

  # output group
  group = optparse.OptionGroup(parser, "Output")
  group.add_option("-d", "--debug",
    dest = "debug",
    help = "Show debug output. And override loglevel with debug.",
    action = "store_true",
    default = False
  )
  group.add_option("-r", "--progress",
    dest = "progress",
    help = "Show progress output. Does not work for ArduinoIDE",
    action = "store_true",
    default = False
  )
  parser.add_option_group(group)

  (options, args) = parser.parse_args(unparsed_args)

  return options
# end parser


def main(args):
  # get options
  options = parser(args)

  # adapt log level
  loglevel = logging.WARNING
  if (options.debug):
    loglevel = logging.DEBUG
  # end if

  # logging
  logging.basicConfig(level = loglevel, format = '%(asctime)-8s [%(levelname)s]: %(message)s', datefmt = '%H:%M:%S')

  logging.debug("Options: %s", str(options))

  # check options
  global PROGRESS
  PROGRESS = options.progress
  if not options.image:
    logging.critical("Not enough arguments.")

    return 1
  # end if

  return serve(options.image, options.esp_port)
# end main


if __name__ == '__main__':
  sys.exit(main(sys.argv))
# end if