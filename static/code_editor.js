class CodeEditor {
    constructor(socket) {
        this.socket = socket;
        this.tabsContainer = $('#tabsContainer');
        this.editorContainer = $('#editorContainer');
    }

    /**
     * Отображает на форме tabs которые пользователь создал.
     */
    renderTabs = async () => {
        const tabsContainer = this.tabsContainer
        tabsContainer.html("");

        try {
            const user_tabs = await this.socket.GetUserTabs();
            let list_user_tabs = $(user_tabs.user_tabs)

            // Создаем элементы табов
            list_user_tabs.each((index, element) => {
                this.createTabElement(element, tabsContainer);
            });

            // Активируем первый таб если есть
            if (list_user_tabs.length > 0) {
                const firstTabId = list_user_tabs[0].pk || list_user_tabs[0].id;
                this.switchTab(firstTabId);
            }
        } catch (error) {
            console.error('Ошибка при загрузке табов:', error);
            this.showError(tabsContainer, error);
        }
    }

    addNewTab = (info_tab) => {
        const tabsContainer = this.tabsContainer
        this.createTabElement(info_tab, tabsContainer);
        this.switchTab(info_tab.pk);
    }

    createTabElement = (tab, container) => {
        const tabElement = document.createElement('div');
        tabElement.className = `tab`; // dirty
        const tabId = tab.pk || tab.id;
        tabElement.dataset.tabId = tabId;

        const { icon, badge } = this.getTabStyle(tab.type_tab);

        tabElement.innerHTML = `
            <i class="fas ${icon} tab-icon"></i>
            <span class="tab-name">${tab.name || 'Без названия'}</span>
            ${badge}
            <i class="fas fa-times tab-close"></i>
        `;

        // Обработчик клика на таб
        tabElement.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab-close')) {
                this.switchTab(tabId);
            }
        });

        // Обработчик закрытия таба
        tabElement.querySelector('.tab-close').addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleTabClose(tabId);
        });

        container.append(tabElement);
    }

    getTabStyle = (type) => {
        let icon = 'fa-file-code';
        let badge = '';

        switch(type) {
            case 'duel':
                icon = 'fa-user-friends';
                badge = '<span class="tab-badge">2</span>';
                break;
            case 'collaborative':
                icon = 'fa-users';
                badge = '<span class="tab-badge">2</span>';
                break;
        }

        return { icon, badge };
    }

    handleTabClose = (tabId) => {
        console.log("Закрытие таба:", tabId);
        this.socket.send("close_user_tab", {"close_tab": tabId});
        $(`[data-tab-id="${tabId}"]`).remove()
    }

    switchTab = (tabId) => {
        console.log("Переключение на таб:", tabId);
        this.renderActiveTab(tabId);
    }

    renderActiveTab = (tabId) => {
        $('.tab').removeClass("active");
        $(`.tab[data-tab-id="${tabId}"]`).addClass("active");
        // Можно загрузить содержимое таба здесь
        this.loadPageContentEditor(this.editorContainer, tabId)

    }

    showError = (container, error) => {
        container.html(`
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i>
                Ошибка: ${error.message || 'Неизвестная ошибка'}
            </div>
        `);
    }

    loadPageContentEditor = (container, tabId) => {
        container.html('')

        $.ajax({
            url: `${location.origin}/code_cup/editor/get_editor/${tabId}/`,
            type: 'GET',
            success: function(response) {
                $(container).html(response);
            },
            error: function(xhr, status, error) {
                console.error('Ошибка:', error);
                console.log('Статус:', xhr.status);
                console.log('Ответ сервера:', xhr.responseText);
            }
        });
    }
}