# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et ai si
#
# Copyright (c) 2012-2014 Intel, Inc.
# License: GPLv2
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

"""
This module contains various shared helper functions.
"""

import os
import struct
from fcntl import ioctl

def human_size(size):
    """Transform size in bytes into a human-readable form."""
    if size == 1:
        return "1 byte"

    if size < 512:
        return "%d bytes" % size

    for modifier in ["KiB", "MiB", "GiB", "TiB"]:
        size /= 1024.0
        if size < 1024:
            return "%.1f %s" % (size, modifier)

    return "%.1f %s" % (size, 'EiB')

def human_time(seconds):
    """Transform time in seconds to the HH:MM:SS format."""
    (minutes, seconds) = divmod(seconds, 60)
    (hours, minutes) = divmod(minutes, 60)

    result = ""
    if hours:
        result = "%dh " % hours
    if minutes:
        result += "%dm " % minutes

    return result + "%.1fs" % seconds

def get_block_size(file_obj):
    """
    Return block size for file object 'file_obj'. Errors are indicated by the
    'IOError' exception.
    """

    # Get the block size of the host file-system for the image file by calling
    # the FIGETBSZ ioctl (number 2).
    try:
        binary_data = ioctl(file_obj, 2, struct.pack('I', 0))
        bsize = struct.unpack('I', binary_data)[0]
        if not bsize:
            raise IOError("get 0 bsize by FIGETBSZ ioctl")
    except IOError as err:
        stat = os.fstat(file_obj.fileno())
        if hasattr(stat, 'st_blksize'):
            bsize = stat.st_blksize
        else:
            raise IOError("Unable to determine block size")
    return bsize

def program_is_available(name):
    """
    This is a helper function which check if the external program 'name' is
    available in the system.
    """

    for path in os.environ["PATH"].split(os.pathsep):
        program = os.path.join(path.strip('"'), name)
        if os.path.isfile(program) and os.access(program, os.X_OK):
            return True

    return False
