import unittest
import sys,os,glob
sys.path.append(os.path.join(sys.path[0],".."))
import globals
from globals import OPTS

class openram_test(unittest.TestCase):
    """ Base unit test that we have some shared classes in. """
    
    def local_drc_check(self, w):
        tempgds = OPTS.openram_temp + "temp.gds"
        w.gds_write(tempgds)
        import verify
        self.assertFalse(verify.run_drc(w.name, tempgds))

        files = glob.glob(OPTS.openram_temp + '*')
        for f in files:
            os.remove(f)        
    
    def local_check(self, a):
        
        tempspice = OPTS.openram_temp + "temp.sp"
        tempgds = OPTS.openram_temp + "temp.gds"

        a.sp_write(tempspice)
        a.gds_write(tempgds)

        import verify
        try:
            self.assertFalse(verify.run_drc(a.name, tempgds)==0)
        except:
            self.reset()
            raise Exception('DRC failed: {}'.format(a.name))
            
        try:
            self.assertFalse(verify.run_lvs(a.name, tempgds, tempspice)==0)
        except:
            self.reset()
            raise Exception('LVS failed: {}'.format(a.name))

        self.cleanup()            

    def cleanup(self):
        """ Reset the duplicate checker and cleanup files. """
        self.reset()
        
        files = glob.glob(OPTS.openram_temp + '*')
        for f in files:
            # Only remove the files
            if os.path.isfile(f):
                os.remove(f)        

    def reset(self):
        """ Reset the static duplicate name checker for unit tests """
        import design
        design.design.name_map=[]

def isclose(value1,value2,error_tolerance=1e-2):
    """ This is used to compare relative values. """
    import debug
    relative_diff = abs(value1 - value2) / max(value1,value2)
    check = relative_diff <= error_tolerance
    if not check:
        debug.info(1,"NOT CLOSE {0} {1} relative diff={2}".format(value1,value2,relative_diff))
    else:
        debug.info(2,"CLOSE {0} {1} relative diff={2}".format(value1,value2,relative_diff))
    return (check)

def relative_compare(value1,value2,error_tolerance):
    """ This is used to compare relative values. """
    if (value1==value2): # if we don't need a relative comparison!
        return True
    return (abs(value1 - value2) / max(value1,value2) <= error_tolerance)

def isapproxdiff(f1, f2, error_tolerance=0.001):
    """Compare two files.

    Arguments:

    f1 -- First file name

    f2 -- Second file name

    Return value:

    True if the files are the same, False otherwise.

    """
    import re
    import debug

    with open(f1, 'rb') as fp1, open(f2, 'rb') as fp2:
        while True:
            b1 = fp1.readline()
            b2 = fp2.readline()
            #print "b1:",b1,
            #print "b2:",b2,

            # 1. Find all of the floats using a regex
            numeric_const_pattern = r"""
            [-+]? # optional sign
            (?:
            (?: \d* \. \d+ ) # .1 .12 .123 etc 9.1 etc 98.1 etc
            |
            (?: \d+ \.? ) # 1. 12. 123. etc 1 12 123 etc
            )
            # followed by optional exponent part if desired
            (?: [Ee] [+-]? \d+ ) ?
            """
            rx = re.compile(numeric_const_pattern, re.VERBOSE)
            b1_floats=rx.findall(b1)
            b2_floats=rx.findall(b2)
            debug.info(3,"b1_floats: "+str(b1_floats))
            debug.info(3,"b2_floats: "+str(b2_floats))
        
            # 2. Remove the floats from the string
            for f in b1_floats:
                b1=b1.replace(str(f),"",1)
            for f in b2_floats:
                b2=b2.replace(str(f),"",1)
            #print "b1:",b1,
            #print "b2:",b2,
            
            # 3. Check if remaining string matches
            if b1 != b2:
                debug.info(1,"Line: {0}\n!=\nLine: {1}".format(b1,b2))
                return False

        # 4. Now compare that the floats match
            if len(b1_floats)!=len(b2_floats):
                debug.info(1,"Len {0} != {1}".format(len(b1_floats),len(b2_floats)))
                return False
            for (f1,f2) in zip(b1_floats,b2_floats):
                if not relative_compare(float(f1),float(f2),error_tolerance):
                    debug.info(1, "Float {0} != {1}".format(f1,f2))
                    return False

            if not b1:
                return True


def isdiff(file1,file2):
    """ This is used to compare two files and display the diff if they are different.. """
    import debug
    import filecmp
    import difflib
    check = filecmp.cmp(file1,file2)
    if not check:
        debug.info(2,"MISMATCH {0} {1}".format(file1,file2))
        f1 = open(file1,"r")
        s1 = f1.readlines()
        f2 = open(file2,"r")
        s2 = f2.readlines()
        for line in difflib.unified_diff(s1, s2):
            debug.info(3,line)
        debug.error("MISMATCH {0} {1}".format(file1,file2))            
    else:
        debug.info(2,"MATCH {0} {1}".format(file1,file2))
    return (check)

def header(filename, technology):
    tst = "Running Test for:"
    print "\n"
    print " ______________________________________________________________________________ "
    print "|==============================================================================|"
    print "|=========" + tst.center(60) + "=========|"
    print "|=========" + technology.center(60) + "=========|"
    print "|=========" + filename.center(60) + "=========|"
    from  globals import OPTS
    print "|=========" + OPTS.openram_temp.center(60) + "=========|"
    print "|==============================================================================|"
