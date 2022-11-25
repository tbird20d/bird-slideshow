#!/usr/bin/python3
#
# bird-slideshow.py - a slideshow app, with network support and async
#     image loading
#
# todo:
#   add usage help

debug = False

import os
import sys
import requests
from urllib.parse import urlparse
from tkinter import *
from PIL import Image, ImageTk
from bs4 import BeautifulSoup

class Config:
    def __init__(self, config_file=None):
        # Configurable items
        self.sources = []
        self.wait_time = 5
        self.start_full = False
        self.win_res = "958x720"
        self.max_grow = 4.0
        self.cache_dir = "cache"

        self.config_file = config_file

    def read_config(self):
        with open(self.config_file) as options_file:
            for line in options_file:
                if not line or line.startswith("#"):
                    continue
                name, value = line.strip().split("=", 1)

                if name == "source":
                    source = value
                    self.sources.append(source)
                elif name == "wait_time":
                    self.wait_time = int(float(value) * 1000)
                elif name == "start_full":
                    self.start_full = {"True":True, "False":False}[value.capitalize()]
                elif name == "default_resolution":
                    self.win_res = value
                elif name == "max_grow":
                    self.max_grow = float(value)
                elif name ==  "cache_dir":
                    self.cache_dir = value
                else:
                    print("Unknown config option: '%s'" % name)

    def input_config(self):
        num_sources = int(input("Number of image sources (from directories or webpages): "))
        for count in range(num_sources):
            source = input("Source of images (directory or url): ")
            self.sources.append(source)
        self.wait_time = int(float(input("Wait time in seconds: ")) * 1000)
        self.start_full = {"True":True, "False":False}[input("Start in fullscreen mode (True/False): ").capitalize()]
        self.win_res = input("Window resolution (in the form '{width}x{height}'): ")
        self.max_grow = float(input("Max growth factor for image resizing (2 = 200%): "))
        self.cache_dir = input("Directory for cache: ")
        

def dprint(msg):
    global debug
    if debug:
        print("DEBUG:", str(msg))

# Globals
img_paths = []
pil_imgs = []
tk_imgs = []
imgs_index = -1

config = Config("options.txt")

win = None
canvas = None
win_width = 0
win_height = 0
is_full = False


# Get options inputs from file, else from console
def get_config():
    global is_full, win_width, win_height

    if config.config_file in os.listdir():
        config.read_config()
    else:
        config.input_config()

    is_full = config.start_full

    width, height = config.win_res.split('x')
    win_width = int(width)
    win_height = int(height)


# Create tkinter window and pack canvas to it
def init_window():
    global win, canvas

    win = Tk()
    win.title("Slideshow")
    win.geometry(config.win_res)
    canvas = Canvas(win,
        width = win_width,
        height = win_height,
        bg='black'
    )
    canvas.pack(fill=BOTH, expand=True)

    win.attributes("-fullscreen", config.start_full)
    win.bind("<F11>", toggle_fullscreen)
    win.bind("<Escape>", quit_window)
    win.bind("<Right>", rotate_img_forward)
    win.bind("<Left>", rotate_img_back)
    update_win_info()


def toggle_fullscreen(event):
    global is_full
    is_full = not is_full
    win.attributes("-fullscreen", is_full)


def quit_window(event):
    win.destroy()


def get_img_tags(html):
    # Parse HTML Code
    soup = BeautifulSoup(html, 'html.parser')
    # find all images in URL
    img_tags = soup.findAll('img')
    dprint("img_tags=%s" % img_tags)
    return img_tags


def get_http_paths(url):
    dprint("getting html for url %s" % url)
    html = requests.get(url).text
    dprint("html='%s'" % html)
    tags = get_img_tags(html)
    dprint("tags=%s" % tags)

    if not tags:
        print("Error: no image tags found on web page: %s" % url)
        return

    for img_tag in tags:
        # link = get_link(url, tag)

        # This does not handle srcset stuff

        base_url = os.path.dirname(url)
        dprint("base_url=%s" % base_url)
        url_parts = urlparse(url)
        url_prefix = url_parts.scheme + "://" + url_parts.netloc

        img_link = img_tag.get("src", None)

        if img_link.startswith("./"):
            img_link = url_prefix + img_link[1:]
        elif img_link.startswith("/"):
            img_link = url_prefix + img_link
        else:
            img_link = url_prefix + "/" + img_link

        dprint("Adding %s to img_paths" % img_link)
        img_paths.append(img_link)
        pil_imgs.append(None)
        tk_imgs.append(None)


def get_file_paths(directory):
    global img_paths, pil_imgs, tk_imgs

    saved_dir = os.getcwd()
    os.chdir(directory)
    img_filenames = os.listdir()

    if not img_filenames:
        print("Error: no image files found in directory %s" % directory)

    for filename in img_filenames:
        path = os.path.abspath(filename)
        img_paths.append(path)
        pil_imgs.append(None)
        tk_imgs.append(None)
    os.chdir(saved_dir)


def get_paths(sources):
    global img_paths

    for src in sources:
        if src.startswith("http"):
            get_http_paths(src)
        else:
            get_file_paths(src)

    if debug:
        for path in img_paths:
            dprint("path=%s" % path)


def async_preload_img(preload_index):
    global img_paths, pil_imgs
    dprint("IN ASYNC PRELOAD: preload_index = %s" % preload_index)

    img_path = img_paths[preload_index]
    pil_image = pil_imgs[preload_index]
    if not pil_image:
        pil_image = load_img(img_path)
        pil_imgs[preload_index] = pil_image


def download_img(cache_dir, img_link):
    dprint("In download_img (line 151) cache_dir = %s" % cache_dir)
    filename = os.path.basename(img_link)
    filepath = cache_dir + os.sep + filename

    if os.path.exists(filepath):
        print("Using img", filename, "from cache directory")
        return filepath

    try:
        print("Downloading img", img_link)
        response = requests.get(img_link)

        # print("filepath =", filepath)

        with open(filepath, "wb+") as f:
            f.write(response.content)

        return filepath

    except:
        print("Error", "Could not download %s" % img_link)
        return ""


def load_img(path):
    # print("loading image: " + path)
    if path.startswith("http"):
        filepath = download_img(config.cache_dir, path)
        if filepath:
            try:
                img = Image.open(filepath)
            except:
                img = None
        else:
            print("Error: could not load remote image from path %s" % path)
            img = None
    else:
        try:
            img = Image.open(path)
        except:
            print("Error: could not load image from path %s" % path)
            img = None

    return img


# bug: If only one path, will throw exception
def preload_imgs():
    for i in range(2):
        try:
            img = load_img(img_paths[i])
        except:
            img = None

        if img:
            pil_imgs[i] = img
    # print("done preloading imgs")


def resize_img(img):
    img_w, img_h = img.size
    w_scale_factor = win_width/img_w
    h_scale_factor = win_height/img_h


    # scale_factor = min(min(w_scale_factor, h_scale_factor), MAX_GROW)
    scale_factor = min(w_scale_factor, h_scale_factor)

    # print("DEBUG", scale_factor, MAX_GROW)

    # print("DEBUG", img_w, img_h, scale_factor, win_width, win_height)

    if scale_factor < .95 or scale_factor > 1.05:
        return img.resize((int(img_w*scale_factor), int(img_h*scale_factor)))


# Define rotation through each image in the directory after WAIT_TIME seconds
def update_img():
    global imgs_index
    global win_width, win_height
    global canvas

    dprint("DEBUG: IN UPDATE IMG: imgs_index = " + str(imgs_index))


    img_path = img_paths[imgs_index]
    # PIL images list
    pil_image = pil_imgs[imgs_index]
    if not pil_image:
        pil_image = load_img(img_path)
        pil_imgs[imgs_index] = pil_image
    else:
        dprint("using already-loaded image")

    # Resize the PIL
    if not pil_image:
        print("ERROR, pil_img was None, img_path =", img_path)
        return

    pil_img_r = resize_img(pil_image)

    # Save tkinter img into global array for python reference counting
    tk_image = ImageTk.PhotoImage(pil_img_r)
    tk_imgs[imgs_index] = tk_image

    canvas.delete("all")

    win_width = win.winfo_width()
    win_height = win.winfo_height()

    canvas.create_image(
        (win_width)/2,
        (win_height)/2,
        anchor = CENTER,
        image = tk_image
    )


def next_img():
    global imgs_index
    imgs_index += 1
    if imgs_index >= len(img_paths)-1:
        imgs_index -= len(img_paths)
    if imgs_index < 0:
        imgs_index += len(img_paths)

    update_img()
    win.after(config.wait_time, next_img)

    preload_index = imgs_index + 1
    if preload_index >= len(img_paths)-1:
        preload_index = 0

    win.after(100, async_preload_img(preload_index))


def rotate_img_forward(event):
    global imgs_index
    imgs_index += 1
    if imgs_index >= len(img_paths)-1:
        imgs_index -= len(img_paths)
    if imgs_index < 0:
        imgs_index += len(img_paths)

    update_img()


def rotate_img_back(event):
    global imgs_index

    imgs_index -= 1

    if imgs_index >= len(img_paths)-1:
        imgs_index -= len(img_paths)
    if imgs_index < 0:
        imgs_index += len(img_paths)

    update_img()


# Gets the current width and height of the window
def update_win_info():
    global win_width, win_height
    win_width = win.winfo_width()
    win_height = win.winfo_height()

    win.after(1, update_win_info)



def main():
    global debug
    if "--debug" in sys.argv:
        debug = True

    get_config()
    init_window()
    get_paths(config.sources)
    if not img_paths:
        print("Error: no images found. Aborting program")
        print("(Maybe check the 'source' lines in your config file?)")
        sys.exit(1)

    print('Slideshow is running in another window...')
    preload_imgs()

    win.after(100, next_img)

    win.mainloop()


main()
