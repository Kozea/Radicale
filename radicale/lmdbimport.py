#!/usr/bin/python
#-*- coding: utf-8 -*-

""" 
Ldmdbimport is a program that migrates an existing Radicale instance that uses 
the filesystem store to a lmdbstore.

The source filesystem is not altered.     
"""

import lmdb
import os
import posixpath
import json
import vobject
import time
import optparse



MAP_SIZE = 1048576 * 400
env = None

def unfold(text):
    """Unfold multi-lines attributes.

    Read rfc5545-3.1 for info.

    """
    lines = []
    for line in text.splitlines():
        if lines and (line.startswith(" ") or line.startswith("\t")):
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def collection(file):
    """Open the file and parse it. """
    return vobject.readComponents ( open(file, 'r') )
    

def to_class_name(item):
    """Return the class name for a vobject ie VEVENT will be Event. """
    return item.name[1:2] + item.name.lower()[2:]
    
def to_radical_name(item):
    """Mimic the Radicale naming convention for an object."""
        # - the ``name`` parameter
        # - the ``X-RADICALE-NAME`` iCal property (for Events, Todos, Journals)
        # - the ``UID`` iCal property (for Events, Todos, Journals)
        # - the ``TZID`` iCal property (for Timezones)
    
    try:
        if item.x_radicale_name:
            return item.x_radicale_name.value #     "X-RADICALE-NAME"
    except:
        pass
    
    if "VTIMEZONE" == item.name:
        return item.tzid.value
    elif item.name in ("VEVENT" , "VTODO", "VJOURNAL", "VCARD"):
        return item.uid.value    
    
def props(file, db_key):
    """Load a property file into the database and return the properties."""
    propsdb = env.open_db(name=encode_name(db_key + ".db"))
    
    properties = {}
    with open(file) as prop_file:
        properties.update(json.load(prop_file))

    with env.begin(write=True, db=propsdb) as txn:
        for key in properties:
            if properties[key]:
                txn.put(key.encode("utf-8"), properties[key].encode("utf-8"))
            else:
                txn.put(key.encode("utf-8"), None)
   
def encode_name(name):
    """db names must be encoded."""
    return name.encode("utf-8")
    
def import_collection(path, items):
    """Import a vobject list of items into a collection 
       instance in the database. 
    """
    headers = []
    for item in  items: 
        if item.name in ("VERSION", "PRODID", "CALSCALE"):
            headers.append(item)
            continue
        
        item_key = "/items/" + path + "#" +  to_class_name(item) + '#' \
             + to_radical_name(item) + ".db"
        item_key = item_key.encode("utf-8")
        item_db = env.open_db(name=item_key) 
        with env.begin(write=True, db=item_db) as txn:
            for (i, line) in enumerate(unfold(item.serialize()), start=100):
                k, v = line.split(":", 1)
                txn.put( str(i) + ":" + k.encode("utf-8"), v) 
     
        coldb = env.open_db(name=encode_name(path + ".db")) 
        with env.begin(write=True, db=coldb) as txn:
            txn.put( str(to_class_name(item) +  "#" + item_key) , 
                     item_key.encode("utf-8"))
            txn.put( to_radical_name(item).encode("utf-8") , 
                     item_key.encode("utf-8") )
                

    with env.begin(write=True, db=coldb) as txn:
        txn.put("last_modified", 
                time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()))


    headerdb = env.open_db(name=encode_name(path + ".header.db"))
    with env.begin(write=True, db=headerdb) as txn:
        for header in headers:
            for line in unfold(header.serialize()):
                k, v = line.split(":", 1)
                txn.put( k.encode("utf-8"), v.encode("utf-8"))
         
    
    
def dump2db(src, dst):
    """Look for files and properties and process them. 
       Input directory should be the Radicale filesystem location that is imported.  
    """
    global env
    env = lmdb.open(dst, map_size=MAP_SIZE, max_dbs=10000000, create=True)
    
    for root, _, files in os.walk(src):
        for file in files:
            abs_path = posixpath.join(root, file)
            col_path = abs_path.replace(src,"")
            if col_path.endswith(".props"):
                pass
            else:
                print ("importing: %s" % col_path)
                if os.path.exists(abs_path + ".props"):
                    props(abs_path + ".props", col_path + ".props")
                                
                vcollection = collection(abs_path)
                item = vcollection.next()
                if "VCALENDAR" == item.name:
                    import_collection(col_path, item.getChildren())
                else:
                    items = [item]
                    for item in vcollection:
                        items.append(item)
                    import_collection(col_path, items)



def main():
    """Fire up the program """
    parser = optparse.OptionParser()
    parser.add_option(
        "-s", "--source",
        help="Source for the import, the Radicale file system store directory")
    parser.add_option(
        "-t", "--target",
        help="Target of the export, the LMDB database directory, " + 
             "an empty directory")
    parser.add_option(
        "-D", "--debug", action="store_true",
        help="print debug information")
    
    
    options = parser.parse_args()[0]
    if not options.source or not options.target:
        print("Source and target arguments are required")
        return
    
    if not os.path.exists(options.source):
        print ("Source directory does not exist")
        return

    if os.path.exists(options.target) and os.listdir(options.target) != []:
        print ("Target directory is not empty")
        return

    dump2db(options.source, options.target)

    if options.debug:
        print "\n\nList of imported items:"
        with env.begin(write=False) as txn:
            for key in txn.cursor().iternext(values=False):
                print ("%s" % key)

if __name__ == '__main__':
    main()    
