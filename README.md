# ASCII ART GENERATOR
画像とアスキーアートの変換に特化したツールです。加えて、パブリックなWebSocketサービスである`achex`を使用してチャットすることもできます。

webサイトはこちら -> **https://chat.infinc.workers.dev/**

---

## 使用例

元画像 `sample.jpg`

<img width="189" height="252" alt="Image" src="https://github.com/user-attachments/assets/a900b6e8-18e2-4451-a744-b1c53ced8c92" />

`sample.jpg`を補正係数0.55、横幅100で白黒アスキーアートに変換した`grayASCII.txt`のスクリーンショット

<img width="304.5" height="410" alt="Image" src="https://github.com/user-attachments/assets/07ee0e2d-b1b7-4059-88e0-8d6552315b37" />

`sample.jpg`を補正係数0.55、横幅100でカラーアスキーアートに変換し、その後画像に再変換した画像 `colorConvert.png`

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

(追記) venv仮想環境を終了するにはdeactivateをします。
```bash
deactivate
```

---

## 各項目の概要
### 1. 画像から白黒のASCII ARTを生成
- **説明**: 画像ファイル（JPG, JPEG, PNG, WEBP, HEIC）を読み込み、白黒のアスキーアートを生成・表示します。
- **特徴**: サイズ変更や文字の濃淡（文字セット）の選択、結果のテキストファイル保存（`generated-art.txt`）が可能です。

### 2. 画像からカラーのASCII ARTを生成
- **説明**: 画像ファイル（JPG, JPEG, PNG, WEBP, HEIC）をカラーのアスキーアートに変換します。
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
  - `/clear` と入力すると画面がスクロールして、それまでの表示を流して綺麗にできます。(自分の画面だけで、他の参加者には影響しません)
  - 利用可能なコマンド一覧はチャット内で `/cmd` と入力すると確認できます。


<img width="437" height="420" alt="Image" src="https://github.com/user-attachments/assets/ace6ac77-8f6c-48dd-9eb5-ced466c34860" />

---

## 技術的な仕組み・工夫した点

ここは「どう使うか」ではなく、**どうやって実現しているか**をまとめた項目です。

### 輝度から文字へのマッピング

グレースケール化した各ピクセルの明るさ (0〜255) を、**薄い順に並べた文字セット**のどれかに割り当てています ([`functions.py`](functions.py) の `gray_generator`)。

```python
ascii_str = "".join([chars[pixel * num_chars // 256] for pixel in pixels])
```

255ではなく **256で割っている**のがポイントです。`pixel * num_chars // 256` にすると、0〜255 の256段階が文字数で**均等に**分割され、`pixel = 255` のときだけ添字がはみ出す、という例外処理が要らなくなります。文字セットの長さが 5文字でも 70文字でも、同じ1行で正しく割り当てられます。

### 3種類の文字セット

同じ画像でも、使う文字によって仕上がりが変わります。用途に合わせて3つ用意しました。

| セット | 文字 | 特徴 |
| --- | --- | --- |
| Normal | `` .:-=+*#%@`` (10段階) | 汎用。階調と読みやすさのバランスが良い |
| Block | `` ░▒▓█`` (5段階) | 塗りつぶし文字なので、離れて見たときに写真らしく見える |
| Impact | `` .'`^",:;Il!i…`` (70段階) | 階調が細かく、大きいサイズで細部が出る |

### 縦横比の補正 (補正係数 0.55)

ターミナルの文字は**正方形ではなく縦長**です。そのため画像の縦横比のまま1ピクセル=1文字に変換すると、出力されたアスキーアートは**縦に間延びして見えます**。

そこで高さにだけ補正係数を掛けています ([`functions.py`](functions.py) の `change_size_function`)。

```python
new_height = math.ceil(height * (new_width / width) * factor)  # factor = 0.55
```

0.55 は「文字の横幅 : 高さ ≒ 1 : 1.8」に相当する値で、多くの等幅フォントで見た目が元画像に近くなります。フォントによって最適値が変わるため、対話入力でもコマンドライン引数 (`--factor`) でも変更できるようにしてあります。

### カラー出力 (ANSI エスケープシーケンス)

カラー変換では、文字の前に色指定のエスケープシーケンスを差し込んでいます ([`functions.py`](functions.py) の `rgb_generator`)。

```python
colored_char = f"\033[38;5;{color_code}m{char}"
```

色番号は RGB から **256色パレット (6×6×6 のカラーキューブ)** へ落とし込んで求めます ([`functions.py`](functions.py) の `rgb_to_256`)。

```python
r_idx = round(r / 255 * 5)   # 0〜5 の6段階に量子化
g_idx = round(g / 255 * 5)
b_idx = round(b / 255 * 5)
return 16 + (36 * r_idx) + (6 * g_idx) + b_idx
```

各色を6段階に落とし、`16 + 36r + 6g + b` で 16〜231 の番号に変換しています (例: 純粋な赤 `(255, 0, 0)` は `196` 番)。24bitのトゥルーカラー (`\033[38;2;R;G;B`) より色数は少なくなりますが、**256色は対応しているターミナルが広く、古い環境や Windows のコンソールでも同じ見た目になります**。行末には `\033[0m` を入れて色をリセットし、色が次の行へ漏れないようにしています。

### ASCII ART → PNG の逆変換

「画像 → アスキーアート」の逆、**アスキーアート → 画像**を行うのが [`functions.py`](functions.py) の `ascii_to_image` です。テキストファイルを読み込み、**1文字を1ピクセル**として画像を組み立て直します。

難しいのは、カラーのアスキーアートには**文字と色情報 (エスケープシーケンス) が混ざっている**点です。単純に1文字ずつ読むと `\033[38;5;196m` の `3` や `8` まで絵の一部として扱ってしまいます。そこで、**正規表現の分割にキャプチャグループを使い、区切り文字自体も結果に残す**ようにしました。

```python
parts = re.split(r'(\x1b\[[0-9;]*m)', line)
```

こうすると1行が「文字の塊」と「エスケープシーケンス」に交互に分かれるので、あとは**現在の色を保持しながら左から処理する**だけで済みます。

- **エスケープシーケンスの塊** → 色を解析して現在の色を更新する
  - `38;5;N` … 256色。`N - 16` を `36 / 6 / 1` で割り戻して RGB に復元する (`rgb_to_256` の逆算)
  - `38;2;R;G;B` … トゥルーカラー。そのまま RGB として読む
  - `0` … 色のリセット。以降は白黒として扱う
- **文字の塊** → 1文字ずつピクセルに変換する
  - 文字セットの並び順から明るさを逆算する (`char_to_gray`)
  - 色が付いていればその色を、白黒ならグレー値を書き込む
  - 空白文字と最も暗い文字は、色が付いていても黒に落とす (背景が滲まないようにするため)

```python
char_to_gray = {char: int((i / (num_chars - 1)) * 255) for i, char in enumerate(chars)}
```

さらに2点、実際に動かして分かった落とし穴に対応しています。

1. **OpenCV は BGR 順** — 解析した `(r, g, b)` をそのまま入れると赤と青が入れ替わるので、`(b, g, r)` の順で格納しています。
2. **縦横比を戻す** — 生成時に高さへ 0.55 を掛けているため、そのまま画像化すると横に潰れます。最後に `height / 0.55` へ引き伸ばして元の比率に戻しています。

```python
restored_height = int(new_height / 0.55)
img_array = cv2.resize(img_array, (new_width, restored_height), interpolation=cv2.INTER_LINEAR)
```

生成時に1文字へ丸めた情報は戻らないため、これは**完全な復元ではなく「アスキーアートの見た目をそのまま画像にしたもの」**です。それでも、色付きのアスキーアートを受け取った相手が、チャット中に `/download png` と打つだけで画像として保存できます。

### チャットのルームID設計

Achex には「部屋」という機能がなく、**宛先IDを指定してメッセージを送る**仕組みしかありません。そこで、部屋名とパスワードをつないで SHA-256 でハッシュ化し、**その結果そのものを宛先ID として使っています** ([`chat_functions.py`](chat_functions.py) の `connect_and_run`)。

```python
secret_key = f"{room_name}::{room_password}"
real_room_id = hashlib.sha256(secret_key.encode()).hexdigest()
```

これによって、サーバー側に部屋の管理機能が無くても次の性質が得られます。

- **同じ部屋名とパスワードを知っている人だけ、同じ宛先IDに行き着く** — 部屋名だけ知られても、パスワードが違えば別のIDになるので合流できません
- **パスワードそのものはネットワークに流れない** — 送信されるのはハッシュ値だけです
- **部屋を作る操作が要らない** — 最初の人が好きな部屋名とパスワードを決めれば、その時点で部屋が存在することになります

ただしハッシュ値は**通信の秘匿には関与しない**（宛先を隠す仕組みではない）ので、README の「WebSocket`Achex`に関する注意点」に書いたとおり、機密情報は送らないでください。

参加者のIDは `secrets.choice` で作る5文字+5文字のランダムな文字列です ([`chat_functions.py`](chat_functions.py) の `generate_absolute_id`)。同じユーザーネームの人が複数いても区別でき、**接続が切れて `connect` で再接続したときも同じIDを引き継ぐ**ので、他の参加者からは同じ人物として見えます。

### Web版はブラウザだけで同じ結果を出している

Web版 (`web/`) は Python版のサーバーを介さず、**変換処理をブラウザ上で実装し直しています**。同じ部屋で会話するために、次の処理を JavaScript 側でも一致させる必要がありました。

- ルームIDの SHA-256 (`crypto.subtle.digest`) — 1バイトでも違うと別の部屋になってしまう
- 参加者IDのランダム生成 — `secrets.choice` と同じく偏りが出ないよう、棄却サンプリングで実装
- グレースケール化とリサイズ — cv2 が使えないため自前で実装し、`INTER_LINEAR_EXACT` とビット単位で一致することを確認

結果として、同じ画像・同じ設定なら Python版とWeb版で**ほぼ同一のアスキーアート**が得られます (差異の詳細は「[生成結果の差について](#生成結果の差について)」を参照)。

---

## コマンドライン引数を用いた生成
このプログラムはコマンドライン引数による生成に対応しています。ただし、`python main.py`だけでも従来通りの対話型の生成も使用可能です。

このコマンドライン引数を用いた生成は、白黒又はカラーのASCII ARTの生成のみ対応しています。画像への変換やGIFの再生、Websocketでのチャットは`python main.py`から行ってください。
```bash
python main.py [-h] (--color | --gray) [--factor FACTOR] [--width WIDTH] [--save] path
```

**【必須な値】**

path &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;変換する画像のパス (JPG, JPEG, PNG, WEBP, HEIC)<br>

**【どちらかが必要な値】**

--color&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;カラーASCII ARTを生成<br>
--gray&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;白黒ASCII ARTを生成<br>

**【オプションの値】**

  -h, --help&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ヘルプを表示します<br>
  --factor FACTOR&nbsp;&nbsp;&nbsp;&nbsp;補正係数(デフォルト=0.55、指定なし=0.55)<br>
  --width WIDTH&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;出力の横幅(指定なし=画像の横幅)<br>
  --save&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;生成したASCII ARTをgenerated-art.txtとして保存(指定なし=保存しない)

<img width="437" height="416" alt="Image" src="https://github.com/user-attachments/assets/651e9fbd-1380-4a50-b3ad-484c20c0899b" />

---

## コマンド一覧

チャット中（`python main.py` のメニュー5 / Web版）で使えるコマンドです。チャット中に `/cmd` と入力しても表示されます。

| コマンド | 説明 |
| --- | --- |
| `/cmd` | 全てのコマンドを表示します |
| `/help` | ヘルプを表示します |
| `/file <file>` | ファイルを送信します（テキストベースのファイルのみ） |
| `/show` | 最新のファイルの中身を表示します |
| `/download <raw または png>` | 最新のファイルを .txt または .png として保存します |
| `/generate <path> <gray または color> <width> <factor>` | すぐに ASCII ART を生成します |
| `/clear` | 画面の表示を消して綺麗にします（自分の画面のみ） |
| `/user <名前>` | 指定したユーザーがオンラインか確認します |
| `/exit` | チャットから退出します |

`<factor>` を省略した場合は 0.55 になります。Web版ではファイルパスが使えないため、`/generate` と `/file` の指定方法だけが変わります（詳細は「[使えるコマンド](#使えるコマンド)」を参照）。

---

## WebSocket`Achex`に関する注意点

チャット機能（メニュー5）では、パブリックなWebSocketサービスである **`achex`** (`wss://cloud.achex.ca/chat`) を利用しています。

- **匿名性とセキュリティについて**:
  このサービスを利用した通信やデータの秘匿性・匿名性は高くありません。
  **パスワード付きのルームであっても、第三者に傍受されるリスクやサーバー側にデータが経由する可能性があるため、機密情報、個人情報、パスワードなどのプライベートな情報は絶対に送信しないようご注意ください**。
- **ASCII ARTの送信やfileの送信について**:
  `/file`や`/generate`でASCII ARTやfileを送信することが可能ですが、**500KBを超えるデータを一度に送信してしまうとAchexは送信しきれないため接続が切れてしまいます**。
- **通信の暗号化について**:
  接続は `wss://` (TLS) で、**サーバー証明書のチェーンとホスト名の検証は有効**にしています。ただし Achex のサーバーは前方秘匿性のある鍵交換 (ECDHE/DHE) に対応しておらず、RSA鍵交換の `AES256-GCM-SHA384` しか受け付けません。そのため Python 版ではこの暗号スイートを明示的に許可しています。**前方秘匿性が無い**ため、サーバーの秘密鍵が将来漏洩した場合、記録された過去の通信が復号され得ます。
  また、Achex は `Origin` ヘッダの無い WebSocket ハンドシェイクを拒否するため、`Origin` だけは付けて接続しています (ブラウザを装う `User-Agent` は不要だったので送っていません)。
- **接続が切れた場合について**:
  チャット中に接続が切れると `[System]接続が切れました` と表示されます。そのまま **`connect` と入力すると、切断前と同じID・同じ部屋のまま再接続**できます (`python main.py` からやり直す必要はありません)。

---

## Web版 — ブラウザからチャットに参加する

### **https://chat.infinc.workers.dev/**

**上のURLを開くだけで、インストールも設定も無しにチャットに参加できます。** Pythonもvenvも不要で、PCでもスマートフォンでも、ブラウザさえあれば利用できます。

これは Python版のチャット機能(メニュー5)をそのままWebサイトにしたもので、Cloudflare Workers 上で公開されています。ソースは `web/` にあります。

### 参加する手順

1. ブラウザで **https://chat.infinc.workers.dev/** を開きます。
2. 「使用するユーザーネーム」「参加する部屋のID」「参加する部屋のパスワード」を入力し、**参加する** を押します。(パスワードを空欄にした場合は `password` になります)
3. あとはメッセージを入力して送信するだけです。`/cmd` と入力するとコマンド一覧が表示されます。

最初に参加する人は部屋IDとパスワードを自由に決めて構いません。同じ部屋で話すには、参加者全員が同じ部屋IDとパスワードを入力してください。

### Python版と混在してチャットできます

**`python main.py` のメニュー5で入った部屋と、https://chat.infinc.workers.dev/ で入った部屋は同じものです。** 部屋IDとパスワードを合わせれば、ターミナルのユーザーとブラウザのユーザーが同じ部屋で会話でき、ASCII ARTやファイルのやり取りもそのまま行えます。

### 使えるコマンド

`/generate` `/user` など、Python版と同じコマンドが使えます。`/clear` はそれまでのチャットの表示を消して画面を綺麗にするコマンドで、消えるのは自分の画面だけです (他の参加者には影響しません)。

ただしブラウザにはファイルパスが無いため、ファイルを扱うコマンドの指定方法だけが変わります。それ以外のコマンドと通信内容はPython版と同じです。

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
- 匿名性は低いままです。**チャットの内容は第三者に傍受される可能性があるため、機密情報や個人情報は送らないでください。**

### 自分の環境で動かす場合

公開サイトを使うだけなら以下の作業は不要です。ローカルで動かしたり、自分のCloudflareアカウントへデプロイしたい場合のみ、Node.js (wrangler のため) を用意してください。ビルドツールは使っておらず、素のES Modulesをそのまま配信しています。

```bash
cd web
npm install
npm run dev
```

```bash
npm run deploy
```

---

## 必要モジュール (`requirements.txt`)
- `numpy v2.5.1` <span style="color: gray;">(数値計算を素早く行うために使用します[BSD-3-Clause])</span>
- `opencv-python v4.13.0.92` <span style="color: gray;">(画像や動画の処理、解析に使用します[MIT License])</span>
- `websockets v16.1` <span style="color: gray;">(チャットするために使用します[BSD-3-Clause])</span>
- `pillow_heif v1.5.0` <span style="color: gray;">(HEICの読み込みに使用します[GNU General Public License v2])</span>
- `certifi v2026.7.22` <span style="color: gray;">(TLS証明書の検証に使用します[Mozilla Public License 2.0])</span>

`requirements.txt`に記載されているので、次のコマンドを打つとすぐにダウンロードできます。
```bash
pip install -r requirements.txt
```

---

## ライセンス

このリポジトリのコードは [MIT License](LICENSE) です。

`sample.jpg` は作者本人が撮影した写真です。これを変換して生成した `grayASCII.txt`・`colorConvert.png`、および README 内のスクリーンショットも同様に作者本人の著作物です。これらの画像もコードと同じく MIT License の条件で自由にご利用いただけます。

ただし `web/public/vendor/libheif/` は libheif (LGPL-3.0) の再配布物であり、**MIT License の対象外**です。改変は行っていません。詳細は [web/public/vendor/libheif/README.md](web/public/vendor/libheif/README.md) を参照してください。
