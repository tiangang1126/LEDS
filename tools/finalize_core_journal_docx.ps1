param(
    [string]$InputPath = "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1_Temperature_K5消融修订稿_图2更新版.docx",
    [string]$OutputPath = "LEDS_指挥与控制学报_李铁乔_0725_一级核心期刊投稿精修稿.docx"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression

$wordNamespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
$xmlNamespace = "http://www.w3.org/XML/1998/namespace"

function Get-ParagraphText {
    param([System.Xml.XmlNode]$Paragraph, [System.Xml.XmlNamespaceManager]$NamespaceManager)
    return (($Paragraph.SelectNodes('.//w:t', $NamespaceManager) | ForEach-Object { $_.InnerText }) -join '')
}

function Set-ParagraphText {
    param(
        [System.Xml.XmlDocument]$Document,
        [System.Xml.XmlNode]$Paragraph,
        [string]$Text,
        [System.Xml.XmlNamespaceManager]$NamespaceManager
    )
    $paragraphProperties = $Paragraph.SelectSingleNode('./w:pPr', $NamespaceManager)
    $savedProperties = if ($null -ne $paragraphProperties) { $paragraphProperties.CloneNode($true) } else { $null }
    while ($Paragraph.HasChildNodes) {
        [void]$Paragraph.RemoveChild($Paragraph.FirstChild)
    }
    if ($null -ne $savedProperties) {
        [void]$Paragraph.AppendChild($savedProperties)
    }
    $run = $Document.CreateElement('w', 'r', $wordNamespace)
    $textNode = $Document.CreateElement('w', 't', $wordNamespace)
    [void]$textNode.SetAttribute('space', $xmlNamespace, 'preserve')
    $textNode.InnerText = $Text
    [void]$run.AppendChild($textNode)
    [void]$Paragraph.AppendChild($run)
}

function New-WordTableCell {
    param(
        [System.Xml.XmlDocument]$Document,
        [string]$Text,
        [int]$Width,
        [bool]$Header = $false
    )
    $cell = $Document.CreateElement('w', 'tc', $wordNamespace)
    $cellProperties = $Document.CreateElement('w', 'tcPr', $wordNamespace)
    $cellWidth = $Document.CreateElement('w', 'tcW', $wordNamespace)
    [void]$cellWidth.SetAttribute('w', $wordNamespace, $Width.ToString())
    [void]$cellWidth.SetAttribute('type', $wordNamespace, 'dxa')
    [void]$cellProperties.AppendChild($cellWidth)
    [void]$cell.AppendChild($cellProperties)

    $paragraph = $Document.CreateElement('w', 'p', $wordNamespace)
    $paragraphProperties = $Document.CreateElement('w', 'pPr', $wordNamespace)
    $spacing = $Document.CreateElement('w', 'spacing', $wordNamespace)
    [void]$spacing.SetAttribute('before', $wordNamespace, '0')
    [void]$spacing.SetAttribute('after', $wordNamespace, '0')
    [void]$spacing.SetAttribute('line', $wordNamespace, '220')
    [void]$spacing.SetAttribute('lineRule', $wordNamespace, 'auto')
    [void]$paragraphProperties.AppendChild($spacing)
    [void]$paragraph.AppendChild($paragraphProperties)

    $run = $Document.CreateElement('w', 'r', $wordNamespace)
    $runProperties = $Document.CreateElement('w', 'rPr', $wordNamespace)
    $fontSize = $Document.CreateElement('w', 'sz', $wordNamespace)
    [void]$fontSize.SetAttribute('val', $wordNamespace, '15')
    [void]$runProperties.AppendChild($fontSize)
    $fontSizeCs = $Document.CreateElement('w', 'szCs', $wordNamespace)
    [void]$fontSizeCs.SetAttribute('val', $wordNamespace, '15')
    [void]$runProperties.AppendChild($fontSizeCs)
    if ($Header) {
        [void]$runProperties.AppendChild($Document.CreateElement('w', 'b', $wordNamespace))
    }
    [void]$run.AppendChild($runProperties)
    $textNode = $Document.CreateElement('w', 't', $wordNamespace)
    [void]$textNode.SetAttribute('space', $xmlNamespace, 'preserve')
    $textNode.InnerText = $Text
    [void]$run.AppendChild($textNode)
    [void]$paragraph.AppendChild($run)
    [void]$cell.AppendChild($paragraph)
    return $cell
}

function New-AlgorithmTable {
    param([System.Xml.XmlDocument]$Document)
    $rows = @(
        @('1', '对所有 v_i∈V：b_i←Neutral，r_i←0，d_i←0。', '初始化节点状态'),
        @('2', '对所有 (u,v)∈E、m∈{RUMOR,DEBUNK}：ν(u,v,m)←0。', '初始化访问标记'),
        @('3', 'Q_0[v_src]←{(-1,v_src,m_init)}，L←∅，t←0。', '初始化事件队列与日志'),
        @('4', 'while Q_t≠∅ 且 t<T_max do', '主循环'),
        @('5', 'Q_{t+1}←∅；A_t←{v_i∣Q_t[v_i]≠∅}。', '仅激活新增消息节点'),
        @('6', 'for each v_i∈sort(A_t,node_id) do', '确定顺序调度'),
        @('7', 'M_i^t←Q_t[v_i]；更新 r_i 与 d_i。', '读取本轮新事件'),
        @('8', 'p_i^t←ConstructPrompt(P_i,b_i,r_i,d_i,M_i^t)。', '规范化输入'),
        @('9', 'h_i^t←H(p_i^t)。', '计算 Prompt 哈希'),
        @('10', 'if h_i^t∈C then', '命中判定记录'),
        @('11', 'y_i^t←C[h_i^t]。', '回放；不访问云端'),
        @('12', 'else', ''),
        @('13', 'y_i^t←F_θ(p_i^t; Temperature=0, Top_P=1)。', '首次云端判定'),
        @('14', 'C[h_i^t]←y_i^t。', '写入判定记录'),
        @('15', 'end if', ''),
        @('16', '解析 y_i^t 得到 (b_i′,a_i^t)。', '结构化状态转移'),
        @('17', 'if 解析失败或输出越界 then', '有界容错'),
        @('18', '在固定预算内重试；耗尽后 b_i′←b_i，a_i^t←Ignore。', '失败时保持原信念'),
        @('19', 'end if；b_i←b_i′。', '更新节点信念'),
        @('20', 'if a_i^t∈{Share,Debunk} then', '生成传播动作'),
        @('21', 'm_out←RUMOR（Share）或 DEBUNK（Debunk）。', '动作映射为消息'),
        @('22', 'for each v_j∈N⁺(v_i) do', '遍历出邻居'),
        @('23', 'if ν(v_i,v_j,m_out)=0 then', '新颖事件过滤'),
        @('24', 'Q_{t+1}[v_j]←Q_{t+1}[v_j]∪{(v_i,v_j,m_out)}。', '事件入队'),
        @('25', 'ν(v_i,v_j,m_out)←1。', '三元事件至多一次'),
        @('26', 'end if；end for；end if', ''),
        @('27', 'L←L∪{(t,v_i,P_i,M_i^t,b_i,a_i^t,h_i^t)}。', '追加审计日志'),
        @('28', 'end for；t←t+1。', '推进逻辑时间'),
        @('29', 'end while', ''),
        @('30', 'ρ_T←|{v_i∈V∣b_i=Accept}|/|V|。', '计算最终渗透率'),
        @('31', 'S_T←{b_i∣v_i∈V}；return S_T,ρ_T,L。', '返回结果')
    )

    $table = $Document.CreateElement('w', 'tbl', $wordNamespace)
    $tableProperties = $Document.CreateElement('w', 'tblPr', $wordNamespace)
    $style = $Document.CreateElement('w', 'tblStyle', $wordNamespace)
    [void]$style.SetAttribute('val', $wordNamespace, 'TableGrid')
    [void]$tableProperties.AppendChild($style)
    $width = $Document.CreateElement('w', 'tblW', $wordNamespace)
    [void]$width.SetAttribute('w', $wordNamespace, '0')
    [void]$width.SetAttribute('type', $wordNamespace, 'auto')
    [void]$tableProperties.AppendChild($width)
    $layout = $Document.CreateElement('w', 'tblLayout', $wordNamespace)
    [void]$layout.SetAttribute('type', $wordNamespace, 'fixed')
    [void]$tableProperties.AppendChild($layout)
    [void]$table.AppendChild($tableProperties)

    $grid = $Document.CreateElement('w', 'tblGrid', $wordNamespace)
    foreach ($gridWidth in @(560, 4800, 1900)) {
        $column = $Document.CreateElement('w', 'gridCol', $wordNamespace)
        [void]$column.SetAttribute('w', $wordNamespace, $gridWidth.ToString())
        [void]$grid.AppendChild($column)
    }
    [void]$table.AppendChild($grid)

    $allRows = @()
    $allRows += ,@('行号', '操作', '说明')
    foreach ($dataRow in $rows) {
        $allRows += ,$dataRow
    }
    for ($rowIndex = 0; $rowIndex -lt $allRows.Count; $rowIndex++) {
        $row = $Document.CreateElement('w', 'tr', $wordNamespace)
        $rowProperties = $Document.CreateElement('w', 'trPr', $wordNamespace)
        [void]$rowProperties.AppendChild($Document.CreateElement('w', 'cantSplit', $wordNamespace))
        if ($rowIndex -eq 0) {
            [void]$rowProperties.AppendChild($Document.CreateElement('w', 'tblHeader', $wordNamespace))
        }
        [void]$row.AppendChild($rowProperties)
        [void]$row.AppendChild((New-WordTableCell -Document $Document -Text $allRows[$rowIndex][0] -Width 560 -Header ($rowIndex -eq 0)))
        [void]$row.AppendChild((New-WordTableCell -Document $Document -Text $allRows[$rowIndex][1] -Width 4800 -Header ($rowIndex -eq 0)))
        [void]$row.AppendChild((New-WordTableCell -Document $Document -Text $allRows[$rowIndex][2] -Width 1900 -Header ($rowIndex -eq 0)))
        [void]$table.AppendChild($row)
    }
    return $table
}

$inputFullPath = (Resolve-Path -LiteralPath $InputPath).Path
$outputFullPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
$sharedInput = [IO.File]::Open(
    $inputFullPath,
    [IO.FileMode]::Open,
    [IO.FileAccess]::Read,
    [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
)
$sharedBuffer = [IO.MemoryStream]::new()
try {
    $sharedInput.CopyTo($sharedBuffer)
    $inputBytes = $sharedBuffer.ToArray()
}
finally {
    $sharedBuffer.Dispose()
    $sharedInput.Dispose()
}
$inputStream = [IO.MemoryStream]::new($inputBytes, $false)
$inputArchive = [IO.Compression.ZipArchive]::new($inputStream, [IO.Compression.ZipArchiveMode]::Read, $false)

try {
    $documentEntry = $inputArchive.GetEntry('word/document.xml')
    $documentReader = [IO.StreamReader]::new($documentEntry.Open())
    try {
        $document = [xml]$documentReader.ReadToEnd()
    }
    finally {
        $documentReader.Dispose()
    }

    $namespaceManager = [Xml.XmlNamespaceManager]::new($document.NameTable)
    $namespaceManager.AddNamespace('w', $wordNamespace)

    $exactReplacements = [ordered]@{
        'LEDS：面向社会信息传播的可重放事件驱动LLM多智能体仿真协议' = 'LEDS：面向社会信息传播的可重放事件驱动LLM多智能体仿真方法'
        'LEDS: A Replayable Event-Driven LLM Multi-Agent Simulation Protocol for Social Information Diffusion' = 'LEDS: A Replayable Event-Driven LLM Multi-Agent Simulation Method for Social Information Diffusion'
        '3.3 离散事件驱动的马尔可夫状态机' = '3.3 类型化事件、状态转移与确定调度'
        '4.1 实验环境与参数设置' = '4.1 实验环境、模型标识与证据边界'
        '本文据此提出如下核心命题：LLM 社会仿真的可信复核不应仅依赖解码参数，而应由协议级可重放机制与统计级重复运行共同保证。本文提出 LEDS，并围绕该命题形成三项贡献：' = '本文据此提出如下核心命题：LLM社会仿真的可信复核不应仅依赖解码参数，而应由记录级可重放机制与运行级统计重复共同保证；经验有效性则需要独立证据支持。围绕这一主线，本文将贡献组织为“定义与建模—事件传播算法—验证与应用”三个层次。'
        '（1）提出 LLM 社交智能体仿真的双层可复现性定义与可重放事件建模方法。将社会信息传播形式化为有限状态、有限消息类型上的事件转移过程，明确区分固定判定记录条件下的轨迹可重放性、无缓存独立运行条件下的统计可复现性和面向真实社会行为的经验有效性，为云端 LLM 社会仿真实验的复核边界提供统一描述。' = '（1）定义与建模。明确区分固定判定记录条件下的记录级可重放性、无记录独立运行条件下的运行级统计可复现性，以及面向真实社会行为的经验有效性；将社会信息传播形式化为冻结有向图上的有限状态、有限消息类型事件转移系统，为云端LLM社会仿真的复核边界提供统一描述。'
        '（2）提出有序调度、新颖事件过滤和判定记录映射相结合的 LEDS 事件传播算法。算法仅调度收到新增消息的活跃节点，并对“发送节点—接收节点—消息类型”三元事件实施至多一次的传播约束；结合固定节点顺序、结构化状态转移和 Prompt/Response 记录，实现传播过程的逐事件审计，并给出轨迹唯一性、有限步终止条件与事件复杂度上界。' = '（2）事件传播算法。提出由确定顺序调度、新颖事件过滤和判定记录映射构成的LEDS事件传播算法。算法仅激活收到新增消息的节点，并约束每个“发送节点—接收节点—消息类型”三元事件至多入队一次；在此基础上给出记录条件下的轨迹唯一性、有限事件终止性和事件复杂度上界。'
        '（3）建立面向运行不确定性与记录回放一致性的双层验证方法。通过无缓存独立运行量化宏观渗透率和微观节点状态的运行间差异，通过固定记录回放检验逐节点轨迹一致性，并在不同 LLM 后端、合成网络和真实社交网络上验证方法适用性。事实核查员空间部署作为应用案例，用于说明忽略运行间不确定性可能导致不稳健的干预结论。' = '（3）验证与应用。通过受控温度敏感性实验、无记录独立运行、固定判定记录回放、跨后端对照、合成网络重复实验和真实网络迁移观察，验证LEDS的可核查性及其适用边界；以事实核查员空间部署作为应用案例，说明忽略运行间不确定性可能导致不稳健的干预结论。'
        '判别内核  通过兼容 OpenAI/DeepSeek 规范的云端 API 调用。本文全部实证数据均由真实 deepseek-chat（、Top_P = 1.0）在  主规模上产生；静态图以固定种子一次性固化，运行期不使用任何伪随机数，并采用 Prompt/Response 缓存重放。三类基线分别为：传统无语义的 Independent Cascade（固定概率转移）、Full Polling（保留 JSON 结构化输出但每步轮询全部节点，以隔离事件驱动机制的贡献）和 Monte Carlo（ 重复采样求均值，以比较方差与评估开销）。' = '实验通过兼容OpenAI/DeepSeek规范的云端API访问模型，并按“API模型标识—实验章节—温度条件—证据用途”记录对应关系。主网络实验、合成与真实网络应用及规模化开销使用deepseek-chat；4.5节方向性对照使用deepseek-reasoner；4.2.1节温度敏感性实验与4.4节K=5零温度补充探针使用deepseek-v4-flash。三者均为供应商托管的API标识，本文不宣称客户端能够冻结其服务端权重版本，也不将不同标识混称为同一模型。温度实验调用时间为2026年7月25日（UTC日志范围：08:54—21:00），K=5探针调用时间为2026年7月26日（UTC日志范围：02:17—07:52）；主实验的可核验条件以随稿结果文件、冻结配置与判定记录为准。除特别注明外，主网络实验采用Temperature=0、Top_P=1.0。'
        '为直接回应“Temperature=0 会不会影响 LLM 效果”的问题，本文在完整网络仿真之外构造受控 Prompt 级温度消融实验。实验固定 System Prompt、User Prompt 模板、三类人设规则、输出 JSON Schema、Top_P=1.0、解析规则和模型后端，仅改变 Temperature。Prompt 池共240条，按易感者、中立者和核查员三类人设各80条分层构造，覆盖当前信念状态、谣言来源数、辟谣来源数和新增消息类型等主要状态转移边界。每个 Prompt 在 Temperature∈{0,0.2,0.5,0.7} 下独立调用3次，共获得2880条真实 DeepSeek API 输出。规则参照由附录A中的三类人设状态转移规则生成，评价指标包括联合规则一致率、stance一致率、action一致率、JSON合法率和同一Prompt三次重复的输出不一致率。' = '为回应“Temperature=0是否影响LLM效果”的问题，本文在完整网络仿真之外构造受控Prompt级温度敏感性实验。实验固定System Prompt、User Prompt模板、三类人设规则、输出JSON Schema、Top_P=1.0、解析规则和deepseek-v4-flash API标识，仅改变Temperature∈{0,0.2,0.5,0.7}。Prompt池共240条，三类人设各80条，覆盖当前信念、谣言来源数、辟谣来源数和新增消息类型等主要状态转移边界。每个Prompt在每个温度下独立调用3次，共获得2880条真实API输出。该实验与deepseek-chat主网络实验使用不同API标识，因此仅作为另一DeepSeek后端上的补充敏感性证据，不为deepseek-chat或一般LLM性能背书。'
        '补充表1给出总体温度消融结果。四个温度下 JSON 合法率均为100%，说明在本文的受约束状态转移任务中，结构化输出约束能够稳定发挥作用。联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，点估计差异小于0.6个百分点；以T=0为基准的差值置信区间分别为T=0.2的[-4.71,4.99]、T=0.5的[-5.27,4.44]和T=0.7的[-4.99,4.71]个百分点。由于置信区间下界未完全落在-3个百分点非劣效界限之上，本文不作严格非劣效断言；但描述性结果未显示T=0相对于更高温度存在规则执行质量下降。' = '补充表1给出总体温度敏感性结果。四个温度下JSON合法率均为100%，联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，点估计最大差异小于0.6个百分点。以T=0为基准，T=0.2、0.5和0.7的差值置信区间分别为[-4.71,4.99]、[-5.27,4.44]和[-4.99,4.71]个百分点。由于置信区间下界未完全高于预设的-3个百分点非劣效界限，本文不作严格非劣效断言。现有证据只支持如下有限结论：在deepseek-v4-flash后端、所测试Prompt池和本文结构化状态转移任务中，未观察到T=0相较更高温度的描述性质量劣化；该结论不能外推到开放式生成、其他模型或deepseek-chat主网络实验。'
        '该补充实验对本文结论形成两点修正。第一，对于本文的结构化状态转移任务，未观察到T=0相较T=0.2、0.5和0.7造成判定质量劣化；因此，主实验使用T=0作为控制显式采样噪声的条件是合理的。第二，T=0并不意味着云端 LLM 输出完全确定：在240个Prompt中仍有16个在三次独立调用中出现不同结构化判定，不一致率为6.67%。因此，LEDS 的可复现性不能建立在“零温度即确定”的假设上，而必须建立在固定判定记录、确定顺序调度、新颖事件过滤和轨迹回放之上。' = '该补充实验形成三点认识。第一，在deepseek-v4-flash后端和本文结构化状态转移任务中，未观察到T=0的描述性质量劣化，但现有样本不足以证明严格非劣性。第二，T=0下仍有16个Prompt在三次独立调用中出现不同结构化判定，不一致率为6.67%，说明零温度不等同于物理级确定性。第三，联合规则一致率仅约67%，且核查员约80%、易感者和中立者约60%～62%，揭示出约三分之一的规则偏离：LLM并非人设规则的无偏执行器。LEDS保证的是模型偏差可记录、可度量、可审计与可回放，而不是消除模型偏差。'
        '在未配置 API Key 时，src/stage2_engine.py 的 _mock_decide 以纯 if/else 规则复现上述三类人设的判定逻辑：易感者收到谣言即 Accept/Share、收到辟谣即纠偏；中立者需 ≥4 个不同邻居的谣言才转变；核查员恒 Reject 且收到谣言即 Debunk。其输入输出签名与真实 LLM 判别器完全一致，供离线链路验证之用。本文正文报告的主仿真实证数据由真实 LLM（deepseek-chat，Temperature=0 或表中注明条件）产生；针对专家意见新增的 Temperature 敏感性实验使用公共 DeepSeek API 当前支持的 deepseek-v4-flash 后端，在同一 Prompt 池上获得2880条真实 API 输出。mock 数据仅用于链路校验，不进入正文统计结论。' = '在未配置API Key时，src/stage2_engine.py中的_mock_decide以确定性if/else规则复现三类人设的判定逻辑，仅用于离线链路验证，不进入正文统计结论。真实API证据按模型标识分开报告：deepseek-chat用于主网络实验、应用分析与规模化开销；deepseek-reasoner仅用于4.5节跨后端方向性对照；deepseek-v4-flash用于4.2.1节温度敏感性实验和4.4节K=5零温度补充探针。不同API标识的结果不混合统计，也不相互替代背书。温度实验和K=5探针的请求时间、端点、Temperature、Top_P、配置哈希与逐次输出均保存在随稿日志中。'
    }

    $containsReplacements = @(
        @('摘  要  针对云端LLM社会仿真难以复核的问题', '摘  要  针对云端LLM社会仿真难以复核的问题，提出可重放事件驱动方法LEDS。该方法将传播建模为有限类型事件转移过程，以确定顺序调度、新颖事件过滤和判定记录映射实现逐事件审计与轨迹回放。作为独立补充证据，deepseek-v4-flash温度敏感性实验在240个分层Prompt、4个温度和3次重复下获得2880条真实API输出：JSON合法率均为100%，联合规则一致率为66.81%～67.36%，但差值置信区间未满足预设非劣效界限，故仅能说明在所测试后端和结构化任务中未观察到T=0的描述性质量劣化；T=0下仍有6.67%的Prompt出现重复调用不一致。K=5零温度探针进一步显示，deepseek-v4-flash后端下最终渗透率均值为55.933%，Student-t 95% CI为[55.587%,56.280%]，5次最终状态哈希均不同；固定判定记录后的3次回放均为云端零调用、节点Hamming距离为0，final state hash与trace hash完全一致。结果表明，LLM社会仿真应区分记录级可重放性、运行级统计可复现性与经验有效性，LEDS保证偏差可记录、可审计和可回放，而非消除模型偏差。'),
        @('引用格式  作者姓名1, 作者姓名2. LEDS：面向社会信息传播的可重放事件驱动LLM多智能体仿真协议', '引用格式  作者姓名1, 作者姓名2. LEDS：面向社会信息传播的可重放事件驱动LLM多智能体仿真方法[J]. 指挥与控制学报, 年, 卷(期): 页码'),
        @('Abstract  A replayable event-driven protocol, LEDS, is proposed', 'Abstract  A replayable event-driven method, LEDS, is proposed for auditable cloud-LLM social simulation. LEDS models diffusion as finite typed events and combines deterministic scheduling, novelty filtering, and decision-record mapping. An independent deepseek-v4-flash temperature study obtains 2,880 API outputs from 240 stratified prompts, four temperatures, and three repeats. Joint rule consistency ranges from 66.81% to 67.36%, but the confidence intervals do not establish non-inferiority; the evidence therefore supports only that no descriptive degradation at T=0 was observed for the tested backend and structured task. Moreover, 6.67% of prompts remain inconsistent across repeated zero-temperature calls. A K=5 zero-temperature probe yields a mean penetration of 55.933% (Student-t 95% CI [55.587%, 56.280%]) with five distinct final-state hashes, whereas three decision-record replays invoke no cloud calls and exactly reproduce node states, final-state hashes, and trace hashes. These results separate record-level replayability, run-level statistical reproducibility, and empirical validity; LEDS makes model deviations recordable, auditable, and replayable rather than eliminating them.'),
        @('Citation  AUTHOR 1, AUTHOR 2. LEDS: A replayable event-driven LLM multi-agent simulation protocol', 'Citation  AUTHOR 1, AUTHOR 2. LEDS: A replayable event-driven LLM multi-agent simulation method for social information diffusion[J]. Journal of Command and Control, year, volume(issue): pages'),
        @('2025 年以后，研究进一步转向专门的扩散系统与验证框架。', '2025 年以后，研究进一步转向专门的扩散系统与验证框架。LLM-AIDSim 将 LLM 决策引入社会网络影响扩散 [10]；Larooij 和 Törnberg 的批判性综述将 validation 明确为生成式社会仿真的中心挑战 [11]。截至 2026 年，最新 LLM 综述也把智能体化、工具化与可靠性治理列为重要发展方向 [16]。与上述工作相比，LEDS 不追求更自由的对话生成，而聚焦一个较窄但可检验的问题：当云端判定内核无法由实验者完全冻结时，如何把自然语言状态转移组织为有限事件算法，并同时获得逐事件回放能力和运行间不确定性估计。事实核查员空间部署仅作为验证方法价值的应用案例，不与可重放事件算法并列为独立目标。'),
        @('Temperature=0 是控制显式采样噪声的实验条件', 'Temperature=0是减少显式采样扰动的实验条件，不是LEDS实现可重放性的充分条件。4.2.1节的deepseek-v4-flash补充实验与deepseek-chat主网络实验使用不同API标识，故其结论严格限定为：在所测试后端、Prompt池和本文结构化状态转移任务中，未观察到T=0相较更高温度的描述性质量劣化；现有样本不足以证明严格非劣性，也不能外推到开放式生成、其他模型或deepseek-chat主实验。T=0下仍有6.67%的Prompt在三次调用中出现不同判定，进一步说明零温度不等同于确定性，记录级可重放仍须由判定记录映射和轨迹回放保证。'),
        @('本章围绕一个补充敏感性检验和两个主体实验板块展开。', '本章按“参数合理性—核心机制验证—应用分析”组织。4.2.1节以独立Prompt池检验零温度是否降低本文结构化状态转移任务的判定质量；4.3至4.5节验证评估开销、运行间非确定性、判定记录回放一致性与跨后端适用性；4.6至4.8节将事实核查员部署作为应用案例，展示重复运行、区间估计和逐事件审计的必要性。'),
        @('本文提出面向社会信息传播的可重放事件驱动仿真协议 LEDS。', '本文提出面向社会信息传播的可重放事件驱动LLM多智能体仿真方法LEDS，并将贡献统一为“定义与建模—事件传播算法—验证与应用”三个层次。LEDS把传播形式化为冻结有向图上的有限类型事件转移过程，通过确定顺序调度、新颖事件过滤和判定记录映射，给出记录条件下的轨迹唯一性、有限事件终止性和事件复杂度上界。关于Temperature=0，补充实验只支持一项有限结论：在deepseek-v4-flash后端、所测试Prompt池和本文结构化状态转移任务中，未观察到T=0相较更高温度的描述性质量劣化；由于差值置信区间未满足预设非劣效界限，本文不作严格非劣效断言，也不将结果外推到开放式生成、其他模型或deepseek-chat主实验。T=0下仍有6.67%的Prompt出现重复调用不一致，且联合规则一致率仅约67%，说明LLM不是人设规则的无偏执行器。K=5零温度探针中，5次最终状态哈希均不同；固定判定记录后的3次回放则实现云端零调用、节点Hamming距离为0、final state hash与trace hash完全一致。LEDS保证的是偏差可记录、可度量、可审计与可回放，而不是消除模型偏差。事件驱动机制将判定次数由2,400次降至701次，并在不同规模下实现2.5～4.8倍的判定次数削减。')
    )

    $changed = 0
    $paragraphs = @($document.SelectNodes('//w:p', $namespaceManager))
    foreach ($paragraph in $paragraphs) {
        $text = Get-ParagraphText -Paragraph $paragraph -NamespaceManager $namespaceManager
        if ($exactReplacements.Contains($text)) {
            Set-ParagraphText -Document $document -Paragraph $paragraph -Text $exactReplacements[$text] -NamespaceManager $namespaceManager
            $changed++
            continue
        }
        foreach ($replacement in $containsReplacements) {
            if ($text.StartsWith($replacement[0])) {
                Set-ParagraphText -Document $document -Paragraph $paragraph -Text $replacement[1] -NamespaceManager $namespaceManager
                $changed++
                break
            }
        }
    }

    $paragraphs = @($document.SelectNodes('//w:p', $namespaceManager))
    foreach ($paragraph in $paragraphs) {
        $text = Get-ParagraphText -Paragraph $paragraph -NamespaceManager $namespaceManager
        if ($text.StartsWith('针对全连接网络带来的计算开销激增问题') -or
            $text.StartsWith('Si,t+1,Ai,t+1=fLLM') -or
            $text.StartsWith('内部信念状态 S 和三元动作')) {
            [void]$paragraph.ParentNode.RemoveChild($paragraph)
            $changed++
        }
    }

    $paragraphs = @($document.SelectNodes('//w:p', $namespaceManager))
    $algorithmStart = $null
    $algorithmEnd = $null
    foreach ($paragraph in $paragraphs) {
        $text = Get-ParagraphText -Paragraph $paragraph -NamespaceManager $namespaceManager
        if ($text.StartsWith('1:  对所有节点')) { $algorithmStart = $paragraph }
        if ($text.StartsWith('34:  return')) { $algorithmEnd = $paragraph }
    }
    if ($null -ne $algorithmStart -and $null -ne $algorithmEnd) {
        $parent = $algorithmStart.ParentNode
        $algorithmTable = New-AlgorithmTable -Document $document
        [void]$parent.InsertBefore($algorithmTable, $algorithmStart)
        $current = $algorithmStart
        while ($null -ne $current) {
            $next = $current.NextSibling
            [void]$parent.RemoveChild($current)
            if ($current -eq $algorithmEnd) { break }
            $current = $next
        }
        $changed++
    }

    foreach ($table in @($document.SelectNodes('//w:tbl', $namespaceManager))) {
        $tableText = (($table.SelectNodes('.//w:t', $namespaceManager) | ForEach-Object { $_.InnerText }) -join '')
        if ($tableText -notmatch 'Temperature' -or $tableText -notmatch '一致率') {
            continue
        }
        $rows = @($table.SelectNodes('./w:tr', $namespaceManager))
        for ($rowIndex = 0; $rowIndex -lt $rows.Count; $rowIndex++) {
            $rowProperties = $rows[$rowIndex].SelectSingleNode('./w:trPr', $namespaceManager)
            if ($null -eq $rowProperties) {
                $rowProperties = $document.CreateElement('w', 'trPr', $wordNamespace)
                [void]$rows[$rowIndex].PrependChild($rowProperties)
            }
            if ($null -eq $rowProperties.SelectSingleNode('./w:cantSplit', $namespaceManager)) {
                [void]$rowProperties.AppendChild($document.CreateElement('w', 'cantSplit', $wordNamespace))
            }
            if ($rowIndex -eq 0 -and $null -eq $rowProperties.SelectSingleNode('./w:tblHeader', $namespaceManager)) {
                [void]$rowProperties.AppendChild($document.CreateElement('w', 'tblHeader', $wordNamespace))
            }
        }
        foreach ($run in @($table.SelectNodes('.//w:r', $namespaceManager))) {
            $runProperties = $run.SelectSingleNode('./w:rPr', $namespaceManager)
            if ($null -eq $runProperties) {
                $runProperties = $document.CreateElement('w', 'rPr', $wordNamespace)
                [void]$run.PrependChild($runProperties)
            }
            foreach ($oldSize in @($runProperties.SelectNodes('./w:sz|./w:szCs', $namespaceManager))) {
                [void]$runProperties.RemoveChild($oldSize)
            }
            $fontSize = $document.CreateElement('w', 'sz', $wordNamespace)
            [void]$fontSize.SetAttribute('val', $wordNamespace, '14')
            [void]$runProperties.AppendChild($fontSize)
            $fontSizeCs = $document.CreateElement('w', 'szCs', $wordNamespace)
            [void]$fontSizeCs.SetAttribute('val', $wordNamespace, '14')
            [void]$runProperties.AppendChild($fontSizeCs)
        }
        $changed++
    }

    $outputStream = [IO.MemoryStream]::new()
    $outputArchive = [IO.Compression.ZipArchive]::new($outputStream, [IO.Compression.ZipArchiveMode]::Create, $true)
    try {
        foreach ($entry in $inputArchive.Entries) {
            $newEntry = $outputArchive.CreateEntry($entry.FullName, [IO.Compression.CompressionLevel]::Optimal)
            $destination = $newEntry.Open()
            try {
                if ($entry.FullName -eq 'word/document.xml') {
                    $settings = [Xml.XmlWriterSettings]::new()
                    $settings.Encoding = [Text.UTF8Encoding]::new($false)
                    $settings.Indent = $false
                    $writer = [Xml.XmlWriter]::Create($destination, $settings)
                    try { $document.Save($writer) } finally { $writer.Dispose() }
                }
                else {
                    $source = $entry.Open()
                    try { $source.CopyTo($destination) } finally { $source.Dispose() }
                }
            }
            finally {
                $destination.Dispose()
            }
        }
    }
    finally {
        $outputArchive.Dispose()
    }
    [IO.File]::WriteAllBytes($outputFullPath, $outputStream.ToArray())
    $outputStream.Dispose()
    Write-Output "output=$outputFullPath"
    Write-Output "changes=$changed"
}
finally {
    $inputArchive.Dispose()
    $inputStream.Dispose()
}
