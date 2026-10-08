最终限定功能复核：PASS_WITH_CONDITIONS

候选：55cb3916262fc6f236a92d156028561248ae2f09；已用/opt/homebrew/bin/git独立只读确认HEAD完全一致且工作区clean。最终Git/checkpoint仍由总控负责。本报告只负责最终候选的限定功能复核，范围为 overnight/data/dataset.py、overnight/fixture/chain.mjs、对应新测试、overnight/verify.py 和 overnight/check.mjs。原全量独立审查范围由第一Reviewer 134个实际断言日志支撑，本报告不替代该范围，也未读取其harness或日志。

新增去重主断言：104 = Python76 + Node28；104 PASS / 0 FAIL / 0 SKIP。编号唯一性已核对。计数含22个release文件hash断言和7个私有产物hash/bytes断言；另外复跑2个Python及5个Node项目定向测试，均PASS，但不计新增数。第一Reviewer134及项目全套结果不计入104。

两处P2在本候选的限定范围内关闭。
1. 源文本边界：历史F1 Bearer样式、F2 sk样式、F3带前缀的内部路径，全部由独立合成输入拒绝；编码路径、通用凭证赋值、过深编码与文本形状也拒绝。合法原文本保持原样，不截断或变换后输出。实现位于dataset.py:89-107，规范化调用位于:117-135；详见P07-P24。
2. options.directory访问器：历史F4以及fixture_case getter均拒绝且getter执行次数为0。独立Proxy观察到每个own data descriptor只读取1次、普通属性value读取0次。调用方在异步等待期间改写directory和case后，producer仍消耗原primitive snapshot；BASE链及回放hash重复一致。实现位于chain.mjs:14-30；详见J01/J02/J09-J13/J24/J25。

四个合法冻结case全部成功。注册结果的复制与改字节被拒绝。typed loader为零参数；caller root在进入loader主体前拒绝。typed注册身份/字节检查采用临时SYNTHETIC测试对象，不调用actual loader，也不读取原始capture：本轮actual loader执行0、raw读取0。合法fixture始终SYNTHETIC/QUARANTINED；跨namespace及权限升级拒绝。

22个release文件的SHA-256全部符合release1.8.2；7个既有外部产物的精确字节hash及大小全部符合evidence。readiness的8个真实权限/可用性字段严格false，9个实际调用/发行计数为0，closed_business_condition_ids为空，source_admission为BLOCKED。范围内13文件执行前后字节hash一致。完整hash列表、逐断言ID、命令、日志和退出码见JSON报告、results和run-metadata。

四个历史失败事实F1-F4和第一Reviewer原日志保留，不因当前修复成功改写为历史PASS。历史引用由总控提供，仅作元数据引用，本reviewer未读取或修改。原第一审查两个后续进程受工具限制中止的事实不影响本次独立完成的限定复核；本次四个job都exit0。

剩余限定与条件：完整fresh clone/fresh npm cache全套、430旧immutable字节验证、44请求/2786行实际离线重放、Git/合同/最后Gate由总控负责。总控报告完整534 unique = 533PASS/0FAIL/1既有V5可选SKIP，本reviewer未复跑且不计数。本轮没有新actual dataset发行、七产物重新生成或跨机器可移植性断言，不提供任意敌对JavaScript或文件系统竞态的全面安全证明。hidden extra属性拒绝已测试，不声称所有合法key的non-enumerable data descriptor必然被拒绝。系统Git只读尝试曾返回Xcode许可错误；该历史metadata已保留。随后用Homebrew Git独立确认候选HEAD一致且worktree clean；见git-check.json。未更改系统许可或权限，Git核对不增加104功能断言计数。

所有真实数据许可/准入、历史可见性、模型、Pilot、cloud、券商、production及真实资金执行仍BLOCKED；没有关闭业务条件。只在指定新私有外部目录写报告、合成harness、测试日志与索引；不修改repo/raw/Git，不读取Keychain、环境值或系统账户，不调用外部服务。runner以空环境启动测试，普通合成临时目录已清理。

复现：保留本append-only目录；把三个harness脚本复制到新的私有外部目录，再用指定Python -B运行run-review.py。脚本固定引用本次repo/runtime，记录实际命令与前后hash。最终证据以final-functional-report-final.json、python-results.json、node-results.json、run-metadata.json、git-check.json与四份.log为准。初版报告与index保留为append-only历史；最终索引为index-final.json。
