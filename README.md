# TPR Skills

用于生成、质检、打包和恢复双语 TPR 动作卡的开源 Codex Skill。

## 技能

- [`generate-adaptive-tpr-action-cards`](skills/generate-adaptive-tpr-action-cards/SKILL.md)：根据人物、动物、玩具、吉祥物、机器人或风格化角色参考图，生成角色一致的中英双语 TPR 动作卡。

技能源码位于独立目录中；仓库级文档、许可证和测试不会混入可安装的 Skill 包。

## 运行环境

- Python 3.10+
- Pillow
- python-docx

安装运行依赖：

```bash
python -m pip install -r requirements.txt
```

请在安装前确认目标 Python 环境。技能生成的参考照片、批次清单、成品图片、Word 文档和 ZIP 交付物应存放在仓库外，避免意外公开用户数据。

## 验证

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

测试覆盖技能元数据、全部命令入口、200 条双语动作库，以及 PNG 合成器在 Windows 和 Linux 上的代表性执行。

## 安装

将 `skills/generate-adaptive-tpr-action-cards/` 复制到你的 Codex Skills 目录，或从 GitHub 仓库安装该子目录。安装后以 `$generate-adaptive-tpr-action-cards` 显式调用。

## 许可证

除第三方字体外，本仓库的代码、文档和数据采用 [MIT License](LICENSE)。打包的 Noto Sans SC 字体继续遵循 [SIL Open Font License 1.1](skills/generate-adaptive-tpr-action-cards/assets/OFL.txt)，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
