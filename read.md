# 这台电脑上的视频通话

基于 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) v1.2.1。电脑打开页面就能说话、听见、看到 Live2D。手机用浏览器打开同一个页面。对话接到本机 DeepSeek Harness 里已经存在的一条会话，不在这里另写一份人格卡。

`conf.yaml`、证书私钥、以及 `live2d-models/deepseek_chan` 不在仓库里。克隆之后要在本机补上。

## 依赖什么

运行通话页需要这些：

- Python 3.10、3.11 或 3.12。项目声明是 `>=3.10,<3.13`。依赖用 [uv](https://docs.astral.sh/uv/) 安装，入口是 `uv sync`。
- 主要 Python 包已写在 `pyproject.toml`：FastAPI、Uvicorn、faster-whisper 用到的 torch / onnxruntime、Edge TTS、sherpa-onnx。本机实际用的是下面这一组，不是模板里的默认值。
- Node.js 18 或更新。本机是 18.18。`tools/` 里要执行一次 `npm install`，装 `ws`。Node 18 没有全局 `WebSocket` 和 `crypto.randomUUID`，`tools/dsh_turn.mjs` 里已经补上。
- 本机的 DeepSeek Harness（surfcore）。每句话由 `tools/dsh_turn.mjs` 调用 `D:\DPH\surfcore\src\dsh-client.js`。DSH 的端口每次启动会变，脚本会先试配置里的地址，再从 `%USERPROFILE%\.dsh\surfcore\bridge-supervisor.log` 最后一行 `DSH=http://127.0.0.1:端口` 里找当前地址。
- 语音识别：faster-whisper，模型 `models/whisper/small`，语言 `zh`，CPU，`int8`。模型文件不在仓库里，第一次运行会下载。
- 声音：Edge TTS，声音 `zh-CN-XiaoxiaoNeural`。这需要能访问微软的语音服务。
- 页面：`frontend/` 里是已经编译好的网页，包含 Live2D 运行库和浏览器端的语音活动检测模型。
- 浏览器：电脑用 Chrome。手机用 Chrome 或 Safari。不要用微信或其他应用内置浏览器，否则麦克风和摄像头不可用。

`conf.yaml` 由模板生成后留在本机，里面有会话 ID，不要提交。

大肥鱼（DeepSeek-chan）模型文件也不在仓库里。作者允许个人直播和使用，不允许把模型文件再上传、转卖或声称是自己做的。原画及拆分：神宫凉子。Live2D 建模：霓虹猫。模型来源：神宫凉子免费配布模型。要用的话，把模型文件夹放到 `live2d-models/deepseek_chan/`，入口文件是 `大肥鱼.model3.json`。`model_dict.json` 里已经有 `deepseek_chan` 这一项。

## 怎么启动

在仓库根目录：

```powershell
uv sync
copy config_templates\conf.ZH.default.yaml conf.yaml
cd tools
npm install
cd ..
powershell -ExecutionPolicy Bypass -File tools\start-server.ps1
```

然后编辑本机的 `conf.yaml`，至少改这几处：

- `character_config.live2d_model_name` 设为 `deepseek_chan`（模型文件要先放好；没有模型文件时可以暂时用 `mao_pro`）。
- `llm_provider` 设为 `dsh_session_llm`。
- `llm_configs.dsh_session_llm.session_id` 填完整的 `session-` 加 UUID。
- `asr_model` 设为 `faster_whisper`，`model_path` 为 `models/whisper/small`，`language` 为 `zh`，`device` 为 `cpu`，`compute_type` 为 `int8`。
- `tts_model` 设为 `edge_tts`，`voice` 为 `zh-CN-XiaoxiaoNeural`。

启动前，本机的 DeepSeek Harness 要已经在跑。服务起来后：

- 这台电脑打开 `http://127.0.0.1:12393`。
- 家里的手机先运行 `tools\start-https.ps1`。手机用 Chrome 或 Safari 打开 `https://这台电脑的局域网IP:12394/`。证书说明页是 `http://这台电脑的局域网IP:12392/cert-help.html`，按页面把 `ca.cer` 装进手机。
- 人在外面、不在同一个局域网时，再运行 `tools\start-tunnel.ps1`。它给出的 `https://` 地址相当于密码，不要发到公开场合。

页面右上角或顶部工具栏里的「会话」可以粘贴新的会话 ID。从下一句开始，电话接到那个会话。不完整的 ID 不会切换。

## 做了哪些改动

相对上游 Open-LLM-VTuber，这套通话做了这些事：

1. **接到已有会话，不另写人格。** 新增 `dsh_session_llm`。每一句交给 DeepSeek Harness 里指定的那条会话，用它自己的人格、记忆和历史来回答。不把人格卡写进通话配置。
2. **页面上可以换会话。** `GET/POST /api/dsh-session`。粘贴完整的 `session-` UUID 后，当前通话和 `conf.yaml` 里的会话 ID 一起换掉。宽屏幕上这个按钮排在原有工具栏最后；手机上那一排按钮会被页面裁掉，所以按钮单独放在右上角，不挡设置。
3. **脸部图层。** 大肥鱼有 49 组需要裁切的图层，页面原来只准备了 36 个位置。装不下的嘴内部和高光会整块画出来，看起来是张着的嘴和鼻子上的白条。`frontend` 里的渲染器改为使用 2 张蒙版纹理，最多能放 64 组。
4. **去掉会抽动脸部的待机。** 模型自带的待机在播受惊、流泪和出汗。通话里不再播放这段，眨眼和说话张嘴还在。
5. **手机上的默认大小。** `deepseek_chan` 的 `kScale` 是 `0.48`。手机页面没有捏合缩放，这个大小能让整个人落在屏幕里。
6. **手机用 HTTPS，电脑仍用本机 HTTP。** `tools/https-proxy.mjs` 在 `12394` 提供页面，`12392` 只提供证书说明。通话服务本身仍在 `127.0.0.1:12393`。
