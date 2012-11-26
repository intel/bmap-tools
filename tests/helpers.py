""" This module contains independent functions shared between various
tests. """

import os
import tempfile
import random
import itertools
from bmaptools import BmapHelpers

def create_random_sparse_file(file_obj, size):
    """ Create a sparse file with randomly distributed holes. The mapped areas
    are filled with random data. Returns a list of unmapped block ranges
    (holes). """

    block_size = BmapHelpers.get_block_size(file_obj)
    blocks_cnt = (size + block_size - 1) / block_size

    def process_block(block):
        """ This is a helper function which processes a block. It randomly
        decides whether the block should be filled with random data or should
        become a hole. Returns 'True' if the block was mapped and 'False'
        otherwise. """

        map_the_block = bool(random.randint(0, 1))

        if map_the_block:
            file_obj.seek(block * block_size)
            file_obj.write(bytearray(os.urandom(block_size)))
        else:
            file_obj.truncate((block + 1) * block_size)

        return map_the_block

    holes = []
    iterator = xrange(0, blocks_cnt)
    for was_mapped, group in itertools.groupby(iterator, process_block):
        if not was_mapped:
            # Start of a hole. Find the last element in the group.
            first = group.next()
            last = first
            for last in group:
                pass

            holes.append((first, last))

    file_obj.truncate(size)
    file_obj.flush()

    return holes
