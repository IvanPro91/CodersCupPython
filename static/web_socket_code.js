class SocketIOCode {
    constructor(currentRoomId) {
        this.socket = null;
        this.currentRoomId = currentRoomId;
    }

    connect() {
        try {
            const token = localStorage.getItem('accessToken');
            this.socket = io(`${location.origin}`, {
                transports: ['websocket'],
                auth: {token: token},
                reconnection: true,
                reconnectionAttempts: 5
            });

            // Socket.IO события отличаются от WebSocket
            this.socket.on('connect', () => {
                console.log('✅ Socket.IO подключен');
            });

            this.socket.on('message', (data) => {
                console.log('Получено:', data);
            });

            this.socket.on('disconnect', (reason) => {
                console.log('Socket.IO отключен:', reason);
            });

            this.socket.on('connect_error', (error) => {
                console.error('Ошибка подключения Socket.IO:', error);
            });

            return new Promise((resolve, reject) => {
                this.socket.on('connect', resolve);
                this.socket.on('connect_error', reject);
            });
        } catch (err) {
            console.error('Ошибка при подключении к Socket.IO:', err);
            throw err;
        }
    }

    async GetUserTabs() {
        if (!this.socket || !this.socket.connected) {
            console.error('Socket не подключен');
            return;
        }

        return new Promise((resolve, reject) => {
            this.socket.emit('get_user_tabs', {
                room_id: this.currentRoomId,
                timestamp: new Date().toISOString()
            }, (response) => {
                if (response && response.status === 'success') {
                    console.log('Данные получены:', response);
                    resolve(response);
                } else {
                    console.error('Ошибка сервера:', response);
                    reject(response);
                }
            });
        });
    }

    async send(event, data){
        return new Promise((resolve, reject) => {
            this.socket.emit(event, data, (response) => {
                if (response && response.status === 'success') {
                    console.log('Данные получены:', response);
                    resolve(response);
                } else {
                    console.error('Ошибка сервера:', response);
                    reject(response);
                }
            });
        });
    }
}