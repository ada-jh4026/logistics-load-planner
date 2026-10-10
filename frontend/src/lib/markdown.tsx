// 极简 Markdown 渲染：标题、粗体、无序/有序列表、段落。助手文本只用到这些。
import type { ReactNode } from 'react'

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = []
  const re = /\*\*(.+?)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    out.push(<strong key={k++}>{m[1]}</strong>)
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let para: string[] = []
  let k = 0

  const flushPara = () => {
    if (para.length) {
      blocks.push(<p key={k++}>{inline(para.join(' '))}</p>)
      para = []
    }
  }
  const flushList = () => {
    if (list) {
      const items = list.items.map((it, i) => <li key={i}>{inline(it)}</li>)
      blocks.push(list.ordered ? <ol key={k++}>{items}</ol> : <ul key={k++}>{items}</ul>)
      list = null
    }
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line)
    const ol = /^\s*(\d+)[.、]\s+(.*)$/.exec(line)
    if (!line.trim()) {
      flushPara()
      flushList()
    } else if (h) {
      flushPara()
      flushList()
      blocks.push(<h4 key={k++}>{inline(h[2])}</h4>)
    } else if (ul) {
      flushPara()
      if (!list || list.ordered) {
        flushList()
        list = { ordered: false, items: [] }
      }
      list.items.push(ul[1])
    } else if (ol) {
      flushPara()
      if (!list || !list.ordered) {
        flushList()
        list = { ordered: true, items: [] }
      }
      list.items.push(ol[2])
    } else {
      flushList()
      para.push(line.trim())
    }
  }
  flushPara()
  flushList()
  return <div className="md">{blocks}</div>
}
