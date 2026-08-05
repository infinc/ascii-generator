import math
import sys
import cv2
import time
import os
import numpy as np
import mimetypes

ASCII_CHARS_BLOCK = " ░▒▓█"
ASCII_CHARS_NORMAL = " .:-=+*#%@"
ASCII_CHARS_IMPACT = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
ASCII_CHARS_CYBER = "  .-+=<>!?0123456789$#@"
ASCII_CHARS_JAPANESE = "  .、トニコキホマ国魔驚鬱"
ASCII_CHARS_MINIMAL = "  .:+@"


def user_choice():
    print("-------ASCII ART ASSISTANT---------")
    print("1: Generate a monochrome ASCII ART")
    print("2: Generate a color ASCII ART")
    print("3: Play a gif file with ASCII ART")
    print("4: Convert ASCII ART to png file")
    print("5: Chat with other people by using achex")
    choice = int(input("Your choice: "))
    return choice


def gain_path(extension):
    print("Ex) cat.jpeg")
    print(f"This generator supports: {extension}")
    print("If you want to use sample, type s and press enter")
    path = input("Enter the path: ")
    if path == "s":
        print("You selected sample")
        path = "./cat.jpeg"
    return path


def change_size_function(width, height):
    question = input("Would you like to change a size?[y/n]: ")

    if question == "y" or question == "Y":
        try:
            new_width = math.ceil(int(input("Type a new width: ")))
        except ValueError:
            print("Error was occurred")
            new_width = width
        # ratio = math.ceil(width / height)
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


def rgb_generator(chars, pixels_rgb, pixels_gray, ter, width):
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
        if (i + 1) % width == 0:
            gen.append("\033[0m\n")

    return "".join(gen)


def save_ascii_art(result):
    if input("You want to save ASCII ART as .txt?[y:n]: ") == "y":
        with open("generated-art.txt", "w", encoding="utf-8") as f:
            f.write(result)
            print("Saved as generated-art.txt")
    else:
        return


def image_to_ascii_gray(gray, width, height):
    resized_image = cv2.resize(gray, (width, height))

    pixels = resized_image.flatten().astype(int)

    ascii_chars_list()
    choose = input("Choose characters: ")
    if choose == "1":
        result = gray_generator(ASCII_CHARS_NORMAL, pixels, width)
        print(result)
        save_ascii_art(result)
    elif choose == "2":
        result = gray_generator(ASCII_CHARS_BLOCK, pixels, width)
        print(result)
        save_ascii_art(result)
    elif choose == "3":
        result = gray_generator(ASCII_CHARS_IMPACT, pixels, width)
        print(result)
        save_ascii_art(result)
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
        print(rgb_generator(ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, ter, width))
    elif choose == "2":
        print(rgb_generator(ASCII_CHARS_BLOCK, pixels_rgb, pixels_gray, ter, width))
    elif choose == "3":
        print(rgb_generator(ASCII_CHARS_IMPACT, pixels_rgb, pixels_gray, ter, width))
    else:
        print("You inputted wrong choice. Defaulting to 1.")
        print(rgb_generator(ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, ter, width))


def gif_to_ascii_gray(width, height, cap, sleep_time):
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
        sys.stdout.write(f"\033[{height + 2}H")
        print("\n\nfinished")
    finally:
        cap.release()


def ascii_to_image(path, chars):
    if not os.path.exists(path):
        print(f"エラー: {path} が見つかりません。")
        return
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_height = len(lines)
    new_width = len(lines[0])
    num_chars = len(chars)
    char_to_gray = {
        char: int((i / (num_chars - 1)) * 255) for i, char in enumerate(chars)
    }
    img_array = np.zeros((new_height, new_width), dtype=np.uint8)
    for y, line in enumerate(lines):
        current_width = min(len(line), new_width)
        for x in range(current_width):
            char = line[x]
            img_array[y, x] = char_to_gray.get(char, 0)

    cv2.imwrite("Generated-photos.png", img_array)
    print("Saved as Generated-photos.png")
    print("This photos ratio is (width:height)" + str(new_width) + ": " + str(new_height))


def command_list():
    print(f"\r[Helper]Command list")
    print(f"\r/cmd ... Show all commands")
    print(f"\r/file <file> ... Send file (only text-based file)")
    print(f"\r/show ... Show latest text-based file's content")
    print(f"\r/download ... Download latest file")
    print(f"\r/generate <path> <[gray/color]> <width> <factor(default=0.55)> ... Generate ascii art instantly")


def help():
    print(f"\r[Helper]To leave the chat, type exit")
    print(f"\r[Helper]To show all commands, type /cmd")
