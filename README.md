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
venv\Scripts\activate.bat #cmd.exe
```
4. requirements.txtを使用して必要なパッケージをインストールします。
```bash
pip install -r requirements.txt
```
5. main.pyを起動します。
```bash
python main.py
```

<img width="436" height="240" alt="Image" src="https://github.com/user-attachments/assets/dfb5410f-0478-414e-9d18-e217455028aa" />

(追記) venv仮想環境を終了するにはdeactivateをします。
```bash
deactivate
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

## コマンドライン引数を用いた生成
このプログラムはコマンドライン引数による生成に対応しています。ただし、`python main.py`だけでも従来通りの対話型の生成も使用可能です。

このコマンドライン引数を用いた生成は、白黒又はカラーのASCII ARTの生成のみ対応しています。画像への変換やGIFの再生、Websocketでのチャットは`python main.py`から行ってください。
```bash
python main.py [-h] (--color | --gray) [--factor FACTOR] [--width WIDTH] [--save] path
```

**【必須な値】**

path &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;変換する画像のパス<br>

**【どちらかが必要な値】**

--color&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;カラーASCII ARTを生成<br>
--gray&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;白黒ASCII ARTを生成<br>

**【オプションの値】**

  -h, --help&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ヘルプを表示します<br>
  --factor FACTOR&nbsp;&nbsp;&nbsp;&nbsp;補正係数(デフォルト=0.55、指定なし=0.55)<br>
  --width WIDTH&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;出力の横幅(指定なし=画像の横幅)<br>
  --save&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;生成したASCII ARTをgenerated-art.txtとして保存(指定なし=保存しない)

---

## WebSocket`Achex`に関する注意点

チャット機能（メニュー5）では、パブリックなWebSocketサービスである **`achex`** (`wss://cloud.achex.ca/chat`) を利用しています。

- **匿名性とセキュリティについて**:
  このサービスを利用した通信やデータの秘匿性・匿名性は高くありません。
  **パスワード付きのルームであっても、第三者に傍受されるリスクやサーバー側にデータが経由する可能性があるため、機密情報、個人情報、パスワードなどのプライベートな情報は絶対に送信しないようご注意ください**。
- **ASCII ARTの送信やfileの送信について**:
  `/file`や`/generate`でASCII ARTやfileを送信することが可能ですが、**500KBを超えるデータを一度に送信してしまうとAchexは送信しきれないため接続が切れてしまいます**。

---

## Web版 (Cloudflare Workers)

`web/` にチャット機能(メニュー5)のWeb版があります。ブラウザから同じ部屋に参加でき、**Python版と混在してチャットできます**(部屋ID・パスワードを同じにしてください)。

### 起動とデプロイ

Node.js が必要です(wrangler のため)。ビルドツールは使っておらず、素のES Modulesをそのまま配信しています。

```bash
cd web
npm install
npm run dev
```

```bash
npm run deploy
```

### Python版との違い

ブラウザにはファイルパスが無いため、ファイルを扱うコマンドの指定方法が変わります。それ以外のコマンドと通信内容はPython版と同じです。

| | Python版 | Web版 |
|---|---|---|
| `/generate` | `/generate <path> <[gray/color]> <width> <factor>` | `/generate <[gray/color]> <width> <factor>` (path を廃止) |
| `/file` | `/file <path>` | `/file` (引数なし) |

画像とテキストファイルは、**画面にドラッグ&ドロップ**しておくか、コマンド実行時に開くファイル選択ダイアログから指定します。`/download` はブラウザのダウンロードとして保存されます。

### 生成結果の差について

Web版はcv2を使えないため、グレースケール化とリサイズをブラウザ上で実装し直しています。リサイズはcv2の `INTER_LINEAR_EXACT` とビット単位で一致することを確認済みですが、Python版が使う既定の `INTER_LINEAR` は OpenCV の旧実装で、最大1階調ずれます。

その結果、**同じ画像・同じ設定でもASCII ARTの 0.3〜0.8% 程度の文字が1段階だけ変わります**(実測: `sample.jpg` を横幅100・補正0.55で 7473文字中56文字)。見た目では区別できません。

### 注意点

- 接続はブラウザから `wss://cloud.achex.ca/chat` へ直接行います。繋がらない場合のみ、Worker経由のリレー(`/ws`)へ自動的に切り替わります。画面右上に、どちらで繋がっているかを表示します。
- Python版と同様、1回に500KBを超えるデータは送信できません。超える場合は送信せずに警告を出します。
- ブラウザは非アクティブなタブのタイマーを遅くするため、ファイル送信中に別タブへ移ると完了が遅れます(内容と順序は保たれます)。送信中は進捗を表示し、入力欄を一時的に無効にします。
- アイドル対策として30秒ごとに `{"ping":1}` を送ります。Achexはこれを無視するだけで他の参加者には届きません(10分間の無通信でも切断されないことは確認済みですが、経路上の機器による切断に備えています)。切断された場合は自動で再接続し、失敗が続いたときは再接続ボタンを出します。
- 匿名性は低いままです。機密情報は送らないでください。

---

## 必要モジュール (`requirements.txt`)
- `numpy v2.5.1`
- `opencv-python v4.13.0.92`
- `websockets v16.1`

`requirements.txt`に記載されているので、次のコマンドを打つとすぐにダウンロードできます。
```bash
pip install -r requirements.txt
```
