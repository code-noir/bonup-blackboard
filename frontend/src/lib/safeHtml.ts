import createDOMPurify from 'dompurify'

export const CONTRACT_FONTS = [
  'Arial', 'Georgia', 'Times New Roman', 'Helvetica', 'Courier New',
  'Verdana', 'Trebuchet MS', 'Impact', 'Comic Sans MS', 'Palatino',
  'Garamond', 'Bookman', 'Avant Garde', 'Optima', 'Futura', 'Gill Sans',
  'Century Gothic', 'Calibri', 'Cambria', 'Constantia', 'Candara',
  'Corbel', 'Segoe UI', 'Tahoma', 'Geneva', 'Lucida Grande',
  'Lucida Sans', 'Rockwell', 'Franklin Gothic', 'Baskerville',
]

const fontFamily = (value: string) => CONTRACT_FONTS.find(font => font.toLowerCase() === value.replace(/["']/g, '').trim().toLowerCase())
const alignments = new Set(['left', 'center', 'right', 'justify'])
const purifier = createDOMPurify(window)

// The current contentEditable uses browser font/style markup. Parse CSS while
// detached, then rebuild only these formatting properties from bounded values.
// No URLs, custom properties, positioning, backgrounds, imports or arbitrary CSS.
function safeEditorStyle(value: string): string {
  const source = document.createElement('span').style
  const target = document.createElement('span').style
  source.cssText = value
  const family = fontFamily(source.fontFamily)
  if (family) target.fontFamily = family
  if (/^(?:[8-9]|[1-6]\d|7[0-2])(?:px|pt)$/.test(source.fontSize)) target.fontSize = source.fontSize
  if (alignments.has(source.textAlign)) target.textAlign = source.textAlign
  if (/^(?:normal|bold|[1-9]00)$/.test(source.fontWeight)) target.fontWeight = source.fontWeight
  if (/^(?:normal|italic)$/.test(source.fontStyle)) target.fontStyle = source.fontStyle
  if (/^(?:underline|line-through)(?: (?:underline|line-through))?$/.test(source.textDecorationLine)) target.textDecorationLine = source.textDecorationLine
  if (/^(?:underline|line-through)$/.test(source.textDecoration)) target.textDecoration = source.textDecoration
  if (/^(?:sub|super|baseline)$/.test(source.verticalAlign)) target.verticalAlign = source.verticalAlign
  if (/^(?:1(?:\.\d{1,2})?|2(?:\.0)?)$/.test(source.lineHeight)) target.lineHeight = source.lineHeight
  // Existing generated headings, paragraphs and placeholders use these colors.
  if (['rgb(15, 31, 61)', 'rgb(55, 65, 81)', 'rgb(156, 163, 175)'].includes(source.color)) target.color = source.color
  for (const property of ['margin-top', 'margin-right', 'margin-bottom', 'margin-left', 'padding-left', 'text-indent']) {
    const length = source.getPropertyValue(property)
    if (/^\d+(?:\.\d+)?px$/.test(length) && parseFloat(length) <= 160) target.setProperty(property, length)
  }
  // Application-generated blank spacer divs are 6px/10px high.
  if (['6px', '10px'].includes(source.height)) target.height = source.height
  return target.cssText
}

purifier.addHook('uponSanitizeAttribute', (node, data) => {
  if (data.attrName === 'style') {
    data.attrValue = safeEditorStyle(data.attrValue)
    data.keepAttr = !!data.attrValue
  } else if (data.attrName === 'face') {
    const family = fontFamily(data.attrValue)
    data.keepAttr = node.nodeName === 'FONT' && !!family
    data.attrValue = family || ''
  } else if (data.attrName === 'size') {
    data.keepAttr = node.nodeName === 'FONT' && /^[1-7]$/.test(data.attrValue)
  } else if (data.attrName === 'align') {
    data.keepAttr = alignments.has(data.attrValue)
  } else if (data.attrName === 'start' || data.attrName === 'value') {
    data.keepAttr = (node.nodeName === 'OL' || node.nodeName === 'LI') && /^-?\d{1,4}$/.test(data.attrValue)
  } else if (data.attrName === 'type') {
    data.keepAttr = (node.nodeName === 'OL' || node.nodeName === 'LI') && /^[1aAiI]$/.test(data.attrValue)
  } else if (data.attrName === 'reversed') {
    data.keepAttr = node.nodeName === 'OL'
    data.attrValue = ''
  } else if (data.attrName === 'colspan' || data.attrName === 'rowspan') {
    data.keepAttr = /^(?:[1-9]|[1-9]\d|100)$/.test(data.attrValue)
  }
})

export function safeContractHtml(value: string): string {
  return purifier.sanitize(value, {
    ALLOWED_TAGS: ['p', 'br', 'div', 'span', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'sup', 'sub', 'font', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'hr', 'a'],
    ALLOWED_ATTR: ['id', 'href', 'title', 'colspan', 'rowspan', 'style', 'face', 'size', 'align', 'start', 'type', 'reversed', 'value'],
    ADD_URI_SAFE_ATTR: ['face', 'size', 'align', 'start', 'type', 'reversed', 'value', 'colspan', 'rowspan'],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|#)/i,
  })
}

export function pastePlainText(event: { preventDefault: () => void; clipboardData: DataTransfer }) {
  event.preventDefault()
  document.execCommand('insertText', false, event.clipboardData.getData('text/plain'))
}
