import chat
import properties
from properties import cv2
from properties import mimetypes
from properties import sys


match properties.user_choice():
    case 1:
        path = properties.gain_path("jpg jpeg png webp")
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and mime_type.startswith('image'):
            img = cv2.imread(path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width = gray.shape
            print("This photos ratio is (width:height)" + str(width) + ":" + str(height))
            width, height = properties.change_size_function(width, height)
            properties.image_to_ascii_gray(gray, width, height)
            print("Generated completely")

    case 2:
        path = properties.gain_path("jpg jpeg png webp")
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and mime_type.startswith('image'):
            img = cv2.imread(path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width = gray.shape
            print("This photos ratio is (width:height)" + str(width) + ":" + str(height))
            width, height = properties.change_size_function(width, height)
            terminal = input("Which do you use, True Color(iTerm2,Pycharm,etc) or RGB(Terminal,etc)?[t/r]: ")
            properties.image_to_ascii_rgb(gray, rgb, width, height, terminal)
            print("Generated completely")

    case 3:
        path = properties.gain_path("gif")
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and (mime_type.startswith('video') or 'gif' in mime_type):
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
            width, height = properties.change_size_function(width, height)
            skip_frames = int(input("How many frames to skip? (normal=1 or 2): "))
            sleep_time = (1.0 / fps) * skip_frames if fps > 0 else 0.05
            properties.gif_to_ascii_gray(width, height, cap, sleep_time)
            print("Generated completely")

    case 4:
        path = properties.gain_path("txt")
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type == 'text/plain':
            properties.ascii_chars_list()
            print("To convert to image, You have to choose chars which used in the generation")
            choose = input("Choose characters: ")
            if choose == "1":
                selected_chars = properties.ASCII_CHARS_NORMAL
            elif choose == "2":
                selected_chars = properties.ASCII_CHARS_BLOCK
            elif choose == "3":
                selected_chars = properties.ASCII_CHARS_IMPACT
            else:
                sys.exit()
            properties.ascii_to_image(path, selected_chars)

    case 5:
        chat.start()
