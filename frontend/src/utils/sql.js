export function extractSqlColumns(sql) {
  if (!sql) return []
  const sqlClean = sql.replace(/--.*$/gm, '').replace(/\/\*.*?\*\//gs, '')
  const selectMatch = sqlClean.match(/SELECT\s+(.*?)\s+FROM/is)
  if (!selectMatch) return []

  let selectClause = selectMatch[1].trim()
  selectClause = selectClause.replace(/DISTINCT\s+/gi, '')

  const columns = []
  let current = ''
  let parenCount = 0

  for (const char of selectClause) {
    if (char === '(') parenCount++
    else if (char === ')') parenCount--
    else if (char === ',' && parenCount === 0) {
      if (current.trim()) columns.push(current.trim())
      current = ''
      continue
    }
    current += char
  }
  if (current.trim()) columns.push(current.trim())

  const result = []
  for (const col of columns) {
    const trimmed = col.trim()
    if (!trimmed) continue

    const asMatch = trimmed.match(/\s+AS\s+(\w+)$/i)
    if (asMatch) { result.push(asMatch[1]); continue }

    const aliasMatch = trimmed.match(/\s+(\w+)$/)
    if (aliasMatch) {
      const alias = aliasMatch[1].toUpperCase()
      if (!['AS','FROM','WHERE','AND','OR','IN','ON','JOIN','CASE','WHEN','THEN','ELSE','END'].includes(alias)) {
        result.push(aliasMatch[1])
        continue
      }
    }

    const funcMatch = trimmed.match(/^(\w+)\s*\(/)
    if (funcMatch) { result.push(funcMatch[1]); continue }

    const dotMatch = trimmed.match(/(\w+)$/)
    if (dotMatch) { result.push(dotMatch[1]); continue }

    result.push(trimmed)
  }

  return result
}
