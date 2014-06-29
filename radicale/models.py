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
Django models. Used in django storage backend.
"""

from django.db import models


class DBCollection(models.Model):
    """Table of collections."""

    path = models.TextField('Path', primary_key=True)
    parent = models.ForeignKey(
        'DBCollection', verbose_name='Parent Collection',
        related_name='children', blank=True, null=True)

    def __str__(self):
        return self.path

    def __unicode__(self):
        return self.path

    class Meta(object):
        db_table = 'radicale_collection'
        verbose_name = 'Collection'
        verbose_name_plural = 'Collections'


class DBItem(models.Model):
    """Table of collection's items."""

    name = models.TextField('Name', primary_key=True)
    tag = models.TextField('Tag')
    collection = models.ForeignKey(
        'DBCollection', verbose_name='Collection', related_name='items')

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name

    class Meta(object):
        db_table = 'radicale_item'
        verbose_name = 'Item'
        verbose_name_plural = 'Items'


class DBHeader(models.Model):
    """Table of item's headers."""

    name = models.TextField('Name', primary_key=True)
    value = models.TextField('Value')
    collection = models.ForeignKey(
        'DBCollection', verbose_name='Collection', related_name='headers')

    def __str__(self):
        return '%s=%s' % (self.name, self.value)

    def __unicode__(self):
        return u'%s=%s' % (self.name, self.value)

    class Meta(object):
        db_table = 'radicale_header'
        verbose_name = 'Header'
        verbose_name_plural = 'Headers'


class DBLine(models.Model):
    """Table of item's lines."""

    name = models.TextField('Name')
    value = models.TextField('Value')
    timestamp = models.DateTimeField(
        'Timestamp', auto_now_add=True, primary_key=True)
    item = models.ForeignKey(
        'DBItem', verbose_name='Item', related_name='lines')

    def __str__(self):
        return '%s=%s' % (self.name, self.value)

    def __unicode__(self):
        return u'%s=%s' % (self.name, self.value)

    class Meta(object):
        db_table = 'radicale_line'
        ordering = 'timestamp',
        verbose_name = 'Line'
        verbose_name_plural = 'Lines'


class DBProperty(models.Model):
    """Table of collection's properties."""

    name = models.TextField('Name', primary_key=True)
    value = models.TextField('Value')
    collection = models.ForeignKey(
        'DBCollection', verbose_name='Collection', related_name='properties')

    def __str__(self):
        return '%s=%s' % (self.name, self.value)

    def __unicode__(self):
        return u'%s=%s' % (self.name, self.value)

    class Meta(object):
        db_table = 'radicale_property'
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
