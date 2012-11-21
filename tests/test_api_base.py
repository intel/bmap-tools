""" This test verifies the base bmap creation and copying API functionality. It
generates a random sparse file, then creates a bmap fir this file and copies it
to a different file using the bmap. Then it compares the original random sparse
file and the copy and verifies that they are identical. """

# Disable the following pylint recommendations:
#   *  Too many instance attributes - R0902
#   *  Too many public methods - R0904
# pylint: disable=R0902,R0904

import os
import tempfile
import random
import filecmp
import unittest
from bmaptools import BmapCreate, BmapCopy, BmapHelpers

# Size of the image to generate and test
IMAGE_SIZE = 65 * 1024 * 1024

def create_random_sparse_file(file_obj, size):
    """ Create a sparse file with randomly distributed holes. The mapped areas
    are filled with random data. """

    block_size = BmapHelpers.get_block_size(file_obj)
    blocks_cnt = (size + block_size - 1) / block_size

    for block in xrange(0, blocks_cnt):
        is_mapped = bool(random.randint(0, 1))

        if is_mapped:
            file_obj.seek(block * block_size)
            file_obj.write(bytearray(os.urandom(block_size)))
        else:
            file_obj.truncate((block + 1) * block_size)

    file_obj.flush()

class TestCreateCopy(unittest.TestCase):
    """" A basic test for the bmap creation and copying functionality. It first
    generates a bmap for a sparse file, and then copies the sparse file to a
    different file, and then checks that all the blocks were copied. The
    original sparse file is generated randomly. The test entry point is the
    'test()' method. """

    # Pylint does not like the 'setUP' and 'tearDown' names - mute it.
    # pylint: disable=C0103
    def setUp(self):
        """ Initialize the test - called by the unittest framework before the
        test starts. """

        self._image_size = IMAGE_SIZE

        # Create and open a temporary file for the image
        (file_obj, self._image_path) = tempfile.mkstemp()
        self._f_image = os.fdopen(file_obj, "wb+")

        # Create and open a temporary file for a copy of the copy
        (file_obj, self._copy_path) = tempfile.mkstemp()
        self._f_copy = os.fdopen(file_obj, "wb+")

        # Create and open 2 temporary files for the bmap
        (file_obj, self._bmap1_path) = tempfile.mkstemp()
        self._f_bmap1 = os.fdopen(file_obj, "w+")
        (file_obj, self._bmap2_path) = tempfile.mkstemp()
        self._f_bmap2 = os.fdopen(file_obj, "w+")

    def tearDown(self):
        """ The clean-up method - called by the unittest framework when the
        test finishes. """

        self._f_image.close()
        os.remove(self._image_path)

        self._f_copy.close()
        os.remove(self._copy_path)

        self._f_bmap1.close()
        os.remove(self._bmap1_path)
        self._f_bmap2.close()
        os.remove(self._bmap2_path)

    # pylint: enable=C0103

    def test(self):
        """ The test entry point. Executed by the unittest framework after the
        'setUp()' method. """

        # Create a sparse file with randomly distributed holes
        create_random_sparse_file(self._f_image, self._image_size)

        #
        # Pass 1: generate the bmap, copy and compare
        #

        # Create bmap for the random sparse file
        creator = BmapCreate.BmapCreate(self._image_path, self._bmap1_path)
        creator.generate()

        # Copy the random sparse file to a different file using bmap
        writer = BmapCopy.BmapCopy(self._image_path, self._copy_path,
                                   self._bmap1_path)
        writer.copy(False, True)

        # Compare the original file and the copy are identical
        filecmp.cmp(self._image_path, self._copy_path, False)

        #
        # Pass 2: same as pass 1, but use file objects instead of paths
        #

        creator = BmapCreate.BmapCreate(self._f_image, self._f_bmap2)
        creator.generate()

        writer = BmapCopy.BmapCopy(self._f_image, self._f_copy, self._f_bmap2)
        writer.copy(False, True)

        filecmp.cmp(self._image_path, self._copy_path, False)

        # Make sure the bmap files generated at pass 1 and pass 2 are identical
        filecmp.cmp(self._bmap1_path, self._bmap2_path, False)

        #
        # Pass 3: repeat pass 2 to make sure the same 'BmapCreate' and
        # 'BmapCopy' objects can be used more than once.
        #
        creator.generate()
        creator.generate()
        writer.copy(True, False)
        writer.copy(False, True)
        writer.sync()
        filecmp.cmp(self._image_path, self._copy_path, False)
        filecmp.cmp(self._bmap1_path, self._bmap2_path, False)

        #
        # Pass 4: copy the sparse file without bmap and make sure it is
        # identical to the original file
        #
        writer = BmapCopy.BmapCopy(self._f_image, self._copy_path)
        writer.copy(True, True)
        filecmp.cmp(self._image_path, self._copy_path, False)

        writer = BmapCopy.BmapCopy(self._f_image, self._f_copy)
        writer.copy(False, True)
        filecmp.cmp(self._image_path, self._copy_path, False)
