# Copyright (c) 2012-2013 Intel, Inc.
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
This unit test verifies that BmapCopy can handle all the bmap file formats and
have no backward-compatibility problems.
"""

import os
import shutil
import tempfile
from tests import helpers
from bmaptools import TransRead

# This is a work-around for Centos 6
try:
    import unittest2 as unittest
except ImportError:
    import unittest

class TestCreateCopy(unittest.TestCase):
    """
    The test class for this unit tests which executes the '_do_test()' function
    for various bmap file formats.
    """

    def test(self):
        """
        The test entry point. Executes the '_do_test()' function for various
        bmap file formats.
        """

        image_name = "test.image.gz"
        bmap_name  = "test.image.bmap.v"
        test_data_dir = "test-data"

        test_data_dir = os.path.join(os.path.dirname(__file__), test_data_dir)
        image_path = os.path.join(test_data_dir, image_name)


        # Get the list of bmap files to test
        bmap_paths = []
        for direntry in os.listdir(test_data_dir):
            direntry_path = os.path.join(test_data_dir, direntry)
            if os.path.isfile(direntry_path) and direntry.startswith(bmap_name):
                bmap_paths.append(direntry_path)

        # Create and open a temporary file for uncompressed image and its copy
        f_image = tempfile.NamedTemporaryFile("wb+", prefix=image_name,
                                              suffix=".image")
        f_copy = tempfile.NamedTemporaryFile("wb+", prefix=image_name,
                                             suffix=".copy")

        # Create an ucompressed version of the image file
        f_tmp_img = TransRead.TransRead(image_path)
        shutil.copyfileobj(f_tmp_img, f_image)
        f_tmp_img.close()
        f_image.flush()

        image_chksum = helpers.calculate_chksum(f_image.name)
        image_size = os.path.getsize(f_image.name)

        for bmap_path in bmap_paths:
            helpers.copy_and_verify_image(image_path, f_copy.name, bmap_path,
                                          image_chksum, image_size)

        f_copy.close()
        f_image.close()
