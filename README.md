# genPDF
Сервис генерации PDF-файлов с заменой шаблона.  

Данный проект представляет из себя спагетти-код, написанный в одном файле, а также хранит внутри ГИТа бинарные файлы в виде скриншотов (ужас) 

По условиям задания должен был использоваться шаблонизатор "t-strings", однако возникли большие сложности с установкой python 3.14 на macos arm, поэтому автор отошел от требований и использовал string.Template
## Установка

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip3 install xhtml2pdf reportlab
```

## Использование

1. Запустите сервис в терминале `python3 main.py`
2. Откройте браузер и перейдите по адресу `http://localhost:8000`
3. Создайте шаблон в WYSIWYG редакторе (слева), используя плейсхолдеры
4. Сохраните шаблон (кнопка "Save")
5. Для генерации PDF:
   - Введите данные для подстановки в формате JSON, нажав "Preview"
   - Нажмите "Generate PDF" для скачивания PDF
   - Или "Live Preview" для предпросмотра в iframe

## Синтаксис шаблонов и подстановка значений

Используйте плейсхолдеры в формате `[%=field_name%]` для подстановки значений:

```html
<h1>[%=company_name%]</h1>
<p>Клиент: [%=client_name%]</p>
<p>Дата: [%=date%]</p>
<p>Сумма: [%=total_amount%]</p>
```

Затем подставьте в них значения, нажав на "Preview"
```json
{
  "field_name": "name"
}
```

# Endpoints (генерация ИИ)

#### 1. Главная страница (UI)

**`GET /`**

Возвращает HTML-страницу с WYSIWYG редактором и панелью предпросмотра PDF.

**Параметры:** отсутствуют

**Ответ:** `200 OK`, `Content-Type: text/html; charset=utf-8`

---

#### 2. Список всех шаблонов

**`GET /templates`**

Возвращает массив всех сохранённых шаблонов, отсортированных по дате обновления.

**Параметры:** отсутствуют

**Ответ:** `200 OK`, `Content-Type: application/json`
```json
[
  {
    "id": "2e0ccd4f-5629-457b-9ae6-7303355c1a81",
    "name": "Invoice Template",
    "description": "Шаблон счёта",
    "content": "<h1>[%=title%]</h1><p>[%=date%]</p>",
    "created_at": "2026-06-02T21:53:06.905385",
    "updated_at": "2026-06-02T21:53:06.905385"
  }
]
```

---

#### 3. Создание шаблона

**`POST /templates`**

Создаёт новый шаблон.

**Параметры (JSON body):**   
| Поле | Тип | Обязательное | Описание |       
|------|-----|--------------|----------|    
| `name` | string | ✅ | Название шаблона |    
| `description` | string | ❌ | Описание шаблона |    
| `content` | string | ✅ | HTML-содержимое с плейсхолдерами `[%=field%]` |    

**Запрос:**
```json
{
  "name": "My Template",
  "description": "Optional description",
  "content": "<h1>[%=title%]</h1><p>[%=content%]</p>"
}
```

**Ответ:** `201 Created`
```json
{
  "id": "new-uuid-string",
  "message": "Template saved"
}
```

**Ошибки:** `400 Bad Request` — если отсутствуют `name` или `content`

---

#### 4. Получение шаблона по ID

**`GET /templates/{id}`**

Возвращает конкретный шаблон по его UUID.

**Параметры:**  
| Параметр | Расположение | Тип | Описание |  
|----------|--------------|-----|----------|  
| `id` | path | string (UUID) | Идентификатор шаблона |   

**Ответ:** `200 OK`
```json
{
  "id": "2e0ccd4f-5629-457b-9ae6-7303355c1a81",
  "name": "Invoice Template",
  "description": "Шаблон счёта",
  "content": "<h1>[%=title%]</h1>",
  "created_at": "2026-06-02T21:53:06.905385",
  "updated_at": "2026-06-02T21:53:06.905385"
}
```

**Ошибки:** `404 Not Found` — если шаблон не найден

---

#### 5. Обновление шаблона

**`PUT /templates/{id}`**

Обновляет существующий шаблон.

**Параметры:**  
| Параметр | Расположение | Тип | Описание |  
|----------|--------------|-----|----------|  
| `id` | path | string (UUID) | Идентификатор шаблона |  

**JSON body:**
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "content": "<h1>[%=newfield%]</h1>"
}
```

**Ответ:** `200 OK`
```json
{
  "message": "Template updated"
}
```

**Ошибки:** `404 Not Found` — если шаблон не найден; `400 Bad Request` — при невалидном JSON

---

#### 6. Удаление шаблона

**`DELETE /templates/{id}`**

Удаляет шаблон по ID.

**Параметры:**  
| Параметр | Расположение | Тип | Описание |  
|----------|--------------|-----|----------|  
| `id` | path | string (UUID) | Идентификатор шаблона |  

**Ответ:** `200 OK`
```json
{
  "message": "Template deleted"
}
```

**Ошибки:** `404 Not Found` — если шаблон не найден

---

#### 7. Генерация PDF

**`POST /render/{id}`**

Генерирует PDF-документ с подстановкой значений и возвращает его для скачивания.

**Параметры:**  
| Параметр | Расположение | Тип | Описание |  
|----------|--------------|-----|----------|  
| `id` | path | string (UUID или `"current"`) | ID шаблона или `"current"` для несохранённого |  

**JSON body (для существующего шаблона):**
```json
{
  "title": "Invoice #123",
  "date": "2026-06-03",
  "client_name": "ООО Ромашка",
  "total_amount": "15000"
}
```

**JSON body (для `id=current` — несохранённый шаблон):**
```json
{
  "content": "<h1>[%=title%]</h1>",
  "data": {
    "title": "My Title"
  }
}
```

**Ответ:** `200 OK`
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="document.pdf"`
- Тело: бинарные данные PDF

**Ошибки:** `404 Not Found`, `400 Bad Request`, `500 Internal Server Error`

---

#### 8. HTML-превью с подстановкой

**`POST /preview/{id}`**

Возвращает HTML с подставленными значениями (без генерации PDF).

**Параметры:**  
| Параметр | Расположение | Тип | Описание |  
|----------|--------------|-----|----------|  
| `id` | path | string (UUID или `"current"`) | ID шаблона или `"current"` для несохранённого |  

**JSON body:** аналогично `/render/{id}`

**Ответ:** `200 OK`
```json
{
  "html": "<h1>Invoice #123</h1><p>Client: ООО Ромашка</p>",
  "placeholders": ["title", "client_name"]
}
```

---

### Формат ошибок

Все ошибки возвращаются в едином формате:
```json
{
  "error": "Описание ошибки"
}
```

**HTTP статус-коды:**
- `200` — Успех
- `201` — Создано
- `400` — Неверный запрос (невалидный JSON, отсутствуют обязательные поля)
- `404` — Ресурс не найден
- `500` — Внутренняя ошибка сервера (ошибка генерации PDF)

---

### CORS

Сервер поддерживает CORS для всех endpoints:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

---

## Примеры использования (cURL)

```bash
# Создать шаблон
curl -X POST http://localhost:8000/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Invoice",
    "description": "Шаблон счёта",
    "content": "<h1>[%=title%]</h1><p>[%=body%]</p>"
  }'

# Получить список шаблонов
curl http://localhost:8000/templates

# Получить конкретный шаблон
curl http://localhost:8000/templates/{template_id}

# Обновить шаблон
curl -X PUT http://localhost:8000/templates/{template_id} \
  -H "Content-Type: application/json" \
  -d '{"name": "New Name", "content": "<h1>[%=new%]</h1>"}'

# Удалить шаблон
curl -X DELETE http://localhost:8000/templates/{template_id}

# Сгенерировать PDF и сохранить в файл
curl -X POST http://localhost:8000/render/{template_id} \
  -H "Content-Type: application/json" \
  -d '{"title": "My Invoice", "body": "Hello World"}' \
  --output document.pdf

# Получить HTML-превью
curl -X POST http://localhost:8000/preview/{template_id} \
  -H "Content-Type: application/json" \
  -d '{"title": "My Invoice", "body": "Hello World"}'
```

---

## Скриншоты работы

Скриншоты интерфейса и процесса работы расположены в директории `screenshots/`:

- `Снимок экрана 2026-06-02 в 23.16.41.png` — главное окно с редактором и предпросмотром PDF
- `Снимок экрана 2026-06-02 в 23.17.18.png` — процесс подстановки значений
- `Снимок экрана 2026-06-02 в 23.18.27.png` — пример логов

## Лог работы

Пример записей из `server.log`:

```
2026-06-02 20:57:16 - POST /templates - 201
2026-06-02 20:57:16 - GET /templates - 200
2026-06-02 20:57:31 - GET /templates/7e823c59-86d2-4475-80f7-1a545101de87 - 200
2026-06-02 20:57:54 - POST /preview/current - 200
2026-06-02 20:58:07 - POST /render/current - 200 (PDF: 1544 bytes)
2026-06-02 23:15:28 - PDF сгенерирован: 1841 байт
2026-06-02 23:15:28 - POST /render/current - 200 (PDF: 1841 bytes)
```

Полный лог работы сервиса доступен в файле `server.log`.

