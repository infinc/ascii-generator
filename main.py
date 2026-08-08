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
            print("この画像の比率は(横:縦)" + str(width) + ":" + str(height))
            width, height = properties.change_size_function(width, height)
            properties.image_to_ascii_gray(gray, width, height)
            print("生成成功")

    case 2:
        path = properties.gain_path("jpg jpeg png webp")
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type and mime_type.startswith('image'):
            img = cv2.imread(path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width = gray.shape
            print("この画像の比率は(横:縦)" + str(width) + ":" + str(height))
            width, height = properties.change_size_function(width, height)
            terminal = input("True Color(iTerm2,Pycharm,等)もしくは(Terminal,等)どちらを使いますか?(デフォルト=r)[t/r]: ")
            properties.image_to_ascii_rgb(gray, rgb, width, height, terminal)
            print("生成成功")

    case 3:
        path = properties.gain_path("gif")
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
            width, height = properties.change_size_function(width, height)
            try:
                skip_frames = int(input("何フレームスキップしますか?(normal=1 or 2): "))
            except ValueError:
                print("エラー: 数字を入力してください")
                print("生成中止")
                sys.exit()
            sleep_time = (1.0 / fps) * skip_frames if fps > 0 else 0.05
            properties.gif_to_ascii_gray(width, height, cap, sleep_time)
            print("生成成功")

    case 4:
        path = properties.gain_path("txt")
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type == 'text/plain':
            properties.ascii_chars_list()
            print("画像に変換するには、生成に使用された文字の種類を選ぶ必要があります")
            choose = input("文字を選んでください: ")
            if choose == "1":
                selected_chars = properties.ASCII_CHARS_NORMAL
            elif choose == "2":
                selected_chars = properties.ASCII_CHARS_BLOCK
            elif choose == "3":
                selected_chars = properties.ASCII_CHARS_IMPACT
            else:
                print("エラー: 1、2、又は3を選んでください。")
                print("生成中止")
                sys.exit()
            properties.ascii_to_image(path, selected_chars)

    case 5:
        chat.start()

    case _:
        print("エラー: 1、2、3、4、又は5を選んでください")
        print("中止")
        sys.exit()
