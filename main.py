import http.server
import json
import os
import re
import html
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from string import Template
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("server.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('genPDF')

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PORT = 8000
HOST = "localhost"


class TemplateStore:
    def __init__(self, storage_dir):
        self.storage_dir = storage_dir
        storage_dir.mkdir(exist_ok=True)

    def save(self, data):
        """Сохраняем шаблон, возвращаем ID"""
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        data['updated_at'] = datetime.now().isoformat()
        if 'created_at' not in data:
            data['created_at'] = data['updated_at']

        file_path = self.storage_dir / f"{data['id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return data['id']

    def load(self, template_id):
        """Загружаем шаблон по ID"""
        file_path = self.storage_dir / f"{template_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_all(self):
        """Список всех шаблонов"""
        templates = []
        for file_path in self.storage_dir.glob("*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                templates.append(json.load(f))
        return sorted(templates, key=lambda x: x.get("updated_at", ""), reverse=True)

    def delete(self, template_id):
        """Удаляем шаблон"""
        file_path = self.storage_dir / f"{template_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class TStringRenderer:
    def __init__(self):
        self.placeholder_pattern = re.compile(r'\[%=(\w+)%\]')

    def get_placeholders(self, content):
        """Извлекаем все плейсхолдеры из шаблона"""
        return self.placeholder_pattern.findall(content)

    def render(self, content, values):
        """Подставляем значения в шаблон"""
        # Конвертируем [%=field%] в ${field} для Template
        converted = self.placeholder_pattern.sub(r'${\1}', content)
        template = Template(converted)
        return template.safe_substitute(**values)

    def check_missing(self, content, values):
        """Проверяем, все ли плейсхолдеры заполнены"""
        placeholders = self.get_placeholders(content)
        missing = [p for p in placeholders if p not in values]
        return len(missing) == 0, missing


# Инициализация
store = TemplateStore(DATA_DIR)
renderer = TStringRenderer()




HTML_UI = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>genPDF - PDF Generator</title>
    <link href="https://cdn.quilljs.com/1.3.6/quill.snow.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            height: 100vh;
            overflow: hidden;
        }
        .container {
            display: flex;
            height: 100vh;
            gap: 20px;
            padding: 20px;
        }
        .editor-panel, .preview-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .panel-header {
            padding: 15px 20px;
            background: #2c3e50;
            color: white;
            font-weight: 600;
            font-size: 16px;
        }
        #editor { flex: 1; overflow: hidden; }
        .ql-container { font-size: 14px; }
        .preview-content {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #fafafa;
        }
        .preview-frame {
            width: 100%;
            height: 100%;
            border: 1px solid #ddd;
            background: white;
        }
        .toolbar {
            padding: 15px 20px;
            background: #ecf0f1;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-primary:hover { background: #2980b9; }
        .btn-success { background: #27ae60; color: white; }
        .btn-success:hover { background: #229954; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-danger:hover { background: #c0392b; }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-secondary:hover { background: #7f8c8d; }
        .template-list {
            margin-top: 10px;
            max-height: 150px;
            overflow-y: auto;
        }
        .template-item {
            padding: 8px 12px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 5px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .template-item:hover {
            background: #f8f9fa;
            border-color: #3498db;
        }
        .template-item.active {
            background: #ebf5fb;
            border-color: #3498db;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 8px;
            min-width: 400px;
            max-width: 600px;
        }
        .modal-header {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #2c3e50;
        }
        .form-group { margin-bottom: 15px; }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #555;
        }
        .form-group input, .form-group textarea {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .form-group textarea { resize: vertical; min-height: 80px; }
        .modal-footer {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        .status-bar {
            padding: 8px 20px;
            background: #34495e;
            color: white;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="editor-panel">
            <div class="panel-header">HTML Template Editor</div>
            <div id="editor"></div>
            <div class="toolbar">
                <button class="btn-secondary" onclick="newTemplate()">New</button>
                <button class="btn-primary" onclick="saveTemplate()">Save</button>
                <button class="btn-success" onclick="showPreviewModal()">Preview</button>
                <button class="btn-secondary" onclick="loadTemplateList()">Load</button>
                <button class="btn-danger" onclick="clearEditor()">Clear</button>
            </div>
            <div class="template-list" id="templateList"></div>
            <div class="status-bar" id="statusBar">Ready</div>
        </div>

        <div class="preview-panel">
            <div class="panel-header">PDF Preview</div>
            <div class="toolbar">
                <button class="btn-success" onclick="renderPDF()">Generate PDF</button>
                <button class="btn-primary" onclick="livePreview()">🔍 Live Preview</button>
            </div>
            <div class="preview-content">
                <iframe id="previewFrame" class="preview-frame"></iframe>
            </div>
        </div>
    </div>

    <!-- Preview Modal -->
    <div class="modal" id="previewModal">
        <div class="modal-content" style="min-width: 800px; max-width: 1000px;">
            <div class="modal-header">Preview with Data Substitution</div>
            <div class="form-group">
                <label>Template Variables (JSON):</label>
                <textarea id="previewData" placeholder='{"name": "John Doe", "date": "2024-01-01"}'></textarea>
            </div>
            <div class="form-group">
                <label>Preview:</label>
                <div id="previewHTML" style="border: 1px solid #ddd; padding: 20px; min-height: 200px; background: white;"></div>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary" onclick="closePreviewModal()">Close</button>
                <button class="btn-primary" onclick="updatePreview()">Update</button>
            </div>
        </div>
    </div>

    <!-- Save Template Modal -->
    <div class="modal" id="saveModal">
        <div class="modal-content">
            <div class="modal-header">Save Template</div>
            <div class="form-group">
                <label>Template Name:</label>
                <input type="text" id="templateName" placeholder="Enter template name">
            </div>
            <div class="form-group">
                <label>Description:</label>
                <textarea id="templateDesc" placeholder="Optional description"></textarea>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary" onclick="closeSaveModal()">Cancel</button>
                <button class="btn-primary" onclick="confirmSaveTemplate()">Save</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.quilljs.com/1.3.6/quill.js"></script>
    <script>
        const quill = new Quill('#editor', {
            theme: 'snow',
            placeholder: 'Enter your HTML template here... Use [%=field%] for variables',
            modules: {
                toolbar: [
                    [{ 'header': [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline'],
                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                    ['link'],
                    ['clean']
                ]
            }
        });

        let currentTemplateId = null;
        let isNewTemplate = true;

        quill.root.innerHTML = `
            <h1>[%=title%]</h1>
            <p><strong>Date:</strong> [%=date%]</p>
            <p><strong>Name:</strong> [%=name%]</p>
            <p><strong>Email:</strong> [%=email%]</p>
            <hr>
            <p>This is a sample template with placeholders.</p>
        `;

        function setStatus(message) {
            document.getElementById('statusBar').textContent = message;
        }

        async function apiRequest(url, method = 'GET', data = null) {
            const options = {
                method,
                headers: { 'Content-Type': 'application/json' }
            };

            if (data) {
                options.body = JSON.stringify(data);
            }

            const response = await fetch(url, options);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/pdf')) {
                return await response.blob();
            }

            return await response.json();
        }

        function newTemplate() {
            if (confirm('Create new template? Unsaved changes will be lost.')) {
                quill.root.innerHTML = `
                    <h1>[%=title%]</h1>
                    <p><strong>Date:</strong> [%=date%]</p>
                    <p><strong>Name:</strong> [%=name%]</p>
                    <hr>
                    <p>Your content here...</p>
                `;
                currentTemplateId = null;
                isNewTemplate = true;
                setStatus('New template created');
            }
        }

        function saveTemplate() {
            document.getElementById('saveModal').classList.add('active');
        }

        function closeSaveModal() {
            document.getElementById('saveModal').classList.remove('active');
        }

        async function confirmSaveTemplate() {
            const name = document.getElementById('templateName').value;
            const description = document.getElementById('templateDesc').value;

            if (!name) {
                alert('Please enter template name');
                return;
            }

            const content = quill.root.innerHTML;

            try {
                const data = { name, description, content };

                if (currentTemplateId && !isNewTemplate) {
                    data.id = currentTemplateId;
                }

                const result = await apiRequest('/templates', 'POST', data);
                currentTemplateId = result.id;
                isNewTemplate = false;

                setStatus(`Template saved: ${name} (ID: ${currentTemplateId.substring(0, 8)}...)`);
                closeSaveModal();
                loadTemplateList();

                document.getElementById('templateName').value = '';
                document.getElementById('templateDesc').value = '';

            } catch (error) {
                setStatus(`Error: ${error.message}`);
                alert('Failed to save template: ' + error.message);
            }
        }

        async function loadTemplateList() {
            try {
                const templates = await apiRequest('/templates');
                const listDiv = document.getElementById('templateList');

                if (templates.length === 0) {
                    listDiv.innerHTML = '<div style="padding: 10px; color: #999;">No templates saved</div>';
                    return;
                }

                listDiv.innerHTML = templates.map(t => `
                    <div class="template-item ${t.id === currentTemplateId ? 'active' : ''}" 
                         onclick="loadTemplate('${t.id}')">
                        <span><strong>${t.name}</strong></span>
                        <span style="font-size: 12px; color: #999;">
                            ${new Date(t.updated_at).toLocaleDateString()}
                        </span>
                    </div>
                `).join('');

                setStatus(`Loaded ${templates.length} templates`);
            } catch (error) {
                setStatus(`Error loading templates: ${error.message}`);
            }
        }

        async function loadTemplate(id) {
            try {
                const template = await apiRequest(`/templates/${id}`);
                quill.root.innerHTML = template.content;
                currentTemplateId = id;
                isNewTemplate = false;
                setStatus(`Loaded template: ${template.name}`);
            } catch (error) {
                setStatus(`Error loading template: ${error.message}`);
            }
        }

        function clearEditor() {
            if (confirm('Clear editor content?')) {
                quill.root.innerHTML = '';
                currentTemplateId = null;
                setStatus('Editor cleared');
            }
        }

        function showPreviewModal() {
            document.getElementById('previewModal').classList.add('active');
            updatePreview();
        }

        function closePreviewModal() {
            document.getElementById('previewModal').classList.remove('active');
        }

        async function updatePreview() {
            const content = quill.root.innerHTML;
            let data = {};

            try {
                const dataStr = document.getElementById('previewData').value;
                if (dataStr) {
                    data = JSON.parse(dataStr);
                }
            } catch (e) {
                document.getElementById('previewHTML').innerHTML = 
                    '<div style="color: red;">Invalid JSON</div>';
                return;
            }

            try {
                const response = await fetch('/preview/current', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content, data })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const result = await response.json();
                document.getElementById('previewHTML').innerHTML = result.html;
            } catch (error) {
                document.getElementById('previewHTML').innerHTML = 
                    `<div style="color: red;">Error: ${error.message}</div>`;
            }
        }

        async function renderPDF() {
            const content = quill.root.innerHTML;
        
            if (!content.trim()) {
                alert('Please enter template content first');
                return;
            }
        
            let data = {};
            try {
                const dataStr = document.getElementById('previewData').value;
                if (dataStr) {
                    data = JSON.parse(dataStr);
                }
            } catch (e) {
                // Use empty data
            }
        
            try {
                setStatus('Generating PDF...');
        
                const blob = await apiRequest('/render/current', 'POST', {
                    content,
                    data
                });
        
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `document_${Date.now()}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
        
                setStatus('PDF downloaded successfully');
            } catch (error) {
                setStatus(`Error generating PDF: ${error.message}`);
                alert('Failed to generate PDF: ' + error.message);
            }
        }
        
        async function updatePreview() {
            const content = quill.root.innerHTML;
            let data = {};
        
            try {
                const dataStr = document.getElementById('previewData').value;
                if (dataStr) {
                    data = JSON.parse(dataStr);
                }
            } catch (e) {
                document.getElementById('previewHTML').innerHTML = 
                    '<div style="color: red;">Invalid JSON</div>';
                return;
            }
        
            try {
                const response = await fetch('/preview/current', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content, data })
                });
        
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
        
                const result = await response.json();
                document.getElementById('previewHTML').innerHTML = result.html;
            } catch (error) {
                document.getElementById('previewHTML').innerHTML = 
                    `<div style="color: red;">Error: ${error.message}</div>`;
            }
        }
        
        async function livePreview() {
            const content = quill.root.innerHTML;
            let data = {};
        
            try {
                const dataStr = document.getElementById('previewData').value;
                if (dataStr) {
                    data = JSON.parse(dataStr);
                }
            } catch (e) {
                setStatus('Invalid JSON in preview data');
                return;
            }
        
            try {
                setStatus('Generating PDF preview...');
        
                const blob = await apiRequest('/render/current', 'POST', {
                    content,
                    data
                });
        
                const url = window.URL.createObjectURL(blob);
                document.getElementById('previewFrame').src = url;
        
                setStatus('PDF preview loaded');
            } catch (error) {
                setStatus(`Error: ${error.message}`);
                const iframe = document.getElementById('previewFrame');
                iframe.srcdoc = `<div style="color: red; padding: 20px;">Error generating PDF: ${error.message}</div>`;
            }
        }

        loadTemplateList();

        let saveTimeout;
        quill.on('text-change', function() {
            setStatus('Editing...');
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                if (currentTemplateId) {
                    setStatus('Auto-saved');
                } else {
                    setStatus('Unsaved changes');
                }
            }, 2000);
        });
    </script>
</body>
</html>'''


class RequestHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
        logger.info(f"{self.command} {self.path} - {status}")

    def send_html_response(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
        logger.info(f"{self.command} {self.path} - 200")

    def send_pdf_response(self, pdf_bytes):
        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Content-Disposition', 'attachment; filename="document.pdf"')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(pdf_bytes)
        logger.info(f"{self.command} {self.path} - 200 (PDF: {len(pdf_bytes)} bytes)")

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}

        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def _clean_html(self, html_content):
        """Очищает HTML от сложных стилей для xhtml2pdf"""
        cleaned = html.unescape(html_content)
        cleaned = re.sub(r'style="[^"]*"', '', cleaned)
        cleaned = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<font[^>]*>(.*?)</font>', r'\1', cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'class="[^"]*"', '', cleaned)

        return cleaned

    def _generate_pdf(self, html_content):
        """Генерация PDF из HTML"""
        try:
            from xhtml2pdf import pisa
            from io import BytesIO
            import html

            clean_html = self._clean_html(html_content)
            full_html = self._wrap_html(clean_html)

            result = BytesIO()
            pdf = pisa.pisaDocument(BytesIO(full_html.encode('UTF-8')), result)

            if pdf.err:
                logger.error(f"PDF ошибка: {pdf.err}")
                return None, str(pdf.err)

            logger.info(f"PDF сгенерирован: {len(result.getvalue())} байт")
            return result.getvalue(), None

        except Exception as e:
            error_msg = f"PDF error: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/':
            self.send_html_response(HTML_UI)
            return

        if path == '/templates':
            templates = store.list_all()
            self.send_json_response(templates)
            return

        if path.startswith('/templates/'):
            template_id = path.split('/')[-1]
            template = store.load(template_id)

            if template:
                self.send_json_response(template)
            else:
                self.send_json_response({'error': 'Template not found'}, 404)
            return

        self.send_json_response({'error': 'Not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            body = self.read_json_body()
        except json.JSONDecodeError:
            self.send_json_response({'error': 'Invalid JSON'}, 400)
            return

        if path == '/templates':
            if 'content' not in body or 'name' not in body:
                self.send_json_response({'error': 'Missing name or content'}, 400)
                return

            template_id = store.save(body)
            self.send_json_response({
                'id': template_id,
                'message': 'Template saved'
            }, 201)
            return

        if path.startswith('/render/'):
            template_id = path.split('/')[-1]

            if template_id == 'current':
                content = body.get('content', '')
                data = body.get('data', {})
            else:
                template = store.load(template_id)
                if not template:
                    self.send_json_response({'error': 'Template not found'}, 404)
                    return
                content = template['content']
                data = body

            if not content:
                self.send_json_response({'error': 'No content'}, 400)
                return

            html = renderer.render(content, data)
            pdf_bytes, error = self._generate_pdf(html)

            if error:
                self.send_json_response({'error': error}, 500)
                return

            self.send_pdf_response(pdf_bytes)
            return

        if path.startswith('/preview/'):
            template_id = path.split('/')[-1]

            if template_id == 'current':
                content = body.get('content', '')
                data = body.get('data', {})
            else:
                template = store.load(template_id)
                if not template:
                    self.send_json_response({'error': 'Template not found'}, 404)
                    return
                content = template['content']
                data = body

            html = renderer.render(content, data)

            self.send_json_response({
                'html': html,
                'placeholders': renderer.get_placeholders(content)
            })
            return

        self.send_json_response({'error': 'Not found'}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path

        if path.startswith('/templates/'):
            template_id = path.split('/')[-1]
            existing = store.load(template_id)

            if not existing:
                self.send_json_response({'error': 'Template not found'}, 404)
                return

            try:
                body = self.read_json_body()
                body['id'] = template_id
                body['created_at'] = existing.get('created_at')

                store.save(body)
                self.send_json_response({'message': 'Template updated'})

            except Exception as e:
                self.send_json_response({'error': str(e)}, 400)
            return

        self.send_json_response({'error': 'Not found'}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path

        if path.startswith('/templates/'):
            template_id = path.split('/')[-1]

            if store.delete(template_id):
                self.send_json_response({'message': 'Template deleted'})
            else:
                self.send_json_response({'error': 'Template not found'}, 404)
            return

        self.send_json_response({'error': 'Not found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _wrap_html(self, content):
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: DejaVu Sans, Arial, sans-serif;
            font-size: 12px;
            line-height: 1.4;
            margin: 20px;
        }}
        h1 {{ font-size: 24px; margin-bottom: 10px; }}
        h2 {{ font-size: 18px; margin-bottom: 8px; }}
        h3 {{ font-size: 16px; margin-bottom: 6px; }}
        p {{ margin-bottom: 8px; }}
        hr {{ margin: 15px 0; }}
    </style>
</head>
<body>
{content}
</body>
</html>'''


def main():
    server_address = (HOST, PORT)
    httpd = http.server.HTTPServer(server_address, RequestHandler)

    print(f"Server running at: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
        print("Server stopped.")


if __name__ == '__main__':
    main()