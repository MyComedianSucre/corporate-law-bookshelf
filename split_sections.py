"""Convert in-memory chapter blocks into the canonical section files."""
from pathlib import Path
import re

root = Path(__file__).resolve().parent
book = root / 'book'
sections = book / 'sections'
sections.mkdir(exist_ok=True)
if 'buffers' not in globals():
    raise RuntimeError('请运行 build_bookshelf.py 从 EPUB 生成书架')
files = sorted(name for name in buffers if re.fullmatch(r'ch\d\d', name))

heading = re.compile(r'^##\s+(\d+\.\d+(?:\.\d+)?)(?:\.)?\s+(.+?)\s*$')
anchor = re.compile(r'<a id="(ch\d\d-p\d{4})"></a>\n')
all_entries = []
for chapter in files:
    text = '\n'.join(buffers[chapter])
    matches = list(anchor.finditer(text))
    if not matches:
        raise RuntimeError(f'No paragraph IDs found in {chapter}')
    blocks = [text[m.start(): matches[i+1].start() if i+1 < len(matches) else len(text)] for i, m in enumerate(matches)]
    groups = []
    label, title, current = 'intro', '本章开头', []
    for block in blocks:
        lines = block.splitlines()
        match = heading.match(lines[1]) if len(lines) > 1 else None
        if match:
            if current:
                groups.append((label, title, current))
            label, title = match.group(1), match.group(2)
            current = []
        current.append(block)
    if current:
        groups.append((label, title, current))
    assert [b for _, _, group in groups for b in group] == blocks
    for label, title, group in groups:
        suffix = label + '-intro' if label != 'intro' and label.count('.') == 1 else label
        path = sections / f'{chapter}-{suffix}.md'
        # Chapter files live one level closer to epub_source than section files.
        content = ''.join(group).replace('](epub_source/', '](../epub_source/')
        metadata = f'# {chapter} / {label} {title}\n\n段落编号在全章内连续；完整章节按目录顺序读取。\n\n'
        all_entries.append((chapter, label, title, path, metadata + content, group))

paths = [entry[3] for entry in all_entries]
if len(paths) != len(set(paths)):
    raise RuntimeError('Duplicate section output paths')
for _, _, _, path, content, _ in all_entries:
    path.write_text(content, encoding='utf-8')

toc = book / 'toc.md'
marker = '\n## 小节文件索引\n'
toc_text = toc.read_text(encoding='utf-8').split(marker)[0]
index = [marker, '小节文件按原文顺序排列；阅读整章时依次读取该章所有文件。二级标题下、三级标题之前的内容列为引言。\n']
for chapter, label, title, path, _, _ in all_entries:
    index.append(f'- [{chapter} / {label} {title}](sections/{path.name})')
toc.write_text(toc_text.rstrip() + '\n' + '\n'.join(index) + '\n', encoding='utf-8')

for chapter in files:
    expected = anchor.findall('\n'.join(buffers[chapter]))
    actual = []
    for ch, _, _, path, _, _ in all_entries:
        if ch == chapter:
            actual.extend(anchor.findall(path.read_text(encoding='utf-8')))
    if expected != actual:
        raise RuntimeError(f'Paragraph coverage mismatch: {chapter}')
print(f'已核对 {len(files)} 章，生成 {len(all_entries)} 个小节和引言文件；所有段落编号按顺序完整对应。')
