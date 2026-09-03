/**
 * 品牌识别 + 自动适配 logo 工具
 *
 * 与 components/ProviderLogo.vue 共用同一套 BRANDS 与 detectBrandKey 逻辑，
 * 此处独立复制以供保存前的自动拉取场景使用（无需组件实例即可判断）。
 */

// 与 ProviderLogo.vue 中 BRANDS 保持同步
export const BRANDS = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  claude: 'Claude',
  deepseek: 'DeepSeek',
  kimi: 'Kimi',
  qwen: 'Qwen',
  gemini: 'Gemini',
  mistral: 'Mistral',
  baidu: 'Baidu',
  openrouter: 'OpenRouter',
  minimax: 'MiniMax',
  ollama: 'Ollama',
  xiaomi: 'Xiaomi',
  sub2api: 'Sub2API',
  agnes: 'Agnes',
  zhipu: 'Zhipu',
  sensetime: 'SenseTime',
  grok: 'Grok',
  hunyuan: 'Hunyuan',
  doubao: 'Doubao',
  poolside: 'Poolside',
  nemotron: 'Nemotron',
  oxalpha: 'OxAlpha',
  stepfun: 'StepFun',
  meituan: 'Meituan',
  generic: 'Generic',
}

export function detectBrandKey(provider, apiBase, modelName) {
  const base = `${provider || ''} ${apiBase || ''}`.toLowerCase()
  if (base.includes('sub2api')) return 'sub2api'
  if (base.includes('agnes')) return 'agnes'
  if (base.includes('openrouter')) return 'openrouter'
  if (base.includes('sensetime') || base.includes('sensenova') || base.includes('商汤')) return 'sensetime'
  if (base.includes('kimi') || base.includes('moonshot')) return 'kimi'
  if (base.includes('deepseek')) return 'deepseek'
  if (base.includes('glm') || base.includes('zhipu') || base.includes('bigmodel') || base.includes('chatglm')) return 'zhipu'
  if (base.includes('dashscope') || base.includes('tongyi')) return 'qwen'
  if (base.includes('generativelanguage')) return 'gemini'
  if (base.includes('x.ai')) return 'grok'
  if (base.includes('mistral')) return 'mistral'
  if (base.includes('ernie') || base.includes('wenxin') || base.includes('baidu')) return 'baidu'
  if (base.includes('minimax')) return 'minimax'
  if (base.includes('xiaomi') || base.includes('milm') || base.includes('mimo')) return 'xiaomi'
  if (base.includes('ollama') || base.includes('localhost') || base.includes('127.0.0.1')) return 'ollama'
  if (base.includes('hunyuan')) return 'hunyuan'
  if (base.includes('doubao') || base.includes('volc')) return 'doubao'
  if (base.includes('poolside')) return 'poolside'
  if (base.includes('nemotron') || base.includes('nvidia')) return 'nemotron'
  if (base.includes('stepfun') || base.includes('step-') || base.includes('阶跃')) return 'stepfun'
  if (base.includes('meituan') || base.includes('美团') || base.includes('longcat')) return 'meituan'
  if (base.includes('openai') || base.includes('gpt')) return 'openai'

  const s = `${base} ${modelName || ''}`.toLowerCase()
  if (s.includes('sensetime') || s.includes('sensenova') || s.includes('sensechat')) return 'sensetime'
  if (s.includes('kimi') || s.includes('moonshot')) return 'kimi'
  if (s.includes('deepseek')) return 'deepseek'
  if (s.includes('glm') || s.includes('zhipu') || s.includes('chatglm')) return 'zhipu'
  if (s.includes('claude')) return 'claude'
  if (s.includes('anthropic')) return 'anthropic'
  if (s.includes('qwen') || s.includes('tongyi')) return 'qwen'
  if (s.includes('gemini')) return 'gemini'
  if (s.includes('grok')) return 'grok'
  if (s.includes('mistral')) return 'mistral'
  if (s.includes('ernie') || s.includes('wenxin')) return 'baidu'
  if (s.includes('minimax')) return 'minimax'
  if (s.includes('xiaomi') || s.includes('milm') || s.includes('mimo')) return 'xiaomi'
  if (s.includes('hunyuan')) return 'hunyuan'
  if (s.includes('doubao') || s.includes('volc')) return 'doubao'
  if (s.includes('poolside') || s.includes('laguna')) return 'poolside'
  if (s.includes('nemotron')) return 'nemotron'
  if (s.includes('stepfun') || s.includes('step-2') || s.includes('step-1') || s.includes('阶跃')) return 'stepfun'
  if (s.includes('meituan') || s.includes('美团')) return 'meituan'
  if (s.includes('ox-alpha') || s.includes('ox_alpha') || s.includes('oxalpha')) return 'oxalpha'
  if (s.includes('gpt') || s.includes('openai') || s.includes('o1') || s.includes('o3') || s.includes('o4')) return 'openai'
  return 'generic'
}

/**
 * 自动适配 logo URL：
 * 1. 若内置 BRANDS 命中（detectBrandKey !== 'generic'），返回空字符串，
 *    由前端组件自动渲染内置 SVG（无需远程图片）。
 * 2. 否则尝试从 api_base 域名推断厂商主机地址，抓取其 favicon / og:image 作为 logo。
 *    - 优先尝试 <host>/favicon.ico
 *    - 备选 DuckDuckGo favicon 服务 https://icons.duckduckgo.com/ip3/<host>.ico
 *
 * 返回值：可直接用作 <img src> 的 URL；拉取失败返回空字符串。
 */
export async function autoFetchLogo(provider, apiBase, modelName) {
  if (!provider && !apiBase && !modelName) return ''
  const key = detectBrandKey(provider, apiBase, modelName)
  if (key !== 'generic') return '' // 内置品牌无需远程图片

  const host = extractHost(apiBase)
  if (!host) return ''

  // 直接走 DuckDuckGo favicon 服务，无需探测
  return `https://icons.duckduckgo.com/ip3/${host}.ico`
}

function extractHost(apiBase) {
  if (!apiBase) return ''
  try {
    const m = String(apiBase).match(/^(?:https?:\/\/)?([^/?#]+)/i)
    if (!m) return ''
    const host = m[1]
    // 去掉端口与子域名中的常见前缀（api.、openapi.、llm.、chat.、gateway.）
    return host.replace(/^(api|openapi|llm|chat|gateway|api-|open-api)\./i, '')
  } catch {
    return ''
  }
}