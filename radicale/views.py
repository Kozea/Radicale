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
Django CBV.
"""

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.utils.decorators import method_decorator
from . import Application


class ApplicationResponse(HttpResponse):
    def start_response(self, status, headers):
        self.status_code = int(status.split(' ')[0])
        for k, v in dict(headers).items():
            self[k] = v


class ApplicationView(Application, View):
    http_method_names = [
        'delete',
        'get',
        'head',
        'mkcalendar',
        'mkcol',
        'move',
        'options',
        'propfind',
        'proppatch',
        'put',
        'report',
    ]

    def __init__(self, **kwargs):
        """Initialize application."""
        super(ApplicationView, self).__init__()
        super(View, self).__init__(**kwargs)

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        if not request.method.lower() in self.http_method_names:
            return self.http_method_not_allowed(request, *args, **kwargs)
        response = ApplicationResponse()
        answer = self(request.META, response.start_response)
        if answer:
            response.write(answer[0])
        return response


application = ApplicationView.as_view()
