# 发布与后续验收约定

Owner 于 2026-10-08 明确授权将 MetaSurvey 工程公开发布至 GitHub。主控独占发布、跨模块合同与最终集成；专项 worktree 不被发布工具改写，子任务不得直接推送公开默认分支。

每轮工作先完成工程和审查，写入版本化报告及 `docs/review/INDEX.json`，再更新固定入口 `docs/review/LATEST.md`。提交本地主控工程后，由发布工具从 Git HEAD 读取文件，生成新的公开快照和逐文件哈希。大型 ZIP、本机数据库、原始第三方数据、credentials、私钥和非 Git 文件不复制；六项已知许可未核验 reference fixture 仅列哈希与排除原因。原始源工程 Git 历史继续在本机，不得直接推送。

默认公开工作区为主控工程的兄弟目录 `metasurvey-github`。工具要求源工程干净且已提交，拒绝不属于该工具的目标目录、符号链接、被人工改动的受管镜像文件、疑似凭证和未审核二进制。它不执行 push，也不从公开工作区回写主控。

```sh
# 在本地主控工程内；git 路径可按实际环境指定。
python3 -B tools/github_publication/prepare.py --git /opt/homebrew/bin/git --destination ../metasurvey-github
# 在生成的公开工作区内：复现 TESTING.md 的检查后再提交和推送。
# 首次 init 后将工具标记排除，绝不能加入 Git：
git init -b main
printf '
/.metasurvey-publication.json
' >> .git/info/exclude
```

后续公开提交只包含已集成代码与可分享验收资料。工具生成的 `Source-Snapshot.json` 绑定本地主控 commit；`Local-Only-Manifest.json` 列已排除原件。第一次公开仓库从安全快照建立独立 Git 历史，没有复制旧原件的可达对象；未来不得强行把本地主控历史合入公开仓库。

每轮给 Owner 的最终通知通常只需：**“验收文件：仓库中的 `docs/review/LATEST.md` → 本轮报告。”** 需要 Owner 决定的事项或新出现的重要失败可另用一句说明。验收应记录具体 commit 固定链接，不能只记录会随时间变化的 main 分支入口。不会因发送对话消息而自动生成虚假验收、修改冻结结果或启动下一阶段。

旧主页原字节保全为根目录 `README-Historical-20261008.md`，因此其历史相对链接仍以原来的仓库根目录解析。当前入口以 `README.md` 和 `docs/review/LATEST.md` 为准。
