if (typeof window.TaskSearch === 'undefined') {
    window.TaskSearch = class TaskSearch {
        constructor(tabId) {
            this.tabId = tabId;
            this.searchInput = document.getElementById(`taskSearchInput_${tabId}`);
            this.taskIdInput = document.getElementById(`selectedTaskId_${tabId}`);
            this.resultsContainer = document.getElementById(`taskResults_${tabId}`);
            this.clearBtn = document.getElementById(`taskClearBtn_${tabId}`);
            this.searchTimeout = null;
            this.selectedTask = null;

            // Проверяем существование элементов
            if (!this.searchInput) {
                console.error(`Элемент taskSearchInput_${tabId} не найден`);
                return;
            }

            this.init();
        }

        init() {
            this.bindEvents();
            // Проверяем, есть ли сохраненная задача для этого таба
            this.loadSelectedTaskFromStorage();
        }

        bindEvents() {
            const self = this;

            // Поиск при вводе
            this.searchInput.addEventListener('input', function () {
                clearTimeout(self.searchTimeout);
                const query = this.value.trim();

                if (query.length === 0) {
                    self.clearBtn.style.display = 'none';
                    self.hideResults();
                    // Если поле очищено вручную, сбрасываем выбранную задачу
                    if (self.selectedTask && self.searchInput.value === '') {
                        self.clearTaskSelection();
                    }
                    return;
                }

                self.clearBtn.style.display = 'block';

                self.searchTimeout = setTimeout(() => {
                    self.searchTasks(query);
                }, 300);
            });

            // Очистка поиска
            if (this.clearBtn) {
                this.clearBtn.addEventListener('click', function () {
                    self.clearTaskSelection();
                });
            }

            // Клик вне результатов
            document.addEventListener('click', function (e) {
                if (!e.target.closest(`#taskSearchInput_${self.tabId}`) &&
                    !e.target.closest(`#taskResults_${self.tabId}`)) {
                    self.hideResults();
                }
            });

            // Выбор задачи из результатов
            if (this.resultsContainer) {
                this.resultsContainer.addEventListener('click', function (e) {
                    const resultItem = e.target.closest('.task-result-item');
                    if (resultItem) {
                        const taskId = resultItem.dataset.taskId;
                        if (taskId) {
                            self.selectTaskById(taskId);
                        }
                    }
                });
            }
        }

        async searchTasks(query) {
            if (!this.resultsContainer) return;

            this.showLoading();

            try {
                const response = await fetch(`/code_cup/editor/tasks/search/?q=${encodeURIComponent(query)}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                if (data.tasks && data.tasks.length > 0) {
                    this.showResults(data.tasks);
                } else {
                    this.showNoResults();
                }
            } catch (error) {
                console.error('Ошибка поиска задач:', error);
                this.showError();
            }
        }

        showLoading() {
            if (!this.resultsContainer) return;

            this.resultsContainer.innerHTML = `
                <div class="search-loading">
                    <i class="fas fa-spinner fa-spin"></i> Поиск задач...
                </div>
            `;
            this.resultsContainer.style.display = 'block';
        }

        showResults(tasks) {
            if (!this.resultsContainer) return;

            const html = tasks.map(task => `
                <div class="task-result-item"
                     data-task-id="${task.id}">
                    <div class="task-result-header">
                        <span class="task-result-title">${task.name}</span>
                        <span class="task-difficulty ${task.level}">
                            ${this.getDifficultyText(task.level)}
                        </span>
                    </div>
                    <div class="task-result-meta">
                        <span class="task-category">${task.category_display || ''}</span>
                        <span class="task-number">#${task.num}</span>
                    </div>
                    <div class="task-result-description">
                        ${this.truncateDescription(task.description, 100)}
                    </div>
                </div>
            `).join('');

            this.resultsContainer.innerHTML = html;
            this.resultsContainer.style.display = 'block';
        }

        showNoResults() {
            if (!this.resultsContainer) return;

            this.resultsContainer.innerHTML = `
                <div class="search-no-results">
                    <i class="fas fa-search"></i> Задачи не найдены
                </div>
            `;
            this.resultsContainer.style.display = 'block';
        }

        showError() {
            if (!this.resultsContainer) return;

            this.resultsContainer.innerHTML = `
                <div class="search-error">
                    <i class="fas fa-exclamation-triangle"></i> Ошибка при поиске задач
                </div>
            `;
            this.resultsContainer.style.display = 'block';
        }

        hideResults() {
            if (this.resultsContainer) {
                this.resultsContainer.style.display = 'none';
            }
        }

        async selectTaskById(taskId) {
            try {
                // Получаем полную информацию о задаче
                const response = await fetch(`/code_cup/editor/tasks/${taskId}/details/`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const task = await response.json();

                // Сохраняем выбранную задачу
                this.selectedTask = task;

                // Сохраняем в полях ввода
                this.saveTaskToInputs(task);

                // Сохраняем в localStorage
                this.saveSelectedTaskToStorage();

                // Скрываем результаты поиска
                this.hideResults();

                // Загружаем код в редактор
                if (window.codeMonkeyInstances && window.codeMonkeyInstances[this.tabId]) {
                    const editor = window.codeMonkeyInstances[this.tabId];
                    if (editor && editor.monacoEditor) {
                        // Сначала очищаем
                        editor.monacoEditor.setValue("");
                        // Затем устанавливаем новое значение
                        editor.monacoEditor.setValue(`"""\n${task.name}\n${task.description || ''}\n"""\n\n${task.code_template || ''}`);
                    }
                }

                console.log(`Задача "${task.name}" выбрана для таба ${this.tabId}`);

            } catch (error) {
                console.error('Ошибка загрузки задачи:', error);
            }
        }

        saveTaskToInputs(task) {
            // Сохраняем название задачи в поле ввода
            if (this.searchInput) {
                this.searchInput.value = task.name;
                this.searchInput.setAttribute('data-task-id', task.id);
            }

            // Сохраняем ID задачи в скрытом поле
            if (this.taskIdInput) {
                this.taskIdInput.value = task.id;
            }

            // Показываем кнопку очистки
            if (this.clearBtn) {
                this.clearBtn.style.display = 'block';
            }
        }

        clearTaskSelection() {
            // Сбрасываем выбранную задачу
            this.selectedTask = null;

            // Очищаем поля ввода
            if (this.searchInput) {
                this.searchInput.value = '';
                this.searchInput.removeAttribute('data-task-id');
            }

            if (this.taskIdInput) {
                this.taskIdInput.value = '';
            }

            // Скрываем кнопку очистки
            if (this.clearBtn) {
                this.clearBtn.style.display = 'none';
            }

            // Скрываем результаты поиска
            this.hideResults();

            // Очищаем localStorage
            this.removeSelectedTaskFromStorage();

            console.log(`Выбор задачи сброшен для таба ${this.tabId}`);
        }

        getSelectedTaskId() {
            // Получаем ID выбранной задачи из поля ввода
            if (this.searchInput && this.searchInput.hasAttribute('data-task-id')) {
                return this.searchInput.getAttribute('data-task-id');
            }
            return this.taskIdInput ? this.taskIdInput.value : null;
        }

        getSelectedTaskName() {
            // Получаем название выбранной задачи из поля ввода
            return this.searchInput ? this.searchInput.value : '';
        }

        hasUnsavedChanges() {
            // Проверяем, есть ли несохраненные изменения в редакторе
            if (window.codeMonkeyInstances && window.codeMonkeyInstances[this.tabId]) {
                const editor = window.codeMonkeyInstances[this.tabId];
                return editor.hasUnsavedChanges ? editor.hasUnsavedChanges() : false;
            }
            return false;
        }

        saveSelectedTaskToStorage() {
            if (this.selectedTask) {
                try {
                    const key = `selected_task_${this.tabId}`;
                    localStorage.setItem(key, JSON.stringify({
                        id: this.selectedTask.id,
                        name: this.selectedTask.name,
                        timestamp: Date.now()
                    }));
                } catch (e) {
                    console.warn('Не удалось сохранить задачу в localStorage:', e);
                }
            }
        }

        loadSelectedTaskFromStorage() {
            try {
                const key = `selected_task_${this.tabId}`;
                const saved = localStorage.getItem(key);

                if (saved) {
                    const savedTask = JSON.parse(saved);
                    // Проверяем, не слишком ли старая запись (больше 24 часов)
                    if (Date.now() - savedTask.timestamp < 24 * 60 * 60 * 1000) {
                        // Загружаем информацию о задаче
                        this.selectTaskById(savedTask.id);
                    } else {
                        // Удаляем старую запись
                        localStorage.removeItem(key);
                    }
                }
            } catch (e) {
                console.warn('Не удалось загрузить задачу из localStorage:', e);
            }
        }

        removeSelectedTaskFromStorage() {
            try {
                const key = `selected_task_${this.tabId}`;
                localStorage.removeItem(key);
            } catch (e) {
                console.warn('Не удалось удалить задачу из localStorage:', e);
            }
        }

        getSelectedTask() {
            return this.selectedTask;
        }

        hasSelectedTask() {
            return this.selectedTask !== null;
        }

        getDifficultyText(level) {
            const difficultyMap = {
                'junior': 'Начинающий',
                'middle': 'Средний',
                'hard': 'Сложный',
                'expert': 'Эксперт',
                'easy': 'Легкая',
                'medium': 'Средняя'
            };
            return difficultyMap[level] || level;
        }

        truncateDescription(text, maxLength) {
            if (!text) return 'Нет описания';
            if (text.length <= maxLength) return text;

            return text.substring(0, maxLength) + '...';
        }
    }
}
