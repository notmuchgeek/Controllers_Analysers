# 缁存姢妫€鏌ヨ〃

鐗堟湰锛歚v16.2.260606.2137`

## 淇敼鍓?
- 纭褰撳墠椤圭洰鏂囦欢澶广€?- 闃呰 `AGENTS.md`銆?- 闃呰鐩稿叧 panel 鍜?core銆?- 鍒ゆ柇鏄惁娑夊強纭欢銆乺estore銆佹枃浠舵爣绛炬垨 sequence 缂栧彿銆?
## 淇敼涓?
- 淇濇寔鍥哄畾宸﹀弬鏁般€佸彸棰勮甯冨眬銆?- 淇濇寔绉戝鏍囩鍑嗙‘銆?- 淇濈暀 Raman sequence 鍜?selected column 鏍囩銆?- 涓嶆敼鍙樼‖浠惰緭鍑鸿涔夛紝闄ら潪鐢ㄦ埛鏄庣‘瑕佹眰銆?- 鐢ㄦ埛鍙鍙樺寲搴斿悓姝ヨ嫳鏂囧拰涓枃鏂囨。銆?
## 鐗堟湰

- plan 瀹炵幇鏃跺鍔?v16 灏忕増鏈€?- 鏇存柊鏃堕棿鍜屾棩鏈熴€?- 鍚屾绋嬪簭鏍囬銆丄bout銆乸ackage metadata銆丷EADME銆丄GENTS銆乨ocs銆?
## 鑷姩妫€鏌?
```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

## 鎼滅储妫€鏌?
杩愯鎼滅储鏃讹紝鎶婂崰浣嶇鏇挎崲涓轰笂涓€涓増鏈彿鎴栨棫鎻忚堪锛?
```cmd
rg -n "<old-version>|<old-package-version>|<stale-electrical-placeholder>" AGENTS.md README.md README.zh-CN.md docs src tests pyproject.toml
```

## 鏂囨。涓€鑷存€?
`docs/en/` 鍜?`docs/zh-CN/` 搴斾繚鎸佺浉鍚屾枃浠跺悕缁撴瀯銆傚唴瀹逛笉蹇呴€愬瓧瀵瑰簲锛屼絾搴旇鐩栧悓鏍风殑淇℃伅銆?
## 娓呯悊

濡傛灉娴嬭瘯鐢熸垚缂撳瓨锛屾竻鐞?`__pycache__/` 鍜?`.pyc`銆備笉瑕佸垹闄ょ敤鎴锋暟鎹垨瀹為獙杈撳嚭锛岄櫎闈炵敤鎴锋槑纭姹傘€?
