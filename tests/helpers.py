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

def generate_test_files():
    """ This is an iterator which generates files which other tests use as the
    input for the testing. The iterator tries to generate "interesting" files
    which cover various corner-cases. For example, a large hole file, a file
    with no holes, files of unaligned length, etc.

    Returns a tuple consisting of the open file object and a list of unmapped
    block ranges (holes) in the file. """

    file_obj = tempfile.NamedTemporaryFile("wb+")

    # Generate a 8MiB random sparse file
    size = 8 * 1024 * 1024
    holes = create_random_sparse_file(file_obj, size)
    yield (file_obj, holes)

    # Do the same for random sparse files of size 8MiB +/- 1 byte
    holes = create_random_sparse_file(file_obj, size + 1)
    yield (file_obj, holes)

    holes = create_random_sparse_file(file_obj, size - 1)
    yield (file_obj, holes)

    file_obj.close()
