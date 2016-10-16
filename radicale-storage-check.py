#!/usr/bin/python3.4 -s
#
# This file is a tool for the Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2016 Guillaume Ayoub
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

import sys
import traceback
import vobject

## Main
if len(sys.argv) < 2:
    print ('Missing file names as arguments')

i = 1
while i < len(sys.argv):
    path = sys.argv[i]
    print ('Analyze file:', path)
    i += 1
    with open(path, encoding="utf-8", newline="") as f:
        print ('Read file:', path)
        text = f.read()
        print ("Parse file contents:", path)
        try:
            item = vobject.readOne(text)
            print ("Parse file contents successful:", path)
        except Exception as e:
            print ("Parse file contents ERROR", path)
            print ("Unexpected error:", e)
            traceback.print_exc(file=sys.stdout)
            exit(1);

        # check whether vobject likes the VCARD item
        try:
            print ("Serialize file contents:", path)
            item_ser = item.serialize()
            print ("Serialize file contents successful:", path)
            print ("=== CONTENTS BEGIN ===")
            print (str(item_ser))
            print ("=== CONTENTS END ===")
        except Exception as e:
            print ("Serialize file contents ERROR", path)
            print ("Unexpected error:", e)
            traceback.print_exc(file=sys.stdout)
            exit(1);
