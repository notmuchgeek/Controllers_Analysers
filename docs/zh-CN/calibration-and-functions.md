# 鏍″噯鍜屽嚱鏁版洸绾?
鐗堟湰锛歚v16.2.260606.2137`

AFM/KPFM 鎺у埗鍣ㄦ湁涓や釜杞崲灞傦細鐢垫祦-鍏夊己鏍″噯鍜屽嚱鏁版洸绾裤€?
## 鏍″噯

榛樿鏍″噯鏂囦欢锛?
```text
src/ca_app/resources/default_intensity_calibration.csv
```

鎺ㄨ崘琛ㄥご锛?
```text
Current_mA,Intensity_mW
```

涔熸帴鍙楄嚦灏戜袱鍒楁暟鍊肩殑 CSV锛岀涓€鏁板€煎垪涓虹數娴?mA锛岀浜屾暟鍊煎垪涓哄厜寮?mW銆?
榛樿鎷熷悎鑼冨洿锛?
```text
67 to 94 mA
```

缁忛獙鎷熷悎鐢ㄤ簬娴嬮噺鑼冨洿鍐呯殑骞虫粦鎻掑€硷紝涓嶅簲琚綋浣滆繙璺濈澶栨帹鐨勭墿鐞嗘ā鍨嬨€?
## 鎷熷悎鏂规硶

GUI 鏀寔锛?
- Empirical power-exp銆?- Two threshold power銆?- Two stage softplus slope銆?- Generalized exponential power銆?- Polynomial degree 3銆?- Interpolation銆?- Linear銆?- Quadratic銆?- Cubic銆?
## 鍑芥暟鏇茬嚎

榛樿锛?
```text
f(x) = x*m+b
X min = 0
X max = 180
Y min = 0.1
Y max = 4.99
```

`Fit it` 浼氭眰瑙ｈ〃杈惧紡涓殑鏈煡鍙傛暟銆備緥濡?`x*m+b` 浼氭眰瑙?`m` 鍜?`b`銆?
鎷熷悎鍚庤〃杈惧紡浼氳鏇挎崲鎴愭暟鍊艰〃杈惧紡锛屼娇棰勮銆侀獙璇併€佸鍑哄拰杩愯浣跨敤鍚屼竴瀹夊叏琛ㄨ揪寮忋€?
## 杩愯

Function control 鍙犲姞鍦?Recurrent 鎴?Step 鐨?ON 闃舵銆侽N duration 鍐冲畾鍑芥暟娉ㄥ叆绐楀彛锛孫N value 杈撳叆妗嗗湪 Function control 涓嬬疆鐏颁笖涓嶈瑙ｆ瀽銆?
杩愯寮€濮嬫椂鍑芥暟鏇茬嚎鍜屾牎鍑嗘ā鍨嬮兘琚喕缁擄紝杩愯涓殑 GUI 淇敼鍙奖鍝嶄笅涓€娆¤繍琛屻€?
