const state = {
  particles: [],
  templateIndex: 0,
};

const templates = {
  resume:
    "我想做一个 AI 简历教练，能根据岗位要求分析简历差距，重写项目亮点，生成面试问题，并提醒哪些表述可能有风险。",
  customer:
    "我想做一个企业客服助手，能根据公司知识库回答客户问题，给客服人员生成回复建议，并在涉及隐私或投诉时提醒人工处理。",
  learning:
    "我想做一个 AI 学习顾问，能根据课程资料回答问题，推荐学习路线，记录学习进度，并提醒用户下一步应该学什么。",
  review:
    "我想做一个 AI 代码评审助手，能阅读项目规范和代码变更，指出潜在风险，生成测试建议，并输出清晰的评审结论。",
};

const canvas = document.querySelector("#flow-canvas");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
  canvas.width = window.innerWidth * window.devicePixelRatio;
  canvas.height = window.innerHeight * window.devicePixelRatio;
  ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
}

function seedParticles() {
  state.particles = Array.from({ length: 70 }, (_, index) => ({
    x: Math.random() * window.innerWidth,
    y: Math.random() * window.innerHeight,
    speed: 0.35 + Math.random() * 0.9,
    size: 1 + Math.random() * 2,
    lane: index % 3,
  }));
}

function drawFlow() {
  ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
  for (const point of state.particles) {
    point.x += point.speed;
    if (point.x > window.innerWidth + 40) {
      point.x = -40;
      point.y = Math.random() * window.innerHeight;
    }

    const color = point.lane === 0 ? "31, 111, 235" : point.lane === 1 ? "0, 143, 140" : "36, 138, 61";
    ctx.beginPath();
    ctx.strokeStyle = `rgba(${color}, 0.12)`;
    ctx.moveTo(point.x - 64, point.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.fillStyle = `rgba(${color}, 0.32)`;
    ctx.arc(point.x, point.y, point.size, 0, Math.PI * 2);
    ctx.fill();
  }
  requestAnimationFrame(drawFlow);
}

function getPayload() {
  return {
    goal: document.querySelector("#goal").value.trim(),
    persona: document.querySelector("#persona").value,
    top_k: Number(document.querySelector("#top-k").value),
    temperature: Number(document.querySelector("#temperature").value),
    strict_grounding: document.querySelector("#strict").checked,
    risk_mode: document.querySelector("#risk-mode").value,
  };
}

async function fetchStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    const stateLabel = document.querySelector("#llm-state");
    stateLabel.textContent = data.llm_enabled
      ? `AI 模型：已接入 ${data.llm_model}`
      : "AI 模型：未配置 Key，使用本地演示模式";
  } catch (error) {
    document.querySelector("#llm-state").textContent = "AI 模型：状态获取失败";
  }
}

function setRunning(isRunning) {
  document.querySelector("#run-btn").disabled = isRunning;
  document.querySelector("#run-state").textContent = isRunning ? "生成中" : "已完成";
}

function animateSteps(steps = []) {
  const nodes = [...document.querySelectorAll(".step")];
  nodes.forEach((node) => node.classList.remove("active", "done"));
  nodes.forEach((node, index) => {
    setTimeout(() => {
      nodes.forEach((item) => item.classList.remove("active"));
      node.classList.add("active");
      nodes.slice(0, index).forEach((item) => item.classList.add("done"));
      if (index === nodes.length - 1) node.classList.add("done");
    }, index * 260);
  });

  if (!steps.length) return;
}

function typeText(target, text) {
  target.textContent = "";
  let index = 0;
  const timer = setInterval(() => {
    target.textContent += text[index] || "";
    index += 1;
    if (index >= text.length) clearInterval(timer);
  }, 10);
}

function renderPlan(items) {
  const list = document.querySelector("#action-plan");
  list.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderMetrics(evaluation) {
  const rows = [
    ["依据充分", evaluation.groundedness],
    ["回答相关", evaluation.relevance],
    ["覆盖完整", evaluation.coverage],
    ["风险较低", Math.max(0, 100 - evaluation.risk)],
  ];

  document.querySelector("#metrics").innerHTML = rows
    .map(
      ([label, value]) => `
        <div>
          <em>${label}</em>
          <span style="--value:${value}%"></span>
          <b>${value}</b>
        </div>
      `,
    )
    .join("");
}

function renderGuardrails(items) {
  const labels = {
    pass: "通过",
    warning: "提醒",
    critical: "高风险",
  };
  document.querySelector("#guardrails").innerHTML = items
    .map(
      (item) => `
        <li class="${item.level}">
          <strong>${labels[item.level] || "提醒"}：${item.title}</strong>
          <span>${item.detail}</span>
        </li>
      `,
    )
    .join("");
}

function renderSources(sources) {
  const box = document.querySelector("#sources");
  if (!sources.length) {
    box.innerHTML = '<p class="muted">暂时没有找到可参考的资料，你可以在左下角补充资料后再生成。</p>';
    return;
  }

  box.innerHTML = sources
    .slice(0, 4)
    .map(
      (source) => `
        <article class="source-card">
          <header>
            <b>${source.title}</b>
            <span>${Math.round(source.score * 100)}%</span>
          </header>
          <p>${source.snippet}</p>
        </article>
      `,
    )
    .join("");
}

async function runWorkflow() {
  const payload = getPayload();
  if (!payload.goal) {
    document.querySelector("#answer").textContent = "请先写下你的需求，再点击生成。";
    return;
  }

  setRunning(true);
  animateSteps();

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    animateSteps(data.agents);
    typeText(document.querySelector("#answer"), data.answer);
    renderPlan(data.action_plan);
    renderMetrics(data.evaluation);
    renderGuardrails(data.guardrails);
    renderSources(data.sources);
  } catch (error) {
    document.querySelector("#answer").textContent = "生成失败，请确认后端服务已经启动。";
  } finally {
    setTimeout(() => setRunning(false), 1200);
  }
}

async function addKnowledge() {
  const title = document.querySelector("#doc-title").value.trim();
  const content = document.querySelector("#doc-content").value.trim();
  const tags = document
    .querySelector("#doc-tags")
    .value.split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  const label = document.querySelector("#knowledge-state");
  if (!title || content.length < 20) {
    label.textContent = "请填写标题，并至少输入 20 个字的资料内容。";
    return;
  }

  label.textContent = "正在加入资料...";
  const response = await fetch("/api/knowledge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content, tags }),
  });
  const data = await response.json();
  label.textContent = `已加入 ${data.documents} 份资料，后续生成会参考这些内容。`;
}

function chooseTemplate(key) {
  document.querySelector("#goal").value = templates[key];
  document.querySelectorAll(".template").forEach((button) => {
    button.classList.toggle("active", button.dataset.template === key);
  });
}

function rotateTemplate() {
  const keys = Object.keys(templates);
  state.templateIndex = (state.templateIndex + 1) % keys.length;
  chooseTemplate(keys[state.templateIndex]);
}

function bindEvents() {
  document.querySelector("#run-btn").addEventListener("click", runWorkflow);
  document.querySelector("#sample-btn").addEventListener("click", rotateTemplate);
  document.querySelector("#add-knowledge-btn").addEventListener("click", addKnowledge);
  document.querySelector("#top-k").addEventListener("input", (event) => {
    document.querySelector("#top-k-value").textContent = event.target.value;
  });
  document.querySelectorAll(".template").forEach((button) => {
    button.addEventListener("click", () => chooseTemplate(button.dataset.template));
  });
}

window.addEventListener("resize", () => {
  resizeCanvas();
  seedParticles();
});

resizeCanvas();
seedParticles();
drawFlow();
bindEvents();
fetchStatus();
