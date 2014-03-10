# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2013 Guillaume Ayoub
# Copyright © 2014 Brian Curran
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

"""
PostgreSQL authentication.

Authenticates against a Blowfish-hashed password stored in a PostgreSQL
database. Requires the pgcrypto module and psycopg2.

"""

import psycopg2
from .. import config, log

DBADDRESS = config.get("auth", "psql_server")
DBNAME = config.get("auth", "psql_db_name")
DBUSER = config.get("auth", "psql_db_user")
DBPASSWORD = config.get("auth", "psql_db_password")
DBTABLE = config.get("auth", "psql_users_table")
DBUSERCOL = config.get("auth", "psql_username_column")
DBPWCOL = config.get("auth", "psql_password_column")

def is_authenticated(user, password):
  
    conn = psycopg2.connect(database=DBNAME,
        user=DBUSER,
        password=DBPASSWORD,
        host=DBADDRESS)
    cur = conn.cursor()
    sql_query = "SELECT " + DBPWCOL + " = crypt(%s, " + DBPWCOL + ") AS \
        pwd_check_result FROM " + DBTABLE + " WHERE " + DBUSERCOL + "=%s;"
    sql_data = (password, user)
    cur.execute(sql_query, sql_data)
    cursor_result = cur.fetchone()
    log.LOGGER.debug("psql authentication result: %s" % cursor_result) 
    if cursor_result and True in cursor_result:
        log.LOGGER.debug("User %s authenticated by psql." % user)
        return True
    else:
        log.LOGGER.debug("User %s NOT authenticated by PSQL." % user)
        return False
