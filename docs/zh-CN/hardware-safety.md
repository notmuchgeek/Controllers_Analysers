# 纭欢瀹夊叏

鐗堟湰锛歚v16.2.260606.2137`

浠讳綍鍙互鎺у埗纭欢鐨勪慨鏀归兘搴旇涓哄畨鍏ㄦ晱鎰熶慨鏀广€?
## Keithley 妯″紡

AFM/KPFM 鎺у埗鍣ㄩ€氳繃 RS-232 鎺у埗 Keithley source meter锛?
- Source function锛歝urrent銆?- Measure function锛歷oltage銆?- 榛樿 COM锛歚COM3`銆?- 榛樿 baudrate锛歚38400`銆?- 榛樿 compliance锛歚5.0 V`銆?
Keithley 姘歌繙鎺ユ敹鐢垫祦鍛戒护銆侷ntensity mode 鍙槸 GUI 灞傜殑鐩爣鍗曚綅锛屼細鍏堣浆鎹㈡垚鐢垫祦銆?
## 鐢垫祦闄愬埗

鎵€鏈夊彲鑳借緭鍑哄埌 Keithley 鐨勭數娴侀兘蹇呴』妫€鏌?`Internal max current / mA`锛?
- Quick Test銆?- Current-mode recurrent ON銆?- Current-mode step ON銆?- Current-mode function profile銆?- Intensity-mode 杞崲鐢垫祦銆?- Intensity-mode function profile 杞崲鐢垫祦銆?
瓒呴檺鏃朵笉鑳芥墦寮€杈撳嚭銆?
## OFF 闃舵

OFF 闃舵涓嶈兘鏌ヨ Keithley 娴嬮噺锛岀姝細

- `:READ?`
- `:INIT`
- `:FETCH?`

鍏佽锛?
- `:OUTP OFF`
- 璁板綍杞欢宸茬煡 `0 V / 0 mA`
- 绛夊緟 OFF duration

## 娓呯悊璺緞

姝ｅ父缁撴潫銆丼TOP銆佸紓甯搁兘搴斿敖閲忓彂閫侊細

```text
:SOUR:CURR:LEV 0
:OUTP OFF
```

鐒跺悗鍐嶅叧闂覆鍙ｃ€?
## 纭欢娴嬭瘯

纭欢娴嬭瘯蹇呴』鐢辩敤鎴锋槑纭‘璁わ紝骞剁‘璁?COM銆乥audrate銆乧ompliance銆佺數娴侀檺鍒跺拰鏍峰搧瀹夊叏銆?
