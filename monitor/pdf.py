import fitz


def pdf_text(content):
    if not content.startswith(b'%PDF'):
        raise ValueError('Not a PDF')
    with fitz.open(stream=content, filetype='pdf') as doc:
        if doc.is_encrypted or doc.page_count > 30:
            raise ValueError('Unsupported encrypted/oversized price document')
        text = '\n'.join(page.get_text(sort=True) for page in doc)
    if len(text.strip()) < 100:
        raise ValueError('Scanned or malformed PDF; manual review required')
    return text
