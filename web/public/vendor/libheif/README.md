# libheif-js (vendored)

ブラウザは HEIC/HEIF を復号できない (Chrome / Firefox など) ため、
`/generate` で HEIC を扱えるように libheif の WebAssembly ビルドを同梱しています。

- 取得元: npm パッケージ [`libheif-js`](https://www.npmjs.com/package/libheif-js) v1.19.8
  (`libheif-wasm/libheif-bundle.mjs` をそのままコピーしたもの。wasm はこのファイルに埋め込まれています)
- 上流: https://github.com/strukturag/libheif / https://github.com/catdad-experiments/libheif-js
- ライセンス: LGPL-3.0 (`LICENSE` を参照)

このファイルは改変していません。読み込みは `js/heic.js` からの動的 import のみで、
HEIC を選んだときだけ取得されます (通常のチャットや JPEG/PNG の変換では読み込まれません)。

更新するときは同じ手順でコピーし直してください。

```bash
npm pack libheif-js@<version>
tar xzf libheif-js-<version>.tgz
cp package/libheif-wasm/libheif-bundle.mjs package/libheif-wasm/LICENSE web/public/vendor/libheif/
```
