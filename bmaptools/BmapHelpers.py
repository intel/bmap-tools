"""
This module contains various helper functions which are shared between
BmapFlasher and BmapCreator or which are useful for users of bmaptools.
"""

def human_size(size):
    """ Transform size in bytes into a human-readable form. """

    for modifier in ["KiB", "MiB", "GiB", "TiB"]:
        size /= 1024.0
        if size < 1024:
            return "%.1f %s" % (size, modifier)

    return "%.1f %s" % (size, 'EiB')

def human_time(seconds):
    """ Transform time in seconds to the HH:MM:SS format. """

    (minutes, seconds) = divmod(seconds, 60)
    (hours, minutes) = divmod(minutes, 60)

    result = ""
    if hours:
        result = "%dh " % hours
    if minutes:
        result += "%dm " % minutes

    return result + "%.1fs" % seconds
