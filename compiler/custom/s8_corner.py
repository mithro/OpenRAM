# See LICENSE for licensing information.
#
# Copyright (c) 2016-2019 Regents of the University of California and The Board
# of Regents for the Oklahoma Agricultural and Mechanical College
# (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#

import debug
import design
import utils
from tech import layer, GDS


class s8_corner(design.design):

    def __init__(self, location, name=""):
        super().__init__(name)
        
        if location == "ul":
            self.name = "s8sram16x16_corner"
        elif location == "ur":
            self.name = "s8sram16x16_cornerb"
        elif location == "ll":
            self.name = "s8sram16x16_cornera"
        elif location == "lr":
            self.name = "s8sram16x16_cornera"
        else:
            debug.error("Invalid s8_corner location", -1)
        design.design.__init__(self, name=self.name)
        (self.width, self.height) = utils.get_libcell_size(self.name,
                                                           GDS["unit"],
                                                           layer["mem"])
        # pin_map = utils.get_libcell_pins(pin_names, self.name, GDS["unit"])
