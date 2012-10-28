from radicale import config, log
import hashlib
from radicale.models.redmine import Users

def is_authenticated(user, password):
    try:
        redmine_user = Users().get(user, 'login')
        password_to_check = hashlib.sha1(password).hexdigest()
        hash_password = hashlib.sha1(redmine_user.salt + password_to_check).hexdigest()
        if hash_password == redmine_user.hashed_password:
            print "Ok"
            return True
    except:
        return False
    return False
