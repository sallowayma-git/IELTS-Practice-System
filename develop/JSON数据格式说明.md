# JSON数据格式说明

> **用途**: 定义IELTS阅读练习文章的JSON数据结构和字段规范  
> **受众**: 脚本开发者、前端开发者  
> **前置阅读**: 无，本文档为独立规范

---

## 1. 整体结构概述

### 1.1 顶层结构

每篇IELTS阅读文章的JSON文件包含四个主要部分：

1. **文章标识** (`id`)
   - 唯一标识符，用于索引和引用
   - 格式: 字母e + 3位数字（如"e028"）

2. **文章内容** (`passage`)
   - 包含文章标题和正文段落
   - 段落可能带有标签（如"A", "B", "C"）

3. **题目列表** (`questions`)
   - 包含该文章的所有题目
   - 题目按顺序排列，编号连续

4. **元数据** (`metadata`)
   - 描述文章的基本信息
   - 包含难度、题目数量、题型统计等

### 1.2 数据流程

```
HTML文件 → 解析提取 → 生成JSON → 验证格式 → 输出文件
```

### 1.3 设计原则

**一致性原则**:
- 所有150篇文章使用相同的JSON结构
- 相同题型在不同文章中的字段保持一致
- 命名规则统一（如答案键统一小写）

**完整性原则**:
- 文章的所有内容都必须包含在JSON中
- 题目的所有选项和答案都必须完整
- 不能有信息丢失

**可解析性原则**:
- 前端可以直接根据JSON渲染出完整页面
- 不需要额外的数据处理或转换
- 字段名清晰，避免歧义

---

## 2. 文章标识部分

### 2.1 ID字段

**字段名**: `id`

**数据类型**: 字符串

**格式规则**:
- 必须以小写字母"e"开头
- 后接3位数字
- 数字部分用0补齐到3位

**取值范围**: "e001" 到 "e150"

**生成规则**:
- 从HTML文件名中提取编号
- 编号转为3位字符串（不足补0）
- 前面添加字母"e"

**示例**:
- HTML文件名包含"28" → id = "e028"
- HTML文件名包含"5" → id = "e005"
- HTML文件名包含"150" → id = "e150"

**用途**:
- 在manifest.json中索引文章
- 作为文件名的一部分（单个JSON文件）
- 前端路由和URL参数

---

## 3. 文章内容部分

### 3.1 passage对象结构

`passage`对象包含两个字段：
- `title`: 文章标题（字符串）
- `paragraphs`: 段落数组（数组）

### 3.2 title字段

**数据类型**: 字符串

**提取来源**: HTML的`<h3>`标签内容

**格式要求**:
- 保留原始英文标题
- 不包含难度标记（P1/P2/P3）
- 去除首尾空格
- 不包含HTML标签

**示例**:
- 正确: "Triumph of the City"
- 正确: "The return of monkey life"
- 错误: "P1 - Triumph of the City" （包含难度标记）
- 错误: "Triumph of the City 城市的胜利" （包含中文）

### 3.3 paragraphs数组

**数据类型**: 对象数组

**数组元素**: 每个元素代表一个段落，包含两个字段：
- `label`: 段落标签（字符串或null）
- `content`: 段落内容（字符串）

**段落数量**: 至少1个，通常5-15个

### 3.4 段落标签（label）

**数据类型**: 字符串或null

**可能的取值**:
- 大写字母: "A", "B", "C", "D" ... （最常见）
- 罗马数字: "I", "II", "III", "IV" ...
- null: 表示该段落没有标签

**提取规则**:
- 如果HTML段落的`data-label`属性存在且非空，使用其值
- 如果`data-label`不存在或为空，使用null
- 不能使用空字符串""

**用途**:
- 段落匹配题（paragraph-matching）的答案引用
- 标题匹配题（heading-matching）的答案引用
- 帮助考生定位文章内容

**示例说明**:
```
第一个段落:
  HTML: <div class="paragraph" data-label="A">...</div>
  JSON: {"label": "A", "content": "..."}

第二个段落:
  HTML: <div class="paragraph">...</div>（无data-label）
  JSON: {"label": null, "content": "..."}
```

### 3.5 段落内容（content）

**数据类型**: 字符串

**提取来源**: HTML段落标签的文本内容

**格式要求**:
- 保留原始文本，包括标点符号
- 去除HTML标签（如`<strong>`, `<em>`等）
- 保留段落内的换行（如有）
- 去除首尾空格

**特殊处理**:
- 如果段落内有多个`<p>`标签，可以用换行符"\n"连接
- 如果段落内有列表，保留列表结构或转为纯文本

**不应包含**:
- HTML标签
- 题目内容（题目在questions部分）
- 注释或说明文字

---

## 4. 题目列表部分

### 4.1 questions数组结构

**数据类型**: 对象数组

**数组元素**: 每个元素代表一道题目

**排序规则**: 按题号从小到大排序

**题号连续性**: 题号必须连续递增，不能跳号

### 4.2 题目通用字段

每道题目对象都包含以下基础字段：

#### questionNumber（题号）

**数据类型**: 整数

**取值规则**:
- 全局连续，从1开始
- 根据文章难度确定范围:
  * P1文章: 1-13 或 1-14
  * P2文章: 14-26 或 14-27
  * P3文章: 27-40

**特殊情况**:
- 多选题（占用多个题号）: 使用第一个题号
- 拖拽题（多个空格共用选项）: 每个空格占一个题号

#### type（题型）

**数据类型**: 字符串

**取值范围**: 14种题型代码之一（见第5节）

**命名规则**: 小写字母，单词间用连字符分隔

**示例**: "true-false-ng", "multiple-choice-single", "heading-matching"

#### instruction（题目说明）

**数据类型**: 字符串

**内容**: 题目的指导语或问题描述

**提取来源**: HTML中题组的`.question-group h4`内容

**格式要求**:
- 保留原始英文文本
- 去除HTML标签
- 去除题号（如"Questions 1-5"部分可保留）

**示例**:
- "Complete the notes below."
- "Choose the correct letter, A, B, C or D."
- "Do the following statements agree with the information given in the passage?"

#### content（题目内容）

**数据类型**: 对象

**说明**: 这是一个包含题目具体内容的对象，其结构根据题型不同而不同

**通用原则**:
- 包含该题所需的所有数据
- 字段名清晰，见名知义
- 前端可直接渲染，无需额外处理

#### answer（正确答案）

**数据类型**: 字符串或数组

**说明**: 该题的正确答案

**格式规则**:
- 遵循第6节的答案格式规范
- 小写（除TRUE/FALSE/NOT GIVEN和选项字母）
- 多选题使用数组

**是否必需**: 建议包含，便于验证和测试

**部署选项**: 
- 开发/测试环境: 保留
- 生产环境: 可选择性移除或加密

#### explanation（答案解析）

**数据类型**: 字符串

**说明**: 解释为什么这是正确答案，通常引用文章原文

**格式**: 英文句子，引用原文时使用单引号

**示例**: 
```
"The passage states 'disease spread rapidly among the population.'"
```

**是否必需**: 可选，但强烈建议包含

**用途**:
- 帮助学生理解答案
- 教师版功能
- 自学模式

### 4.3 多选题特殊字段

对于"multiple-choice-multiple"题型，需要额外字段：

**checkboxGroupName**:
- 数据类型: 字符串
- 格式: "group" + 题号
- 示例: "group14"（第14题）
- 用途: HTML表单中checkbox的name属性

**occupiesQuestions**:
- 数据类型: 整数
- 说明: 该题占用几个题号
- 示例: 如果是"选3个答案"的题，值为3
- 用途: 计算下一题的题号

### 4.4 拖拽题特殊字段

对于拖拽类题型（如paragraph-matching, feature-matching等），需要：

**canReuse**:
- 数据类型: 布尔值（true/false）
- 说明: 选项是否可重复使用
- 提取规则: 
  * HTML中选项有`data-clone="true"`属性 → canReuse = true
  * 否则 → canReuse = false
- 用途: 前端渲染时决定是否显示多个相同选项

---

## 5. 题型详细说明

### 5.1 题型分类原则

**重要**: 题型识别和分类严格基于《PDF转网页工作流.md》中定义的HTML结构和交互方式。

根据工作流，所有题型分为5大类，每类对应特定的HTML元素和交互方式：

| 大类 | HTML交互元素 | 包含的具体题型代码 |
|------|-------------|------------------|
| **判断题** | `<input type="radio">` | `true-false-ng`, `yes-no-ng` |
| **单选题** | `<input type="radio">` | `multiple-choice-single` |
| **多选题** | `<input type="checkbox">` | `multiple-choice-multiple` |
| **填空题** | `<input type="text" class="blank">` | `sentence-completion`, `summary-completion`, `notes-completion`, `table-completion`, `short-answer` |
| **拖拽匹配题** | `<div class="card" draggable="true">` + `<span class="dropzone">` | `paragraph-matching`, `heading-matching`, `feature-matching`, `statement-matching`, `sentence-ending-matching`, `classification` |

### 5.2 题型代码完整列表

根据工作流和实际HTML文件，以下是所有题型代码：

| 题型代码 | 中文名称 | HTML识别特征 |
|---------|---------|-------------|
| `true-false-ng` | TRUE/FALSE/NOT GIVEN判断题 | radio按钮，3个选项：TRUE/FALSE/NOT GIVEN |
| `yes-no-ng` | YES/NO/NOT GIVEN判断题 | radio按钮，3个选项：YES/NO/NOT GIVEN |
| `multiple-choice-single` | 单选题 | radio按钮，4个选项（A/B/C/D） |
| `multiple-choice-multiple` | 多选题 | checkbox按钮，5-7个选项，需选2-3个 |
| `sentence-completion` | 句子填空 | text input，句子结构 |
| `summary-completion` | 摘要填空 | text input或drag-drop，段落结构 |
| `notes-completion` | 笔记填空 | text input或drag-drop，笔记/列表结构 |
| `table-completion` | 表格填空 | text input，表格结构 |
| `short-answer` | 简答题 | text input，完整问题+答案 |
| `paragraph-matching` | 段落信息匹配 | drag-drop，选项为段落标签（A/B/C...） |
| `heading-matching` | 标题匹配 | drag-drop，选项为标题列表 |
| `feature-matching` | 特征匹配 | drag-drop，选项为人名/地名/概念等 |
| `statement-matching` | 陈述匹配 | drag-drop，匹配陈述与人名/观点 |
| `sentence-ending-matching` | 句子结尾匹配 | drag-drop，匹配句子开头与结尾 |
| `classification` | 分类题 | drag-drop，将项目分类 |

### 5.3 题型识别规则

**从HTML识别题型的步骤**:

**步骤1: 确定大类**
1. 检查HTML中的交互元素类型
2. 根据元素类型确定大类（判断/单选/多选/填空/拖拽）

**步骤2: 确定具体题型**
1. 对于判断题类: 检查选项是TRUE/FALSE还是YES/NO
2. 对于填空题类: 检查题目结构（句子/摘要/笔记/表格）
3. 对于拖拽题类: 检查选项内容（段落标签/标题/人名等）

**步骤3: 提取content字段**
1. 根据题型提取对应的字段
2. 确保字段名与下表一致

### 5.4 content字段结构（按大类）

#### 5.4.1 判断题类（true-false-ng, yes-no-ng）

**HTML元素**: `<input type="radio" name="qX" value="TRUE/FALSE/NOT GIVEN">`

**content结构**:
```
{
  "statement": "陈述句文本"
}
```

**说明**: 
- statement是需要判断真伪的陈述
- 选项固定为3个（TRUE/FALSE/NOT GIVEN 或 YES/NO/NOT GIVEN）
- 不需要在JSON中存储选项（前端固定渲染）

#### 5.4.2 单选题（multiple-choice-single）

**HTML元素**: `<input type="radio" name="qX" value="A/B/C/D">`

**content结构**:
```
{
  "questionText": "问题文本",
  "options": [
    {"label": "A", "text": "选项A文本"},
    {"label": "B", "text": "选项B文本"},
    {"label": "C", "text": "选项C文本"},
    {"label": "D", "text": "选项D文本"}
  ]
}
```

**说明**:
- questionText是完整问题
- options通常4个选项（A/B/C/D）

#### 5.4.3 多选题（multiple-choice-multiple）

**HTML元素**: `<input type="checkbox" name="groupX">`

**content结构**:
```
{
  "questionText": "问题文本",
  "options": [
    {"label": "A", "text": "选项A文本"},
    {"label": "B", "text": "选项B文本"},
    ...（5-7个选项）
  ]
}
```

**额外字段**（题目对象级别）:
- `checkboxGroupName`: 字符串，格式"groupX"
- `occupiesQuestions`: 整数，需要选择的答案数量

**说明**:
- options通常5-7个选项（A到F或G）
- 题目说明中会指明选几个（如"Choose TWO letters"）

#### 5.4.4 填空题类（completion类型）

**HTML元素**: `<input type="text" class="blank" name="qX">`

**通用content结构**:
```
{
  "sentence": "带______ 空格的句子或段落",
  "wordLimit": "ONE WORD ONLY"  或  "NO MORE THAN TWO WORDS"
}
```

**如果是选词填空（带拖拽选项）**:
```
{
  "sentence": "带______ 空格的句子",
  "wordLimit": "选词填空",
  "options": [
    {"label": "A", "text": "选项A"},
    {"label": "B", "text": "选项B"}
  ],
  "canReuse": true/false
}
```

**各子类型的差异**:
- `notes-completion`: 通常有结构化的笔记格式（标题、缩进）
- `summary-completion`: 通常是连续段落
- `sentence-completion`: 单个句子
- `table-completion`: 表格结构
- `short-answer`: 完整问题+答案，不用下划线

#### 5.4.5 拖拽匹配题类（matching类型）

**HTML元素**: 
- `<div class="card" draggable="true" data-value="X" data-clone="true/false">`
- `<span class="dropzone" data-target="qX">`

**通用content结构**:
```
{
  "statement": "要匹配的内容",  // 或其他名称，见下表
  "options": [
    {"label": "A", "text": "选项A文本"},
    {"label": "B", "text": "选项B文本"}
  ],
  "canReuse": true/false  // 根据data-clone属性确定
}
```

**各子类型的字段差异**:

| 题型代码 | statement字段名 | options的label | options的text |
|---------|----------------|---------------|--------------|
| `paragraph-matching` | `statement` | 段落标签（A/B/C） | 通常为空或段落首句 |
| `heading-matching` | `paragraphLabel` | 罗马数字（i/ii/iii） | 标题文本 |
| `feature-matching` | `feature` 或 `statement` | 字母（A/B/C） | 人名/地名/概念 |
| `statement-matching` | `statement` | 字母（A/B/C） | 人名/学者名 |
| `sentence-ending-matching` | `sentenceStart` | 字母（A/B/C） | 句子结尾 |
| `classification` | `item` 或 `statement` | 字母（A/B/C） | 类别名称 |

**canReuse确定规则**:
- HTML中有`data-clone="true"` → `canReuse: true`
- 没有或为`false` → `canReuse: false`
- 通常paragraph-matching和classification为true（可重复使用）

---

## 6. 答案和解析

### 6.1 答案存储方案

**推荐方案**: 答案和解析直接存储在题目JSON中，部署时可选择性处理

#### 数据源

**HTML文件中的答案**:
```javascript
const correctAnswers = {
    q1: 'disease',
    q2: 'political',
    q9: 'FALSE'
};
```
- 位置：`<script>`标签内
- 格式：JavaScript对象
- 内容：仅答案，无解析

**JSON中的存储**:
```json
{
  "questionNumber": 1,
  "type": "notes-completion",
  "content": {...},
  "answer": "disease",
  "explanation": "The passage states 'disease spread rapidly among the population.'"
}
```

#### 存储策略的优势

**1. 数据完整性**:
- 题目、答案、解析在一起，便于管理
- 单一数据源，避免不一致

**2. 开发便利**:
- 转换脚本一次性处理所有数据
- 便于验证JSON的正确性
- 测试时可直接使用答案

**3. 部署灵活**:
```javascript
// 构建脚本可选择性处理答案
// 选项1: 保留答案（教师版/自学版）
// 选项2: 移除答案（学生考试版）
// 选项3: 加密答案（需要时解密）
```

**4. 功能扩展**:
- 支持"查看答案"功能
- 支持"查看解析"功能
- 支持自动批改
- 支持学习模式

### 6.2 answer字段格式

每道题的`answer`字段直接存储答案值：

**单答案题型**（字符串）:
```json
"answer": "disease"          // 填空题
"answer": "TRUE"             // 判断题
"answer": "C"                // 选择/匹配题
```

**多答案题型**（数组）:
```json
"answer": ["B", "D", "F"]    // 多选题
```

### 6.3 explanation字段格式

每道题的`explanation`字段提供答案解析：

**格式要求**:
- 英文句子或段落
- 引用原文时使用单引号
- 解释为什么选择该答案
- 指出答案在文章中的位置

**示例**:
```json
"explanation": "The passage states 'disease spread rapidly among the population.'"
"explanation": "Paragraph C explains that younger forests produce lower levels of toxins."
"explanation": "The writer's focus throughout the passage is describing various attempts to decode the manuscript."
```

### 6.4 HTML中的答案对象（数据源）

从HTML提取答案时，需要解析`correctAnswers`对象：

```javascript
const correctAnswers = {
  q1: "答案1",
  q2: "答案2",
  q14: ["B", "D"],  // 多选题是数组
  ...
};
```

**键格式**: 小写"q" + 题号

### 6.5 答案值格式规则

**格式**: 小写字母"q" + 题号

**示例**:
- 第1题 → q1
- 第14题 → q14
- 第27题 → q27

**重要**: 必须是小写"q"，不能是"Q"或"question1"

### 6.4 答案值格式规则

#### 通用规则1: 大小写

**默认规则**: 答案字符串全部转为小写

**例外情况**: 以下答案保持原大写
- TRUE / FALSE / NOT GIVEN
- YES / NO / NOT GIVEN
- 选项字母: A, B, C, D, E, F, G
- 段落标签: A, B, C, D ...（用于段落匹配题）
- 罗马数字: i, ii, iii, iv ...（但通常是小写）

**示例**:
- 填空题答案"Disease" → 转为"disease"
- 填空题答案"New York" → 转为"new york"
- 判断题答案"TRUE" → 保持"TRUE"
- 单选题答案"B" → 保持"B"
- 段落匹配答案"C" → 保持"C"

#### 通用规则2: 数组格式

**单选/单答案**: 使用字符串
```javascript
q1: "disease"
q2: "TRUE"
q3: "B"
```

**多选/多答案**: 使用数组
```javascript
q14: ["B", "D", "F"]  // 多选题
```

**重要**: 即使多选题只选了一个答案，也必须用数组格式：
```javascript
q14: ["B"]  // 正确
q14: "B"    // 错误
```

#### 通用规则3: 空格处理

**规则**: 去除答案字符串首尾的空格

**示例**:
- " disease " → "disease"
- "  new york  " → "new york"

**注意**: 答案中间的空格保留

### 6.5 各题型答案格式

| 题型 | 答案格式 | 示例 |
|------|---------|------|
| 单选题 | 大写字母 | "B" |
| 多选题 | 大写字母数组 | ["B", "D", "F"] |
| TRUE/FALSE/NOT GIVEN | 大写单词 | "TRUE", "NOT GIVEN" |
| YES/NO/NOT GIVEN | 大写单词 | "YES", "NOT GIVEN" |
| 段落匹配 | 大写段落标签 | "C" |
| 标题匹配 | 小写罗马数字 | "iii" |
| 特征匹配 | 大写字母 | "A" |
| 句子结尾匹配 | 大写字母 | "D" |
| 填空题（自由填空） | 小写单词/短语 | "disease", "new york" |
| 填空题（选词填空） | 大写字母 | "B" |
| 简答题 | 小写单词/短语 | "three years", "the government" |
| 分类题 | 大写字母 | "A" |

### 6.6 答案提取逻辑

从HTML提取答案时的处理步骤：

**步骤1**: 定位`correctAnswers`对象
- 在HTML中查找`<script>`标签
- 找到包含`const correctAnswers = {`的部分
- 解析为JavaScript对象

**步骤2**: 提取每道题的答案
- 遍历所有题号
- 读取对应的答案值

**步骤3**: 格式验证和转换
- 检查答案键是否符合"q+数字"格式
- 检查答案值类型（字符串或数组）
- 根据题型验证答案格式
- 应用大小写规则
- 去除空格

**步骤4**: 存储用于验证
- 将答案与对应题目关联
- 用于验证JSON的完整性
- 检查是否有题目缺少答案

---

## 7. 元数据部分

### 7.1 metadata对象结构

`metadata`对象包含以下字段：

#### difficulty（难度级别）

**数据类型**: 整数

**取值范围**: 1, 2, 或 3

**对应关系**:
- 1 = P1 = 简单
- 2 = P2 = 中等
- 3 = P3 = 困难

**提取来源**: HTML文件名中的"P1"/"P2"/"P3"部分

#### totalQuestions（题目总数）

**数据类型**: 整数

**计算方法**: questions数组的长度

**取值范围**: 通常13-14题（根据难度）

**验证规则**: 必须等于questions数组的实际长度

#### questionTypes（题型列表）

**数据类型**: 字符串数组

**内容**: 该文章包含的所有题型代码

**生成方法**:
1. 遍历questions数组
2. 提取每道题的type字段
3. 去重（相同题型只保留一次）
4. 保持出现顺序

**示例**:
```javascript
["notes-completion", "true-false-ng"]
["paragraph-matching", "summary-completion", "feature-matching"]
```

**用途**:
- 快速了解文章包含哪些题型
- manifest中的搜索和筛选
- 统计分析

---

## 8. 特殊情况处理

### 8.1 拖拽题的处理

#### 识别拖拽题

拖拽题包括：
- paragraph-matching
- heading-matching
- feature-matching
- sentence-ending-matching
- classification
- 以及带选项的填空题（summary/notes/table/sentence-completion with options）

#### canReuse字段的确定

**提取规则**:
1. 在HTML中找到该题的选项容器（通常是`.drag-options`）
2. 检查容器或其中的选项元素是否有`data-clone="true"`属性
3. 如果有，设置`canReuse: true`
4. 如果没有，设置`canReuse: false`

**逻辑说明**:
- `data-clone="true"` 表示前端会克隆选项，允许重复拖拽
- 这对应IELTS中的"选项可重复使用"规则
- 常见于特征匹配、分类题

#### 选项的提取

拖拽题的选项通常在专门的选项区域：

**HTML结构**:
```
<div class="drag-options">
  <div class="drag-option" data-answer="A">选项A文本</div>
  <div class="drag-option" data-answer="B">选项B文本</div>
  ...
</div>
```

**提取步骤**:
1. 定位选项容器
2. 遍历所有`.drag-option`元素
3. 提取`data-answer`作为key
4. 提取元素文本内容作为text
5. 构建options数组

### 8.2 多选题的处理

#### 识别多选题

**HTML特征**:
- 题目说明中包含"choose TWO/THREE letters"等字样
- 使用`<input type="checkbox">`而非`<input type="radio">`
- name属性为"group"+"题号"

#### 占用题号的计算

**规则**: 从题目说明中提取选择数量

**示例说明**:
- "Choose TWO letters" → occupiesQuestions = 2
- "Choose THREE letters" → occupiesQuestions = 3
- "Which THREE statements..." → occupiesQuestions = 3

**提取方法**:
1. 在instruction中查找"TWO"/"THREE"/"FOUR"等单词
2. 转换为数字: TWO→2, THREE→3
3. 如果找不到，检查答案数组长度

#### checkboxGroupName的生成

**格式**: "group" + 题号

**示例**:
- 第14题 → "group14"
- 第25题 → "group25"

**用途**: 前端渲染checkbox时作为name属性，确保同一组的checkbox关联

### 8.3 填空题的处理

#### 识别填空题类型

填空题分为两类：

**自由填空**:
- 无选项，考生自己填写
- content只需要sentence和wordLimit
- 不需要options和canReuse字段

**选词填空**:
- 有选项列表，考生从中选择
- content需要sentence, wordLimit, options, canReuse
- 选项通常是拖拽方式

#### 空格的表示

**HTML中的表示**: `<input type="text">`或`.blank-input`

**JSON中的表示**: 连续的下划线`______`（至少5个）

**转换规则**:
1. 找到题目句子中的空格位置
2. 将`<input>`或类似元素替换为`______`
3. 保留句子的其余部分

**示例**:
```
HTML: The disease was first discovered in <input type="text"> by researchers.
JSON: "sentence": "The disease was first discovered in ______ by researchers."
```

#### wordLimit的提取

**来源**: 题目说明（instruction）

**提取方法**:
- 查找"ONE WORD"/"TWO WORDS"/"THREE WORDS"等
- 提取数字部分
- 如果是"NO MORE THAN TWO WORDS"，取2
- 如果是"ONE WORD AND/OR A NUMBER"，取2

**默认值**: 如果无法提取，使用1

### 8.4 题号连续性问题

#### 基本规则

题号必须连续递增，不能跳号。

#### 多选题的题号

**规则**: 多选题使用第一个题号，但占用多个题号

**示例**:
```
题号13: 单选题
题号14: 多选题（选3个，占用14、15、16）
题号17: 下一道题
```

**JSON表示**:
```javascript
{
  "questionNumber": 14,
  "type": "multiple-choice-multiple",
  "occupiesQuestions": 3,
  ...
}
```

#### 题号范围验证

**规则**: 根据文章难度验证题号范围

**P1文章**:
- 预期范围: 1-13 或 1-14
- 如果超出范围，报告警告

**P2文章**:
- 预期范围: 14-26 或 14-27
- 起始题号通常是14

**P3文章**:
- 预期范围: 27-40
- 起始题号通常是27或28

---

## 9. 数据验证规则

### 9.1 结构完整性验证

**必需字段检查**:
- 顶层必须有: id, passage, questions, metadata
- passage必须有: title, paragraphs
- 每个段落必须有: label, content
- 每道题必须有: questionNumber, type, instruction, content
- metadata必须有: difficulty, totalQuestions, questionTypes

**字段类型检查**:
- id: 字符串
- passage.title: 字符串
- passage.paragraphs: 数组
- questions: 数组
- metadata.difficulty: 数字
- metadata.totalQuestions: 数字
- metadata.questionTypes: 数组

### 9.2 数据一致性验证

**题目数量一致性**:
- metadata.totalQuestions 必须等于 questions.length

**题号连续性**:
- questions数组的questionNumber必须从小到大连续
- 考虑多选题的占用情况

**题型一致性**:
- metadata.questionTypes 必须包含questions中所有出现的type
- 不能有重复的题型代码

### 9.3 内容有效性验证

**非空检查**:
- passage.title 不能为空字符串
- 每个段落的content 不能为空
- 每道题的instruction 不能为空

**段落标签有效性**:
- label 只能是字符串或null
- 如果是字符串，不能为空字符串""
- 大写字母段落标签应该按顺序（A, B, C...）

**题号范围有效性**:
- 根据difficulty验证questionNumber范围
- P1: 1-14, P2: 14-27, P3: 27-40

### 9.4 题型特定验证

**拖拽题验证**:
- 必须有canReuse字段
- options数组不能为空
- 每个选项必须有key和text

**多选题验证**:
- 必须有checkboxGroupName字段
- 必须有occupiesQuestions字段
- occupiesQuestions必须≥2

**填空题验证**:
- 必须有wordLimit字段
- wordLimit必须是正整数
- sentence必须包含空格标记`______`

**判断题验证**:
- content必须有statement字段
- statement不能为空

**选择题验证**:
- content必须有question和options
- options数组不能为空
- 每个选项必须有key和text

---

## 10. JSON生成工作流

### 10.1 整体流程

```
读取HTML文件
    ↓
提取文章ID和元数据（从文件名）
    ↓
提取文章内容（title和paragraphs）
    ↓
提取题目列表（逐题处理）
    ↓
提取答案对象（用于验证）
    ↓
构建JSON对象
    ↓
验证JSON格式
    ↓
输出JSON文件
```

### 10.2 提取顺序建议

**阶段1: 基础信息**
1. 从文件名提取编号和难度
2. 生成文章ID
3. 设置metadata.difficulty

**阶段2: 文章内容**
1. 提取文章标题（`<h3>`）
2. 提取所有段落（`.paragraph`）
3. 对每个段落提取label和content

**阶段3: 题目信息**
1. 定位所有题组（`.question-group`）
2. 对每个题组提取instruction
3. 对每个题目：
   - 提取题号
   - 识别题型
   - 提取content（根据题型不同而不同）

**阶段4: 答案和验证**
1. 提取correctAnswers对象
2. 验证每道题都有对应答案
3. 验证答案格式

**阶段5: 元数据补充**
1. 计算totalQuestions
2. 统计questionTypes
3. 完成metadata对象

**阶段6: 输出**
1. 构建完整JSON对象
2. 运行验证规则
3. 格式化输出（带缩进）
4. 保存到文件

### 10.3 错误处理原则

**遇到错误时的策略**:

**可恢复错误**:
- 记录警告，继续处理
- 例如: 段落标签缺失 → 使用null

**不可恢复错误**:
- 记录错误，跳过该文件
- 例如: 找不到文章标题、题目区域为空

**错误记录内容**:
- 文件名/ID
- 错误类型
- 错误位置（如第几个段落、第几道题）
- 错误详情

---

## 11. 最佳实践

### 11.1 开发建议

**从简单开始**:
1. 先处理1个示例文件
2. 先实现1-2种题型
3. 逐步增加题型支持
4. 最后处理边界情况

**充分测试**:
1. 使用3个示例文件验证
2. 对比手工制作的样例JSON
3. 测试每种题型
4. 测试特殊情况（如多选题、拖拽题）

**日志记录**:
1. 记录每个文件的处理状态
2. 记录每道题的题型
3. 记录提取的答案
4. 记录验证结果

### 11.2 常见陷阱

**陷阱1: 答案大小写**
- 错误: 所有答案都转小写
- 正确: TRUE/FALSE/NOT GIVEN和选项字母保持大写

**陷阱2: 多选题答案格式**
- 错误: 多选题答案使用字符串
- 正确: 必须使用数组，即使只有一个答案

**陷阱3: 段落标签空字符串**
- 错误: label设为空字符串""
- 正确: 如果没有标签，使用null

**陷阱4: 题号跳号**
- 错误: 多选题后的题号直接+1
- 正确: 需要加上occupiesQuestions的值

**陷阱5: HTML标签未清理**
- 错误: content中包含`<strong>`等HTML标签
- 正确: 提取纯文本，去除所有HTML标签

### 11.3 性能优化

**批量处理**:
- 不要一次加载所有150个文件
- 分批处理，每批10-20个

**增量处理**:
- 检查输出文件是否已存在
- 支持跳过已处理的文件
- 支持重新处理单个文件

**内存管理**:
- 处理完一个文件后释放内存
- 不要在内存中保存所有JSON
- 逐个写入文件

---

## 12. 输出格式

### 12.1 JSON格式化

**缩进**: 使用2个空格

**字段顺序**: 建议保持以下顺序
1. id
2. passage
3. questions
4. metadata

**数组格式**: 每个元素可以在同一行（如果短）或单独一行（如果长）

**示例**:
```json
{
  "id": "e028",
  "passage": {
    "title": "...",
    "paragraphs": [...]
  },
  "questions": [...],
  "metadata": {...}
}
```

### 12.2 文件编码

**编码格式**: UTF-8

**换行符**: LF（Unix风格）

**BOM**: 不包含BOM

### 12.3 文件命名

**单个JSON文件**: `[id].json`
- 示例: e028.json

**Chunk文件**: `[hash].json`
- 示例: a3f5b2.json

**Manifest文件**: `manifest.json`

---

## 13. 相关文档

**核心文档**:
- **脚本开发项目配置.md** - 文件路径、命名规则、输入输出规范
- **PDF转网页工作流.md** - HTML源文件结构和题型定义

**参考文档**:
- **JSON与HTML工作流对应指南.md** - HTML元素到JSON字段的映射
- **预制JSON题库方案.md** - 整体架构设计

**示例文件**:
- **demo/sample-chunk-a3f5b2.json** - 完整的chunk JSON示例
- **demo/sample-manifest.json** - manifest索引文件示例

---

## 14. 完整JSON示例

以下是一个包含三篇文章（P1/P2/P3）的chunk JSON示例，展示了7种不同题型：

```json
{
  "version": "1.0",
  "data": [
    {
      "id": "e028",
      "passage": {
        "title": "Triumph of the City",
        "paragraphs": [
          {
            "label": null,
            "content": "Triumph of the City, by Edward Glaeser, is a thrilling and very readable hymn of praise to an invention so vast and so effective that it is generally taken for granted. More than half the global population already live in urban areas and, every month, five million more flood into the cities of the developed and developing worlds."
          },
          {
            "label": null,
            "content": "This idea has had more than two hundred years of resistance. Not long after the Industrial Revolution began in Britain, the Romantic poets turned away from the smoke and factories of their cities to celebrate the air and light of untouched nature."
          },
          {
            "label": null,
            "content": "They had, Glaeser admits, a point. The early industrial cities were dirty, since they lacked efficient waste-disposal systems, and disease spread rapidly among the population. But more importantly they were profitable, and there were enormous commercial incentives to make them work, as well as political ones."
          }
        ]
      },
      "questions": [
        {
          "questionNumber": 1,
          "type": "notes-completion",
          "instruction": "Complete the notes below. Choose ONE WORD ONLY from the passage for each answer.",
          "content": {
            "sentence": "Problems with early cities: dirt, ______ but there were commercial and ______ reasons for improving them",
            "wordLimit": "ONE WORD ONLY"
          },
          "answer": "disease",
          "explanation": "The passage states 'The early industrial cities were dirty, since they lacked efficient waste-disposal systems, and disease spread rapidly among the population.'"
        },
        {
          "questionNumber": 2,
          "type": "notes-completion",
          "instruction": "Complete the notes below. Choose ONE WORD ONLY from the passage for each answer.",
          "content": {
            "sentence": "but there were commercial and ______ reasons for improving them",
            "wordLimit": "ONE WORD ONLY"
          },
          "answer": "political",
          "explanation": "The text mentions 'there were enormous commercial incentives to make them work, as well as political ones.'"
        },
        {
          "questionNumber": 9,
          "type": "true-false-ng",
          "instruction": "Do the following statements agree with the information in Reading Passage 1? Write TRUE if the statement agrees, FALSE if it contradicts, or NOT GIVEN if there is no information.",
          "content": {
            "statement": "Glaeser believes that congestion and poverty in some modern cities indicate serious problems."
          },
          "answer": "FALSE",
          "explanation": "The passage clearly states that Glaeser views congestion and poverty as 'signs of growth, energy and aspiration,' not as problems."
        },
        {
          "questionNumber": 10,
          "type": "true-false-ng",
          "instruction": "Do the following statements agree with the information in Reading Passage 1? Write TRUE if the statement agrees, FALSE if it contradicts, or NOT GIVEN if there is no information.",
          "content": {
            "statement": "The writer Henry David Thoreau discussed the ideas of the Romantic poets in his work."
          },
          "answer": "NOT GIVEN",
          "explanation": "While both Thoreau and the Romantic poets are mentioned as opposing cities, the passage does not state that Thoreau discussed their ideas."
        },
        {
          "questionNumber": 13,
          "type": "true-false-ng",
          "instruction": "Do the following statements agree with the information in Reading Passage 1? Write TRUE if the statement agrees, FALSE if it contradicts, or NOT GIVEN if there is no information.",
          "content": {
            "statement": "Glaeser argues that the location of commercial development at La Défense was a bad idea."
          },
          "answer": "TRUE",
          "explanation": "The passage states that Glaeser 'argues that in the 1950s the French made a mistake in establishing a huge high-rise commercial development — La Défense — on the outskirts of the city.'"
        }
      ],
      "metadata": {
        "difficulty": 1,
        "totalQuestions": 13,
        "questionTypes": ["notes-completion", "true-false-ng"]
      }
    },
    {
      "id": "e056",
      "passage": {
        "title": "The Return of Monkey Life",
        "paragraphs": [
          {
            "label": "A",
            "content": "Hacienda La Pacifica, a remote working cattle ranch in Guanacaste Province of northern Costa Rica, has for decades been home to a community of mantled howler monkeys."
          },
          {
            "label": "B",
            "content": "Other native primates—white-faced capuchin monkeys and spider monkeys—were once common in this area too, but vanished after the Pan-American Highway was built nearby in the 1950s."
          },
          {
            "label": "C",
            "content": "Howlers persist at La Pacifica, Glander explains, because they are leaf-eaters. They eat fruit when it is available but, unlike capuchin and spider monkeys, do not depend on large areas of fruiting trees."
          }
        ]
      },
      "questions": [
        {
          "questionNumber": 14,
          "type": "paragraph-matching",
          "instruction": "Reading Passage 2 has seven paragraphs, A-G. Which paragraph contains the following information? Write the correct letter, A-G. NB You may use any letter more than once.",
          "content": {
            "statement": "a reason why newer forests provide howlers with better feeding opportunities than older forests",
            "canReuse": true
          },
          "answer": "C",
          "explanation": "Paragraph C explains that younger forests produce lower levels of toxins: 'In younger forests, trees put most of their limited energy into growing wood, leaves and fruit, so they produce much lower levels of toxin than do well-established, old-growth trees.'"
        },
        {
          "questionNumber": 15,
          "type": "paragraph-matching",
          "instruction": "Reading Passage 2 has seven paragraphs, A-G. Which paragraph contains the following information? Write the correct letter, A-G. NB You may use any letter more than once.",
          "content": {
            "statement": "a reference to howler monkeys using a particular call at different times of the day",
            "canReuse": true
          },
          "answer": "G",
          "explanation": "Paragraph G mentions that howler monkeys use their distinctive call both at dawn and dusk to mark their territory."
        },
        {
          "questionNumber": 20,
          "type": "summary-completion",
          "instruction": "Complete the summary below. Choose ONE WORD ONLY from the passage for each answer.",
          "content": {
            "sentence": "Howler monkeys have a more rapid rate of ______ than either capuchin or spider monkeys.",
            "wordLimit": "ONE WORD ONLY"
          },
          "answer": "reproduction",
          "explanation": "Paragraph E states that howlers reproduce faster than capuchins and spider monkeys: 'Howler reproduction is faster than that of other native monkey species.'"
        },
        {
          "questionNumber": 24,
          "type": "feature-matching",
          "instruction": "Look at the following features (Questions 24-26) and the list of locations below. Match each feature with the correct location, A, B or C. NB You may use any letter more than once.",
          "content": {
            "feature": "trees planted for shade",
            "locationsList": [
              {"label": "A", "text": "Hacienda La Pacifica"},
              {"label": "B", "text": "Santa Rosa National Park"},
              {"label": "C", "text": "Cholula Cacao Farm"}
            ],
            "canReuse": true
          },
          "answer": "C",
          "explanation": "The passage states that at Cholula Cacao Farm: 'Cacao plants need shade to grow, so 40 years ago the owners planted figs, monkey-pod and other tall trees to form a protective canopy over their crop.'"
        }
      ],
      "metadata": {
        "difficulty": 2,
        "totalQuestions": 13,
        "questionTypes": ["paragraph-matching", "summary-completion", "feature-matching"]
      }
    },
    {
      "id": "e099",
      "passage": {
        "title": "The Voynich Manuscript",
        "paragraphs": [
          {
            "label": null,
            "content": "The starkly modern Beinecke Library at Yale University is home to some of the most valuable books in the world: first folios of Shakespeare, Gutenberg Bibles and manuscripts from the early Middle Ages."
          }
        ]
      },
      "questions": [
        {
          "questionNumber": 27,
          "type": "true-false-ng",
          "instruction": "Do the following statements agree with the information given in Reading Passage 3? Write TRUE if the statement agrees, FALSE if it contradicts, or NOT GIVEN if there is no information.",
          "content": {
            "statement": "It is uncertain when the Voynich manuscript was written."
          },
          "answer": "TRUE",
          "explanation": "The passage describes the manuscript as having 'unknown age and authorship', confirming the uncertainty about when it was written."
        },
        {
          "questionNumber": 31,
          "type": "statement-matching",
          "instruction": "Look at the following statements (Questions 31-34) and the list of people below. Match each statement with the correct person, A-H.",
          "content": {
            "statement": "The number of times that some words occur makes it unlikely that the manuscript is based on an authentic language.",
            "peopleList": [
              {"label": "A", "text": "Gordon Rugg"},
              {"label": "B", "text": "Roger Bacon"},
              {"label": "C", "text": "William Newbold"},
              {"label": "D", "text": "William Friedman"},
              {"label": "E", "text": "Rob Churchill"},
              {"label": "F", "text": "Gabriel Landini"},
              {"label": "G", "text": "René Zandbergen"},
              {"label": "H", "text": "Girolamo Cardano"}
            ],
            "canReuse": false
          },
          "answer": "D",
          "explanation": "William Friedman discovered that 'some words and phrases appeared more often than expected in a standard language, casting doubt on claims that the manuscript concealed a real language.'"
        },
        {
          "questionNumber": 35,
          "type": "summary-completion",
          "instruction": "Complete the summary below. Choose NO MORE THAN TWO WORDS from the passage for each answer.",
          "content": {
            "sentence": "William Newbold believed that the author of the Voynich manuscript had been able to look at cells through a ______.",
            "wordLimit": "NO MORE THAN TWO WORDS"
          },
          "answer": "microscope",
          "explanation": "The passage states: 'According to Newbold, the manuscript proved that Bacon had access to a microscope centuries before they were supposedly first invented.'"
        },
        {
          "questionNumber": 40,
          "type": "multiple-choice-single",
          "instruction": "Choose the correct letter, A, B, C or D.",
          "content": {
            "questionText": "The writer's main aim in this passage is to",
            "options": [
              {"label": "A", "text": "explain the meaning of the manuscript."},
              {"label": "B", "text": "determine the true identity of the manuscript's author."},
              {"label": "C", "text": "describe the numerous attempts to decode the manuscript."},
              {"label": "D", "text": "identify which research into the manuscript has had the most media coverage."}
            ]
          },
          "answer": "C",
          "explanation": "The passage focuses on describing various researchers' attempts to decode the Voynich manuscript throughout history, from Voynich himself to Newbold, Friedman, Landini, Zandbergen, and Rugg."
        }
      ],
      "metadata": {
        "difficulty": 3,
        "totalQuestions": 14,
        "questionTypes": ["true-false-ng", "statement-matching", "summary-completion", "multiple-choice-single"]
      }
    }
  ]
}
```
