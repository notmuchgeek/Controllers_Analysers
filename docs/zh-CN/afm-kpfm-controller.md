# AFM/KPFM 鎺у埗鍣?
鐗堟湰锛歚v16.2.260606.2137`

AFM/KPFM Controller 鏄湰椤圭洰涓渶闇€瑕佸畨鍏ㄧ淮鎶ょ殑宸ヤ綔鍖猴紝鍥犱负瀹冨彲浠ョ洿鎺ユ帶鍒?Keithley 杈撳嚭銆?
## 纭欢妯″紡

Keithley 鐨勬牳蹇冩ā寮忥細

```text
Source: current
Measure: voltage
Default COM: COM3
Default baudrate: 38400
Default compliance: 5.0 V
```

鍗充娇鐢ㄦ埛閫夋嫨 Intensity mode锛孠eithley 浠嶇劧鍙帴鏀剁數娴佸懡浠ゃ€傚厜寮轰細鍏堟牴鎹牎鍑嗘ā鍨嬭浆鎹㈡垚鐢垫祦銆?
## GUI 鍖哄煙

宸︿晶鍖呭惈锛?
- Hardware 璁剧疆銆?- Source mode銆?- Quick Test銆?- Recurrent/Step timing銆?- Intensity calibration銆?- Function control銆?- 淇濆瓨鍜?START/STOP 鎸夐挳銆?
鍙充晶鍖呭惈锛?
- Source profile銆?- Intensity calibration銆?- Function profile銆?- Live voltage銆?- Status/log銆?
## START 蹇収

鐐瑰嚮 `START` 鏃跺繀椤绘瀯寤哄喕缁撳揩鐓с€傚揩鐓у寘鎷覆鍙ｈ缃€乻ource mode銆佹牎鍑嗘ā鍨嬨€佸嚱鏁版洸绾垮拰瀹屾暣 sequence steps銆?
杩愯绾跨▼涓嶈兘鍦ㄨ繍琛屼腑閲嶆柊璇诲彇 live GUI 鎺т欢銆傝繍琛屼腑鐢ㄦ埛淇敼鏍″噯銆佸嚱鏁般€侀瑙堝弬鏁板彧褰卞搷涓嬩竴娆?`START`銆?
## OFF 闃舵

OFF 闃舵鍙兘鍏抽棴杈撳嚭骞跺啓鍏ヨ蒋浠跺凡鐭ョ殑 0 鐐广€備笉鑳藉彂閫?`:READ?`銆乣:INIT` 鎴?`:FETCH?`銆?
鍘熷洜鏄?Keithley 鍦?output off 鏃舵煡璇㈡祴閲忓彲鑳借Е鍙?error `803`銆?
## Function Control

Function control 鍚敤鏃讹細

- 鑷姩閫夋嫨 Function profile preview銆?- Recurrent/Step ON value 杈撳叆妗嗙疆鐏般€?- 绋嬪簭涓嶈兘瑙ｆ瀽缃伆鐨?ON value銆?- ON duration 浠嶅喅瀹氬嚱鏁版敞鍏ユ椂闂寸獥鍙ｃ€?
## 淇濆瓨琛屼负

- `Save CSV (Source)` 淇濆瓨璁″垝杈撳嚭鏇茬嚎銆?- `Save Keithley CSV` 淇濆瓨鐢ㄦ埛鎵嬪姩閫夋嫨淇濆瓨鐨勮繍琛屾祴閲忔暟鎹€?- sequence 瀹屾垚鏃朵笉鑳借嚜鍔ㄧ敓鎴?`keithley_run_data_*.csv`銆?
