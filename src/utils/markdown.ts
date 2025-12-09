export const sanitizeMarkdownContent = (input: string): string => {
  if (!input) {
    return ''
  }
  return input
    .replace(/\r\n/g, '\n')
    .replace(/<\|ref\|>[\s\S]*?<\|\/ref\|>/g, '')
    .replace(/<\|det\|>[\s\S]*?<\|\/det\|>/g, '')
    .replace(/<\|bbox\|>[\s\S]*?<\|\/bbox\|>/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export const buildMarkdownPreview = (input: string, maxLength = 80): string => {
  const sanitized = sanitizeMarkdownContent(input).replace(/\s+/g, ' ').trim()
  if (!sanitized) {
    return ''
  }
  if (sanitized.length <= maxLength) {
    return sanitized
  }
  return `${sanitized.slice(0, maxLength - 1)}…`
}
