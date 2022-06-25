# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et ai si
#
# Copyright (c) 2022 Benedikt Wildenhain
# License: GPLv2
# Author: Benedikt Wildenhain <benedikt.wildenhain@hs-bochum.de>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License, version 2 or any later version,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

import unittest

import os
import subprocess
import sys
import tempfile
import tests.helpers


class TestCLI(unittest.TestCase):
    def test_valid_signature(self):
        completed_process = subprocess.run(
            [
                "./bmaptool",
                "copy",
                "--bmap",
                "tests/test-data/test.image.bmap.v2.0",
                "--bmap-sig",
                "tests/test-data/test.image.bmap.v2.0.valid-sig",
                "tests/test-data/test.image.gz",
                self.tmpfile,
            ],
            check=False,
        )
        self.assertEqual(completed_process.returncode, 0)

    def test_unknown_signer(self):
        completed_process = subprocess.run(
            [
                "./bmaptool",
                "copy",
                "--bmap",
                "tests/test-data/test.image.bmap.v2.0",
                "--bmap-sig",
                "tests/test-data/test.image.bmap.v2.0.sig-by-wrong-key",
                "tests/test-data/test.image.gz",
                self.tmpfile,
            ],
            check=False,
        )
        self.assertEqual(completed_process.returncode, 1)

    def test_wrong_signature(self):
        completed_process = subprocess.run(
            [
                "./bmaptool",
                "copy",
                "--bmap",
                "tests/test-data/test.image.bmap.v1.4",
                "--bmap-sig",
                "tests/test-data/test.image.bmap.v2.0.valid-sig",
                "tests/test-data/test.image.gz",
                self.tmpfile,
            ],
            check=False,
        )
        self.assertEqual(completed_process.returncode, 1)

    def test_wrong_signature_uknown_signer(self):
        completed_process = subprocess.run(
            [
                "./bmaptool",
                "copy",
                "--bmap",
                "tests/test-data/test.image.bmap.v1.4",
                "--bmap-sig",
                "tests/test-data/test.image.bmap.v2.0.sig-by-wrong-key",
                "tests/test-data/test.image.gz",
                self.tmpfile,
            ],
            check=False,
        )
        self.assertEqual(completed_process.returncode, 1)

    def setUp(self):
        os.environ["GNUPGHOME"] = "tests/test-data/gnupg/"
        self.tmpfile = tempfile.mkstemp(prefix="testfile_", dir=".")[1]

    def tearDown(self):
        os.unlink(self.tmpfile)


if __name__ == "__main__":
    unittest.main()
