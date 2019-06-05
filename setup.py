#!/usr/bin/env python

# Copyright (C) 2006, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import sys

from sugar3.activity import bundlebuilder

bundlebuilder.start()

try:
    if sys.argv.index('install'):
        # create schemas directory if missing
        path = '/usr/share/glib-2.0/schemas'
        if not os.access(path, os.F_OK):
            os.makedirs(path)

        # create compiled schema file if missing
        src = 'org.laptop.WebActivity.gschema.xml'
        lines = \
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<schemalist>',
                '<schema id="org.laptop.WebActivity" '
                'path="/org/laptop/WebActivity/">',
                '<key name="home-page" type="s">',
                "<default>''</default>",
                '<summary>Home page URL</summary>',
                '<description>URL to show as default or when home button '
                'is pressed.</description>',
                '</key>',
                '<key name="search-engine-url" type="s">',
                "<default>'http://www.google.com/search?q=%(query)s"
                "&amp;ie=UTF-8&amp;oe=UTF-8&amp;hl=%(language)s'</default>",
                '<summary>Search engine URL</summary>',
                '<description>URL to which to submit search '
                'results. Parameters: %(query)s: The search query. '
                '%(language)s: A POSIX-compliant language string '
                'describing the language of the result '
                'page.</description>',
                '</key>',
                '</schema>',
                '</schemalist>',
            ]
        open(os.path.join(path, src), 'w').writelines(lines)
        os.system('glib-compile-schemas %s' % path)
except ValueError:
    pass
