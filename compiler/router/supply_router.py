import gdsMill
import tech
from contact import contact
import math
import debug
from globals import OPTS
from pin_layout import pin_layout
from vector import vector
from vector3d import vector3d 
from router import router
from direction import direction
import grid_utils

class supply_router(router):
    """
    A router class to read an obstruction map from a gds and
    routes a grid to connect the supply on the two layers.
    """

    def __init__(self, layers, design, gds_filename=None):
        """
        This will route on layers in design. It will get the blockages from
        either the gds file name or the design itself (by saving to a gds file).
        """
        router.__init__(self, layers, design, gds_filename)
        

        # The list of supply rails (grid sets) that may be routed
        self.supply_rails = {}
        self.supply_rail_wires = {}        
        # This is the same as above but as a sigle set for the all the rails
        self.supply_rail_tracks = {}
        self.supply_rail_wire_tracks = {}        
        
        # Power rail width in grid units.
        self.rail_track_width = 2

        
    def create_routing_grid(self):
        """ 
        Create a sprase routing grid with A* expansion functions.
        """
        size = self.ur - self.ll
        debug.info(1,"Size: {0} x {1}".format(size.x,size.y))

        import supply_grid
        self.rg = supply_grid.supply_grid(self.ll, self.ur, self.track_width)
    
    def route(self, vdd_name="vdd", gnd_name="gnd"):
        """ 
        Add power supply rails and connect all pins to these rails.
        """
        debug.info(1,"Running supply router on {0} and {1}...".format(vdd_name, gnd_name))
        self.vdd_name = vdd_name
        self.gnd_name = gnd_name

        # Clear the pins if we have previously routed
        if (hasattr(self,'rg')):
            self.clear_pins()
        else:
            # Creat a routing grid over the entire area
            # FIXME: This could be created only over the routing region,
            # but this is simplest for now.
            self.create_routing_grid()

        # Get the pin shapes
        self.find_pins_and_blockages([self.vdd_name, self.gnd_name])

        #self.write_debug_gds("pin_enclosures.gds",stop_program=True)

        # Add the supply rails in a mesh network and connect H/V with vias
        # Block everything
        self.prepare_blockages(self.gnd_name)
        # Determine the rail locations
        self.route_supply_rails(self.gnd_name,0)
        
        # Block everything
        self.prepare_blockages(self.vdd_name)
        # Determine the rail locations
        self.route_supply_rails(self.vdd_name,1)
        #self.write_debug_gds("debug_rails.gds",stop_program=True)
        
        remaining_vdd_pin_indices = self.route_simple_overlaps(vdd_name)
        remaining_gnd_pin_indices = self.route_simple_overlaps(gnd_name)
        #self.write_debug_gds("debug_simple_route.gds",stop_program=True)
        
        # Route the supply pins to the supply rails
        # Route vdd first since we want it to be shorter
        self.route_pins_to_rails(vdd_name, remaining_vdd_pin_indices)
        self.route_pins_to_rails(gnd_name, remaining_gnd_pin_indices)
        #self.write_debug_gds("debug_pin_routes.gds",stop_program=True)
        
        return True


                
                
    
    def route_simple_overlaps(self, pin_name):
        """
        This checks for simple cases where a pin component already overlaps a supply rail.
        It will add an enclosure to ensure the overlap in wide DRC rule cases.
        """
        num_components = self.num_pin_components(pin_name)
        remaining_pins = []
        supply_tracks = self.supply_rail_tracks[pin_name]

        for index in range(num_components):
            pin_in_tracks = self.pin_grids[pin_name][index]
            common_set = supply_tracks & pin_in_tracks

            if len(common_set)==0:
                # if no overlap, add it to the complex route pins
                remaining_pins.append(index)
            else:
                print("Overlap!",index)
                self.create_simple_overlap_enclosure(pin_name, common_set)
            
        return remaining_pins

    def recurse_simple_overlap_enclosure(self, pin_name, start_set, direct):
        """
        Recursive function to return set of tracks that connects to
        the actual supply rail wire in a given direction (or terminating
        when any track is no longer in the supply rail.
        """
        next_set = grid_utils.expand_border(start_set, direct)

        supply_tracks = self.supply_rail_tracks[pin_name]
        supply_wire_tracks = self.supply_rail_wire_tracks[pin_name]
        
        supply_overlap = next_set & supply_tracks
        wire_overlap = next_set & supply_wire_tracks

        print("EXAMINING: ",start_set,len(start_set),len(supply_overlap),len(wire_overlap),direct)
        # If the rail overlap is the same, we are done, since we connected to the actual wire
        if len(wire_overlap)==len(start_set):
            print("HIT RAIL", wire_overlap)
            new_set = start_set | wire_overlap
        # If the supply overlap is the same, keep expanding unti we hit the wire or move out of the rail region
        elif len(supply_overlap)==len(start_set):
            print("RECURSE", supply_overlap)
            recurse_set = self.recurse_simple_overlap_enclosure(pin_name, supply_overlap, direct)
            new_set = start_set | supply_overlap | recurse_set
        else:
            # If we got no next set, we are done, can't expand!
            print("NO MORE OVERLAP", supply_overlap)
            new_set = set()
            
        return new_set
            
    def create_simple_overlap_enclosure(self, pin_name, start_set):
        """
        This takes a set of tracks that overlap a supply rail and creates an enclosure
        that is ensured to overlap the supply rail wire.
        It then adds rectangle(s) for the enclosure.
        """
        additional_set = set()
        # Check the layer of any element in the pin to determine which direction to route it
        e = next(iter(start_set))
        new_set = start_set.copy()
        if e.z==0:
            new_set = self.recurse_simple_overlap_enclosure(pin_name, start_set, direction.NORTH)
            if not new_set:
                new_set = self.recurse_simple_overlap_enclosure(pin_name, start_set, direction.SOUTH)
        else:
            new_set = self.recurse_simple_overlap_enclosure(pin_name, start_set, direction.EAST)
            if not new_set:
                new_set = self.recurse_simple_overlap_enclosure(pin_name, start_set, direction.WEST)

        enclosure_list = self.compute_enclosures(new_set)
        for pin in enclosure_list:
            debug.info(2,"Adding simple overlap enclosure {0} {1}".format(pin_name, pin))
            self.cell.add_rect(layer=pin.layer,
                               offset=pin.ll(),
                               width=pin.width(),
                               height=pin.height())



    
    def finalize_supply_rails(self, name):
        """
        Determine which supply rails overlap and can accomodate a via.
        Remove any supply rails that do not have a via since they are disconnected.
        NOTE: It is still possible though unlikely that there are disconnected groups of rails.
        """

        all_rails = self.supply_rail_wires[name]

        connections = set()
        via_areas = []
        for i1,r1 in enumerate(all_rails):
            # We need to move this rail to the other layer for the intersection to work
            e = next(iter(r1))
            newz = (e.z+1)%2
            new_r1 = {vector3d(i.x,i.y,newz) for i in r1}
            for i2,r2 in enumerate(all_rails):
                if i1==i2:
                    continue
                overlap = new_r1 & r2
                if len(overlap) >= self.supply_rail_wire_width**2:
                    connections.add(i1)
                    connections.add(i2)
                    via_areas.append(overlap)
                
        # Go through and add the vias at the center of the intersection
        for area in via_areas:
            ll = grid_utils.get_lower_left(area)
            ur = grid_utils.get_upper_right(area)
            center = (ll + ur).scale(0.5,0.5,0)
            self.add_via(center,self.rail_track_width)

        all_indices = set([x for x in range(len(self.supply_rails[name]))])
        missing_indices = all_indices ^ connections

        for rail_index in missing_indices:
            ll = grid_utils.get_lower_left(all_rails[rail_index])
            ur = grid_utils.get_upper_right(all_rails[rail_index])
            debug.info(1,"Removing disconnected supply rail {0} .. {1}".format(ll,ur))
            self.supply_rails[name].pop(rail_index)
            self.supply_rail_wires[name].pop(rail_index)            

        # Make the supply rails into a big giant set of grids
        # Must be done after determine which ones are connected)
        self.create_supply_track_set(name)
        
            
    def add_supply_rails(self, name):
        """
        Add the shapes that represent the routed supply rails.
        This is after the paths have been pruned and only include rails that are
        connected with vias.
        """
        for rail in self.supply_rails[name]:
            ll = grid_utils.get_lower_left(rail)
            ur = grid_utils.get_upper_right(rail)        
            z = ll.z
            pin = self.compute_wide_enclosure(ll, ur, z, name)
            debug.info(1,"Adding supply rail {0} {1}->{2} {3}".format(name,ll,ur,pin))
            self.cell.add_layout_pin(text=name,
                                     layer=pin.layer,
                                     offset=pin.ll(),
                                     width=pin.width(),
                                     height=pin.height())

    def compute_supply_rail_dimensions(self):
        """
        Compute the supply rail dimensions including wide metal spacing rules.
        """
        
        self.max_yoffset = self.rg.ur.y
        self.max_xoffset = self.rg.ur.x

        # Longest length is conservative
        rail_length = max(self.max_yoffset,self.max_xoffset)
        # Convert the number of tracks to dimensions to get the design rule spacing
        rail_width = self.track_width*self.rail_track_width

        # Get the conservative width and spacing of the top rails
        (horizontal_width, horizontal_space) = self.get_layer_width_space(0, rail_width, rail_length)
        (vertical_width, vertical_space) = self.get_layer_width_space(1, rail_width, rail_length)
        width = max(horizontal_width, vertical_width)
        space = max(horizontal_space, vertical_space)
        
        # This is the supply rail pitch in terms of routing grids
        # i.e. a rail of self.rail_track_width needs this many tracks including
        # space
        track_pitch = self.rail_track_width*width + space

        # Determine the pitch (in tracks) of the rail wire + spacing
        self.supply_rail_width = math.ceil(track_pitch/self.track_width)
        debug.info(1,"Rail step: {}".format(self.supply_rail_width))
        
        # Conservatively determine the number of tracks that the rail actually occupies
        space_tracks = math.ceil(space/self.track_width)
        self.supply_rail_wire_width = self.supply_rail_width - space_tracks
        debug.info(1,"Rail wire tracks: {}".format(self.supply_rail_wire_width))
        total_space = self.supply_rail_width - self.supply_rail_wire_width
        debug.check(total_space % 2 == 0, "Asymmetric wire track spacing...")
        self.supply_rail_space_width = int(0.5*total_space)
        debug.info(1,"Rail space tracks: {} (on both sides)".format(self.supply_rail_space_width))


    def compute_supply_rails(self, name, supply_number):
        """
        Compute the unblocked locations for the horizontal and vertical supply rails.
        Go in a raster order from bottom to the top (for horizontal) and left to right
        (for vertical). Start with an initial start_offset in x and y direction.
        """

        self.supply_rails[name]=[]
        self.supply_rail_wires[name]=[]        
        
        start_offset = supply_number*self.supply_rail_width

        # Horizontal supply rails
        for offset in range(start_offset, self.max_yoffset, 2*self.supply_rail_width):
            # Seed the function at the location with the given width
            wave = [vector3d(0,offset+i,0) for i in range(self.supply_rail_width)]
            # While we can keep expanding east in this horizontal track
            while wave and wave[0].x < self.max_xoffset:
                added_rail = self.find_supply_rail(name, wave, direction.EAST)
                if added_rail:
                    wave = added_rail.neighbor(direction.EAST)
                else:
                    wave = None


        # Vertical supply rails
        max_offset = self.rg.ur.x
        for offset in range(start_offset, self.max_xoffset, 2*self.supply_rail_width):
            # Seed the function at the location with the given width
            wave = [vector3d(offset+i,0,1) for i in range(self.supply_rail_width)]
            # While we can keep expanding north in this vertical track
            while wave and wave[0].y < self.max_yoffset:
                added_rail = self.find_supply_rail(name, wave, direction.NORTH)
                if added_rail:
                    wave = added_rail.neighbor(direction.NORTH)
                else:
                    wave = None

    def find_supply_rail(self, name, seed_wave, direct):
        """
        Find a start location, probe in the direction, and see if the rail is big enough
        to contain a via, and, if so, add it.
        """
        start_wave = self.find_supply_rail_start(name, seed_wave, direct)
        if not start_wave:
            return None
        
        wave_path = self.probe_supply_rail(name, start_wave, direct)
        
        if self.approve_supply_rail(name, wave_path):
            return wave_path
        else:
            return None

    def find_supply_rail_start(self, name, seed_wave, direct):
        """
        This finds the first valid starting location and routes a supply rail
        in the given direction.
        It returns the space after the end of the rail to seed another call for multiple
        supply rails in the same "track" when there is a blockage.
        """
        # Sweep to find an initial unblocked valid wave
        start_wave = self.rg.find_start_wave(seed_wave, len(seed_wave), direct)

        return start_wave
    
    def probe_supply_rail(self, name, start_wave, direct):
        """
        This finds the first valid starting location and routes a supply rail
        in the given direction.
        It returns the space after the end of the rail to seed another call for multiple
        supply rails in the same "track" when there is a blockage.
        """

        # Expand the wave to the right
        wave_path = self.rg.probe(start_wave, direct)

        if not wave_path:
            return None

        # drop the first and last steps to leave escape routing room
        # around the blockage that stopped the probe
        # except, don't drop the first if it is the first in a row/column
        if (direct==direction.NORTH and start_wave[0].y>0):
            wave_path.trim_first()
        elif (direct == direction.EAST and start_wave[0].x>0):
            wave_path.trim_first()

        wave_path.trim_last()
            
        return wave_path

    def approve_supply_rail(self, name, wave_path):
        """
        Check if the supply rail is sufficient (big enough) and add it to the
        data structure. Return whether it was added or not.
        """
        # We must have at least 2 tracks to drop plus 2 tracks for a via
        if len(wave_path)>=4*self.rail_track_width:
            grid_set = wave_path.get_grids()
            self.supply_rails[name].append(grid_set)
            start_wire_index = self.supply_rail_space_width
            end_wire_index = self.supply_rail_width - self.supply_rail_space_width
            wire_set = wave_path.get_wire_grids(start_wire_index,end_wire_index)
            self.supply_rail_wires[name].append(wire_set)
            return True
        
        return False

    

                    
                
    def route_supply_rails(self, name, supply_number):
        """
        Route the horizontal and vertical supply rails across the entire design.
        Must be done with lower left at 0,0
        """

        # Compute the grid dimensions
        self.compute_supply_rail_dimensions()
        
        # Compute the grid locations of the supply rails
        self.compute_supply_rails(name, supply_number)
        
        # Add the supply rail vias (and prune disconnected rails)
        self.finalize_supply_rails(name)

        # Add the rails themselves
        self.add_supply_rails(name)

        
    def create_supply_track_set(self, pin_name):
        """
        Make a single set of all the tracks for the rail and wire itself.
        """
        rail_set = set()
        for rail in self.supply_rails[pin_name]:
            rail_set.update(rail)
        self.supply_rail_tracks[pin_name] = rail_set

        wire_set = set()
        for rail in self.supply_rail_wires[pin_name]:
            wire_set.update(rail)
        self.supply_rail_wire_tracks[pin_name] = wire_set

        
    def route_pins_to_rails(self, pin_name, remaining_component_indices):
        """
        This will route each of the remaining pin components to the supply rails. 
        After it is done, the cells are added to the pin blockage list.
        """

        
        debug.info(1,"Pin {0} has {1} remaining components to route.".format(pin_name,
                                                                             len(remaining_component_indices)))

        recent_paths = []
        # For every component
        for index in remaining_component_indices:
            debug.info(2,"Routing component {0} {1}".format(pin_name, index))
            
            self.rg.reinit()
            
            self.prepare_blockages(pin_name)
            
            # Add the single component of the pin as the source
            # which unmarks it as a blockage too
            self.add_pin_component_source(pin_name,index)

            # Add all of the rails as targets
            # Don't add the other pins, but we could?
            self.add_supply_rail_target(pin_name)

            # Add the previous paths as targets too
            #self.add_path_target(recent_paths)

            #print(self.rg.target)
            
            # Actually run the A* router
            if not self.run_router(detour_scale=5):
                self.write_debug_gds()
            
            recent_paths.append(self.paths[-1])

    
    def add_supply_rail_target(self, pin_name):
        """
        Add the supply rails of given name as a routing target.
        """
        debug.info(2,"Add supply rail target {}".format(pin_name))
        # Add the wire itself as the target
        self.rg.set_target(self.supply_rail_wire_tracks[pin_name])
        # But unblock all the rail tracks including the space
        self.rg.set_blocked(self.supply_rail_tracks[pin_name],False)

                
    def set_supply_rail_blocked(self, value=True):
        """
        Add the supply rails of given name as a routing target.
        """
        debug.info(3,"Blocking supply rail")        
        for rail_name in self.supply_rail_tracks:
            self.rg.set_blocked(self.supply_rail_tracks[rail_name])
                
