# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Okami <okami@fuzetsu.info>
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
Django admin web interface.
"""

from django import forms
from django.contrib import admin
from django.db import models

from .models import DBCollection, DBItem, DBHeader, DBLine, DBProperty


class TextInputAdmin(object):
    formfield_overrides = {
        models.TextField: {'widget': forms.TextInput},
    }


class DBHeaderInline(TextInputAdmin, admin.TabularInline):
    extra = 0
    model = DBHeader


class DBPropertyInline(TextInputAdmin, admin.TabularInline):
    extra = 0
    model = DBProperty


class DBCollectionAdmin(TextInputAdmin, admin.ModelAdmin):
    inlines = DBHeaderInline, DBPropertyInline
    list_display = 'path', 'parent'
    list_filter = 'parent',
    search_fields = 'path',
    fields = 'path', 'parent'


class DBLineInline(TextInputAdmin, admin.TabularInline):
    extra = 0
    model = DBLine


class DBItemAdmin(TextInputAdmin, admin.ModelAdmin):
    inlines = DBLineInline,
    list_display = 'name', 'tag'
    list_filter = 'tag', 'collection'
    search_fields = 'name', 'tag'
    fields = 'name', 'tag', 'collection'


admin.site.register(DBCollection, DBCollectionAdmin)
admin.site.register(DBItem, DBItemAdmin)
