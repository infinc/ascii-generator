import os

import cv2
import math
import mimetypes
import sys
import time


ASCII_CHARS_BLOCK = " ░▒▓█"
ASCII_CHARS_NORMAL = " .:-=+*#%@"
ASCII_CHARS_IMPACT = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
ASCII_CHARS_CYBER = "  .-+=<>!?0123456789$#@"
ASCII_CHARS_JAPANESE = "  .、トニコキホマ国魔驚鬱"
ASCII_CHARS_MINIMAL = "  .:+@"
ASCII_CHARS_LINE = "   .,-_~\/|()[]{}+*#%"


new_width = None
new_height = None
skip_frames = None
gray = None
rgb = None
identify = None
terminal = None
colored_char = None
gen = None

def change_size_function(width, height):
    question = input("Would you like to change a size?[y/n]: ")

    if question == "y" or question == "Y":
        try:
            new_width = math.ceil(int(input("Type a new width: ")))
        except ValueError:
            print("Error was occurred")
            new_width = width
        ratio = math.ceil(width / height)
        factor = float(input("Input a correction factor (normal=0.55): "))
        new_height = math.ceil(height * (new_width / width) * factor)
    elif question == "n" or question == "N":
        factor = float(input("Input a correction factor (normal=0.55): "))
        new_width = width
        new_height = math.ceil(height * (new_width / width) * factor)
    else:
        print("You inputted wrong choice")
        print("Aborted")
        sys.exit()

    return new_width, new_height





print("-------ASCII ART GENERATOR---------")
print("Ex) cat.jpeg")
print("This generator supports: jpg, jpeg, png, webp, gif")
print("If you want to use sample, type s and press enter")
path = input("Enter the path: ")
if path == "s":
    print("You selected sample")
    path = "./cat.jpeg"


if path.lower().endswith(".gif"):
    print("You selected gif")
    identify = "gif"
    cap = cv2.VideoCapture(path)

    if not cap.isOpened():
        print("Error was occurred")
        print("Aborted")
        sys.exit()

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0 or fps != fps:
        fps = 15.0
    sleep_time = 1.0 / fps
    print("This gifs ratio is (width:height)" + str(width) + ":" + str(height))
    new_width, new_height = change_size_function(width, height)
    speed_factor = float(input("Choose a playback speed(normal=1.0, 2x=2.0): "))
    sleep_time = sleep_time / speed_factor


else:
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type and mime_type.startswith('image'):
        print("You selected image")
        identify = "image"
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width = gray.shape
        print("This photos ratio is (width:height)" + str(width) + ":" + str(height))
        new_width, new_height = change_size_function(width, height)



    elif mime_type and mime_type.startswith('video'):
        print("You selected video")
        identify = "video"
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print("Error was occurred")
            print("Aborted")
            sys.exit()

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print("This videos ratio is (width:height)" + str(width) + ": " + str(height))
        print("FPS: " + str(int(fps)))
        new_width, new_height = change_size_function(width, height)
        skip_frames = int(input("How many frames to skip? (normal=1 or 2): "))
        sleep_time = (1.0 / fps) * skip_frames if fps > 0 else 0.05

        print("\n--- Starting Video in 3 seconds... Press Ctrl+C to stop ---")
        time.sleep(3)


    else:
        print("You selected wrong file")
        print("Aborted")
        sys.exit()



def ascii_chars_list():
    print("1: " + ASCII_CHARS_NORMAL)
    print("2: " + ASCII_CHARS_BLOCK)
    print("3: " + ASCII_CHARS_IMPACT)

def rgb_to_256(r, g, b):
    r_idx = round(r / 255 * 5)
    g_idx = round(g / 255 * 5)
    b_idx = round(b / 255 * 5)

    return 16 + (36 * r_idx) + (6 * g_idx) + b_idx


def gray_generator(chars, pixels, width):
    num_chars = len(chars)
    ascii_str = "".join([chars[pixel * num_chars // 256] for pixel in pixels])
    ascii_image = "\n".join(ascii_str[i:(i + width)] for i in range(0, len(ascii_str), width))
    return ascii_image


def rgb_generator(chars, pixels_rgb, pixels_gray, ter):
    num_chars = len(chars)
    gen = []

    for i in range(len(pixels_gray)):
        brightness = pixels_gray[i]
        char = chars[brightness * num_chars // 256]
        r, g, b = pixels_rgb[i]
        if ter == "t":
            colored_char = f"\033[38;2;{r};{g};{b}m{char}"

        elif ter == "r":
            color_code = rgb_to_256(r, g, b)
            colored_char = f"\033[38;5;{color_code}m{char}"

        else:
            print("Error was occurred")
            print("Aborted")
            sys.exit()

        gen.append(colored_char)
        if (i + 1) % new_width == 0:
            gen.append("\033[0m\n")

    return "".join(gen)

def image_to_ascii_gray(gray, width, height):
    resized_image = cv2.resize(gray, (width, height))

    pixels = resized_image.flatten().astype(int)

    ascii_chars_list()
    choose = input("Choose characters: ")
    if choose == "1":
        print(gray_generator(ASCII_CHARS_NORMAL, pixels, width))
    elif choose == "2":
        print(gray_generator(ASCII_CHARS_BLOCK, pixels, width))
    elif choose == "3":
        print(gray_generator(ASCII_CHARS_IMPACT, pixels, width))
    else:
        print("You inputted wrong choice")
        print("Aborted")
        sys.exit()


def image_to_ascii_rgb(gray, rgb, width, height, ter):
    resized_rgb = cv2.resize(rgb, (width, height))
    resized_gray = cv2.resize(gray, (width, height))

    pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
    pixels_gray = resized_gray.flatten().astype(int)

    ascii_chars_list()
    choose = input("Choose characters: ")
    if choose == "1":
        print(rgb_generator(ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, ter))
    elif choose == "2":
        print(rgb_generator(ASCII_CHARS_BLOCK, pixels_rgb, pixels_gray, ter))
    elif choose == "3":
        print(rgb_generator(ASCII_CHARS_IMPACT, pixels_rgb, pixels_gray, ter))
    else:
        print("You inputted wrong choice. Defaulting to 1.")
        print(rgb_generator(ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, ter))


def video_to_ascii_gray():
    print("test")


def gif_to_ascii_gray(width, height):
    ascii_chars_list()
    choose = input("Choose characters: ")
    if choose == "1":
        selected_chars = ASCII_CHARS_NORMAL
    elif choose == "2":
        selected_chars = ASCII_CHARS_BLOCK
    elif choose == "3":
        selected_chars = ASCII_CHARS_IMPACT
    else:
        print("You inputted wrong choice. Defaulting to 1.")
        selected_chars = ASCII_CHARS_NORMAL

    print("\n--- Starting Video in 3 seconds... Press Ctrl+C to stop ---")
    time.sleep(3)
    os.system('cls' if os.name == 'nt' else 'clear')

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            resized_gray = cv2.resize(gray, (width, height))
            pixels = resized_gray.flatten().astype(int)

            ascii_image = gray_generator(selected_chars, pixels, width)

            sys.stdout.write('\033[H')
            sys.stdout.write(ascii_image)
            sys.stdout.flush()
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        sys.stdout.write(f"\033[{new_height + 2}H")
        print("\n\nfinished")
    finally:
        cap.release()



if identify == "image":
    color = input("Which do you prefer, color or gray?[r/g]:")
    if color == "r":
        terminal = input("Which do you use, True Color(iTerm2,Pycharm,etc) or RGB(Terminal,etc)?[t/r]: ")
        image_to_ascii_rgb(gray, rgb, new_width, new_height, terminal)
    elif color == "g":
        image_to_ascii_gray(gray, new_width, new_height)
    else:
        print("You inputted wrong choice")
        print("Aborted")
        sys.exit()
elif identify == "video":
    video_to_ascii_gray()
elif identify == "gif":
    gif_to_ascii_gray(new_width, new_height)


print("Generated completely")