#!/usr/bin/env python3
# See LICENSE for licensing information.
#
# Copyright (c) 2016-2019 Regents of the University of California and The Board
# of Regents for the Oklahoma Agricultural and Mechanical College
# (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
"""
Run a regression test on a basic array
"""

import unittest
from testutils import header,openram_test
import sys,os
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS
from sram_factory import factory
import debug

#@unittest.skip("SKIPPING 05_pbitcell_array_test")
class pbitcell_array_test(openram_test):

    def runTest(self):
        globals.init_openram("config_{0}".format(OPTS.tech_name))

        debug.info(2, "Testing 4x4 array for multiport bitcell, with read ports at the edge of the bit cell")
        OPTS.bitcell = "pbitcell"
        OPTS.num_rw_ports = 2
        OPTS.num_r_ports = 2
        OPTS.num_w_ports = 2
        a = factory.create(module_type="bitcell_array", cols=4, rows=4)
        self.local_check(a)
            
        debug.info(2, "Testing 4x4 array for multiport bitcell, with write ports at the edge of the bit cell")
        OPTS.bitcell = "pbitcell"
        OPTS.num_rw_ports = 2
        OPTS.num_r_ports = 0
        OPTS.num_w_ports = 2
        a = factory.create(module_type="bitcell_array", cols=4, rows=4)
        self.local_check(a)
        
        debug.info(2, "Testing 4x4 array for multiport bitcell, with read/write ports at the edge of the bit cell")
        OPTS.bitcell = "pbitcell"
        OPTS.num_rw_ports = 2
        OPTS.num_r_ports = 0
        OPTS.num_w_ports = 0
        a = factory.create(module_type="bitcell_array", cols=4, rows=4)
        self.local_check(a)

        globals.end_openram()

# run the test from the command line
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
