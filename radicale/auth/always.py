# -*- coding: utf-8 -*-
#
# eric: for debugging

def is_authenticated(user, password):
    if user: # if we are really too permissive then that confuses radicale
        return True
    else:
        return False