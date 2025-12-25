if (typeof window.MonacoEditor === 'undefined') {
    window.MonacoEditor = class MonacoEditor {
        constructor(tabId, name, initialCode = '') {
            this.tabId = tabId;
            this.name = name;
            this.initialCode = initialCode;
            this.editor = null;
            this.fontSize = localStorage.getItem('monacoeditor_fontsize') || 14;
            this.stats = {
                totalChars: 0,
                nonSpaceChars: 0,
                functionCount: 0,
                classCount: 0,
                selectedChars: 0,
                selectedNonSpaceChars: 0,
                selectedWords: 0,
                selectedLines: 0,
                errors: 0
            };
            this.functions = [];
            this.classes = [];
            this.imports = [];
            this.errors = [];
            this.pep8Limit = 119;

            // Данные для создания задачи
            this.taskData = {
                forbiddenWords: [],
                examples: [{
                    input: '',
                    output: ''
                }],
                tags: ['python', 'задача'],
                constraints: {
                    maxLines: null,
                    maxLineLength: null,
                    maxChars: null,
                    maxFunctions: null,
                    maxClasses: null
                }
            };

            // Monaco Editor instance
            this.monacoEditor = null;
            this.decorations = [];


            this.init();
        }

        async init() {
            this.applyFontSize();
            await this.createEditor();
            this.bindEvents();
            this.updateAllStats();
            this.setupTooltips();
            this.initStructureSidebar();
            this.initTaskModal();

            // Структуру инициализируем после обновления статистики
            setTimeout(() => {
                this.initStructureSidebar();
            }, 100);
        }

        applyFontSize() {
            document.documentElement.style.setProperty('--editor-font-size', `${this.fontSize}px`);
            $(`#fontSize_${this.tabId}`).text(`${this.fontSize}px`);
        }

        increaseFontSize() {
            if (this.fontSize < 24) {
                this.fontSize++;
                this.applyFontSize();
                this.updateEditorFont();
                localStorage.setItem('monacoeditor_fontsize', this.fontSize);
            }
        }

        decreaseFontSize() {
            if (this.fontSize > 10) {
                this.fontSize--;
                this.applyFontSize();
                this.updateEditorFont();
                localStorage.setItem('monacoeditor_fontsize', this.fontSize);
            }
        }

        updateEditorFont() {
            if (this.monacoEditor) {
                this.monacoEditor.updateOptions({
                    fontSize: this.fontSize
                });
            }
        }

        async createEditor() {
            const container = document.getElementById('editorContainer_' + this.tabId);
            if (!container) return;

            try {
                if (typeof require === 'undefined') return;

                require.config({paths: {'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.34.0/min/vs'}});
                await new Promise((res, rej) => require(['vs/editor/editor.main'], res, rej));

                this.monacoEditor = monaco.editor.defineTheme('oneDarkCustom', {
                    base: 'vs-dark',
                    inherit: true,
                    rules: [
                        {token: 'keyword.python', foreground: 'C678DD'},       // from, import, def
                        {token: 'string.python', foreground: '98C379'},        // строки
                        {token: 'function.python', foreground: '61AFEF'},      // названия функций
                        {token: 'type.python', foreground: 'E5C07B'},          // классы
                        {token: 'comment.python', foreground: '5C6370', fontStyle: 'italic'},
                        {token: 'number.python', foreground: 'D19A66'},        // числа
                        {token: 'operator.python', foreground: '56B6C2'},      // + - * /
                        {token: 'identifier.python', foreground: 'ABB2BF'},    // переменные
                        {token: 'meta.function.decorator.python', foreground: 'D19A66'}, // @decorator
                    ],
                    colors: {
                        'editor.background': '#282C34',
                        'editor.foreground': '#ABB2BF',
                        'editor.lineHighlightBackground': '#2C313C',
                        'editorLineNumber.foreground': '#495162',
                        'editorLineNumber.activeForeground': '#ABB2BF',
                        'editorIndentGuide.background': '#3B4048',
                        'editorIndentGuide.activeBackground': '#528BFF',
                        'editor.selectionBackground': '#3E4451',
                    }
                });

                // 2. СОЗДАЕМ РЕДАКТОР
                this.monacoEditor = monaco.editor.create(container, {
                    value: this.initialCode || '',
                    language: 'python',
                    theme: 'oneDarkCustom', // Применяем созданную тему

                    // ШРИФТ (JetBrains Mono должен быть установлен в системе или подключен через CSS)
                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    fontSize: 14,
                    lineHeight: 25, // На скрине очень свободный интервал
                    letterSpacing: 0.5,
                    fontLigatures: true,

                    padding: {top: 20, bottom: 20},

                    minimap: {enabled: false},
                    scrollbar: {
                        vertical: 'visible',
                        horizontal: 'visible',
                        verticalScrollbarSize: 10,
                        horizontalScrollbarSize: 10,
                        useShadows: false
                    },

                    lineNumbersMinChars: 4,
                    glyphMargin: false,
                    folding: true,

                    automaticLayout: true,
                    scrollBeyondLastLine: false,
                    renderLineHighlight: 'all',

                    // Настройки поведения (режим "экзамен")
                    quickSuggestions: false,
                    suggestOnTriggerCharacters: false,
                    autoClosingBrackets: 'always',
                    tabSize: 4,
                    insertSpaces: true,

                    guides: {
                        indentation: true,
                        bracketPairs: true
                    }
                });

            } catch (err) {
                console.error('Monaco Init Error:', err);
            }
        }

        updateSelectionUI() {
            const selectedText = this.stats.selectedNonSpaceChars > 0
                ? `${this.stats.selectedNonSpaceChars}с`
                : "0";

            $('#selectedChars_' + this.tabId).text(selectedText);

            // Детальный tooltip
            const tooltipText = this.stats.selectedNonSpaceChars > 0
                ? `${this.stats.selectedNonSpaceChars} символов (без пробелов/табов/переносов)\n` +
                `${this.stats.selectedWords} слов\n` +
                `${this.stats.selectedLines} строк`
                : 'Выделено символов (без whitespace)';

            $(`#selectedChars_${this.tabId}`).parent().attr('title', tooltipText);
        }

        initStructureSidebar() {
            // Инициализируем боковую панель структуры
            this.updateStructureSidebar();

            // Восстанавливаем состояние секций из localStorage
            this.restoreSectionStates();
        }

        restoreSectionStates() {
            const sections = ['functions', 'classes', 'imports'];

            sections.forEach(sectionType => {
                const storageKey = `monacoeditor_section_${this.tabId}_${sectionType}`;
                const savedState = localStorage.getItem(storageKey);
                const section = document.getElementById(`${sectionType}Section_${this.tabId}`);

                if (section && savedState === 'closed') {
                    const items = section.querySelector('.section-items');
                    const toggle = section.querySelector('.section-toggle');

                    if (items && toggle) {
                        items.style.display = 'none';
                        toggle.classList.remove('fa-chevron-up');
                        toggle.classList.add('fa-chevron-down');
                    }
                }
            });
        }

        updateStructureSidebar() {
            this.analyzeCodeStructure();
            this.renderFunctionsList();
            this.renderClassesList();
            this.renderImportsList();
            this.updateStructureCounts();
        }

        analyzeCodeStructure() {
            if (!this.monacoEditor) return;

            const code = this.monacoEditor.getValue();
            const lines = code.split('\n');

            this.functions = [];
            this.classes = [];
            this.imports = [];

            lines.forEach((line, index) => {
                const lineNum = index + 1;
                const trimmed = line.trim();

                // Обнаружение функций
                const funcMatch = trimmed.match(/^def\s+(\w+)\s*\(/);
                if (funcMatch) {
                    const funcName = funcMatch[1];
                    const indent = line.match(/^(\s*)/)[1].length;

                    // Определяем тип функции по имени
                    let type = 'function';
                    let icon = 'fa-code';

                    if (funcName.startsWith('__') && funcName.endsWith('__')) {
                        type = 'magic';
                        icon = 'fa-magic';
                    } else if (funcName.startsWith('_')) {
                        type = 'private';
                        icon = 'fa-lock';
                    } else if (funcName === funcName.toUpperCase()) {
                        type = 'constant';
                        icon = 'fa-hashtag';
                    }

                    this.functions.push({
                        name: funcName,
                        line: lineNum,
                        indent: indent,
                        type: type,
                        icon: icon
                    });
                }

                // Обнаружение классов
                const classMatch = trimmed.match(/^class\s+(\w+)/);
                if (classMatch) {
                    const className = classMatch[1];
                    const indent = line.match(/^(\s*)/)[1].length;

                    // Определяем тип класса
                    let type = 'class';
                    let icon = 'fa-cube';

                    if (className.includes('Abstract') || className.includes('Base')) {
                        type = 'abstract';
                        icon = 'fa-shapes';
                    } else if (className.includes('Mixin')) {
                        type = 'mixin';
                        icon = 'fa-puzzle-piece';
                    } else if (className.includes('Exception') || className.includes('Error')) {
                        type = 'exception';
                        icon = 'fa-exclamation-circle';
                    }

                    this.classes.push({
                        name: className,
                        line: lineNum,
                        indent: indent,
                        type: type,
                        icon: icon
                    });
                }

                // Обнаружение импортов
                const importMatch = trimmed.match(/^(import|from)\s+(\w+)/);
                if (importMatch) {
                    const importType = importMatch[1];
                    const module = importMatch[2];

                    this.imports.push({
                        module: module,
                        line: lineNum,
                        type: importType
                    });
                }
            });
        }

        renderFunctionsList() {
            const container = document.getElementById('functionsList_' + this.tabId);
            if (!container) return;

            container.innerHTML = '';

            if (this.functions.length === 0) {
                container.innerHTML = '<div class="empty-message">Нет функций</div>';
                return;
            }

            this.functions.forEach(func => {
                const funcElement = document.createElement('div');
                funcElement.className = `structure-item func-${func.type}`;
                funcElement.innerHTML = `
                    <i class="fas ${func.icon}"></i>
                    <span class="item-name">${func.name}</span>
                    <span class="item-line">:${func.line}</span>
                `;

                funcElement.onclick = (e) => {
                    e.stopPropagation();
                    this.goToLine(func.line);
                };

                container.appendChild(funcElement);
            });
        }

        renderClassesList() {
            const container = document.getElementById('classesList_' + this.tabId);
            if (!container) return;

            container.innerHTML = '';

            if (this.classes.length === 0) {
                container.innerHTML = '<div class="empty-message">Нет классов</div>';
                return;
            }

            this.classes.forEach(cls => {
                const classElement = document.createElement('div');
                classElement.className = `structure-item class-${cls.type}`;
                classElement.innerHTML = `
                    <i class="fas ${cls.icon}"></i>
                    <span class="item-name">${cls.name}</span>
                    <span class="item-line">:${cls.line}</span>
                `;

                classElement.onclick = (e) => {
                    e.stopPropagation();
                    this.goToLine(cls.line);
                };

                container.appendChild(classElement);
            });
        }

        renderImportsList() {
            const container = document.getElementById('importsList_' + this.tabId);
            if (!container) return;

            container.innerHTML = '';

            if (this.imports.length === 0) {
                container.innerHTML = '<div class="empty-message">Нет импортов</div>';
                return;
            }

            // Группируем импорты по модулям
            const groupedImports = {};
            this.imports.forEach(imp => {
                if (!groupedImports[imp.module]) {
                    groupedImports[imp.module] = [];
                }
                groupedImports[imp.module].push(imp);
            });

            Object.entries(groupedImports).forEach(([module, imports]) => {
                const importElement = document.createElement('div');
                importElement.className = 'structure-item import';
                importElement.innerHTML = `
                    <i class="fas fa-file-import"></i>
                    <span class="item-name">${module}</span>
                `;

                // При клике переходим к первому импорту этого модуля
                importElement.onclick = (e) => {
                    e.stopPropagation();
                    this.goToLine(imports[0].line);
                };

                container.appendChild(importElement);
            });
        }

        updateStructureCounts() {
            $(`#functionCountDisplay_${this.tabId}`).text(this.functions.length);
            $(`#classCountDisplay_${this.tabId}`).text(this.classes.length);
        }

        initTaskModal() {
            // Инициализация модального окна создания задачи
            this.updateForbiddenWordsList();
            this.updateTagsList();
            this.updateExamplesList();
        }

        bindEvents() {
            // Запуск кода
            $('#tabRunBtn_' + this.tabId).off('click').on('click', () => {
                this.runCode();
            });

            // Очистка консоли
            $('#clearConsoleBtn_' + this.tabId).off('click').on('click', () => {
                this.clearConsole();
            });

            // Развернуть консоль
            $(`#expandConsoleBtn_${this.tabId}`).off('click').on('click', () => {
                this.expandConsole();
            });

            // Свернуть консоль
            $(`#collapseConsoleBtn_${this.tabId}`).off('click').on('click', () => {
                this.collapseConsole();
            });


            // Клик по иконке ошибок PEP8
            $(document).on('click', `#pep8Errors_${this.tabId}`, (e) => {
                e.stopPropagation();
                this.showErrorsModal();
            });

            if (this.monacoEditor) {
                // Обновление статистики и структуры
                this.monacoEditor.onDidChangeModelContent(() => {
                    this.updateAllStats();
                    this.updateStructureSidebar();
                    this.autoSave();
                });

                // Обновление статистики выделения
                this.monacoEditor.onDidChangeCursorSelection(() => {
                    this.updateSelectionStats();
                });

                // Проверка ввода
                this.monacoEditor.onKeyDown((e) => {
                    this.validateKeyInput(e);
                });
            }
        }

        validateKeyInput(e) {
            // Запрет на точку с запятой
            if (e.key === ';') {
                this.addConsoleMessage('Python не использует точку с запятой (;) в конце строк', 'warning');
                e.preventDefault();
                e.stopPropagation();
                return;
            }
        }

        setupTooltips() {
            // Инициализация тултипов для статистики
            $(`#statusBar_${this.tabId} .stat-item[data-tooltip]`).each(function () {
                const tooltip = $(this).data('tooltip');
                $(this).attr('title', tooltip);
            });
        }

        updateAllStats() {
            if (!this.monacoEditor) return;

            const code = this.monacoEditor.getValue();

            this.updateCharStats(code);
            this.updateCodeStructureStats(code);
            this.updateSelectionStats();
            this.checkPEP8Rules(code);

            this.updateStatsUI();
        }

        updateCharStats(code) {
            this.stats.totalChars = code.length;
            this.stats.nonSpaceChars = code.replace(/\s/g, '').length;
        }

        updateCodeStructureStats(code) {
            this.stats.functionCount = this.functions.length;
            this.stats.classCount = this.classes.length;
        }

        updateSelectionStats() {
            if (!this.monacoEditor) return;

            const selection = this.monacoEditor.getSelection();
            let selectedAllChars = 0;
            let selectedNonWhitespaceChars = 0;
            let selectedWords = 0;
            let selectedLines = 0;

            if (!selection.isEmpty()) {
                const model = this.monacoEditor.getModel();
                const text = model.getValueInRange(selection);

                // Все символы
                selectedAllChars = text.length;

                // Не-whitespace символы
                selectedNonWhitespaceChars = text.replace(/\s/g, '').length;

                // Подсчет слов
                const wordArray = text.match(/\S+/g) || [];
                selectedWords = wordArray.length;

                // Подсчет строк
                const startLine = selection.startLineNumber;
                const endLine = selection.endLineNumber;
                selectedLines = endLine - startLine + 1;
            }

            // Обновляем статистику
            this.stats.selectedChars = selectedAllChars;
            this.stats.selectedNonSpaceChars = selectedNonWhitespaceChars;
            this.stats.selectedWords = selectedWords;
            this.stats.selectedLines = selectedLines;

            // Обновляем UI
            this.updateSelectionUI();
        }

        checkPEP8Rules(code) {
            const lines = code.split('\n');
            this.errors = [];

            this.clearLineMarkers();

            lines.forEach((line, index) => {
                const lineNum = index + 1;

                if (line.length > this.pep8Limit) {
                    this.addError(lineNum, `Строка слишком длинная (${line.length}/${this.pep8Limit} символов)`, 'pep8');
                }

                if (line.includes(';')) {
                    this.addError(lineNum, 'Точка с запятой не используется в Python', 'syntax');
                }

                if (line.startsWith('\t')) {
                    this.addError(lineNum, 'Используйте 4 пробела вместо табов для отступов', 'pep8');
                }

                if (line.endsWith(' ') || line.endsWith('\t')) {
                    this.addError(lineNum, 'Уберите пробелы в конце строки', 'pep8');
                }
            });

            this.stats.errors = this.errors.length;
        }

        addError(lineNum, message, type) {
            this.errors.push({line: lineNum, message, type});

            if (this.monacoEditor) {
                const model = this.monacoEditor.getModel();
                if (!model) return;

                const lineDecoration = {
                    range: new monaco.Range(lineNum, 1, lineNum, 1),
                    options: {
                        isWholeLine: true,
                        className: type === 'syntax' ? 'error-line-decoration' : 'warning-line-decoration',
                        glyphMarginClassName: type === 'syntax' ? 'error-glyph-margin' : 'warning-glyph-margin'
                    }
                };

                this.decorations = this.monacoEditor.deltaDecorations(
                    this.decorations,
                    [lineDecoration]
                );
            }
        }

        clearLineMarkers() {
            if (!this.monacoEditor) return;
            this.decorations = this.monacoEditor.deltaDecorations(this.decorations, []);
        }

        updateStatsUI() {
            $('#nonSpaceChars_' + this.tabId).text(this.stats.nonSpaceChars);
            $('#functionCount_' + this.tabId).text(this.stats.functionCount);
            $('#classCount_' + this.tabId).text(this.stats.classCount);
            $('#selectedChars_' + this.tabId).text(this.stats.selectedNonSpaceChars);
            $('#errorCount_' + this.tabId).text(this.stats.errors);

            const errorStat = $('#pep8Errors_' + this.tabId);
            if (this.stats.errors > 0) {
                errorStat.addClass('has-errors');
            } else {
                errorStat.removeClass('has-errors');
            }
        }

        showErrorsModal() {
            if (this.errors.length === 0) return;

            const modal = document.getElementById('pep8ErrorsModal_' + this.tabId);
            const errorsList = document.getElementById('errorsList_' + this.tabId);

            errorsList.innerHTML = '';

            const pep8Errors = this.errors.filter(e => e.type === 'pep8');
            const syntaxErrors = this.errors.filter(e => e.type === 'syntax');

            if (pep8Errors.length > 0) {
                errorsList.innerHTML += '<div class="error-group-title">Ошибки PEP8:</div>';
                pep8Errors.forEach(error => {
                    errorsList.innerHTML += `
                        <div class="error-item" onclick="window.codeMonkeyInstances['${this.tabId}'].goToLine(${error.line})">
                            <span class="error-line">Строка ${error.line}:</span>
                            <span class="error-message">${error.message}</span>
                        </div>
                    `;
                });
            }

            if (syntaxErrors.length > 0) {
                errorsList.innerHTML += '<div class="error-group-title">Синтаксические ошибки:</div>';
                syntaxErrors.forEach(error => {
                    errorsList.innerHTML += `
                        <div class="error-item" onclick="window.codeMonkeyInstances['${this.tabId}'].goToLine(${error.line})">
                            <span class="error-line">Строка ${error.line}:</span>
                            <span class="error-message">${error.message}</span>
                        </div>
                    `;
                });
            }

            modal.style.display = 'block';
        }

        hideErrorsModal() {
            document.getElementById('pep8ErrorsModal_' + this.tabId).style.display = 'none';
        }

        hideTaskModal() {
            document.getElementById('taskCreationModal_' + this.tabId).style.display = 'none';
        }

        updateTaskCodePreview() {
            const codePreview = document.getElementById('taskCodePreview_' + this.tabId);
            if (!codePreview || !this.monacoEditor) return;

            const code = this.monacoEditor.getValue();
            const lines = code.split('\n');

            // Форматируем код для отображения
            let html = '<pre><code>';
            lines.forEach((line, index) => {
                html += `<span class="line-number">${index + 1}</span> ${this.escapeHtml(line)}\n`;
            });
            html += '</code></pre>';

            codePreview.innerHTML = html;

            // Обновляем статистику
            $('#taskLinesCount_' + this.tabId).text(lines.length);
            $('#taskCharsCount_' + this.tabId).text(code.length);
            $('#taskNonSpaceCount_' + this.tabId).text(code.replace(/\s/g, '').length);
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        resetTaskForm() {
            // Сбрасываем форму к начальным значениям
            $('#taskDescription_' + this.tabId).val('');

            // Сбрасываем ограничения
            $('#limitLines_' + this.tabId).prop('checked', false);
            $('#limitLineLength_' + this.tabId).prop('checked', false);
            $('#limitChars_' + this.tabId).prop('checked', false);
            $('#limitFunctions_' + this.tabId).prop('checked', false);
            $('#limitClasses_' + this.tabId).prop('checked', false);

            $('#maxLines_' + this.tabId).prop('disabled', true);
            $('#maxLineLength_' + this.tabId).prop('disabled', true);
            $('#maxChars_' + this.tabId).prop('disabled', true);
            $('#maxFunctions_' + this.tabId).prop('disabled', true);
            $('#maxClasses_' + this.tabId).prop('disabled', true);

            // Сбрасываем запрещённые слова
            this.taskData.forbiddenWords = [];
            this.updateForbiddenWordsList();

            // Сбрасываем примеры
            this.taskData.examples = [{
                input: '',
                output: ''
            }];
            this.updateExamplesList();

            // Сбрасываем теги
            this.taskData.tags = ['python', 'задача'];
            this.updateTagsList();

            // Устанавливаем лёгкий уровень сложности
            $('input[name="difficulty_' + this.tabId + '"][value="easy"]').prop('checked', true);
        }

        updateForbiddenWordsList() {
            const list = document.getElementById('forbiddenWordsList_' + this.tabId);
            if (!list) return;

            list.innerHTML = '';

            if (this.taskData.forbiddenWords.length === 0) {
                list.innerHTML = '<div class="empty-words">Запрещённые слова не добавлены</div>';
                return;
            }

            this.taskData.forbiddenWords.forEach((word, index) => {
                const wordElement = document.createElement('div');
                wordElement.className = 'forbidden-word';
                wordElement.innerHTML = `
                        <span>${word}</span>
                        <button type="button" class="remove-word-btn" onclick="removeForbiddenWord('${this.tabId}', ${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    `;
                list.appendChild(wordElement);
            });
        }

        updateTagsList() {
            const list = document.getElementById('tagsList_' + this.tabId);
            if (!list) return;

            list.innerHTML = '';

            this.taskData.tags.forEach((tag, index) => {
                const tagElement = document.createElement('span');
                tagElement.className = 'tag';
                tagElement.innerHTML = `
                        ${tag}
                        <span class="remove-tag" onclick="removeTag('${this.tabId}', ${index})">×</span>
                    `;
                list.appendChild(tagElement);
            });
        }

        clearConsoleContent() {
            // Только очищаем содержимое, не меняем высоту
            $('#consoleOutput_' + this.tabId).empty();
            this.addConsoleMessage("Консоль очищена", "info");
        }

        updateExamplesList() {
            const container = $('.io-examples');
            if (!container.length) return;

            // Очищаем все примеры кроме первого
            $('.io-example:gt(0)').remove();

            // Обновляем первый пример
            $('#inputExample1_' + this.tabId).val(this.taskData.examples[0].input || '');
            $('#outputExample1_' + this.tabId).val(this.taskData.examples[0].output || '');

            // Добавляем остальные примеры
            for (let i = 1; i < this.taskData.examples.length; i++) {
                this.addExampleToDOM(i + 1, this.taskData.examples[i]);
            }
        }

        addExampleToDOM(exampleNum, exampleData) {
            const examplesContainer = $('.io-examples');
            const exampleHtml = `
                    <div class="io-example" id="example_${exampleNum}_${this.tabId}">
                        <div class="io-header">
                            <span>Пример ${exampleNum}</span>
                            <button type="button" class="remove-example-btn" onclick="removeExample('${this.tabId}', ${exampleNum - 1})">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div class="io-row">
                            <div class="io-cell">
                                <label>Входные данные:</label>
                                <textarea class="io-input" id="inputExample${exampleNum}_${this.tabId}" placeholder='{"arg1": "value", "arg2": 123}'>${exampleData.input || ''}</textarea>
                            </div>
                            <div class="io-cell">
                                <label>Ожидаемый результат:</label>
                                <textarea class="io-output" id="outputExample${exampleNum}_${this.tabId}" placeholder='{"result": "expected"}' >${exampleData.output || ''}</textarea>
                            </div>
                        </div>
                    </div>
                `;

            examplesContainer.append(exampleHtml);
        }

        goToLine(line) {
            if (!this.monacoEditor) return;

            this.monacoEditor.revealLineInCenter(line);
            this.monacoEditor.setPosition({
                lineNumber: line,
                column: 1
            });
            this.monacoEditor.focus();
            this.hideErrorsModal();
        }

        runCode() {
    if (!this.monacoEditor) return;

    const code = this.monacoEditor.getValue();
    const runBtn = $('#tabRunBtn_' + this.tabId);

    runBtn.prop('disabled', true);
    runBtn.html('<div class="loading"></div> Тестирование...');

    this.clearConsoleContent();
    this.addConsoleMessage(`🚀 Запуск тестов...`, 'info');

    $.ajax({
        url: `${location.origin}/code_cup/editor/run-code/`,
        type: 'POST',
        data: {
            code: code,
            task_id: this.currentTaskId, // Не забудьте передавать ID задачи
            language: 'python'
        },
        success: (response) => {
            if (response.success && response.task_id) {
                this.pollTaskStatus(response.task_id);
            } else {
                this.addConsoleMessage(`❌ Ошибка запуска: ${response.error || 'Неизвестно'}`, 'error');
                this.resetRunButton();
            }
        },
        error: () => {
            this.addConsoleMessage(`❌ Ошибка сервера (AJAX)`, 'error');
            this.resetRunButton();
        }
    });
}

pollTaskStatus(taskId) {
    const checkInterval = setInterval(() => {
        $.ajax({
            url: `${location.origin}/code_cup/editor/get-status/${taskId}/`,
            type: 'GET',
            success: (data) => {
                if (data.status === 'SUCCESS') {
                    clearInterval(checkInterval);
                    const res = data.result;

                    if (res.success) {
                        // 1. Отображаем общий вердикт
                        const verdict = res.passed ? '✅ Все тесты пройдены!' : '❌ Решение не принято';
                        this.addConsoleMessage(verdict, res.passed ? 'success' : 'error');

                        // 2. Отображаем статистику
                        if (res.stats) {
                            this.addConsoleMessage(
                                `📊 Пройдено: ${res.stats.passed_tests}/${res.stats.total_tests} (${res.stats.success_rate}%) | Время: ${res.execution_time_ms}мс`,
                                'info'
                            );
                        }

                        // 3. Выводим детали по каждому тесту (кратко)
                        if (res.test_details) {
                            res.test_details.forEach(test => {
                                const icon = test.status === 'passed' ? '●' : '○';
                                const colorClass = test.status === 'passed' ? 'success' : 'error';
                                this.addConsoleMessage(`${icon} ${test.name}: ${test.message}`, colorClass);
                            });
                        }

                        // 4. Выводим print() пользователя, если они были
                        if (res.user_print) {
                            this.addConsoleMessage(`\n--- Вывод консоли ---`, 'info');
                            this.addConsoleMessage(res.user_print, 'output');
                        }

                    } else {
                        // Ошибки компиляции или таймауты
                        this.addConsoleMessage(`❌ ${res.error || 'Ошибка выполнения'}`, 'error');
                    }
                    this.resetRunButton();
                } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
                    clearInterval(checkInterval);
                    this.addConsoleMessage(`❌ Ошибка выполнения задачи (Celery)`, 'error');
                    this.resetRunButton();
                }
            },
            error: () => {
                clearInterval(checkInterval);
                this.addConsoleMessage(`❌ Ошибка связи с сервером`, 'error');
                this.resetRunButton();
            }
        });
    }, 700); // Опрос чуть реже, чтобы не спамить сервер
}

        resetRunButton() {
            const runBtn = $('#tabRunBtn_' + this.tabId);
            runBtn.prop('disabled', false);
            runBtn.html('<i class="fas fa-play"></i> Запустить');
        }

        addConsoleMessage(message, type = 'info') {
            const consoleOutput = $('#consoleOutput_' + this.tabId);
            if (!consoleOutput.length) return;

            const timestamp = new Date().toLocaleTimeString().slice(0, 5);
            const messageClass = type === 'error' ? 'error' :
                type === 'success' ? 'success' :
                    type === 'warning' ? 'warning' :
                        type === 'output' ? 'output' : 'info';

            const messageLine = `<div class="console-line ${messageClass}">` +
                `${message}` +
                `</div>`;

            consoleOutput.append(messageLine);
            consoleOutput.scrollTop(consoleOutput[0].scrollHeight);
        }

        clearConsole() {
            // Полностью очищаем консоль (по кнопке)
            $('#consoleOutput_' + this.tabId).empty();
            this.addConsoleMessage("Консоль очищена", "info");
            // Не сбрасываем высоту!
        }

        autoSave() {
            if (!this.monacoEditor) return;
            const content = this.monacoEditor.getValue();

            try {
                const tabs = JSON.parse(localStorage.getItem('codeMonkeyTabs') || '{}');
                tabs[this.tabId] = {
                    id: this.tabId,
                    name: this.name,
                    content: content,
                    lastModified: new Date().toISOString(),
                    stats: this.stats,
                    functions: this.functions,
                    classes: this.classes
                };
                localStorage.setItem('codeMonkeyTabs', JSON.stringify(tabs));
            } catch (e) {
                console.error('Error saving tab:', e);
            }
        }

        formatCode() {
            if (!this.monacoEditor) return;

            try {
                // Используем форматирование Monaco Editor
                this.monacoEditor.getAction('editor.action.formatDocument').run();

                this.updateAllStats();
                this.updateStructureSidebar();
                this.hideErrorsModal();
                this.addConsoleMessage("Код отформатирован", "success");
            } catch (error) {
                console.error('Error formatting code:', error);
                this.addConsoleMessage("Ошибка при форматировании кода", "error");
            }
        }

        createTask() {
            // Собираем данные из формы
            const taskTitle = $('#taskTitle_' + this.tabId).val();
            const taskDescription = $('#taskDescription_' + this.tabId).val();
            const code = this.monacoEditor.getValue();

            // Собираем ограничения
            const constraints = {
                maxLines: $('#limitLines_' + this.tabId).is(':checked') ? parseInt($('#maxLines_' + this.tabId).val()) : null,
                maxLineLength: $('#limitLineLength_' + this.tabId).is(':checked') ? parseInt($('#maxLineLength_' + this.tabId).val()) : null,
                maxChars: $('#limitChars_' + this.tabId).is(':checked') ? parseInt($('#maxChars_' + this.tabId).val()) : null,
                maxFunctions: $('#limitFunctions_' + this.tabId).is(':checked') ? parseInt($('#maxFunctions_' + this.tabId).val()) : null,
                maxClasses: $('#limitClasses_' + this.tabId).is(':checked') ? parseInt($('#maxClasses_' + this.tabId).val()) : null
            };

            // Собираем примеры
            const examples = [];
            $('.io-example').each((index, element) => {
                const exampleNum = index + 1;
                const input = $('#inputExample' + exampleNum + '_' + this.tabId).val();
                const output = $('#outputExample' + exampleNum + '_' + this.tabId).val();

                if (input || output) {
                    examples.push({
                        input: input,
                        output: output
                    });
                }
            });

            // Уровень сложности
            const difficulty = $('input[name="difficulty_' + this.tabId + '"]:checked').val();

            // Формируем объект задачи
            const task = {
                id: 'task_' + Date.now(),
                title: taskTitle,
                description: taskDescription,
                code: code,
                constraints: constraints,
                forbiddenWords: this.taskData.forbiddenWords,
                examples: examples,
                tags: this.taskData.tags,
                difficulty: difficulty,
                created: new Date().toISOString(),
                stats: {
                    lines: code.split('\n').length,
                    chars: code.length,
                    nonSpaceChars: code.replace(/\s/g, '').length,
                    functions: this.functions.length,
                    classes: this.classes.length
                }
            };

            // Сохраняем задачу в localStorage
            this.saveTask(task);

            // Закрываем модальное окно
            this.hideTaskModal();

            // Показываем уведомление
            this.addConsoleMessage(`Задача "${taskTitle}" успешно создана!`, 'success');

            return task;
        }

        saveTask(task) {
            console.log("saveTask", task)
            try {
                const tasks = JSON.parse(localStorage.getItem('codeMonkeyTasks') || '[]');
                tasks.push(task);
                localStorage.setItem('codeMonkeyTasks', JSON.stringify(tasks));
                return true;
            } catch (e) {
                console.error('Error saving task:', e);
                this.addConsoleMessage('Ошибка при сохранении задачи', 'error');
                return false;
            }
        }
    };
}