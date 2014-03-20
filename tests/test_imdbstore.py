#from __future__ import absolute_import

from .helpers import get_file_content
import radicale
import shutil
import tempfile
from xml.dom import minidom
from radicale import config
from tests import BaseTest
from .test_base import BaseRequests
import lmdb

MAP_SIZE = 1048576 * 400

def dumpDB(path):
    print ("db path: %s" % path)
    
    #return
    env = lmdb.open(path, map_size=MAP_SIZE, max_dbs=10000000)
    env.sync()
        
    print ("<<<<<<<<<<<<< db dump ")
    with env.begin(write=False,) as txn:
        #print "c: " , txn.get("c").decode("utf-8")
        for key, value in txn.cursor().iternext():
            if key.endswith(b".db"):
                # print key.decode("utf-8") , ":" # + value
                dumpNamedDB(env, key)     
            else:
                print (key.decode("utf-8")) # , ":" , value.decode("utf-8") 
            
    print (">>>>>>>>> db dump")

    
def dumpNamedDB(env, dbkey):
    db = env.open_db(name=dbkey)
    print ("<<<<<<<<<<<<< db dump %s" % dbkey.decode("utf-8"))
    with env.begin(write=False,db=db) as txn:
        for key, value in txn.cursor().iternext():
            if key.endswith(b".db"):
                print ('\t' +  key.decode("utf-8") + ":") # + value 
            else:
                try:
                    print ('\t' + key.decode("utf-8") + " -> "  + value.decode("utf-8"))
                except:
                    print ('\t' + "missing ...")
                    pass    
            
    print (">>>>>>>>> db dump")
    

class MoreBaseRequests(BaseRequests):
    """Tests with some more simple requests."""

    def test_propfind(self):
        """Test a PROPFIND request at "/bob/"."""

        status, headers, answer = self.request("PROPFIND", "/bob/",  )
        assert status == 207
        
        #self.request("GET", "/bob/agenda/")
        #VEVENT test
        event = get_file_content("put.ics")
        path = "/bob/agenda/02805f81-4cc2-4d68-8d39-72768ffa02d9.ics"
        status, headers, answer = self.request("PUT", path, event )
        assert status == 201
        assert "ETag" in headers.keys()
        status, headers, answer = self.request("GET", path)
        assert status == 200
        assert "VEVENT" in answer
        assert b"Nouvel \xc3\xa9v\xc3\xa8nement".decode("utf-8") in answer
        assert "UID:02805f81-4cc2-4d68-8d39-72768ffa02d9" in answer
        

        
        propfind = """<D:propfind xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CS="http://calendarserver.org/ns/" xmlns:IC="http://apple.com/ns/ical/" xmlns:D="DAV:">
  <D:prop>
    <C:calendar-home-set/>
    <C:calendar-user-address-set/>
  </D:prop>
</D:propfind>"""
        
        status, headers, answer = self.request("PROPFIND", "/bob/", propfind, HTTP_DEPTH="1")
        assert status == 207
        xmldoc = minidom.parseString(answer)
        itemlist = xmldoc.getElementsByTagName('response') 
        assert len(itemlist) == 2       

class TestLMDB(MoreBaseRequests, BaseTest):
    """Base class for TestLMDB tests."""
    storage_type = "lmdbstore"
    
    def setup(self):
        """Setup function for each test."""
        self.dbpath = tempfile.mkdtemp()
        config.set("storage", "type", self.storage_type)
        config.set("storage", "db_path", self.dbpath)
        self.application = radicale.Application()

    def teardown(self):
        """Teardown function for each test."""
        #dumpDB(self.dbpath)
        shutil.rmtree(self.dbpath)
