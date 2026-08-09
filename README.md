# ASCII ART GENERATOR
画像とアスキーアートの変換に特化したツールです

---

## 使用例

元画像 `sample.jpg`

<img width="189" height="252" alt="Image" src="https://github.com/user-attachments/assets/a900b6e8-18e2-4451-a744-b1c53ced8c92" />

`sample.jpg`を補正関数0.55、横幅100で白黒アスキーアートに変換した`grayASCII.txt`のスクリーンショット

<img width="304.5" height="410" alt="Image" src="https://github.com/user-attachments/assets/07ee0e2d-b1b7-4059-88e0-8d6552315b37" />

`sample.jpg`を補正関数0.55、横幅100でカラーアスキーアートに変換し、その後画像に再変換した画像 `colorConvert.png`

<img width="100" height="134" alt="Image" src="https://github.com/user-attachments/assets/c9cedeb7-227e-4fba-9ead-95a638362cbb" />



---

## 利用方法

プログラムを起動する手順をご説明します。

1. python 3.10以降のpythonをダウンロードします。
2. venv仮想環境を作成します。
```bash
python -m venv venv 
```
3. 仮想環境をactivateします。
```bash
source venv/bin/activate #Mac, Linux
venv\Scripts\activate.bat #Cmd.exe
```
4. requirements.txtを使用して必要なパッケージをインストールします。
```bash
pip install -r requirements.txt
```
5. main.pyを起動します。
```bash
python main.py
```

---

## 各項目の概要
### 1. 画像から白黒のASCII ARTを生成
- **説明**: 画像ファイル（JPG, JPEG, PNG, WEBP）を読み込み、白黒のアスキーアートを生成・表示します。
- **特徴**: サイズ変更や文字の濃淡（文字セット）の選択、結果のテキストファイル保存（`generated-art.txt`）が可能です。

### 2. 画像からカラーのASCII ARTを生成
- **説明**: 画像ファイルをカラーのアスキーアートに変換します。
- **特徴**: RGBで色を表現して色がついたアスキーアートを表示できます。テキストファイルとしても保存は可能で、文字の判別は不可能ですが画像に再変換可能です。

### 3. gif画像から白黒のASCII ARTに変換し再生
- **説明**: GIF動画ファイルを読み込み、ターミナル上でアスキーアートとしてアニメーション再生します。
- **特徴**: フレームのスキップ数（再生速度）の調整が可能です。（停止するには `Ctrl + C` を押します）

### 4. ASCII ARTをpng画像に変換
- **説明**: アスキーアートのテキストファイル（`.txt`）を読み込み、カラーのPNG画像（`Generated-photos.png`）として復元します。
- **特徴**: 生成時に使用された文字セット（Normal, Block, Impact）に合わせた復元を行います。

### 5. Achexを使用してチャット
- **説明**: WebSocketを利用したチャットルームに参加し、他のユーザーとメッセージやファイルをやり取りできます。
- **特徴**: 
  - 自分の名前、ルーム名、ルームのパスワードを設定して入室します。
  - 最初に参加する人はルーム名とパスワードは何でもよいですが、ほかの人がその部屋に参加したい場合ルーム名とパスワードは同じ値を入力してください。
  - チャット中に `/generate` コマンドで即座にアスキーアートを生成・共有したり、`/file` コマンドでテキストファイルを送信、`/download` で相手の共有したファイルを保存できます。
  - 利用可能なコマンド一覧はチャット内で `/cmd` と入力すると確認できます。

---

## WebSocket`Achex`に関する注意点

チャット機能（メニュー5）では、パブリックなWebSocketサービスである **`achex`** (`wss://cloud.achex.ca/chat`) を利用しています。

- **匿名性とセキュリティについて**:
  このサービスを利用した通信やデータの秘匿性・匿名性は高くありません。
  **パスワード付きのルームであっても、第三者に傍受されるリスクやサーバー側にデータが経由する可能性があるため、機密情報、個人情報、パスワードなどのプライベートな情報は絶対に送信しないようご注意ください**。
- **ASCII ARTの送信やfileの送信について**:
  `/file`や`/generate`でASCII ARTやfileを送信することが可能ですが、**500KBを超えるデータを一度に送信してしまうとAchexは送信しきれないため接続が切れてしまいます**。

---

## 必要モジュール (`requirements.txt`)
- `numpy v2.5.1`
- `opencv-python v4.13.0.92`
- `websockets v16.1`

`requirements.txt`に記載されているので、次のコマンドを打つとすぐにダウンロードできます。
```bash
pip install -r requirements.txt
```
