from .. import config, log
import MySQLdb


class Users(object):
    common_fields = 'id, login, hashed_password, salt, status, type, lastname'
    type = 'User'
    
    def __init__(self):
        DATABASE = config.get("database", "database")
        USER = config.get("database", "database_user")
        PASSWD = config.get("database", "database_passwd")
        HOST = config.get("database", "database_host")
        self.db = MySQLdb.connect(HOST, USER, PASSWD, DATABASE)
        
    def sql(self, command):
        cursor = self.db.cursor()
        cursor.execute(command)
        result = cursor.fetchall()
        cursor.close()
        return result

    def groups(self):
        answer = self.sql('select group_id from groups_users where user_id = "%s"' % (self.id))
        groups_list = list()
        for entry in answer:
            groups_list.append(Users().get(entry[0], 'id', type='Group'))
        return groups_list
        
    def get(self, search, field, type='User'):
        select_by = '%s = "%s"' % (field, search)
        if field == 'lastname' or type == 'Group':
            self.type = 'Group'
        sentence = 'select %s from users where status = "1" and type = "%s" and %s;' % (self.common_fields, self.type, select_by)
        answer = self.sql(sentence)
        if len(answer) > 0:
            if self.type == 'Group':
                self.name = answer[0][6]
            else:
                self.name = answer[0][1]
            self.id = answer[0][0]
            self.hashed_password = answer[0][2]
            self.salt = answer[0][3]
            self.type = answer[0][4]
            return self
        return None
