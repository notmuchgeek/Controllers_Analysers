# 宸ヤ綔鍖烘寚鍗?
鐗堟湰锛歚v16.2.260606.2137`

鏈枃浠朵粠鐢ㄦ埛瑙掑害璇存槑鍚勫伐浣滃尯鐨勫姛鑳藉拰棰勬湡琛屼负銆?
## AFM/KPFM Controller

鍏ュ彛锛?
```text
View -> AFM/KPFM -> Controller
```

鍔熻兘锛?
- 璁剧疆 COM port銆乥audrate銆乿oltage compliance銆乮nternal max current銆?- 閫夋嫨 Current mode 鎴?Intensity mode銆?- 杩愯 Quick Test銆?- 鏋勫缓 Recurrent 鎴?Step 鏃跺簭銆?- 浣跨敤 Function control 鍦?ON 闃舵鍙犲姞 `f(x)`銆?- 棰勮 source profile銆乮ntensity calibration銆乫unction profile銆乴ive voltage銆?- 淇濆瓨璁″垝 source CSV 鎴栨墜鍔ㄤ繚瀛?Keithley 杩愯 CSV銆?
閲嶈琛屼负锛?
- Quick Test 鍜?Function control 浜掓枼銆?- Function control 鍚敤鏃讹紝Recurrent/Step 鐨?ON value 杈撳叆妗嗙疆鐏颁笖涓嶅簲琚В鏋愩€?- `START` 鍚庤繍琛屽揩鐓у喕缁擄紝杩愯涓?GUI 淇敼鍙奖鍝嶄笅涓€娆¤繍琛屻€?
## AFM/KPFM Analysis

鐢ㄤ簬 CPD 鍥惧儚鍒嗘瀽锛?
- 璇诲彇 TIFF/PNG銆?- 鏄剧ず CPD 鎴?energy銆?- HOPG reference fitting銆?- 鍏夌収鍖哄煙鍜?mask銆?- dark/light 鐩存柟鍥俱€?- row/time profiles銆?
## APS/DWF/SPV

鐢ㄤ簬 APS銆丏WF銆亀orkfunction銆丏OS銆丼PV 鏁版嵁鍒嗘瀽銆傝宸ヤ綔鍖轰互鍒嗘瀽鍙傛暟鍜岄瑙堝浘涓轰腑蹇冿紝鏀寔瀵煎嚭鍥惧拰 CSV銆?
## TPC Control

鐢ㄤ簬绾?缁挎縺鍏変簩鏋佺鐢垫祦鎺у埗銆傜敱浜庢秹鍙婄‖浠惰緭鍑猴紝浠讳綍鍛戒护璺緞閮藉繀椤荤粡杩囩數娴侀檺鍒舵鏌ャ€?
## Raman Baseline

鍏ュ彛锛?
```text
View -> Raman -> Baseline
```

琛屼负锛?
- `Load txt` 璇诲彇涓ゅ垪 Raman 鏂囨湰銆?- 鏀寔 `asPLS`銆乣drPLS`銆乣Polynomial/backcor`銆?- Auto 妯″紡鍔犺浇鍚庤嚜鍔ㄦ嫙鍚堛€?- Manual 妯″紡闇€瑕佺偣鍑?`Fit`銆?- 棰勮涓婂浘涓哄師濮嬭氨鍜屽熀绾匡紝涓嬪浘涓烘牎姝ｈ氨銆?- 淇濆瓨鍙啓涓ゅ垪鏍℃璋便€?
## Raman Mapping

鍏ュ彛锛?
```text
View -> Raman -> Mapping
```

琛屼负锛?
- `Load wdf/txt` 璇诲彇 WiRE WDF 鎴?stacked TXT銆?- `Avg./Norm.` 鏄剧ず骞冲潎/褰掍竴鍖栬〃鏍煎拰棰勮銆?- `Raw data` 鏀寔 Every N 鍜?legend銆?- `Location` 鏄剧ず mapping location 鍜?WDF metadata銆?- `Selected` 鍙樉绀洪€変腑璋便€?- `Save selected` 浣跨敤鍘熷閫変腑鍒楀彿浣滀负 `#Sequence`銆?- `Load to Insitu Echem` 浠ュ唴瀛樹紶閫掞紝涓嶇敓鎴愰殣钘?TXT銆?
## Raman Insitu EChem

鍏ュ彛锛?
```text
View -> Raman -> Insitu EChem
```

琛屼负锛?
- `Load wdf/txt` 璇诲彇搴忓垪 WDF 鎴?TXT銆?- 鏀寔 `#Time #Wave #Intensity` 鍜?`#Sequence #Wave #Intensity`銆?- `#Sequence` 杈撳叆浼氱鐢?Time mode 骞跺己鍒?Sequence mode銆?- 宄扮獥鍙ｇ紪杈戣嚜鍔ㄦ洿鏂伴瑙堛€?- Analysis tab 鏄剧ず璋便€佸嘲浣嶃€佸嘲寮恒€佸綊涓€鍖栨瘮鍊笺€?
## Raman Electrical

鍏ュ彛锛?
```text
View -> Raman -> Electrical
```

琛屼负锛?
- `Load csv` 璇诲彇鐢靛 CSV锛屽苟鑷姩鍒囧埌 `Vg/Vd` 棰勮銆?- Electrical section 涓嬮潰鏈変竴涓叡浜?Raw preview seconds 杈撳叆妗嗗拰 slider锛岀敤鏉ユ帶鍒跺洓涓?raw figure銆?- Preview section 鏈?V_Gate 鍜?V_Drain 涓よ锛屾瘡琛屼竴涓?seconds 杈撳叆妗嗗拰 slider銆?- Raw data tab 鏄剧ず Gate V銆丏rain V銆丟ate I銆丏rain I 鍥涘浘銆?- Vg/Vd tab 鏄剧ず V_Gate/V_Drain 鍙?y 杞撮瑙堝拰鑴夊啿琛ㄦ牸銆?- slider 鏄剧ず鍊间繚鐣?1 浣嶅皬鏁般€?- Raw data 绾垮浼氭牴鎹瑙堢鏁拌嚜鍔ㄥ彉鍖栵紝绉掓暟瓒婂ぇ绾胯秺缁嗐€?
