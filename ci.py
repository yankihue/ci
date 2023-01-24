import rumps
from AppKit import NSScreen
from PIL import Image, ImageFont, ImageDraw
from time import time, sleep
import json
import random
import os


class CiApp(object):
    def __init__(self):
        self.config = {
            "app_name": "Ci",
            "generate_poem": "Generate Ci",
            "interval": 1200,
        }
        self.app = rumps.App(self.config["app_name"])
        self.set_up_menu()
        self.generate_poem_button = rumps.MenuItem(
            title=self.config["generate_poem"], callback=self.generate_poem)
        self.app.menu = [self.generate_poem_button]
        self.interval = self.config["interval"]

    def set_up_menu(self):
        self.app.title = "词"

    def generate_poem(self, sender):
        __location__ = os.path.realpath(os.path.join(
            os.getcwd(), os.path.dirname(__file__)))

        self.set_up_menu()

        n = random.randint(1, 320)  # generate random poem id
        print(n)

        # with open('poems.json') as f:
        # data = json.load(f)
        with open(os.path.join(__location__, 'poems.json'), 'r') as f:
            data = json.load(f)

        def find_poem(n):  # extract poem from json
            for keyval in data:
                if n == keyval['id']:
                    return keyval['contents']

        if (find_poem(n) != None):
            title_text = find_poem(n)

        def find_title(n):  # extract poem title from json
            for keyval in data:
                if n == keyval['id']:
                    return keyval['title']
        if (find_title(n) != None):
            title = find_title(n)

        base = Image.open(os.path.join(
            __location__, 'base.jpeg'))  # open base image

        image_editable = ImageDraw.Draw(base)  # make it editable

        ttf = ImageFont.truetype(
            'qiji-combo.ttf', 64)  # load font

        # get the size of the poem with font
        w, h = image_editable.textsize(title_text, font=ttf)

        image_editable.text(((NSScreen.mainScreen().frame().size.width-w)/2, (NSScreen.mainScreen().frame().size.height-h)/2), title_text,
                            (49, 27, 8, 64), font=ttf)  # center the poem itself

        # get the size of the title with font
        w2, h2 = image_editable.textsize(title, font=ttf)

        # center the title horizontally, keep it above the poem vertically
        image_editable.text(((NSScreen.mainScreen().frame().size.width-w2)/2, ((NSScreen.mainScreen().frame().size.height-h)/2)-h),
                            title, (49, 27, 8, 64), font=ttf)

        base.save('output.jpeg')  # save output
        print(title_text)
        print("Current screen resolution: %dx%d" % (NSScreen.mainScreen(
        ).frame().size.width, NSScreen.mainScreen().frame().size.height))
        # change macos wallpaper
        command = "osascript -e 'tell application \"System Events\" to tell every desktop to set picture to \"/Users/yanki/Desktop/ci/output.jpeg\" as POSIX file'"
        os.system(command)

    def run(self):
        self.app.run()


if __name__ == '__main__':
    app = CiApp()
    app.run()
