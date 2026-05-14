"""SCALIST prompt-rewriting agent for HiDream-O1-Image.

Adapted from HiDream's upstream ``prompt_agent.py`` (Lightricks repo,
``examples/...``). Takes a raw user prompt + calls a local Ollama model
via its OpenAI-compatible ``/v1/chat/completions`` endpoint with the
SCALIST system prompt. Returns the rewritten English prompt designed
for accurate text rendering, layout anchoring, and resolved implicit
knowledge.

Why this exists:

HiDream-O1's leaderboard text-rendering scores assume the user prompt
has been pre-processed by this agent — the model was trained on
SCALIST-shaped prompts that spell out the exact glyphs, their fonts,
materials, and pixel-anchored positions. Feeding it Wyltek's raw
infographic prompts (e.g. "a poster titled 'Top 5 Coffee Origins'")
makes the model infer all that detail at generation time, which is
exactly the pixel-text mode where diffusion peers (and dense U1) still
beat it.

The default Wyltek prompt_optimizer (gemma4:26b) is great for general
creativity but doesn't enforce the SCALIST framework. This module
runs gemma4:26b (or whatever is configured) with the upstream HiDream
system prompt instead.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx


log = logging.getLogger(__name__)


# Upstream-exact SCALIST system prompt. Keep verbatim — the model is
# trained against this exact rubric (Chinese + bilingual examples).
# Copy taken from /home/phill/hidream-o1-image/prompt_agent.py 2026-05-13.
REWRITE_SYSTEM_PROMPT = """\
你是专业的AI图像生成Prompt工程师的Prompt Engineering Engine,也是一名拥有百科知识和视觉导演能力的创意总监.你的任务是分析用户的原始图像需求,推理出隐含知识和最佳视觉方案,并改写成一个**明确,详细,可直接用于图像生成的英文prompt**.

## 核心目标

图像生成模型只能执行直接的视觉描述,不能自行补全背景知识,逻辑关系或文字内容.因此,你必须提前完成知识解析,空间规划和视觉导演,把结果显式写入prompt中.

使用 SCALIST 框架扩写每个画面:
- **Subject**: 主体的身份,外观,颜色,材质,纹理,动作,表情,服饰.
- **Composition**: 镜头景别,视角,主体位置,前景/中景/背景层次,留白和视觉焦点.
- **Action**: 主体正在做什么,动作方向,姿态,互动关系.
- **Location**: 场景地点,室内/室外,时代,天气,时间段,环境细节.
- **Image style**: photorealistic, cinematic, oil painting, watercolor, anime, 3D render 等,并匹配合适的光线和色彩氛围.
- **Specs**: 摄影/渲染参数,如 85mm lens, low-angle shot, shallow depth of field, soft diffused light, dramatic backlighting, matte texture, sharp focus.
- **Text rendering**: 如果用户要求文字,必须把准确文字放在英文双引号中,并说明字体风格,颜色,大小,材质和精确位置.

1. **知识解析与显式化**: 凡是诗词,歌词,名言,公式,历史人物,科学概念,地标,名画,文化符号,历史事件,UI布局或现实世界对象,都要先解析出具体答案和可见特征,再写入prompt.不要只写 "Mona Lisa","Dunkirk evacuation","freedom" 这类需要模型自行理解的词.
2. **空间与逻辑锚定**: 把模糊关系改写为明确布局,例如 top left corner, centered in the foreground, slightly behind the main subject, background out of focus, text aligned along the bottom edge.不要使用"旁边""一些""好看"等含糊表达.
3. **文字排版精度**: 中文,英文,公式,多语言文本都必须逐字保留在引号中,例如 "床前明月光,疑是地上霜.举头望明月,低头思故乡." 或 "E = mc²";同时指定字体(calligraphy, serif, sans-serif, handwritten),颜色,材质和位置.
4. **真实世界落地**: 如果用户要求事实准确的内容,例如历史文物,天气现象,人物肖像,建筑,仪表盘或应用界面,要使用你的内部知识补全准确视觉细节.
5. **抽象概念具象化**: 把"自由,孤独,未来感,治愈"等抽象词转成可见场景,符号和氛围,例如飞鸟,断裂锁链,辽阔天空,冷色霓虹,柔和晨光等.

## 示例合并学习

- 用户说"李白的静夜思写在墙上",prompt 应写出完整中文诗句,并指定它以优雅中国书法写在古旧石墙的哪个位置.
- 用户说"三大力学的奠基人"或"爱因斯坦写质能方程",prompt 应解析出 Isaac Newton 或 Albert Einstein,并描述人物外貌,时代服饰,黑板,公式 "E = mc²" 等可见内容.
- 用户说"蒙娜丽莎""比萨斜塔""福字""敦刻尔克大撤退",prompt 应描述对应画面特征: 神秘微笑与交叠双手,倾斜白色大理石钟楼与拱廊,红底金色/黑色书法 "福",1940年海滩上等待撤离的士兵和海面船只.

## 输出prompt要求

- prompt 必须是一个英文的,连贯自然的单段落,像 Creative Director's Brief,而不是关键词堆砌或 tag soup.
- 长度通常为 80-220 词;**对于已经包含大量具体文字、列表或多段内容的用户输入,长度可以扩展到 600 词或更长,以确保所有文字元素都被保留**.
- 最重要的主体和画面意图放在开头,然后自然展开构图,动作,地点,风格,技术参数和文字渲染.
- 使用完整句子,丰富但准确的形容词,摄影/绘画/设计术语.
- 不要包含任何需要图像模型继续推理才能理解的表达.
- prompt 必须自包含,仅凭prompt本身就能准确生成图片.

## ⚠️ 强制文字保留规则 (HARD TEXT PRESERVATION RULE — 最高优先级,优先于长度限制)

如果用户的输入包含以下任何元素,你**必须**在输出prompt中**逐字保留全部内容**:

- 引号内的文字 (例如 "Hello World", "床前明月光")
- 标题、副标题、章节名 (例如 "Top 5 Coffee Origins", "Actionable Takeaways")
- 列表项目 (无论是bullet list、numbered list还是comma-separated)
- 百分比、数字、日期、统计数据 (例如 "22%", "Ethiopia 22%")
- 公式或方程 (例如 "E = mc²", "Narratives + Infrastructure = Adoption")
- 引语或Caption (例如 "Visibility creates attention.")
- 表格中的行/列内容
- 分类标签 (例如 "For Builders:", "For Investors:")
- 任何被用户明确写出的字符串

**绝对禁止**:
- 把多个具体文字项目总结成一个抽象描述 (不要把 "Ethiopia 22%, Colombia 19%, Brazil 18%" 简化为 "five country percentages")
- 用 "etc." 或 "and others" 省略用户列出的项目
- 把表格的列标题保留但丢失行内容
- 因为长度限制而删除用户提供的任何文字元素 — **长度限制服从于文字保留**

**如果用户列出10个文字元素,你的输出必须包含全部10个,每一个都用英文双引号包裹,并指定其字体/颜色/位置.**

如果由于内容极多,无法在单张图片中清晰渲染所有文字,**仍然要把所有文字写入prompt**,然后在prompt末尾添加视觉指令说明"some text may be rendered smaller for legibility, but all listed content must be visible"——让图像模型决定如何排版,而不是你替它筛选.

## 执行步骤

1. **Analyze**: 识别核心主体,用户意图,文字要求,参考限制和需要解析的隐含知识.
2. **Reason**: 选择最适合画面的光线,镜头,角度,纹理,风格,空间布局和事实细节.
3. **Rewrite**: 输出最终增强后的英文单段落prompt.

## 布局坐标 (Layout Bounding Boxes — 关键功能)

HiDream-O1 支持 `layout_bboxes` 参数,可以为每个文字元素指定精确的像素区域.这是处理密集文字图表的最佳方式 — 通过显式指定每段文字的位置,你减轻了图像模型的布局决策负担,让它专注于渲染.

**必须为输出prompt中所有显著的文字元素提供bbox坐标.**

坐标格式: `{"bbox": [x1, x2, y1, y2], "text": "exact text string"}`
- 全部使用 0.0 到 1.0 的相对坐标
- x1 < x2 (左边界 < 右边界), y1 < y2 (上边界 < 下边界)
- (0, 0) 在左上角, (1, 1) 在右下角
- 每个bbox必须配对一个简短的text字段 (引号内的精确字符串)

需要bbox的文字元素:
- 标题、副标题、章节名
- 列表中的每一项 (即使是5个国家的百分比也要逐一列出bbox)
- 公式
- 引语和captions
- 表格单元格
- 任何明确写出的字符串

不需要bbox的文字元素:
- 提示模型选择的字体名 (这些在prompt里描述,不需要bbox)
- 装饰性背景纹理或style描述

**布局规划原则**:
- 标题通常在画面顶部 (y1≈0.05, y2≈0.15, x1≈0.1, x2≈0.9)
- 副标题或重要主体在中上部 (y1≈0.15, y2≈0.3)
- 多列内容可分布为左右两半 (左: x1=0.1, x2=0.48; 右: x1=0.52, x2=0.9)
- 列表项垂直堆叠时,每个item的y范围相邻不重叠
- 底部quote或caption在底部 (y1≈0.85, y2≈0.95)
- bbox互不重叠,留有合理间距(0.02-0.05)
- 重要文字给更大bbox,辅助文字给更小bbox

## 输出格式 (最终)

只输出JSON,不加任何其他文字:
{
  "prompt": "英文单段落prompt(包含所有文字元素逐字保留)",
  "reasoning": "你的推理和知识解析过程(中文简述)",
  "resolved_knowledge": "你解析了哪些隐含知识(中文,如果没有隐含知识写'无')",
  "layout_bboxes": [
    {"bbox": [x1, x2, y1, y2], "text": "exact text 1"},
    {"bbox": [x1, x2, y1, y2], "text": "exact text 2"}
  ]
}\
"""


# Default endpoint — Wyltek's existing prompt_optimizer config talks to the
# same Ollama instance at ``http://[::1]:11434``. We hit the OpenAI-compatible
# subpath so we can use any model Ollama serves without per-model SDKs.
DEFAULT_OLLAMA_URL = os.environ.get("HIDREAM_OLLAMA_URL", "http://[::1]:11434")
DEFAULT_MODEL = os.environ.get("HIDREAM_PROMPT_MODEL", "gemma4:26b")
DEFAULT_TIMEOUT_S = 120.0


# ── JSON extraction (lifted verbatim from upstream, well-tested) ────────────

def _extract_json_block(text: str) -> str | None:
    depth = 0
    start = None
    in_string = False
    escape_next = False
    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : i + 1]
    return None


def _fix_unescaped_newlines(text: str) -> str:
    out: list[str] = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            out.append(ch)
            escape_next = False
            continue
        if ch == "\\" and in_string:
            out.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            continue
        out.append(ch)
    return "".join(out)


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

    block = _extract_json_block(text) or text

    for candidate in (block, _fix_unescaped_newlines(block)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"Failed to parse JSON from model output:\n{text[:500]}")


def _sanitize_bbox(item: Any) -> dict[str, Any] | None:
    """Validate one bbox entry, return cleaned dict or None if invalid.

    Accepts either ``{"bbox": [x1,x2,y1,y2], "text": "..."}`` or just a
    bare ``[x1,x2,y1,y2]``. Coordinates outside [0, 1] are clipped; bboxes
    with inverted order (x1>=x2 or y1>=y2) or non-numeric coords are
    rejected (return None) so we don't push junk to the renderer.
    """
    if isinstance(item, dict) and "bbox" in item:
        bbox = item["bbox"]
        text = str(item.get("text", "") or "")
    elif isinstance(item, (list, tuple)):
        bbox = item
        text = ""
    else:
        return None

    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, x2, y1, y2 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None

    # Clip to [0, 1]; reject inverted boxes.
    x1, x2 = max(0.0, min(x1, 1.0)), max(0.0, min(x2, 1.0))
    y1, y2 = max(0.0, min(y1, 1.0)), max(0.0, min(y2, 1.0))
    if x1 >= x2 or y1 >= y2:
        return None

    return {"bbox": [x1, x2, y1, y2], "text": text}


def _sanitize_bboxes(raw_bboxes: Any) -> list[dict[str, Any]]:
    """Normalise the model's bbox output to a clean list. Drops invalid
    entries silently — the renderer still gets the text via the prompt,
    so a missing bbox is graceful degradation, not a hard failure."""
    if not isinstance(raw_bboxes, (list, tuple)):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in raw_bboxes:
        b = _sanitize_bbox(item)
        if b is not None:
            cleaned.append(b)
    return cleaned


def _wrap_result(raw: str, user_input: str) -> dict[str, Any]:
    """Parse the model's JSON output; on any failure fall back to a
    quality-keyword augmentation of the original prompt so the caller
    can still proceed to generation.

    Also normalises the ``layout_bboxes`` field (new 2026-05-13): any
    invalid bbox entries are dropped, leaving a clean list of
    ``{"bbox": [x1,x2,y1,y2], "text": "..."}`` items for HiDream's
    generate_image to consume directly.
    """
    try:
        result = _parse_json(raw)
        if "prompt" not in result or not isinstance(result["prompt"], str):
            raise ValueError("Missing 'prompt' field in parsed JSON.")
        # Normalise bboxes — drops to [] if absent or malformed, keeping
        # the rest of the result intact.
        result["layout_bboxes"] = _sanitize_bboxes(result.get("layout_bboxes"))
        return result
    except (ValueError, json.JSONDecodeError):
        return {
            "prompt": user_input + ", highly detailed, masterpiece, best quality, sharp focus",
            "reasoning": "(parse failed; falling back to keyword-augmented original)",
            "resolved_knowledge": "n/a",
            "layout_bboxes": [],
            "raw": raw,
            "fallback": True,
        }


# ── Async Ollama call ───────────────────────────────────────────────────────


async def rewrite_prompt(
    user_input: str,
    *,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Async SCALIST rewrite via Ollama's native ``/api/chat`` endpoint.

    Uses the native endpoint (not the OpenAI-compat proxy) so we can set
    ``keep_alive: 0`` — this tells Ollama to release the gemma4 model
    immediately after the response, instead of holding it in VRAM for
    the default 5 minutes. Critical on a 24 GB GPU where the next step
    (hidream weight load) wants ~17 GB; without this, the two model
    residents collide and OOM.

    ``think: false`` is also set per the project's Ollama-endpoint
    convention (gemma4 has internal thinking mode that bloats output
    and slows generation; we want raw completion).

    Returns a dict with at least ``prompt`` (str). On any failure
    (network, JSON parse, missing field) returns a graceful fallback
    dict with ``fallback: True`` so callers can decide whether to log +
    proceed or surface the failure. We err on the side of "always
    return something usable" — a stuck infographic UI is worse than an
    un-rewritten render.
    """
    url = f"{ollama_url.rstrip('/')}/api/chat"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "stream": False,
        "think": False,
        # 0 = unload immediately after response. Required to free VRAM
        # before the hidream-worker's weight-load step. See module
        # docstring for the OOM history that motivated this.
        "keep_alive": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        log.warning(f"SCALIST rewrite HTTP error: {exc}; falling back")
        return {
            "prompt": user_input + ", highly detailed, masterpiece, best quality, sharp focus",
            "reasoning": f"(SCALIST endpoint unreachable: {exc})",
            "resolved_knowledge": "n/a",
            "fallback": True,
            "error": str(exc),
        }

    # Native /api/chat shape: {"message": {"content": "..."}, "done": true, ...}
    # Falls back to message.thinking when content is empty (gemma4 quirk per
    # the project's Ollama-endpoint memory note).
    try:
        msg = data.get("message") or {}
        raw = msg.get("content") or msg.get("thinking") or ""
        if not raw:
            raise ValueError("Ollama returned empty content and empty thinking")
    except (KeyError, ValueError, AttributeError) as exc:
        log.warning(f"SCALIST: unexpected response shape: {exc}; falling back")
        return {
            "prompt": user_input + ", highly detailed, masterpiece, best quality, sharp focus",
            "reasoning": f"(unexpected Ollama response shape: {exc})",
            "resolved_knowledge": "n/a",
            "fallback": True,
            "error": str(exc),
        }

    return _wrap_result(raw, user_input)
