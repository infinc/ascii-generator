import argparse
import math
import mimetypes
import chat_functions
import functions
from functions import cv2
from functions import sys


def parse_cli_args(argv):
    parser = argparse.ArgumentParser(prog="main.py")
    parser.add_argument("path", help="変換する画像のパス")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--color", action="store_true", help="カラーASCII ARTを生成")
    mode_group.add_argument("--gray", action="store_true", help="白黒ASCII ARTを生成")
    parser.add_argument("--factor", type=float, default=0.55, help="補正係数(デフォルト=0.55、指定なし=0.55)")
    parser.add_argument("--width", type=int, default=None, help="出力の横幅(指定なし=画像の横幅)")
    parser.add_argument("--save", action="store_true", help="生成したASCII ARTをgenerated-art.txtとして保存(指定なし=保存しない)")
    return parser.parse_args(argv)


def run_cli(argv):
    args = parse_cli_args(argv)

    if not functions.is_image_path(args.path):
        print("エラー: 未対応のファイル、または拡張子の可能性があります。")
        sys.exit(1)

    img = functions.read_image(args.path)
    if img is None:
        print(f"エラー: {args.path} を読み込めませんでした。パスを確認してください。")
        sys.exit(1)

    if args.width is not None and args.width <= 0:
        print("エラー: --widthは1以上の整数で指定してください。")
        sys.exit(1)

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        orig_height, orig_width = gray.shape
        width = args.width if args.width is not None else orig_width
        new_height = math.ceil(orig_height * (width / orig_width) * args.factor)

        if args.color:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            resized_rgb = cv2.resize(rgb, (width, new_height))
            resized_gray = cv2.resize(gray, (width, new_height))
            pixels_rgb = resized_rgb.reshape(-1, 3).astype(int)
            pixels_gray = resized_gray.flatten().astype(int)
            result = functions.rgb_generator(functions.ASCII_CHARS_NORMAL, pixels_rgb, pixels_gray, width)
        else:
            resized_gray = cv2.resize(gray, (width, new_height))
            pixels = resized_gray.flatten().astype(int)
            result = functions.gray_generator(functions.ASCII_CHARS_NORMAL, pixels, width)
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

    print(result)

    if args.save:
        with open("generated-art.txt", "w", encoding="utf-8") as f:
            f.write(result)
        print("generated-art.txtとして保存しました")


if len(sys.argv) > 1:
    run_cli(sys.argv[1:])
else:
    match functions.user_choice():
        case 1:
            path = functions.gain_path(".jpg .jpeg .png .webp .heic", "sample.jpg")
            if functions.is_image_path(path):
                img = functions.read_image(path)
                if img is None:
                    print(f"エラー: {path} を読み込めませんでした。パスを確認してください。")
                    print("生成中止")
                    sys.exit()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                height, width = gray.shape
                print("この画像の比率は(横:縦)" + str(width) + ":" + str(height))
                width, height = functions.change_size_function(width, height)
                functions.image_to_ascii_gray(gray, width, height)
                print("生成成功")
            else:
                print("エラー: 未対応のファイル、または拡張子の可能性があります。")
                print("生成中止")
                sys.exit()

        case 2:
            path = functions.gain_path(".jpg .jpeg .png .webp .heic", "sample.jpg")
            if functions.is_image_path(path):
                img = functions.read_image(path)
                if img is None:
                    print(f"エラー: {path} を読み込めませんでした。パスを確認してください。")
                    print("生成中止")
                    sys.exit()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                height, width = gray.shape
                print("この画像の比率は(横:縦)" + str(width) + ":" + str(height))
                width, height = functions.change_size_function(width, height)
                functions.image_to_ascii_rgb(gray, rgb, width, height)
                print("生成成功")
            else:
                print("エラー: 未対応のファイル、または拡張子の可能性があります。")
                print("生成中止")
                sys.exit()

        case 3:
            path = functions.gain_path(".gif", "")
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type and (mime_type.startswith('video') or 'gif' in mime_type):
                cap = cv2.VideoCapture(path)
                if not cap.isOpened():
                    print("gif画像を読み込めません")
                    print("生成中止")
                    sys.exit()

                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                print("この画像の比率は(横:縦)" + str(width) + ": " + str(height))
                print("FPS(フレームレート): " + str(int(fps)))
                width, height = functions.change_size_function(width, height)
                try:
                    skip_frames = int(input("何フレームスキップしますか?(normal=1 or 2): "))
                    if skip_frames < 1:
                        print("エラー: 1以上の整数を入力してください。0は指定できません。")
                        print("生成中止")
                        sys.exit()
                except ValueError:
                    print("エラー: 数字を入力してください")
                    print("生成中止")
                    sys.exit()
                sleep_time = (1.0 / fps) * skip_frames if fps > 0 else 0.05
                functions.gif_to_ascii_gray(width, height, cap, sleep_time)
                print("生成成功")
            else:
                print("エラー: 未対応のファイル、または拡張子の可能性があります。")
                sys.exit()

        case 4:
            path = functions.gain_path(".txt", "grayASCII.txt")
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type == 'text/plain':
                functions.ascii_chars_list()
                print("画像に変換するには、生成に使用された文字の種類を選ぶ必要があります")
                choose = input("文字を選んでください: ")
                if choose == "1":
                    selected_chars = functions.ASCII_CHARS_NORMAL
                elif choose == "2":
                    selected_chars = functions.ASCII_CHARS_BLOCK
                elif choose == "3":
                    selected_chars = functions.ASCII_CHARS_IMPACT
                else:
                    print("エラー: 1、2、又は3を選んでください。")
                    print("生成中止")
                    sys.exit()
                functions.ascii_to_image(path, selected_chars)

            else:
                print("エラー: 未対応のファイル、または拡張子の可能性があります。")
                sys.exit()

        case 5:
            chat_functions.start()

        case _:
            print("エラー: 1、2、3、4、又は5を選んでください")
            print("中止")
            sys.exit()
