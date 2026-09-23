// 生成宠物预览页：从各 pet 组件提取 template + scoped style，包裹 .ai-pet 容器，
// 复用 pet-moods.css 表情系统样式，渲染 normal / working 两行供截图检查。
// 参数：--only=Bunny,Cat（只渲染指定宠物） --scale=5（放大倍数，默认2.8） --cols=3（每行个数，默认5）
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..')
const args = process.argv.slice(2)
const opt = {}
for (const a of args) {
  const m = a.match(/^--(\w+)=(.+)$/)
  if (m) opt[m[1]] = m[2]
}
const allPets = ['Cat', 'Bunny', 'Bear', 'Fox', 'Panda', 'Pig', 'Frog', 'Koala', 'Chick']
const pets = opt.only ? opt.only.split(',').map(s => s.trim()).filter(s => allPets.includes(s)) : allPets
const scale = parseFloat(opt.scale || '2.8')
const cols = parseInt(opt.cols || '5', 10)

function extract(file) {
  const src = fs.readFileSync(file, 'utf8')
  const tpl = src.match(/<template>([\s\S]*?)<\/template>/)[1]
  const style = src.match(/<style scoped>([\s\S]*?)<\/style>/)[1]
  return { tpl, style }
}

const moodCss = fs.readFileSync(path.join(ROOT, 'src/styles/pet-moods.css'), 'utf8')
const furCss = fs.readFileSync(path.join(ROOT, 'src/styles/pet-fur.css'), 'utf8')

let cells = ''
let styles = ''
for (const name of pets) {
  const comp = path.join(ROOT, `src/components/pets/${name}Pet.vue`)
  const { tpl, style } = extract(comp)
  const species = name.toLowerCase()
  // 去掉根节点的 :class 绑定，分别渲染 normal 与 working 两态
  const normal = tpl.replace(/\s*:class="\[\{ working \}, 'mood-' \+ \(mood \|\| 'normal'\)\]"/, '')
  const working = normal.replace(`class="creature ${species}"`, `class="creature ${species} working"`)
  cells += `
    <div class="cell"><div class="pet-wrap">${normal}</div><div class="name">${name}</div></div>`
  // working 行
  cells += `
    <div class="cell working-cell"><div class="pet-wrap">${working}</div><div class="name">${name}(working)</div></div>`
  // mood 行（验证表情系统在新结构下的对齐）
  for (const mood of ['happy', 'curious', 'proud']) {
    const mooded = normal.replace(`class="creature ${species}"`, `class="creature ${species} mood-${mood}"`)
    cells += `
    <div class="cell"><div class="pet-wrap">${mooded}</div><div class="name">${name}(${mood})</div></div>`
  }
  styles += style
}

const html = `<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
body { margin: 0; background: #f0f2f5; font-family: sans-serif; }
.ai-pet { position: relative; }
.grid { display: grid; grid-template-columns: repeat(${cols}, 1fr); gap: 4px; padding: 30px; }
.cell { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; min-height: ${Math.round(scale * 100)}px; }
.pet-wrap { position: relative; transform: scale(${scale}); transform-origin: bottom center; margin-bottom: ${Math.round(scale * 16)}px; }
.name { font-size: 11px; color: #888; }
${moodCss}
${furCss}
${styles}
</style>
</head>
<body>
<div class="ai-pet"><div class="grid">${cells}</div></div>
</body>
</html>`

const out = path.join(__dirname, 'pet-preview.html')
fs.writeFileSync(out, html, 'utf8')
console.log('written:', out)
