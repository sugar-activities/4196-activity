#!/usr/bin/python

# ZetCode PyGTK tutorial
#
# This example shows a TreeView widget
# in a list view mode
#
# author: jan bodnar
# website: zetcode.com
# last edited: February 2009

import sys, os
import gtk
from sugar.datastore import datastore
from path import path
from datetime import datetime

class Listview(gtk.VBox):
    def __init__(self, activity, deck):
        print 'listview init'
        self.activity = activity
        gtk.VBox.__init__(self)
        vbox = gtk.VBox(False, 8)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.pack_start(sw, True, True, 0)
        treeView = gtk.TreeView()
        treeView.connect("row-activated", self.on_activated)
        treeView.set_rules_hint(True)
        sw.add(treeView)
        self.create_columns(treeView)
        self.treeView = treeView
        self.deck = deck
        self.add(vbox)
        self.show_all()

    def create_columns(self, treeView):

        rendererText = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Title", rendererText, text=1)
        column.set_sort_column_id(1)
        treeView.append_column(column)
        rendererText = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Mime_type", rendererText, text=2)
        column.set_sort_column_id(2)
        treeView.append_column(column)
        rendererText = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Date", rendererText, text=3)
        column.set_sort_order(gtk.SORT_DESCENDING)
        column.set_sort_column_id(3)
        treeView.append_column(column)

    def get_treeView(self):
        return self.treeView

    def set_store(self, mountpoint, pth):
        print 'set_store', mountpoint, pth
        store = gtk.ListStore(str, str, str, str)
        #get objects from the local datastore
        ds_objects, num_objects = datastore.find({'mountpoints':[mountpoint], 'mime_type':['image/jpg', 'image/png', 'image/svg', 'image/jpeg']})
        for f in ds_objects:
            try:
                object = f.object_id
            except:
                print 'set object_id failed'
            try:
                title = f.metadata['title']
            except:
                title = ""
            try:
                mime_type = f.metadata['mime_type']
            except:
                mime_type = 'unknown'
            try:
                t = f.metadata['timestamp']
                timestamp = datetime.fromtimestamp(t)
            except:
                timestamp = ""
            store.append([object, title, mime_type, timestamp])
            print 'store.append', object, title, mime_type, timestamp
            f.destroy()
        return store

    def on_activated(self, widget, row, col):

        model = widget.get_model()
        print 'row', model[row][0], model[row][1], model[row][2], model[row][3]
        title = model[row][1]
        mime_type = model[row][2]
        timestamp = model[row][3]
        object = datastore.get(model[row][0])
        fn = object.file_path
        print 'object filename', path(fn).exists(), fn
        self.deck.addSlide(fn)
        self.deck.reload()
        object.destroy()
        self.activity.set_screen(0)
