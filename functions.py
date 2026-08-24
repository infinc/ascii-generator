import math
import sys
import cv2
import time
import os
import numpy as np

ASCII_CHARS_BLOCK = " ░▒▓█"
ASCII_CHARS_NORMAL = " .:-=+*#%@"
ASCII_CHARS_IMPACT = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def user_choice():
    print("-------アスキーアート---------")
    print("1: 画像から白黒のASCII ARTを生成します")
    print("2: 画像からカラーのASCII ARTを生成します")
    print("3: gif画像から白黒のASCII ARTに変換し再生します")
    print("4: ASCII ARTをpng画像に変換します")
    print("5: Achexを使用してチャットします")
    try:
        choice = int(input("選択: "))
        return choice
    except ValueError:
        print("エラー: 数字を入力してください")
        print("中止")
        sys.exit()

def read_image(path):
    """cv2.imread の代わり。cv2 が対応していない HEIC/HEIF は pillow-heif で読む。"""
    img = cv2.imread(path)
    if img is not None:
        return img

    if os.path.splitext(path)[1].lower() not in (".heic", ".heif"):
        return None

    try:
        import pillow_heif
    except ImportError:
        print("エラー: HEICを読み込むには pillow-heif が必要です。")
        print("pip install -r requirements.txt を実行してください。")
        return None

    try:
        heif = pillow_heif.read_heif(path)
        arr = np.ascontiguousarray(np.asarray(heif))
    except Exception as e:
        print(f"エラー: HEICを読み込めませんでした。({e})")
        return None

    # cv2 と同じ BGR 並びに揃える
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def gain_path(extension, sample):
    print("例) cat.jpeg")
    print(f"対応している拡張子: {extension}")
    if sample != "":
        print("サンプルを使用するには、sと入力してください")
    path = input("パス(変換したい画像): ")
    if path == "s":
        if sample == "":
            print("エラー: サンプルはありません。")
            sys.exit()
        print("サンプルを選択しました")
        path = "./" + sample
    return path


def change_size_function(width, height):
    question = input("サイズを変更しますか?[y/n]: ")

    if question == "y" or question == "Y":
        try:
            new_width = math.ceil(int(input("横幅を入力: ")))
        except ValueError:
            print("エラー: 数字を入力してください")
            print("生成中止")
            sys.exit()
        try:
            print("補正係数はfloat(小数点を含む数字)である必要があります")
            factor = float(input("補正係数を入力してください(デフォルト=0.55): "))
        except ValueError:
            print("エラー: 小数点を含む数字を入力してください")
            print("生成中止")
            sys.exit()
        new_height = math.ceil(height * (new_width / width) * factor)
    elif question == "n" or question == "N":
        try:
            print("補正係数はfloat(小数点を含む数字)である必要があります")
            factor = float(input("補正係数を入力してください(デフォルト=0.55): "))
        except ValueError:
            print("エラー: 小数点を含む数字を入力してください")
            print("生成中止")
            sys.exit()
        new_width = width
        new_height = math.ceil(height * (new_width / width) * factor)
    else:
        print("エラー: y、又はnを選択してください")
        print("生成中止")
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


def rgb_generator(chars, pixels_rgb, pixels_gray, width):
    num_chars = len(chars)
    gen = []

    for i in range(len(pixels_gray)):
        brightness = pixels_gray[i]
        char = chars[brightness * num_chars // 256]
        r, g, b = pixels_rgb[i]

        color_code = rgb_to_256(r, g, b)
        colored_char = f"\033[38;5;{color_code}m{char}"

        gen.append(colored_char)
        if (i + 1) % width == 0:
            gen.append("\033[0m\n")

    return "".join(gen)


def save_ascii_art(result):
    opinion = input(".txtとしてASCII ARTを保存しますか?[y:n]: ")
    if opinion == "y" or opinion == "Y":
        with open("generated-art.txt", "w", encoding="utf-8") as f:
            f.write(result)
            print("generated-art.txtとして保存しました")
            sys.exit()
    else:
        return


def image_to_ascii_gray(gray, width, height):
    resized_image = cv2.resize(gray, (width, height))

    pixels = resized_image.flatten().astype(int)

    ascii_chars_list()
    choose = input("文字を選択: ")
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
        print("エラー: 1、2、又は3を選択してください")
        print("デフォルトで1を選択します")
        result = gray_generator(ASCII_CHARS_NORMAL, pixels, width)
        print(result)
        save_ascii_art(result)


def image_to_ascii_rgb(gray, rgb, width, height):
    resized_rgb = cv2.resize(rgb, (width, height))
    resized_gray = cv2.resize(gray, (width, height))

    pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
    pixels_gray = resized_gray.flatten().astype(int)

    ascii_chars_list()
    choose = input("文字を選択: ")
    if choose == "1":
        result = rgb_generator(ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, width)
        print(result)
        save_ascii_art(result)
    elif choose == "2":
        result = rgb_generator(ASCII_CHARS_BLOCK, pixels_rgb, pixels_gray, width)
        print(result)
        save_ascii_art(result)
    elif choose == "3":
        result = rgb_generator(ASCII_CHARS_IMPACT, pixels_rgb, pixels_gray, width)
        print(result)
        save_ascii_art(result)
    else:
        print("エラー: 1、2、又は3を選択してください")
        print("デフォルトで1を選択します")
        result = rgb_generator(ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, width)
        print(result)
        save_ascii_art(result)


def gif_to_ascii_gray(width, height, cap, sleep_time):
    ascii_chars_list()
    choose = input("文字を選択: ")
    if choose == "1":
        selected_chars = ASCII_CHARS_NORMAL
    elif choose == "2":
        selected_chars = ASCII_CHARS_BLOCK
    elif choose == "3":
        selected_chars = ASCII_CHARS_IMPACT
    else:
        print("エラー: 1、2、又は3を選択してください")
        print("デフォルトで1を選択します")
        selected_chars = ASCII_CHARS_NORMAL

    print("\n--- 3秒後に開始します。Ctrl + Cで中止します ---")
    time.sleep(3)
    os.system('cls' if os.name == 'nt' else 'clear')

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
    import re
    if not os.path.exists(path):
        print(f"エラー: {path} は存在しません。")
        print("生成中止")
        sys.exit()

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f.readlines()]

    if not lines:
        return

    def clean_text(text):
        return re.sub(r'\x1b\[[0-9;]*m', '', text)

    new_height = len(lines)
    new_width = max((len(clean_text(line)) for line in lines), default=0)

    if new_width == 0:
        return

    num_chars = len(chars)
    char_to_gray = {
        char: int((i / (num_chars - 1)) * 255) for i, char in enumerate(chars)
    }
    img_array = np.zeros((new_height, new_width, 3), dtype=np.uint8)

    for y, line in enumerate(lines):
        parts = re.split(r'(\x1b\[[0-9;]*m)', line)
        current_color = None
        x = 0

        for part in parts:
            if not part:
                continue

            if part.startswith('\x1b['):
                m = re.match(r'\x1b\[([0-9;]+)m', part)
                if m:
                    codes = m.group(1).split(';')
                    if len(codes) >= 3 and codes[0] == '38':
                        if codes[1] == '5' and len(codes) == 3:
                            code = int(codes[2])
                            if code >= 16:
                                code -= 16
                                r = int(((code // 36) / 5) * 255)
                                g = int((((code % 36) // 6) / 5) * 255)
                                b = int(((code % 6) / 5) * 255)
                                current_color = (b, g, r)
                        elif codes[1] == '2' and len(codes) == 5:
                            r, g, b = int(codes[2]), int(codes[3]), int(codes[4])
                            current_color = (b, g, r)
                    elif codes[0] == '0':
                        current_color = None
            else:
                for char in part:
                    if x < new_width:
                        gray_val = char_to_gray.get(char, 0)
                        if current_color is None:
                            img_array[y, x] = (gray_val, gray_val, gray_val)
                        else:
                            if char == ' ' or gray_val == 0:
                                img_array[y, x] = (0, 0, 0)
                            else:
                                img_array[y, x] = current_color
                        x += 1
    restored_height = int(new_height / 0.55)
    img_array = cv2.resize(img_array, (new_width, restored_height), interpolation=cv2.INTER_LINEAR)

    cv2.imwrite("Generated-photos.png", img_array)
    print("Generated-photos.png として保存しました")
    print("この画像の比率は(横:縦)" + str(new_width) + ": " + str(restored_height))


def command_list():
    print(f"\r[Helper]コマンドリスト")
    print(f"\r/cmd ... 全てのコマンドを表示します")
    print(f"\r/help ... ヘルプを表示します")
    print(f"\r/file <file> ... ファイルを送信します(テキストベースのファイルのみ)")
    print(f"\r/show ... 最新のファイルの中身を表示します")
    print(f"\r/download <[raw/png]> ... 最新のファイルを　.txt(そのまま) もしくは　.png(写真に変換)して保存します")
    print(f"\r/generate <path> <[gray/color]> <width> <factor(default=0.55)> ... すぐにASCII ARTを生成します")
    print(f"\r/clear ... 画面を綺麗にします")


def clear_screen():
    try:
        lines = os.get_terminal_size().lines
    except OSError:
        lines = 0
    if lines < 5:
        lines = 40
    print("\n" * lines, end="")
    print(f"\r[System]画面をクリアしました")


def help_list():
    print(f"\r[Helper]退出するには/exitと入力してください")
    print(f"\r[Helper]全てのコマンドを出力するには、/cmdと入力してください")
    print(f"\r[Helper]デフォルトの補正係数は0.55です。")
