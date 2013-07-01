# Copyright (c) 2012 Intel, Inc.
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
    Returns block size for file object 'file_obj'. Errors are indicated by the
    'IOError' exception.
    """

    from fcntl import ioctl
    import struct

    # Get the block size of the host file-system for the image file by calling
    # the FIGETBSZ ioctl (number 2).
    binary_data = ioctl(file_obj, 2, struct.pack('I', 0))
    return struct.unpack('I', binary_data)[0]
