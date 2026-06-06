# 鏋舵瀯璇存槑

鐗堟湰锛歚v16.2.260606.2137`

鏈」鐩殑缁撴瀯鍙互浠庝笂鍒颁笅鐞嗚В涓猴細鍚姩鑴氭湰銆佸簲鐢ㄥ叆鍙ｃ€佷富绐楀彛銆佸伐浣滃尯 panel銆佹牳蹇冪畻娉曘€佺‖浠惰竟鐣屻€佽祫婧愬拰娴嬭瘯銆?
## 椤跺眰鍏ュ彛

```text
run_ca_app.py
```

浠庢簮鐮佺洰褰曞惎鍔?GUI銆?
```text
src/ca_app/app.py
```

鍒涘缓 wxPython app 鍜屼富绐楀彛銆?
```text
src/ca_app/gui/main_frame.py
```

涓荤獥鍙?shell锛岃礋璐ｇ獥鍙ｆ爣棰樸€乂iew 鑿滃崟銆丷estore 鑿滃崟銆丄bout 鑿滃崟銆佸伐浣滃尯鍒囨崲鍜?`app_state.json`銆?
## GUI 宸ヤ綔鍖?
```text
src/ca_app/gui/panels/
```

姣忎釜涓昏鍔熻兘灏介噺鏀惧湪鐙珛 panel 涓細

- `afm_kpfm_panel.py`锛欰FM/KPFM notebook銆?- `afm_controller_panel.py`锛欿eithley 鎺у埗鍣?GUI 鍜岃繍琛岄€昏緫銆?- `afm_analysis_panel.py`锛欳PD 鍥惧儚鍒嗘瀽銆?- `aps_panel.py`锛欰PS/DWF/DOS/SPV 鍒嗘瀽銆?- `raman_panel.py`锛歊aman Baseline銆丮apping銆両nsitu EChem銆丒lectrical銆?- `tpc_panel.py`锛歍PC 婵€鍏変簩鏋佺鎺у埗銆?
澶氭暟宸ヤ綔鍖洪噰鐢ㄥ浐瀹氬竷灞€锛氬乏渚у弬鏁帮紝鍙充笂棰勮锛屽彸涓?log銆?
## 鏍稿績妯″潡

```text
src/ca_app/core/
```

杩欓噷鏀鹃潪 GUI 鐨勭畻娉曞拰鏁版嵁澶勭悊锛?
- `intensity_profile_tools.py`锛氱數娴?鍏夊己鏍″噯銆佸嚱鏁拌〃杈惧紡銆佹洸绾跨敓鎴愩€?- `calibration_models.py`锛氭牎鍑嗘ā鍨嬬ǔ瀹氬鍏ラ潰銆?- `function_profiles.py`锛氬嚱鏁版洸绾跨ǔ瀹氬鍏ラ潰銆?- `raman_baseline.py`锛歊aman 鍩虹嚎鏍℃銆?- `raman_mapping.py`锛歊aman mapping 璇诲彇銆乽nstack銆佸鍑恒€?- `raman_insitu_echem.py`锛歊aman 搴忓垪宄板垎鏋愩€?
## 纭欢杈圭晫

```text
src/ca_app/hardware/keithley_serial.py
```

淇濆瓨涓插彛璁剧疆鍜?Keithley SCPI 鍘熻銆傚綋鍓?AFM/KPFM 鎺у埗鍣ㄤ粛鎶婄粡杩囨祴璇曠殑杩愯缂栨帓淇濈暀鍦?panel 鍐咃紝閬垮厤鍦ㄩ噸鏋勬椂鏀瑰彉纭欢璇箟銆?
## 鏈潵鎶藉彇鍖哄煙

```text
src/ca_app/runtime/
src/ca_app/io/
```

杩欎簺鐩綍鐢ㄤ簬浠ュ悗鎶?worker service 鍜屽鍏?瀵煎嚭杈圭晫浠?GUI 涓娊鍑烘潵銆傚綋鍓嶄笉瑕佷负浜嗘暣鐞嗙洰褰曡€屾敼鍙樺凡缁忔祴璇曡繃鐨勭‖浠惰涓恒€?
## 娴嬭瘯

```text
tests/
```

鍙斁闈炵‖浠惰嚜鍔ㄦ祴璇曘€傜‖浠舵祴璇曞繀椤荤敱鐢ㄦ埛鏄庣‘纭銆?
