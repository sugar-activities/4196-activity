# -*- mode:python; tab-width:4; indent-tabs-mode:t; -*-

# showntell.py
#
# Derived from:
#
# Classroom Presenter for the XO Laptop
# Main class
# B. Mayton <bmayton@cs.washington.edu>
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

from sugar.activity import activity
from sugar.datastore import datastore
import logging

import sys, os
import subprocess
import atexit, signal
import gtk
import zipfile

import slideviewer
import sidebar
import sliderenderer
import slideshow
import textarea
import toolbars
import utils
import shared
import time
import pdb
from path import path

import listview
import cpxoview

import hulahop
from sugar import env
hulahop.startup(os.path.join(env.get_profile_path(), 'gecko'))
from hulahop.webview import WebView

import xml.dom.minidom

SLIDESHOW_TOOLBAR = 1
NAVIGATION_TOOLBAR = 2

class ShowNTell(activity.Activity):

    def __init__(self, handle):
        #pdb.set_trace()
        activity.Activity.__init__(self, handle)
        self.__logger = logging.getLogger('ClassroomPresenter')
        logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')
        self.__screens = []
        # Find our instance path
        self.__work_path = path(self.get_activity_root()) /  'instance'
        self.__save_path = path(self.get_activity_root()) /  'data'
        self.__deck_dir = self.__work_path /  'deck'
        bpth = path(activity.get_bundle_path())
        self.__rsrc_dir = bpth / 'resources'
        self.__handle = handle
        # Set up the main canvas
        self.__slide_view = gtk.HBox()
        print 'enter set_canvas', self.__handle.object_id
        self.set_canvas(self.__slide_view)

        self.__deck = slideshow.Deck(self, handle, self.__rsrc_dir, self.__deck_dir)

        # Set up activity sharing
        self.__shared = shared.Shared(self, self.__deck, self.__work_path)

        # Create a renderer for slides
        self.__renderer = sliderenderer.Renderer(self, self.__deck)

        # Set up Main Viewer box
        self.__main_view_box = gtk.VBox()
        self.__slide = slideviewer.SlideViewer(self.__deck, self.__renderer)
        self.__text_area = textarea.TextArea(self.__deck, self.__work_path)
        self.__image_chooser = listview.Listview(self, self.__deck)
        self.__slideshow_chooser = cpxoview.Cpxoview(self, self.__deck)
        self.__html_slide = gtk.EventBox()
        self.__html_slide.set_size_request(600,480)
        self.__main_view_box.pack_start(self.__slide, True, True, 5)
        self.__screens.append(self.__slide)
        self.__main_view_box.pack_start(self.__image_chooser, True, True, 5)
        self.__screens.append(self.__image_chooser)
        self.__main_view_box.pack_start(self.__slideshow_chooser, True, True, 5)
        self.__screens.append(self.__slideshow_chooser)
        self.__main_view_box.pack_start(self.__html_slide, True, True, 5)
        self.__screens.append(self.__html_slide)
        self.__main_view_box.pack_start(self.__text_area, False, False, 0)

        # Create our toolbars
        makeTB = toolbars.MakeToolBar(self, self.__deck)
        self.__makeTB = makeTB
        navTB = toolbars.NavToolBar(self, self.__shared, self.__deck)
        inkTB = toolbars.InkToolBar(self.__slide, self.__deck)

        # Create the standard activity toolbox; add our toolbars
        toolbox = activity.ActivityToolbox(self)
        toolbox.add_toolbar("Presentation", makeTB)
        toolbox.add_toolbar("Navigation",navTB)
        toolbox.add_toolbar("Ink", inkTB)
        self.set_toolbox(toolbox)
        toolbox.show()
        self.__toolbox = toolbox

        # Open with slideshow toolbar
        toolbox.set_current_toolbar(SLIDESHOW_TOOLBAR)

        # Set up the side scrollbar widget
        self.__side_bar = sidebar.SideBar(self.__deck, self.__renderer)
        self.__side_bar.set_size_request(225, 100)

        # Set up a separator for the two widgets
        separator = gtk.VSeparator()

        # Pack widgets into main window
        self.__slide_view.pack_start(self.__main_view_box, True, True, 0)
        self.__slide_view.pack_start(separator, False, False, 5)
        self.__slide_view.pack_start(self.__side_bar, False, False, 0)

        # Show all widgets
        self.__slide_view.show_all()
        self.__main_view_box.show()
        self.__slide.show()
        self.__text_area.show()
        self.__image_chooser.hide()
        self.__slideshow_chooser.hide()
        #self.__html_viewer.hide()
        separator.show()
        self.__side_bar.show_all()

        # Set up the progress view
        self.__progress_max = 1.0
        self.__progress_cur = 0.01
        self.__progress_view = gtk.VBox()
        self.__progress_lbl = gtk.Label("Loading slide deck...")
        self.__progress_bar = gtk.ProgressBar()
        self.__progress_view.pack_start(self.__progress_lbl, True, False, 5)
        #self.__progress_view.pack_start(self.__progress_bar, False, False, 5)
        self.__progress_bar.set_fraction(self.__progress_cur / self.__progress_max)

        self.__shared.connect('deck-download-complete', self.dl_complete_cb)

        #if launched by Learn, set up deck
        pth = path('/tmp/showntell')
        if pth.exists():
            #open slideshow, set Navigation toolbar current
            fin = open(pth,'r')
            fn = fin.read()
            fin.close()
            self.read_file(fn)
            self.set_screen(0)
            subprocess.call('rm -rf ' + pth,shell=True)

    def dl_complete_cb(self, widget):
        self.do_slideview_mode()

    def do_slideview_mode(self):
        self.set_canvas(self.__slide_view)
        self.__slide_view.show_all()

    def set_progress_max(self, maxval):
        self.__progress_max = maxval
        self.__progress_bar.set_fraction(float(self.__progress_cur) / float(self.__progress_max))

    def do_progress_view(self):
        self.set_canvas(self.__progress_view)
        self.__progress_view.show_all()

    def set_progress(self, val):
        self.__progress_cur = val
        self.__progress_bar.set_fraction(float(self.__progress_cur) / float(self.__progress_max))

    #resume from journal
    def read_file(self, file_path):
        self.__logger.debug("read_file " + str(file_path))
        print 'read_file:', file_path
        ftype = utils.getFileType(file_path)
        z = zipfile.ZipFile(file_path, "r")
        for i in z.infolist():
            f = open(os.path.join(self.__deck_dir, i.filename), "wb")
            f.write(z.read(i.filename))
            f.close()
        z.close()
        self.__deck.reload()
        print 'read_file: before', self.__deck.get_title(), self.metadata['title']
        self.__makeTB.decktitle_set_new(self.metadata['title'])
        print 'read_file: after',  self.__deck.get_title()
        self.__toolbox.set_current_toolbar(NAVIGATION_TOOLBAR)
        newindex = 0
        if 'current_index' in self.metadata:
            newindex = int(self.metadata.get('current_index', '0'))
        self.__deck.goToIndex(newindex, is_local=False)

    #save state in journal for resume
    def write_file(self, file_path):
        print 'write_file', self.__toolbox.get_current_toolbar(), str(file_path)
        self.__logger.debug("write_file " + str(file_path))
        print 'title', self.__deck.get_title()
        self.metadata['title'] = self.__deck.get_title()
        self.metadata['mime_type'] = "application/x-classroompresenter"
        self.metadata['current_index'] = str(self.__deck.getIndex())
        self.__deck.save()
        z = zipfile.ZipFile(file_path, "w")
        root, dirs, files = os.walk(self.__deck_dir).next()
        for f in files:
            z.write(os.path.join(root, f), f)
        z.close()

    def get_shared_activity(self):
        return self._shared_activity

    def set_screen(self,scrn):
        if len(self.__screens) < 1:
            return
        self.__screens[0].hide()
        self.__screens[1].hide()
        self.__screens[2].hide()
        self.__screens[3].hide()
        self.__screens[scrn].show()
        return self.__screens[scrn]
