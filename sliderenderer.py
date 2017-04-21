# -*- mode:python; tab-width:4; indent-tabs-mode:t;  -*-

# sliderenderer.py
#
# Class for rendering slides to a surface
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

import cairo
import rsvg
import gtk
import os
import utils
import time
import logging
import hulahop
import xml.dom.minidom
from sugar import env
hulahop.startup(os.path.join(env.get_profile_path(), 'gecko'))
from hulahop.webview import WebView

class Renderer(object):
    def __init__(self, activity, deck):
        """Constructs a new SlideRenderer that will render slides from deck"""
        self.__logger = logging.getLogger('Renderer')
        self.__logger.setLevel('error')
        self.__deck = deck
        self.__activity = activity
        self.__wv = WebView()
        self.__wv.show()
        self.__htmlflag = True

    def getSlideDimensionsFromFirstLayer(self, n=None):
        """Returns the [width, height] of the first slide layer"""
        if n is None:
            n = self.__deck.getIndex()
        layers = self.__deck.getSlideLayers(n)
        
        # return some default reasonable value if this is an empty slide
        if len(layers) == 0:
            return [640.0, 480.0]
        
        ftype = utils.getFileType(layers[0])
        
        # This may be optimizable to avoid having to open the first layer to get its size,
        # or at least keeping it around to re-use it when the slide is first rendered
        if ftype == "svg":
            f = open(layers[0], 'rb')
            svg_data = f.read()
            f.close()
            handle = rsvg.Handle(data=svg_data)
            a, b, w, h = handle.get_dimension_data()
            return [w,h]
        elif ftype == "png":
            surface = cairo.ImageSurface.create_from_png(layers[0])
            return [float(surface.get_width()), float(surface.get_height())]
        elif ftype == "jpg":
            pbuf = gtk.gdk.pixbuf_new_from_file(layers[0])
            return [float(pbuf.get_width()), float(pbuf.get_height())]
        else:
            return [640.0, 480.0]
    
    def getSlideDimensions(self, n=None):
        """Returns the slide dimensions, using the value in the XML file first, if it exists, and then the size of the first layer"""
        if n is None:
            n = self.__deck.getIndex()
        dims = self.__deck.getSlideDimensionsFromXML(n)
        if dims == False:
            return self.getSlideDimensionsFromFirstLayer(n)
        else:
            w, h = dims
            return [w, h]
    
    def renderSlideToSurface(self, surface, n=None):
        if n is None:
            n = self.__deck.getIndex()
            
        timerstart = time.time()
            
        self.__logger.debug("rendering slide " + str(n))
        ctx = gtk.gdk.CairoContext(cairo.Context(surface))
        #ctx = cairo.Context(surface)
        
        self.__logger.debug("Got context at " + str(time.time() - timerstart))
        
        # Get the slide dimensions and set up a Cairo transformation matrix
        srcw, srch = self.getSlideDimensions(n)
        if srcw > 640:
            srcw = 640
        if srch > 480:
            srch = 480
        targw = float(surface.get_width())
        targh = float(surface.get_height())
        x_scale = targw/srcw
        y_scale = targh/srch
        print 'rendering slide', str(n), "w=", targw, srcw, x_scale, "h=", targh, srch, y_scale
        
        self.__logger.debug("Surface is " + str(targw) +  "x" + str(targh)) 
        
        scale = x_scale
        if y_scale < x_scale:
            scale = y_scale
        
        if scale < .98 or scale > 1.02:
            ctx.transform(cairo.Matrix(scale, 0, 0, scale, 0, 0))
        
        self.__logger.debug("Got transformation matrix at " + str(time.time() - timerstart))
        
        # Paint the slide background
        ctx.set_source_rgb(1.0, 1.0, 1.0)
        ctx.rectangle(0, 0, srcw, srch)
        ctx.fill()
        
        self.__logger.debug("Filled background at " + str(time.time() - timerstart))
        
        # Paint the layers
        layers = self.__deck.getSlideLayers(n)
        self.__logger.debug("Got layers at " + str(time.time() - timerstart))
        for layer in layers:
            type = utils.getFileType(layer)
            print 'Drawing layer ', type, layer
            self.__logger.debug("Drawing layer " + str(layer) +" " + str(scale) + " at "  + str(time.time() - timerstart))
            print 'drawing layer', type, str(layer)
            if type == "svg":
                f = open(layer, "rb")
                svg_data = f.read()
                f.close()
                handle = rsvg.Handle(data=svg_data)
                handle.render_cairo(ctx)
            elif type == "png":
                png_surface = cairo.ImageSurface.create_from_png(layer)
                self.__logger.debug("Got PNG surface at "+ str(time.time() - timerstart))
                ctx.set_source_surface(png_surface, 0, 0)
                ctx.rectangle(0, 0, png_surface.get_width(), png_surface.get_height())
                ctx.fill()
            elif type == "jpg":
                jpg_pixbuf = gtk.gdk.pixbuf_new_from_file(layer)
                self.__logger.debug("Got JPG pixbuf at "+ str(time.time() - timerstart))
                ctx.set_source_pixbuf(jpg_pixbuf, 0, 0)
                ctx.rectangle(0, 0, jpg_pixbuf.get_width(), jpg_pixbuf.get_height())
                ctx.fill()
            elif type == "html":
                #use hulahop to display
                print 'html slide', self.__htmlflag, layer
                scrn4 = self.__activity.set_screen(3)
                if self.__htmlflag:
                    scrn4.add(self.__wv)
                    self.__htmlflag = False
                self.__wv.load_uri('file://' + layer)
                self.__wv.show()
            self.__logger.debug("Finished drawing layer at "+ str(time.time() - timerstart))
