const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFile } = require('child_process');
const { toMarkdownBytes } = require('@firecrawl/anydoc');

const app = express();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

app.use(express.static(path.join(__dirname, 'public')));

function convertPdf(buffer) {
  return new Promise((resolve, reject) => {
    const tmp = path.join(os.tmpdir(), `anydoc-${Date.now()}.pdf`);
    fs.writeFileSync(tmp, buffer);
    const script = path.join(__dirname, 'pdf-convert.py');
    execFile('python3', [script, tmp], { maxBuffer: 20 * 1024 * 1024 }, (err, stdout, stderr) => {
      try { fs.unlinkSync(tmp); } catch {}
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout);
    });
  });
}

app.post('/convert', upload.single('file'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file uploaded' });

  const ext = path.extname(req.file.originalname).toLowerCase().replace('.', '');
  try {
    let markdown;
    if (ext === 'pdf') {
      markdown = await convertPdf(req.file.buffer);
    } else {
      markdown = await toMarkdownBytes(req.file.buffer, ext || undefined);
    }
    res.json({ markdown, filename: req.file.originalname });
  } catch (err) {
    res.status(422).json({ error: err.message, code: err.code });
  }
});

const PORT = process.env.PORT || 3456;
app.listen(PORT, () => console.log(`Anydoc UI running at http://localhost:${PORT}`));
