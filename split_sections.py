"""Create section views of the existing chapter files without changing them."""
from pathlib import Path
import re

root = Path(__file__).resolve().parent
book = root / 'book'
sections = book / 'sections'
sections.mkdir(exist_ok=True)
files = sorted(book.glob('ch[0-9][0-9].md'))
if len(files) != 10:
    raise RuntimeError('Expected ten chapter files; no section files were changed')

heading = re.compile(r'^##\s+(\d+\.\d+(?:\.\d+)?)(?:\.)?\s+(.+?)\s*$')
anchor = re.compile(r'<a id="(ch\d\d-p\d{4})"></a>\n')
all_entries = []
for chapter in files:
    text = chapter.read_text(encoding='utf-8')
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
        path = sections / f'{chapter.stem}-{suffix}.md'
        # Chapter files live one level closer to epub_source than section files.
        content = ''.join(group).replace('](epub_source/', '](../epub_source/')
        metadata = f'# {chapter.stem} / {label} {title}\n\n来源：[整章](../{chapter.name})；段落编号与整章一致。\n\n'
        all_entries.append((chapter.stem, label, title, path, metadata + content, group))

paths = [entry[3] for entry in all_entries]
if len(paths) != len(set(paths)):
    raise RuntimeError('Duplicate section output paths')
for _, _, _, path, content, _ in all_entries:
    path.write_text(content, encoding='utf-8')

toc = book / 'toc.md'
marker = '\n## 小节文件索引\n'
toc_text = toc.read_text(encoding='utf-8').split(marker)[0]
index = [marker, '整章文件保持原位；小节文件按原文顺序排列，保留同一套段落编号。二级标题下、三级标题之前的内容列为引言。\n']
for chapter, label, title, path, _, _ in all_entries:
    index.append(f'- [{chapter} / {label} {title}](sections/{path.name})')
toc.write_text(toc_text.rstrip() + '\n' + '\n'.join(index) + '\n', encoding='utf-8')

for chapter in files:
    expected = anchor.findall(chapter.read_text(encoding='utf-8'))
    actual = []
    for ch, _, _, path, _, _ in all_entries:
        if ch == chapter.stem:
            actual.extend(anchor.findall(path.read_text(encoding='utf-8')))
    if expected != actual:
        raise RuntimeError(f'Paragraph coverage mismatch: {chapter}')
print(f'已核对 {len(files)} 章，生成 {len(all_entries)} 个小节和引言文件；所有段落编号按顺序完整对应。')
