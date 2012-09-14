"""

Unit test for radicale.rights.from_file.

Tests reading the file. The processing is untested, yet.

"""


from radicale.rights import from_file
import unittest



class Test1(unittest.TestCase):
    
    def testProcessEmptyLine(self):
        """ Line with a comment """

        # Input values        
        line = " "
        read = {}
        write = {}
        
        try:
            # Call SUT
            from_file._process(line, read, write)
        except from_file.ParsingError:
            self.assertTrue(False)

        self.assertTrue(len(read.keys()) == 0)
        self.assertTrue(len(write.keys()) == 0)


    def testProcessComment(self):
        """ Line with a comment """

        # Input values        
        line = "# some comment"
        read = {}
        write = {}
        
        try:
            # Call SUT
            from_file._process(line, read, write)
        except from_file.ParsingError:
            self.assertTrue(False)

        self.assertTrue(len(read.keys()) == 0)
        self.assertTrue(len(write.keys()) == 0)


    def testProcess0a(self):
        """ Pointless line: no rights definitions """

        # Input values        
        line = "/user1/collection1 : "
        read = {}
        write = {}
        
        try:
            # Call SUT
            from_file._process(line, read, write)
        except from_file.ParsingError:
            self.fail("Unexpected exception")

        self.assertTrue(len(read.keys()) == 0)
        self.assertTrue(len(write.keys()) == 0)


    def testProcess1a(self):
        """ Malformed line: no collection definitions """

        # Input values        
        line = " : a b"
        read = {}
        write = {}
        
        try:
            # Call SUT
            from_file._process(line, read, write)
        except from_file.ParsingError:
            """Exception expected"""
        else:
            self.fail("Expected exception not raised")



    def testProcess1b(self):
        """ Malformed line: right "b" unknown """

        # Input values        
        line = "/user1/collection1 : a b"
        read = {}
        write = {}
        
        try:
            # Call SUT
            from_file._process(line, read, write)
        except from_file.ParsingError:
            """Exception expected"""
        else:
            self.fail("Expected exception not raised")


    def testProcess1c(self):
        """ Malformed line: user/right empty """

        # Input values        
        line = "/user1/collection1 : a"
        read = {}
        write = {}
        
        try:
            # Call SUT
            from_file._process(line, read, write)
        except from_file.ParsingError:
            """Exception expected"""
        else:
            self.fail("Expected exception not raised")


    def testProcess2(self):
        """Actual sensible input all of which means the same"""

        lines = [
                 "/user1/collection1 : other1 r, other2 w, other6 rw",
                 "/user1/collection1/ : other1 r, other2 w, other6 rw",
                 "/user1/collection1: other1 r, other2 w, other6 rw",
                 "/user1/collection1/: other1 r, other2 w, other6 rw",
                 "/user1/collection1: other1  r,    other2 w,other6 rw",
                 "/user1/collection1 :other1 r,other2 w,   other6 rw",
                 "/user1/collection1\t:other1 r,\tother2 w,\tother6 rw",
                 ]

        for line in lines:
            # Input values        
            read = {}
            write = {}

            try:            
                # Call SUT
                from_file._process(line, read, write)
            except:
                self.fail("unexpected exception for input %s" % line)
            
            # Check
            self.assertEquals(len(read.keys()), 1, "keys in %s" % line)
            self.assertEquals(len(read.get("/user1/collection1")), 2, "rights in %s" % line)
            self.assertTrue(read.get("/user1/collection1").count("other1"), "other1 read in %s" % line)
            self.assertTrue(read.get("/user1/collection1").count("other6"), "other6 read in %s" % line)
    
            self.assertEquals(len(write.keys()), 1, "keys in %s" % line)
            self.assertEquals(len(write.get("/user1/collection1")), 2, "rights in %s" % line)
            self.assertTrue(write.get("/user1/collection1").count("other2"), "other2 write in %s" % line)
            self.assertTrue(write.get("/user1/collection1").count("other6"), "other6 write in %s" % line)





if __name__ == "__main__":
    unittest.main()