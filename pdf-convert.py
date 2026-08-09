#!/usr/bin/env python3
"""Convert PDF to markdown with proper RTL and table support via pdftotext -layout."""
import sys
import re
import subprocess
import tempfile
import os

def convert_pdf(pdf_path):
    result = subprocess.run(
        ['pdftotext', '-layout', '-enc', 'UTF-8', pdf_path, '-'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return layout_to_markdown(result.stdout)

def strip_bidi(text):
    """Strip BiDi markers only, preserving whitespace for column detection."""
    return re.sub(r'[‎‏‪-‮⁦-⁩­]', '', text)

def fix_bidi_text(text):
    """Fix Hebrew punctuation/number spacing after BiDi markers are stripped."""
    bidi = re.compile(r'[‎‏‪-‮⁦-⁩­]+')
    result = []
    last_end = 0
    for m in bidi.finditer(text):
        result.append(text[last_end:m.start()])
        before = text[m.start()-1] if m.start() > 0 else ' '
        after = text[m.end()] if m.end() < len(text) else ' '
        if before != ' ' and after != ' ':
            result.append(' ')
        last_end = m.end()
    result.append(text[last_end:])
    text = ''.join(result)
    text = re.sub(r'([֐-׿]) ([.,:;!?])', r'\1\2', text)
    text = re.sub(r'(\d) ([.,:;!?]) ', r'\1\2 ', text)
    text = re.sub(r'(\d) ([.,:;!?])$', r'\1\2', text)
    text = re.sub(r'(?<= )([֐-׿])\. ([֐-׿])\.', r'\1.\2.', text)
    text = re.sub(r'(?<= )([֐-׿])\. ([֐-׿])(?=[^.])', r'\1.\2', text)
    text = re.sub(r'([.,:;!?])([֐-׿])', r'\1 \2', text)
    # Fix RTL-mirrored punctuation around numbers
    text = re.sub(r'(\d+)- ', r'-\1 ', text)
    text = re.sub(r'([֐-׿]) -(\d)', r'\1-\2', text)
    text = re.sub(r'(?<=\s)\.(\d+)(?=[\s֐-׿]|$)', r' \1.', text)
    text = re.sub(r'(?<=[֐-׿])\.(\d+)(?=[\s֐-׿]|$)', r' \1.', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()

def split_columns(line):
    """Split a layout line into columns based on 3+ space gaps."""
    parts = [p.strip() for p in re.split(r'   {2,}', line) if p.strip()]
    return parts

def layout_to_markdown(raw):
    lines = raw.split('\n')

    output = []
    table_rows = []
    table_col_count = 0
    continuation_buffer = None
    i = 0

    def flush_table():
        nonlocal table_rows, table_col_count
        if not table_rows:
            return
        # Reverse column order for RTL (layout has leftmost = last in RTL)
        header = table_rows[0]
        n = len(header)
        output.append('| ' + ' | '.join(header) + ' |')
        output.append('| ' + ' | '.join(['---'] * n) + ' |')
        for row in table_rows[1:]:
            while len(row) < n:
                row.append('')
            output.append('| ' + ' | '.join(row[:n]) + ' |')
        output.append('')
        table_rows = []
        table_col_count = 0

    while i < len(lines):
        line = lines[i]
        trimmed = line.strip()
        i += 1

        if trimmed == '' or trimmed == '\f':
            if not table_rows:
                if output and output[-1] != '':
                    output.append('')
            continue

        if '\f' in line:
            trimmed = trimmed.replace('\f', '').strip()
            if not trimmed:
                continue

        cols = split_columns(line)

        if len(cols) >= 3:
            if not table_rows:
                table_col_count = len(cols)

            row = list(cols)
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line == '':
                    break
                next_cols = split_columns(lines[i])
                if len(next_cols) == 1 and len(next_cols[0]) < 40:
                    row[0] = row[0] + ' ' + next_cols[0]
                    i += 1
                elif len(next_cols) < table_col_count and len(next_cols) >= 1:
                    for ci, val in enumerate(next_cols):
                        if ci < len(row):
                            row[ci] = row[ci] + ' ' + val
                    i += 1
                else:
                    break

            if table_rows and row == table_rows[0]:
                continue
            table_rows.append(row)

        elif len(cols) == 1:
            if table_rows:
                if len(trimmed) < 80 and i < len(lines):
                    next_non_empty = ''
                    for j in range(i, min(i + 3, len(lines))):
                        if lines[j].strip():
                            next_non_empty = lines[j]
                            break
                    next_cols = split_columns(next_non_empty) if next_non_empty else []
                    if len(next_cols) >= 3:
                        table_rows.append([trimmed, '', ''])
                        continue

                flush_table()

            text = trimmed
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line == '':
                    break
                next_cols = split_columns(lines[i])
                if len(next_cols) >= 3:
                    break
                text += ' ' + next_line
                i += 1
            output.append(text)
        else:
            if table_rows:
                flush_table()
            output.append(trimmed)

    flush_table()

    md = '\n'.join(output)
    md = re.sub(r'\n{3,}', '\n\n', md)
    # Apply BiDi text fixes line by line (preserves table pipe structure)
    fixed_lines = []
    for line in md.split('\n'):
        fixed_lines.append(fix_bidi_text(line) if line.strip() else line)
    md = '\n'.join(fixed_lines)
    return md.strip()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: pdf-convert.py <file.pdf>", file=sys.stderr)
        sys.exit(1)
    if sys.argv[1] == '--stdin':
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(sys.stdin.buffer.read())
            tmp = f.name
        try:
            print(convert_pdf(tmp))
        finally:
            os.unlink(tmp)
    else:
        print(convert_pdf(sys.argv[1]))
