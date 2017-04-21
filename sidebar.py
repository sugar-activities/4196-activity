# -*- mode:python; tab-width:4; indent-tabs-mode:t;  -*-

# sidebar.py
#
# Class to handle thumbnail views of the slide on the side of the main viewer
# 
# W.Burnside <wburnsid@u.washington.edu>
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

import pygtk
import gtk
import slideshow
import slideviewer
import os
import logging
import gobject

from sugar.graphics import style

class SideBar(gtk.Notebook):
	
	def __init__(self, deck, renderer):
		gtk.Notebook.__init__(self)
		self.__logger = logging.getLogger('SideBar')
		self.__deck = deck
		self.__renderer = renderer	
		self.__is_instr = True	
		
		self.set_show_border(False)
		self.set_show_tabs(True)
		#self.show_tabs = True
		#self.show_border = True

        self.slide_context_menu = gtk.Menu()    # Don't need to show menus

        # Create the menu items
        move_item = gtk.ImageMenuItem('Move')
        img = gtk.Image()
        img.set_from_file('icons/Icon-move.svg')
        move_item.set_image(img)
        move_item.connect("activate", self.moveslide)

        remove_item = gtk.ImageMenuItem('remove')
        img = gtk.Image()
        img.set_from_file('icons/Icon-remove.svg')
        remove_item.set_image(img)
        remove_item.connect("activate", self.removeslide)

        # Add them to the menu
        self.slide_context_menu.append(move_item)
        self.slide_context_menu.append(remove_item)

        # We do need to show menu items
        move_item.show()
        remove_item.show()

		# Create scrolled window for viewing thumbs or subs
		# Scrollbar: horizontal if necessary; vertical always
		self.__viewing_box = gtk.ScrolledWindow()
		self.__viewing_box.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
		slide_label = gtk.Label("Slides")
		event_box = gtk.EventBox()
		event_box.add(self.__viewing_box)
		
		self.append_page(event_box, slide_label)
		#self.append_page(self.__viewing_box, sub_label)
				
		self.__sublist_store = gtk.ListStore(str, int)
		self.__sub_col = gtk.TreeViewColumn("Versions of this slide:")
		self.__sublist = gtk.TreeView(self.__sublist_store)
		self.__sublist.append_column(self.__sub_col)
		self.__sublist_cell = gtk.CellRendererText()
		self.__sub_col.pack_start(self.__sublist_cell, True)
		self.__sub_col.add_attribute(self.__sublist_cell, 'text', 0)
		
		sub_label = gtk.Label("Submissions")
		self.append_page(self.__sublist, sub_label)
		
		#self.__sublist_store.append(["My Ink", -1])
		
		self.load_thumbs()
		
		# show widgets
		self.show_all()
		
		self.__deck.connect('deck-changed', self.load_thumbs)
		self.__deck.connect('update-submissions', self.load_subs)
		self.__sublist.get_selection().connect('changed', self.sub_sel_changed)
		
	def load_subs(self, widget=None, def_sub=-1):
		self.__logger.debug("Loading submission list")
		self.__sublist_store.clear()
		sublist = self.__deck.getSubmissionList()
		self.__sublist_store.append(["My Ink", -1])
		i = 0
		for submission in sublist:
			self.__sublist_store.append([str(submission) + "'s Ink", i])
			i = i + 1
		self.__sublist.get_selection().select_path(def_sub+1)
		
	def sub_sel_changed(self, widget=None):
		(model, itera) = widget.get_selected()
		if itera:
			newindex = model.get_value(itera, 1)
			self.__logger.debug("Submission selection changed to "+ str(newindex))
			self.__deck.setActiveSubmission(newindex)

	# Method to load slides into Scrolling side window
	# The method uses a table to organize the slides
	def load_thumbs(self, widget=None):
		for c in self.__viewing_box.get_children():
			self.__viewing_box.remove(c)

		# create image table for thumbnails
		self.image_table = gtk.Table(self.__deck.getSlideCount(), 1, False)

		# Loop to show slides
		for i in range(self.__deck.getSlideCount()):		
			# Create event box for table entry
			event_box = gtk.EventBox()
			event_box.set_size_request(209, 160)

			# Add navigation to event boxes
			event_box.set_above_child(True)
			event_box.connect('button_press_event', self.change_slide, i)

			# Create viewer for slide and add to box
			slide = slideviewer.ThumbViewer(self.__deck, self.__renderer, i)
			event_box.add(slide)

			# Put box in table and show 
			self.image_table.attach(event_box, 0, 1, i, i+1)
			event_box.show()			

			# Show each slide
			slide.show()

		# show images
		self.__viewing_box.add_with_viewport(self.image_table)
		self.image_table.show()
        self.movemode=False


	def change_slide(self, widget, event, n):
        if event.button == 3:
            self.selected_slide = n
	        self.slide_context_menu.popup( None, None, None, event.button, event.time)
        elif self.movemode:
            self.movemode=False
            self.__deck.moveSlide(self.moved_slide, n)
            self.__deck.save()
            self.__deck.reload()
        else:
		    self.__deck.goToIndex(n, is_local=True)

    def moveslide(self, params):
            self.movemode=True
            self.moved_slide = self.selected_slide

    def removeslide(self, params):
            self.__deck.removeSlide(self.selected_slide)
            self.__deck.save()
            self.__deck.reload()

	
