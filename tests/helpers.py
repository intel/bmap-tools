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

    file_obj.truncate(0)
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

def generate_test_files(max_size = 4 * 1024 * 1024, directory = None):
    """ This is an iterator which generates files which other tests use as the
    input for the testing. The iterator tries to generate "interesting" files
    which cover various corner-cases. For example, a large hole file, a file
    with no holes, files of unaligned length, etc.

    The 'directory' argument specifies the directory path where the generated
    test files should be created.

    Returns a tuple consisting of the open file object and a list of unmapped
    block ranges (holes) in the file. """

    #
    # Generate sparse files with one single hole spanning the entire file
    #

    # A block-sized hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Khole_",
                                           dir = directory, suffix = ".img")
    block_size = BmapHelpers.get_block_size(file_obj)
    file_obj.truncate(block_size)
    yield (file_obj, [(0, 0)])
    file_obj.close()

    # A block size + 1 byte hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Khole_plus_1_",
                                           dir = directory, suffix = ".img")
    file_obj.truncate(block_size + 1)
    yield (file_obj, [(0, 0)])
    file_obj.close()

    # A block size - 1 byte hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "4Khole_minus_1_",
                                           dir = directory, suffix = ".img")
    file_obj.truncate(block_size - 1)
    yield (file_obj, [(0, 0)])
    file_obj.close()

    # A 1-byte hole
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "1byte_hole_",
                                           dir = directory, suffix = ".img")
    file_obj.truncate(1)
    yield (file_obj, [(0, 0)])
    file_obj.close()

    # And 10 holes of random size
    for i in xrange(10):
        size = random.randint(1, max_size)
        file_obj = tempfile.NamedTemporaryFile("wb+", suffix = ".img",
                                dir = directory, prefix = "rand_hole_%d_" % i)
        file_obj.truncate(size)
        blocks_cnt = (size + block_size - 1) / block_size
        yield (file_obj, [(0, blocks_cnt - 1)])
        file_obj.close()

    #
    # Generate a random sparse files
    #

    # The maximum size
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "sparse_",
                                           dir = directory, suffix = ".img")
    holes = create_random_sparse_file(file_obj, max_size)
    yield (file_obj, holes)
    file_obj.close()

    # The maximum size + 1 byte
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "sparse_plus_1_",
                                           dir = directory, suffix = ".img")
    holes = create_random_sparse_file(file_obj, max_size + 1)
    yield (file_obj, holes)
    file_obj.close()

    # The maximum size - 1 byte
    file_obj = tempfile.NamedTemporaryFile("wb+", prefix = "sparse_minus_1_",
                                           dir = directory, suffix = ".img")
    holes = create_random_sparse_file(file_obj, max_size - 1)
    yield (file_obj, holes)
    file_obj.close()

    # And 10 files of random size
    for i in xrange(10):
        size = random.randint(1, max_size)
        file_obj = tempfile.NamedTemporaryFile("wb+", suffix = ".img",
                                   dir = directory, prefix = "sparse_%d_" % i)
        holes = create_random_sparse_file(file_obj, size)
        yield (file_obj, holes)
        file_obj.close()
