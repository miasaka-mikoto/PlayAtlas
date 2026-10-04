# GitHub 上传状态

PlayAtlas 已通过当前会话的 GitHub 连接创建并同步到：

- 仓库：<https://github.com/miasaka-mikoto/PlayAtlas>
- 可见性：Public
- 默认分支：`main`
- 上传方式：GitHub 连接器的 Git Data API（blob → tree → commit → ref）
- 初始网页提交：`578c788d1c76b45f9206372d8c512dc295f916fb`

本地仓库仍保留完整历史和 `main` 分支，并已写入 `origin` URL。由于仓库是
本轮由网页先创建、再用 Git Data API 上传文件，远端提交历史从网页的
`Initial commit` 开始，与本地历史不是同一条祖先链；直接 `git push` 可能需要
先合并或重新克隆远端。当前 shell 没有 `gh` CLI、SSH key 或 credential helper，
因此没有把未经授权的凭据写入项目；GitHub 连接器使用会话中已经授权的账号
`miasaka-mikoto` 完成外部写入。

验证方式：

```bash
git -C PlayAtlas log --oneline --decorate -5
git -C PlayAtlas status --short
```

如果需要在本机继续推送，建议先从远端重新克隆，或在已登录的 Git 客户端中
明确处理历史合并：

```bash
git -C PlayAtlas fetch origin main
git -C PlayAtlas merge --allow-unrelated-histories origin/main
git -C PlayAtlas push -u origin main
```

不要把访问令牌、密码或浏览器会话写入仓库。
