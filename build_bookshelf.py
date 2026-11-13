from pathlib import Path
import hashlib, re, zipfile, xml.etree.ElementTree as ET
from bs4 import BeautifulSoup, NavigableString, Tag

root = Path(__file__).parent
epub = next(root.glob('*.epub'))
out = root / 'book'
out.mkdir(exist_ok=True)
z = zipfile.ZipFile(epub)
if 'META-INF/encryption.xml' in z.namelist():
    raise RuntimeError('EPUB contains encryption metadata; inspect before conversion')
z.extractall(out / 'epub_source')
ns = {'n': 'http://www.daisy.org/z3986/2005/ncx/', 'o': 'http://www.idpf.org/2007/opf'}
opf = ET.fromstring(z.read('content.opf'))
manifest = {i.get('id'): i.get('href') for i in opf.findall('.//o:manifest/o:item', ns)}
spine = [manifest[x.get('idref')] for x in opf.findall('.//o:spine/o:itemref', ns)]
ncx = ET.fromstring(z.read('toc.ncx'))
nav = [(x.find('n:navLabel/n:text', ns).text.strip().replace('\u00a0',' '), x.find('n:content', ns).get('src')) for x in ncx.findall('.//n:navPoint', ns)]
chapters = [(int(m.group(1)), title, src) for title, src in nav if (m := re.match(r'^(\d+)\s+(.+)', title))]
assert [x[0] for x in chapters] == list(range(1, 11))
starts = {src: num for num, _, src in chapters}
buffers = {'front': []}; rawtexts = {}; counts = {}; current = 'front'; images = []; tables = []

def inline(node):
    if isinstance(node, NavigableString): return str(node)
    if not isinstance(node, Tag): return ''
    if node.name == 'br': return ' '
    if node.name == 'img': return f"[图片: {node.get('alt','')}](epub_source/{node.get('src','')})"
    t = ''.join(inline(x) for x in node.children)
    if node.name == 'a' and node.get('href'):
        href = node['href']
        if href.startswith('#'): href = source + href
        if not re.match(r'^[a-z]+:', href): href = 'epub_source/' + href
        return f'[{t}]({href})' if t.strip() else ''
    return t

for source in spine:
    soup = BeautifulSoup(z.read(source), 'html.parser')
    body = soup.body
    if not body: continue
    # The index and endnotes follow the chapters in the EPUB spine.
    if source.endswith('split_008.html'): current = 'index'
    if re.search(r'split_01[0-2]\.html$', source) or source.endswith('split_009.html'): current = source[-8:-5] + '_notes'
    buffers.setdefault(current, [])
    for child in body.children:
        if not isinstance(child, Tag): continue
        ident = child.get('id')
        key = source + ('#' + ident if ident else '')
        if key in starts:
            current = f'ch{starts[key]:02d}'
            buffers.setdefault(current, [])
        for img in child.find_all('img'): images.append((source, current, img.get('src','')))
        if child.name == 'table' or child.find('table'): tables.append((source, current, ident or ''))
        text = re.sub(r'\s+', ' ', inline(child)).strip()
        if not text: continue
        rawtexts.setdefault(current, []).append(re.sub(r'\s+', ' ', child.get_text(' ', strip=True)))
        counts[current] = counts.get(current, 0) + 1
        pid = f'{current}-p{counts[current]:04d}'
        source_id = f'#{ident}' if ident else ''
        prefix = '## ' if child.name in ['h1','h2','h3','h4','h5','h6'] else ''
        buffers[current].append(f'<a id="{pid}"></a>\n{prefix}{text}  \n〔{pid}；[EPUB 原文](epub_source/{source}{source_id})〕\n')

for name, entries in buffers.items():
    (out / (name + '.md')).write_text(f'# {name}\n\n' + '\n'.join(entries), encoding='utf-8')
lines = ['# 书籍目录', '', '原书：The Anatomy of Corporate Law: A Comparative and Functional Approach，第二版（2009）。', '段落定位符是转换时生成的，不是纸书页码。脚注链接指向保留的 EPUB 原始 HTML。', '']
for num, title, src in chapters:
    lines.append(f'- 第 {num} 章 [{title}](ch{num:02d}.md) — EPUB: `{src}`')
    for subtitle, subsrc in nav:
        if re.match(rf'^{num}\.\d', subtitle): lines.append(f'  - {subtitle} — `{subsrc}`')
lines += ['', '其他文件：front.md（前置内容）、index.md（索引和部分尾注）、009_notes.md 至 012_notes.md（其余尾注及其他末尾内容，按 EPUB 顺序）。正文脚注可能链接至 split_008.html 或后续文件。', '完整原始 EPUB 内容保存在 epub_source/，图片和原 HTML 链接可从中检查。']
(out / 'toc.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
report = ['# 转换检查', '', f'原 EPUB SHA-256：`{hashlib.sha256(epub.read_bytes()).hexdigest()}`', f'EPUB 阅读顺序文件数：{len(spine)}，均已处理。', f'目录章节：{len(chapters)}，章节起点均已找到。', f'图片引用：{len(images)}；含表格的顶层元素：{len(tables)}。图片与表格应核对原始 HTML；未对图片执行 OCR。', '文本按 EPUB 中 HTML 的顶层元素输出并生成定位符；文本空白和部分排版已规范化。正文中的链接保留指向原始 HTML 的位置。', '', '| 文件 | 英文单词数（近似） | 字符数 | 定位块数 |', '|---|---:|---:|---:|']
for name, entries in buffers.items():
    text = '\n'.join(entries)
    plain = '\n'.join(rawtexts.get(name, []))
    words = len(re.findall(r"\b[\w]+(?:[’\x27-][\w]+)*\b", plain))
    report.append(f'| {name}.md | {words} | {len(plain)} | {len(entries)} |')
report += ['', '图片引用：'] + [f'- `{a}` / `{b}` / `{c}`' for a,b,c in images] + ['', '表格位置：'] + [f'- `{a}` / `{b}` / `{c}`' for a,b,c in tables]
(out / 'conversion_report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print('\n'.join(report[:22]))
section_builder = root / 'split_sections.py'
if section_builder.exists():
    import runpy
    runpy.run_path(str(section_builder), run_name='__main__')
