# 寮€鍙戣€呮寚鍗?
鐗堟湰锛歚v16.2.260606.2137`

鏈寚鍗椾緵 coding agent 鍜屼汉宸ョ淮鎶よ€呬娇鐢ㄣ€?
## 淇敼绛栫暐

淇敼鍓嶅厛闃呰鐩稿叧 panel 鍜?core 妯″潡銆備笉鍚屽伐浣滃尯鐪嬭捣鏉ョ浉浼硷紝浣嗘枃浠舵牸寮忋€佺瀛︽爣绛惧拰瀹夊叏绾︽潫涓嶅悓銆?
浼樺厛锛?
- 浣跨敤宸叉湁 GUI 椋庢牸銆?- 鎶婇潪 GUI 閫昏緫鏀惧叆 core銆?- 灏忚寖鍥翠慨鏀广€?- 涓哄叡浜牳蹇冭涓鸿ˉ娴嬭瘯銆?
閬垮厤锛?
- 鏈粡鏄庣‘瑕佹眰鏀瑰彉纭欢鍛戒护椤哄簭銆?- 瑙ｆ瀽琚鐢ㄧ殑杈撳叆妗嗐€?- 閲嶇紪鍙?Raman sequence 鎴?mapping selected column銆?- 杩愯缁撴潫鍚庤嚜鍔ㄤ繚瀛樻祴閲忔枃浠躲€?- 鍦?app-state 涓繚瀛樼‖浠惰緭鍑虹姸鎬併€?
## GUI 杈圭晫

澶у鏁板伐浣滃尯閲囩敤鍥哄畾宸?鍙冲竷灞€锛?
- 宸︿晶鍙傛暟銆?- 鍙充笂 preview notebook銆?- 鍙充笅 log銆?
闄ら潪鐢ㄦ埛鏄庣‘瑕佹眰锛屼笉瑕佹敼鎴?splitter 鎴栧畬鍏ㄤ笉鍚屽竷灞€銆?
## 鐗堟湰鏇存柊

瀹炵幇璁″垝涓殑淇敼鏃讹紝鏇存柊锛?
- `src/ca_app/gui/main_frame.py` 鐨?`APP_VERSION`銆?- `src/ca_app/__init__.py` 鐨?`__version__`銆?- `pyproject.toml` 鐨?`version`銆?- `README.md`銆?- `README.zh-CN.md`銆?- `AGENTS.md`銆?- `docs/en/` 鍜?`docs/zh-CN/` 涓浉鍏虫枃妗ｃ€?
## Raman Electrical

Electrical tab 鏉ユ簮浜?`current_voltage_single_file_processor_v2.ipynb`锛岀幇鍦ㄥ凡鏈?GUI锛?
- CSV loader銆?- shared raw preview seconds銆?- V_Gate/V_Drain preview seconds銆?- Raw data 鍥涘浘銆?- V_Gate/V_Drain 鍙岃酱鍥俱€?- pulse summary 琛ㄣ€?
Raw data 绾垮浼氭牴鎹瑙堢鏁拌嚜鍔ㄨ绠楋紝涓嶈闅忔剰鏀逛负鍥哄畾绾垮銆?
