# -*- mode:python; tab-width:4; indent-tabs-mode:t;  -*-

# slideshow.py
#
# Classes to represent a deck of slides, and handle things like file I/O and
# formats
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

import os, sys, subprocess
from time import strftime
import gtk
import xml.dom.minidom
import gobject
import logging
from path import path
from sugar.activity import activity
from sugar.datastore import datastore

class Deck(gobject.GObject):

    __gsignals__ = {
        'slide-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'decktitle-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'slide-redraw' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'remove-path' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,)),
        'deck-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'local-ink-added' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        'remote-ink-added' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        'instr-state-propagate' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
        'lock-state-propagate' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
        'ink-submitted' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING)),
        'ink-broadcast' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                            (gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)),
        'update-submissions' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,)),
        'instructor-ink-cleared' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,)),
        'instructor-ink-removed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT, gobject.TYPE_INT)),
    }

    def __init__(self, sugaractivity, handle, rsrc, base="/nfs/show"):
        gobject.GObject.__init__(self)
        self.__handle = handle
        if self.__handle.object_id == None:
            print 'slideshow - from home view'
        else:
            obj = datastore.get(self.__handle.object_id)
            print 'object:', obj.get_file_path()
        self.__logger = logging.getLogger('Deck')
        self.__base = base
        self.__rsrc = rsrc
        self.__activity = sugaractivity

        self.__is_initiating = True
        self.__nav_locked = False
        self.__active_sub = -1
        self.__self_text = ""
        self.__text_tag = None
        self.__xmlpath = os.path.join(base, "deck.xml")
        #we always create a new presentation and copy over it on resume
        if path(base).exists():
            #we can't have permissions.info for this to work
            subprocess.call("cp -r " + base + " /home/olpc/save", shell=True)
            subprocess.call("rm -rf " + base + '/*', shell=True)
        else:
            path.mkdir(base)
        path.copy(self.__rsrc / 'deck.xml', base / 'deck.xml')
        path.copy(self.__rsrc / 'title.html', base / 'title.html')
        path.copy(self.__rsrc / 'title_thumb.png', base / 'title_thumb.png')
        self.reload()
        self.set_title('New')

    def set_locked_mode(self, locked):
        """ Setter method for the navigation lock flag"""
        self.__logger.debug("Lock state: " +str(locked))
        self.__nav_locked = locked
        self.emit('lock-state-propagate', locked)

    def set_is_initiating(self, is_init):
        """ Setter method for the instructor flag """
        self.__logger.debug("Instructor state: " +str(is_init))
        self.__is_initiating = is_init
        self.emit('instr-state-propagate', is_init)

    def getIsInitiating(self):
        return self.__is_initiating

    def make_title_slide(self, title):
        #open and read title.html
        self.__work_path = os.path.join(activity.get_activity_root(), 'instance')
        deckpath = path(activity.get_activity_root()) / 'instance' / 'deck'
        slide = open(deckpath / 'title.html', 'r')
        txt = slide.read()
        slide.close()
        #here change title.html - change between <h1> and </h1>
        h1pos = txt.find('<h1>')
        h1end = txt.find('</h1>')
        txtmod = txt[:h1pos+4] + title + txt[h1end:]
        #here change date       - change between <h3> and </h3>
        h3pos = txtmod.find('<h3>')
        h3end = txtmod.find('</h3>')
        txt = txtmod[:h3pos+4] + strftime("%a, %b %d, %Y %H:%M") + txtmod[h3end:]
        #save title.html and close
        slide = open(deckpath / 'title.html', 'w')
        slide.write(txt)
        slide.close()
        print 'title slide changed', title

    def set_title(self, title):
        nodes = self.__dom.getElementsByTagName("title")
        nodes[0].firstChild.data = title
        self.make_title_slide(title)
        self.save()
        self.goToIndex(0, is_local=False)
        self.emit('deck-changed')
        print 'set_title', self.get_title()

    def get_title(self):
        nodes = self.__dom.getElementsByTagName("title")
        return nodes[0].firstChild.data

    def reload(self):
        self.__logger.debug("Reading deck")
        print 'reload:', self.__xmlpath
        if os.path.exists(self.__xmlpath):
            self.__dom = xml.dom.minidom.parse(self.__xmlpath)
        decks = self.__dom.getElementsByTagName("deck")
        self.__deck = decks[0]
        # Get the slides from the show
        self.__slides = self.__deck.getElementsByTagName("slide")
        self.__nslides = len(self.__slides)
        self.__logger.debug(str(self.__nslides) + " slides in show")
        self.goToIndex(0, is_local=False)
        self.emit('deck-changed')
        print 'deck reloaded'

    def save(self, path=None):
        """Writes the XML DOM in memory out to disk"""
        print 'save:', path
        if not path:
            path = self.__xmlpath

        """
        print '***************save************************'
        print self.__dom.toprettyxml()
        print '***************save************************'
        """

        outfile = open(path, "w")
        self.__dom.writexml(outfile)
        outfile.close()

    def rebuild_dom(self, title, slides):
        dom = xml.dom.minidom.Document()
        deck = dom.createElement("deck")
        title = dom.createElement("title")
        title.appendChild(dom.createTextNode("new"))
        deck.appendChild(title)
        for slide in slides:
            deck.appendChild(slide)
        dom.appendChild(deck)
        print '*************rebuild**************************'
        print dom.toprettyxml()
        print '**********************************************'
        return dom

    def getDeckPath(self):
        """Returns the path to the folder that stores this slide deck"""
        return self.__base

    def resizeImage(self, inpath, outpath, w, h):
        # resize an image
        print 'resizeImage', inpath, outpath, w, h
        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(inpath, w, h)
        #scaled_buf = pixbuf.scale.simple(w, h, gtk.gdk.INTERP_BILINEAR)
        pixbuf.save(outpath, "png")

    def get_SlideTitle(self):
        n = self.getIndex()
        slide = self.__slides[n]
        return slide.getAttribute('title')

    def set_SlideTitle(self, slideTitle):
        n = self.getIndex()
        slide = self.__slides[n]
        slide.setAttribute('title', slideTitle)

    def addSlide(self,file_path):

        INSTANCE = path(activity.get_activity_root()) / 'instance'
        filepath = path(file_path)
        print 'addSlide file_path', filepath.exists(), filepath
        filename = filepath.name
        inpath = INSTANCE / 'deck' / filename
        print 'inpath', inpath.exists(), inpath
        path.copy(filepath, inpath)
        outpath = path(activity.get_activity_root() ) / 'instance' / 'deck' / filename
        print 'outpath=', outpath.exists(), outpath
        self.resizeImage(inpath, outpath, 640, 480)
        print 'outpath=', outpath.exists(), outpath

        print 'get slide dimensions'
        dims = self.getSlideDimensionsFromXML(0)
        if dims == False:
            wf = 640
            hf = 480
        else:
            wf, hf = dims
        w = str(int(wf))
        h = str(int(hf))
        print 'add slide', w, h
        newslide = self.__dom.createElement("slide")
        newslide.setAttribute("height", h)
        newslide.setAttribute("title", "newslide")
        newslide.setAttribute("width", w)
        newlayer = self.__dom.createElement("layer")
        txt = self.__dom.createTextNode(filename)
        newlayer.appendChild(txt)
        newslide.appendChild(newlayer)
        self.__deck.appendChild(newslide)
        print '**************addSlide*************'
        print self.__dom.toprettyxml()
        print '***********************************'
        self.save()

    def removeSlide(self, n):
        del self.__slides[n]
        self.__dom = self.rebuild_dom("modified deck", self.__slides)

    def moveSlide(self, f, t):
        if f < t:
            self.__slides.insert(t, self.__slides[f])
            del self.__slides[f]
        elif t < f:
            self.__slides.insert(t, self.__slides[f])
            del self.__slides[f+1]
        self.__dom = self.rebuild_dom("modified deck", self.__slides)

    def getSlideLayers(self, n=-1):
        """Returns a list of the layers that comprise this slide"""
        if n == -1:
            n = self.__pos
        slide = self.__slides[n]
        self.__layers = slide.getElementsByTagName("layer")
        layers = []
        for l in self.__layers:
            p = os.path.join(self.__base, l.firstChild.nodeValue)
            layers.append(p)
        return layers

    def getInstructorInk(self):
        self.__instructor_ink = []
        instr = self.__slide.getElementsByTagName("instructor")
        if len(instr) > 0:
            self.__instructor_tag = instr[0]
            pathtags = self.__instructor_tag.getElementsByTagName("path")
            for pathstr in pathtags:
                self.__instructor_ink.append(pathstr.firstChild.nodeValue)
        return self.__instructor_ink

    def getSelfInkOrSubmission(self):
        if self.__active_sub == -1:
            return (self.__self_ink, self.__self_text)
        subtags = self.__slide.getElementsByTagName("submission")
        if self.__active_sub > -1 and self.__active_sub < len(subtags):
            active_subtag = subtags[self.__active_sub]
            text = ""
            texts = active_subtag.getElementsByTagName("text")
            if len(texts) > 0:
                if texts[0].firstChild:
                    text = texts[0].firstChild.nodeValue
            pathlist = []
            paths = active_subtag.getElementsByTagName("path")
            for path in paths:
                if path.firstChild:
                    pathlist.append(path.firstChild.nodeValue)
            return (pathlist, text)
        return None

    def setActiveSubmission(self, sub):
        self.__active_sub = sub
        self.emit('slide-redraw')

    def getActiveSubmission(self):
        return self.__active_sub

    def getSubmissionList(self, n=None):
        if n is None:
            n = self.__pos
        subtags = self.__slide.getElementsByTagName("submission")
        sublist = []
        for subtag in subtags:
            sublist.append(subtag.getAttribute("from"))
        return sublist

    def addSubmission(self, whofrom, inks, text="", n=None):
        if n is None:
            n = self.__pos
        if n >= 0 and n < self.getSlideCount():
            slide = self.__slides[n]
        else:
            slide = self.__slides[self.__pos]
        newsub = self.__dom.createElement("submission")
        newsub.setAttribute("from", whofrom)
        substrparts = inks.split("$")
        for part in substrparts:
            if len(part) > 0:
                newpath = self.__dom.createElement("path")
                newpath.appendChild(self.__dom.createTextNode(part))
                newsub.appendChild(newpath)
        subtext = self.__dom.createElement("text")
        subtext.appendChild(self.__dom.createTextNode(text))
        newsub.appendChild(subtext)
        subs = slide.getElementsByTagName("submission")
        for sub in subs:
            if sub.getAttribute("from") == whofrom:
                slide.removeChild(sub)
        slide.appendChild(newsub)
        subs = slide.getElementsByTagName("submission")
        if n == self.__pos:
            self.emit('update-submissions', len(subs) - 1)

    def addInkToSlide(self, pathstr, islocal, n=None):
        """Adds ink to the current slide, or slide n if given.  Instructor ink may be added to any slide;
        but it only makes sense to add student ink to the current slide (n will be ignored)"""
        if n is None:
            slide = self.__slide
            instr_tag = self.__instructor_tag
            if instr_tag == None:
                instr_tag = self.__dom.createElement("instructor")
                slide.appendChild(instr_tag)
                self.__instructor_tag = instr_tag
        else:
            if n < self.getSlideCount and n >= 0:
                slide = self.__slides[n]
            else:
                slide = self.__slides[self.__pos]
            instr_tags = slide.getElementsByTagName("instructor")
            if len(instr_tags) > 0:
                instr_tag = instr_tags[0]
            else:
                instr_tag = self.__dom.createElement("instructor")
                slide.appendChild(instr_tag)
        if not islocal or self.__is_initiating:
            self.__instructor_ink.append(pathstr)
            path = self.__dom.createElement("path")
            path.appendChild(self.__dom.createTextNode(pathstr))
            instr_tag.appendChild(path)
        else:
            self.__self_ink.append(pathstr)
            if not self.__self_ink_tag:
                self.__self_ink_tag = self.__dom.createElement("self")
                self.__slide.appendChild(self.__self_ink_tag)
            path = self.__dom.createElement("path")
            path.appendChild(self.__dom.createTextNode(pathstr))
            self.__self_ink_tag.appendChild(path)
        if islocal:
            self.emit("local-ink-added", pathstr)
        else:
            if n is None or n == self.__pos:
                self.emit("remote-ink-added", pathstr)

    def clearInk(self, n=None):
        if n is None:
            n = self.__pos
        slide = self.__slides[n]
        if self.__is_initiating:
            self.clearInstructorInk(n)
            self.emit('instructor-ink-cleared', n)
        self_tags = slide.getElementsByTagName("self")
        for self_tag in self_tags:
            slide.removeChild(self_tag)
        self.__self_ink = []
        self.__self_ink_tag = None

    def clearInstructorInk(self, n=None):
        if n is None:
            n = self.__pos
        slide = self.__slides[n]
        instructor_tags = slide.getElementsByTagName("instructor")
        for instructor_tag in instructor_tags:
            slide.removeChild(instructor_tag)
        if n == self.__pos:
            self.__instructor_ink = []
            self.__instructor_tag = None
            self.emit('slide-redraw')

    def removeInstructorPathByUID(self, uid, n=None):
        if n is None:
            n = self.__pos
        needs_redraw = False
        slide = self.__slides[n]
        instructor_tags = slide.getElementsByTagName("instructor")
        if len(instructor_tags) > 0:
            instructor_tag = instructor_tags[0]
        else:
            return
        path_tags = instructor_tag.getElementsByTagName("path")
        for path_tag in path_tags:
            if path_tag.firstChild:
                pathstr = path_tag.firstChild.nodeValue
                path_uid = 0
                try:
                    path_uid = int(pathstr[0:pathstr.find(';')])
                except Exception, e:
                    pass
                if path_uid == uid:
                    instructor_tag.removeChild(path_tag)
                    needs_redraw = True
        if n == self.__pos and needs_redraw:
            self.emit('remove-path', uid)

    def removeLocalPathByUID(self, uid, n=None):
        if n is None:
            n = self.__pos
        slide = self.__slides[n]
        if self.__is_initiating:
            self.emit('instructor_ink_removed', uid, n)
            tags = slide.getElementsByTagName("instructor")
        else:
            tags = slide.getElementsByTagName("self")
        if len(tags) > 0:
            tag = tags[0]
        else:
            return
        path_tags = tag.getElementsByTagName("path")
        for path_tag in path_tags:
            if path_tag.firstChild:
                pathstr = path_tag.firstChild.nodeValue
                path_uid = 0
                try:
                    path_uid = int(pathstr[0:pathstr.find(';')])
                except Exception, e:
                    pass
                if path_uid == uid:
                    tag.removeChild(path_tag)

    def doSubmit(self):
        inks, text, whofrom = self.getSerializedInkSubmission()
        self.__logger.debug("Submitting ink: " + str(inks) + " text: " + text)
        self.emit('ink-submitted', inks, text)

    def doBroadcast(self):
        inks, text, whofrom = self.getSerializedInkSubmission()
        self.emit('ink-broadcast', whofrom, inks, text)

    def getSerializedInkSubmission(self):
        sub = ""
        text = ""
        if self.__active_sub == -1:
            self_tags = self.__slide.getElementsByTagName("self")
            if len(self_tags) > 0:
                texts = self_tags[0].getElementsByTagName("text")
                if len(texts) > 0:
                    if texts[0].firstChild:
                        text = texts[0].firstChild.nodeValue
                for path in self_tags[0].getElementsByTagName("path"):
                    sub = sub + path.firstChild.nodeValue + "$"
            return sub, text, "myself"
        else:
            sub = ""
            whofrom = "unknown"
            subtags = self.__slide.getElementsByTagName("submission")
            if self.__active_sub > -1 and self.__active_sub < len(subtags):
                active_subtag = subtags[self.__active_sub]
                text = ""
                whofrom = active_subtag.getAttribute("from")
                texts = active_subtag.getElementsByTagName("text")
                if len(texts) > 0:
                    if texts[0].firstChild:
                        text = texts[0].firstChild.nodeValue
                pathlist = []
                paths = active_subtag.getElementsByTagName("path")
                for path in paths:
                    if path.firstChild:
                        sub = sub + path.firstChild.nodeValue + "$"
            return sub, text, whofrom

    def getSlideThumb(self, n=-1):
        """Returns the full path to the thumbnail for this slide if it is defined; otherwise False"""
        if n == -1:
            n = self.__pos
        slide = self.__slides[n]
        print slide.toprettyxml()
        thumbs = slide.getElementsByTagName("thumb")
        if len(thumbs) < 1:
            return False
        return os.path.join(self.__base, thumbs[0].firstChild.nodeValue)

    def setSlideThumb(self, filename, n=-1):
        """Sets the thumbnail for this slide to filename (provide a *relative* path!)"""
        if n == -1:
            n = self.__pos
        slide = self.__slides[n]
        thumbs = slide.getElementsByTagName("thumb")
        for t in thumbs:
            slide.removeChild(t)
        thumb = self.__dom.createElement("thumb")
        thumb.appendChild(self.__dom.createTextNode(filename))
        slide.appendChild(thumb)

    def getSlideClip(self, n=-1):
        """Returns the full path to the audio clip for this slide if it is defined; otherwise False"""
        if n == -1:
            n = self.__pos
        slide = self.__slides[n]
        clip = slide.getElementsByTagName("clip")
        if len(clip) < 1:
            return False
        return os.path.join(self.__base, clip[0].firstChild.nodeValue)

    def setSlideClip(self, filename, n=-1):
        """Sets the clip for this slide to filename (provide a *relative* path!)"""
        if n == -1:
            n = self.__pos
        slide = self.__slides[n]
        clips = slide.getElementsByTagName("clip")
        for clip in clips:
            slide.removeChild(clip)
        clip = self.__dom.createElement("clip")
        clip.appendChild(self.__dom.createTextNode(filename))
        slide.appendChild(clip)

    def setSlideText(self, textval):
        self.__self_text = textval
        if self.__text_tag:
            if self.__text_tag.firstChild:
                self.__text_tag.firstChild.nodeValue = textval
            else:
                self.__text_tag.appendChild(self.__dom.createTextNode(textval))

    def doNewIndex(self):
        """Updates any necessary state associated with moving to a new slide"""
        self.__slide = self.__slides[self.__pos]
        #set slide title - entry text from xml
        self.set_SlideTitle(self.__slide.getAttribute('title'))

        self_ink = self.__slide.getElementsByTagName("self")
        self.__instructor_tag = None
        self.__self_ink_tag = None
        self.__instructor_ink = []
        self.__self_ink = []
        self.__self_text = ""
        self.__text_tag = None
        self.__active_sub = -1
        if len(self_ink) > 0:
            self.__self_ink_tag = self_ink[0]
            texttags = self.__self_ink_tag.getElementsByTagName("text")
            if len(texttags) > 0:
                self.__text_tag = texttags[0]
            else:
                self.__text_tag = self.__dom.createElement(text)
                self.__text_tag.appendChild(self.__dom.createTextNode(""))
                self.__self_ink_tag.appendChild(text)
            pathtags = self.__self_ink_tag.getElementsByTagName("path")
            for pathstr in pathtags:
                self.__self_ink.append(pathstr.firstChild.nodeValue)
        else:
            self.__self_ink_tag = self.__dom.createElement("self")
            self.__slide.appendChild(self.__self_ink_tag)
            self.__text_tag = self.__dom.createElement("text")
            self.__text_tag.appendChild(self.__dom.createTextNode(""))
            self.__self_ink_tag.appendChild(self.__text_tag)
        if self.__text_tag.firstChild:
            self.__self_text = self.__text_tag.firstChild.nodeValue
        self.__activity.set_screen(0)

        self.emit("slide-changed")
        self.emit("update-submissions", self.__active_sub)
        self.emit("slide-redraw")

    def goToIndex(self, index, is_local):
        """Jumps to the slide at the given index, if it's valid"""
        self.__logger.debug("Trying to change slides: locked? %u, instructor? %u, is_local? %u",
            self.__nav_locked, self.__is_initiating, is_local)

        in_range = index < self.__nslides and index >= 0

        if (self.__is_initiating or not is_local or not self.__nav_locked) and in_range:
            self.__logger.debug("Changing slide to index: %u", index)
            self.__pos = index
            self.doNewIndex()
        else:
            self.__pos = index
            print 'invalid index', index

    def getIndex(self):
        """Returns the index of the current slide"""
        return self.__pos

    def next(self):
        """Moves to the next slide"""
        self.goToIndex(self.__pos + 1, is_local=True)

    def previous(self):
        """Moves to the previous slide"""
        self.goToIndex(self.__pos - 1, is_local=True)

    def isAtBeginning(self):
        """Returns true if show is on the first slide in the deck"""
        if self.__nslides < 1:
            return True

        if self.__pos == 0:
            return True
        else:
            return False

    def isAtEnd(self):
        """Returns true if the show is at the last slide in the deck"""
        if self.__nslides < 1:
            return True

        if self.__pos == self.__nslides - 1:
            return True
        else:
            return False

    def getSlideDimensionsFromXML(self, n=-1):
        """Returns the dimensions for the slide at index n, if they're specified"""
        if n == -1:
            n = self.__pos
        slide = self.__slides[n]
        wstring = slide.getAttribute("width")
        hstring = slide.getAttribute("height")
        if wstring != '' and hstring != '':
            return [float(wstring), float(hstring)]
        return False

    def getSlideCount(self):
        return self.__nslides

gobject.type_register(Deck)
