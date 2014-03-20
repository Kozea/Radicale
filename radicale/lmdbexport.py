#!/usr/bin/python
#-*- coding: utf-8 -*-

""" 
Ldmdbexport is a program that migrates an existing Radicale instance that uses 
the lmdbstore store to a filesystem.

The source database is opened read-only.      
"""

import lmdb
import os
import json
import re
import codecs
from contextlib import contextmanager
import optparse

MAP_SIZE = 1048576 * 400
FOLDER = None
env = None



# This function overrides the builtin ``open`` function for this module
# pylint: disable=W0622
@contextmanager
def open(path, mode="r"):
    """Open a file at ``path`` with encoding set in the configuration."""
    # On enter
    abs_path = os.path.join(FOLDER, path.replace("/", os.sep))
    with codecs.open(abs_path, mode, "utf-8") as fd:
        yield fd
# pylint: enable=W0622


def _path(name):
    """Absolute path of the file storing the collection."""
    return os.path.join(FOLDER, name.replace("/", os.sep))

def _props_path(name):
    """Absolute path of the file storing the collection properties."""
    return _path(name + ".props")

def _create_dirs(name):
    """Create folder storing the collection if absent."""
    if not os.path.exists(os.path.dirname(_path(name))):
        os.makedirs(os.path.dirname(_path(name)))

def props(db_key):
    """write the properties to file."""
    name = re.sub(r'\.props\.db', '', db_key)
    propsdb = env.open_db(name=db_key.encode("utf-8"), create=False)

    properties = {}

    with env.begin(write=False, db=propsdb) as txn:
        for key, value in txn.cursor().iternext(): 
            properties[key.decode("utf-8")] = value.decode("utf-8")

    _create_dirs(name)
    with open(_props_path(name), "w") as prop_file:
        json.dump(properties, prop_file)

    return properties    

def load_item(db_key):
    """Read an item from the database and return it a string """
    db = env.open_db(name=db_key.encode("utf-8"), create=False)
    with env.begin(write=False, db=db) as txn:
        text = "\n".join(
                     "%s:%s" % (key.decode("utf-8").split(':',1)[1] , 
                                value.decode("utf-8")) 
                         for key, value in txn.cursor().iternext())
    
    return text    


def serialize(tag, header, text):
    """Wrap the text with BEGIN and END tags when needed. """
    if tag == "VADDRESSBOOK":
        return text
    else:
        lines = ["BEGIN:%s" % tag]
        lines.append(header)
        lines.append(text)
        lines.append("END:%s\n" % tag)
    return "\n".join(lines)


def headers(db_key):
    """return the headers as a string. """
    headerdb = env.open_db(name=db_key.encode("utf-8"), create=False)
    with env.begin(write=False, db=headerdb) as txn:
        text = "\n".join(
                 "%s:%s" % (key.decode("utf-8"), 
                            value.decode("utf-8")) 
                         for key, value in txn.cursor().iternext())

    return text

def dump_collection(db_key):
    """Load a collection from the database and store it as a file,
        including the properties file. 
    """
    name = re.sub(r'\.db$', '', db_key)
    _create_dirs(name)
    db = env.open_db(name=db_key.encode("utf-8"), create=False)
    items = {}
    text = ''
    with env.begin(write=False, db=db) as txn:
        for key, v in txn.cursor().iternext():
            value = v.decode("utf-8")
            if value.endswith(".db"):
                items[value] = '1'
         
        for key in sorted(items):
            text += load_item(key) + "\n"
    
    if text:
        # add container
        p = props(name +".props.db")
        h = headers(name + ".header.db")
        text = serialize(p['tag'], h, text)
        with open(_path(name), "w") as fd:
            fd.write(text)           

def dump_to_file(src, dst, quiet):
    """Locate all collections in the database process them. """
    global env, FOLDER 
    env = lmdb.open(src, map_size=MAP_SIZE, max_dbs=10000000, create=False, readonly=True)
    FOLDER = dst
    
    with env.begin(write=False,) as txn:
        for key, value in txn.cursor().iternext():
            key_name = key.decode("utf-8")
            if key_name.startswith("/items/"):
                pass  
            elif (key_name.endswith(".props.db") or 
                key_name.endswith(".header.db")):
                pass
            elif key_name.endswith(".db"):
                if not quiet:
                    print ("exporting: %s" %  re.sub(r'\.db$', '', key_name) )
                dump_collection(key_name)     
            else:
                print ("ignore %s with value %s"  
                       % (key_name, value.decode("utf-8"))) 
    
def main():
    """Fire up the program """
    parser = optparse.OptionParser()
    parser.add_option(
        "-s", "--source",
        help="Source for the export, the LMDB database directory")
    parser.add_option(
        "-t", "--target",
        help="Target the export, an empty directory")
    parser.add_option(
        "-q", "--quiet", action="store_true", 
        help="Be quiet")
    
    options = parser.parse_args()[0]
    if not options.source or not options.target:
        print("Source and target arguments are required")
        return
    
    if not os.path.exists(options.source):
        print ("Source does not exist")
        return

    if os.path.exists(options.target) and os.listdir(options.target) != []:
        print ("Target is not empty")
        return

    dump_to_file(options.source, options.target, options.quiet)



if __name__ == '__main__':
    main()    
