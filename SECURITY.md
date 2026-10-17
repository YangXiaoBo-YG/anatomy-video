# Security

## What is in scope

Anatomy is a set of instructions, a drawing kit and local Node scripts. The scripts that start Chrome (`capture.mjs`, `drive.mjs`, `lines.mjs`, `turn-check.mjs`) run it headless with a throwaway profile and `--allow-file-access-from-files`, and `drive.mjs` runs JavaScript you pass it in the page. Point them only at pages you trust.

A security problem is anything in this repository that could let a page, a prompt or a file run code, read files or reach the network in a way the user did not ask for: in the kit, in the scripts, in the built example pages, or in instructions in `SKILL.md` and `references/` that would lead Claude to do something unsafe.

## Supported versions

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Please don't open a public issue for a security problem. Report it privately through GitHub's [private vulnerability reporting](https://github.com/wheresryan22/anatomy/security/advisories/new) for this repository. If that link does not work, send a direct message to [@wheresryan22](https://x.com/wheresryan22) on X asking for a private channel, without the details.

Include what you found, how to reproduce it, and what it could let someone do.


# API 密钥与示例媒体

视频 Skill 的 API 调用代码可以公开。实际配音密钥通过 `VOLC_API_KEY` 环境变量读取，不应粘贴到脚本、示例配置、README、Issue 或截图。

不要提交真实 `.env`、私钥、鉴权头、原始请求 / 响应、签名下载链接、个人缓存和用户数据。当前示例入口提供导出的截图和视频媒体，不需要访问个人 API 账户。

检查应覆盖当前源码与 Git 历史。`key`、`token`、`password` 出现在变量名或文档中不等于泄露；需要判断是否包含实际值。

若发现真实密钥公开，先吊销或轮换，再清理文件与历史。扫描没有发现凭据不能证明不存在其他未识别的敏感内容。
