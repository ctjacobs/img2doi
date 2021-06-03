""" img2doi is a smartphone application that captures any DOIs in a photo taken by the camera, and looks up their bibliographic information.

The MIT License

Copyright 2021 Christian T. Jacobs

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import cv2
import pytesseract
import random
import re
#import gi
#gi.require_version('Gst', '1.0')

from doi2bib.crossref import get_bib_from_doi

import os
#os.environ['KIVY_GL_BACKEND'] = 'sdl2'
os.environ['KIVY_IMAGE'] = 'pil'

from kivy_garden.xcamera import *
from kivy_garden.xcamera.platform_api import *

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.properties import BooleanProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.core.clipboard import Clipboard

# Note: RecycleView-related code taken from https://kivy.org/doc/stable-1.10.1/api-kivy.uix.recycleview.html

Builder.load_string('''
<DOIView>:
    viewclass: 'SelectableLabel'
    SelectableRecycleBoxLayout:
        key_selection: "True"
        default_size: None, dp(56)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'
        multiselect: False
        touch_multiselect: True
        touch_deselect_last: True
''')


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''


class SelectableLabel(RecycleDataViewBehavior, Label):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(SelectableLabel, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected


class DOIView(RecycleView):
    """ The list of DOIs captured from the camera. """
    def __init__(self, **kwargs):
        super(DOIView, self).__init__(**kwargs)
        self.data = []
    
    def add(self, doi):
        """ Add a DOI to the list. """
        self.data.append({'text': doi})

    def clear(self):
        """ Clear all DOIs from the list. """
        self.data.clear()

class MyCamera(XCamera):
    def __init__(self):
        super(MyCamera, self).__init__()
        set_orientation(PORTRAIT)

    def shoot(self):
        def on_success(filename):
            self.dispatch('on_picture_taken', filename)
        filename = "capture.png"
        take_picture(self, filename, on_success)

class IMG2DOI(App):
    """ The main application class. The application enables a user to take a photo of one or more DOIs (e.g. written on a poster). Optical character recognition (OCR) and regular expressions are then used to detect the DOI(s) and list them in the app. If the user clicks on one of the listed DOIs, the app looks up the bibliographic details and displays them in the Harvard referencing format. These bibliographic details can then be copied to the clipboard for use elsewhere (e.g. on social media). """

    def __init__(self):
        super(IMG2DOI, self).__init__()
        
        # The DOI handler.
        self.doi = DOI()

        return

    def build(self):
        """ Construct the interface. """
        self.layout = BoxLayout(orientation='vertical', padding=2)

        self.camera_layout = BoxLayout(orientation='vertical', padding=2)

        self.camera = MyCamera()
        self.camera_layout.add_widget(self.camera)

        self.doi_layout = BoxLayout(orientation ='vertical') 

        # List of DOIs.
        self.list_doi = DOIView()
        self.list_doi.layout_manager.bind(selected_nodes=self.on_doi_click)
        self.doi_layout.add_widget(self.list_doi)

        # Bib box.
        self.bib_text = TextInput(text='')
        self.doi_layout.add_widget(self.bib_text)

        # Buttons.
        self.button_layout = BoxLayout(orientation ='horizontal') 

        # 'Take Photo' button.
        self.camera_click = Button(text="Take Photo")
        self.button_layout.add_widget(self.camera_click)
        self.camera_click.bind(on_press=self.on_camera_click)

        # Clipboard button.
        self.btn_clipboard = Button(text="Copy to Clipboard")
        self.button_layout.add_widget(self.btn_clipboard)
        self.btn_clipboard.bind(on_press=self.on_copy_click)

        self.doi_layout.add_widget(self.button_layout)

        # Layouts.
        self.layout.add_widget(self.camera_layout)
        self.layout.add_widget(self.doi_layout)

        return self.layout

    def on_camera_click(self, *args):
        """ When the camera button is clicked, export the captured image to a file and perform OCR on it. All DOIs will be added to a list. """
        self.list_doi.clear()
        self.camera.shoot()
        dois = self.doi.search()
        print(dois)
        for d in dois:
            self.list_doi.add(d)
        return

    def on_doi_click(self, inst, val):
        """ When a DOI entry is clicked, perform a lookup, convert the reference to Harvard format and display it in the bibliography text box. The user can then edit the entry if necessary. """
        if(val):
            doi = self.list_doi.data[val[0]]['text']
            if(doi):
                result = self.doi.lookup(doi)
                if(result):
                    harvard = self.bib_to_harvard(result, doi)
                    self.bib_text.insert_text(harvard)
                    
        return

    def on_copy_click(self, *args):
        """ If the copy button is pressed, copy all text in the bibliography box to the clipboard. """
        self.bib_text.select_all()
        self.bib_text.copy()
        return

    def bib_to_harvard(self, bib, doi):
        """ Convert the BibTeX reference to Harvard format. """

        # Get author(s).
        results = re.search(r"author = (.+)", bib, re.MULTILINE | re.IGNORECASE)
        if(results):
            author = results.group(1)
        else:
            author = ""

        # Get year.
        results = re.search(r"year = ([0-9]+)", bib, re.MULTILINE | re.IGNORECASE)
        if(results):
            year = results.group(1)
        else:
            year = ""

        # Get title.
        results = re.search(r"title = (.+)", bib, re.MULTILINE | re.IGNORECASE)
        if(results):
            title = results.group(1)
        else:
            title = ""

        # Get journal.
        results = re.search(r"journal = (.+)", bib, re.MULTILINE | re.IGNORECASE)
        if(results):
            journal = results.group(1)
        else:
            journal = ""

        s = "%s (%s). %s. %s. doi:%s" % (author, year, title, journal, doi)

        return s

class DOI(object):
    """ The DOI handler. """
    def __init__(self):
        return

    def search(self):
        dois = []

        raw = cv2.imread('capture.png')
        raw = cv2.resize(raw, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        grey = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)

        threshold = cv2.adaptiveThreshold(grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 5)

        custom_config = r'-c tessedit_char_blacklist={},'
        data = pytesseract.image_to_data(threshold, output_type=pytesseract.Output.DICT, config=custom_config)

        pattern = r"10.\d{4,9}/[-._;()/:A-Z0-9]+$"

        n_boxes = len(data['level'])
        print("n_boxes = %d" % n_boxes)
        for i in range(n_boxes-1):
            (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
            cv2.rectangle(threshold, (x, y), (x + w, y + h), (0, 255, 0), 2)

            results = re.search(pattern, data['text'][i], re.IGNORECASE)
            if(results):
                
                doi = results.group(0)
                if(doi[-1] == "."):
                    # Cut off the trailing full stop.
                    doi = doi[:-1]

                (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                cv2.rectangle(threshold, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(threshold, "DOI = %s, Confidence = %d%%" % (doi, int(data['conf'][i])), (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

                dois.append(doi)

        return dois

    def lookup(self, doi):
        """ Obtain information about the DOI (author(s), year, title, etc) in BibTeX format. """
        found, bib = get_bib_from_doi(doi)
        if(found):
            return bib
        else:
            return None


if __name__ == '__main__':
    app = IMG2DOI()
    app.run()
