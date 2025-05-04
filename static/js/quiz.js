/**
 * Quiz.js - Versão híbrida com Socket.IO e fallback HTTP
 * Script para gerenciar o quiz usando Socket.IO com fallback para requisições HTTP
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elementos do DOM
    const questionContainer = document.getElementById('questionContainer');
    const resultContainer = document.getElementById('resultContainer');
    const currentQuestionNum = document.getElementById('currentQuestionNum');
    const totalQuestions = document.getElementById('totalQuestions');
    const timer = document.getElementById('timer');
    const questionText = document.getElementById('questionText');
    const optionA = document.getElementById('optionA');
    const optionB = document.getElementById('optionB');
    const optionC = document.getElementById('optionC');
    const optionD = document.getElementById('optionD');
    const correctAnswerText = document.getElementById('correctAnswerText');
    const explanationText = document.getElementById('explanationText');
    const rankList = document.getElementById('rankList');
    const chatContainer = document.getElementById('chatContainer');
    const countingVotesElement = document.getElementById('countingVotes');
    const quizOverlay = document.getElementById('quizOverlay');
    const totalVotesElement = document.getElementById('totalVotes');
    const correctVotesElement = document.getElementById('correctVotes');
    const correctPercentageElement = document.getElementById('correctPercentage');
    const quizStatusElement = document.getElementById('quizStatus');

    // Variáveis globais
    let socket = null;
    let quizRunning = false;
    let fallbackErrorCount = 0;
    let serverHealthy = true;
    
    // Variáveis para persistência local do estado do quiz
    let currentQuestionData = null;
    let lastQuestionNumber = 0;
    let quizState = {
        currentQuestion: null,
        questionNumber: 0,
        totalQuestions: 0,
        votes: {},
        lastUpdateTime: 0
    };
    
    // Função para salvar o estado do quiz localmente
    function saveQuizState() {
        try {
            // Atualizar o timestamp antes de salvar
            quizState.lastUpdateTime = Date.now();
            localStorage.setItem('quizState', JSON.stringify(quizState));
            console.log('Estado do quiz salvo localmente:', quizState);
        } catch (e) {
            console.error('Erro ao salvar estado do quiz:', e);
        }
    }
    
    // Função para carregar o estado do quiz do armazenamento local
    function loadQuizState() {
        try {
            const savedState = localStorage.getItem('quizState');
            if (savedState) {
                quizState = JSON.parse(savedState);
                console.log('Estado do quiz carregado do armazenamento local:', quizState);
                return true;
            }
        } catch (e) {
            console.error('Erro ao carregar estado do quiz:', e);
        }
        return false;
    }
    let countdownInterval = null;
    let currentTime = 0;
    let socketConnected = false;
    let usingFallback = false;
    let lastChatTimestamp = 0;
    let fallbackPollingInterval = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 3;

    // Inicializar
    init();
    
    function init() {
        console.log('Inicializando quiz...');
        
        // Tentar conectar via Socket.IO
        connectSocket();
        
        // Adicionar botões de controle
        addControlButtons();
        
        // Carregar ranking inicial
        loadRanking();
        
        // Verificar se há um estado salvo do quiz
        setTimeout(function() {
            // Tentar restaurar o estado anterior do quiz após um pequeno delay
            // para garantir que tudo foi carregado
            const savedState = loadQuizState();
            if (savedState && savedState.currentQuestion && savedState.questionNumber > 0) {
                console.log('Restaurando estado anterior do quiz');
                // Verificar se o estado é recente (menos de 5 minutos)
                const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
                if (savedState.lastUpdateTime > fiveMinutesAgo) {
                    hideResults();
                    showQuestion(
                        savedState.currentQuestion,
                        savedState.questionNumber,
                        savedState.totalQuestions
                    );
                }
            }
        }, 1000);
    }
    
    // Conectar ao Socket.IO com fallback para HTTP
    function connectSocket() {
        try {
            console.log('Tentando conectar ao Socket.IO...');
            
            // Limpar conexão anterior se existir
            if (socket) {
                try {
                    socket.disconnect();
                    socket.close();
                } catch (e) {
                    console.warn('Erro ao limpar conexão anterior:', e);
                }
                socket = null;
            }
            
            // Usar a função io já configurada pelo socket-config.js
            socket = io();
            
            // Adicionar tratamento de erro para problemas de transporte
            socket.on('connect_error', function(error) {
                console.error('Erro de conexão Socket.IO:', error);
                
                // Verificar se é um erro de transporte
                if (error && error.type === 'TransportError') {
                    console.log('Erro de transporte detectado, tentando reconectar com configuração alternativa');
                    
                    // Tentar reconectar com configuração alternativa
                    if (socket) {
                        socket.disconnect();
                        
                        // Tentar novamente com apenas polling
                        setTimeout(function() {
                            try {
                                socket = io(window.location.origin, {
                                    transports: ['polling'],
                                    upgrade: false,
                                    forceNew: true
                                });
                                setupSocketListeners();
                            } catch (e) {
                                console.error('Erro ao tentar reconectar com configuração alternativa:', e);
                                activateFallbackMode();
                            }
                        }, 1000);
                    }
                }
            });
            
            // Iniciar um ping periódico para manter a conexão ativa
            let pingInterval = null;
            
            // Quando conectar, iniciar o ping periódico
            socket.on('connect', function() {
                console.log('Socket.IO conectado com sucesso, iniciando ping periódico');
                socketConnected = true;
                reconnectAttempts = 0;
                
                // Limpar intervalo anterior se existir
                if (pingInterval) {
                    clearInterval(pingInterval);
                }
                
                // Iniciar ping a cada 8 segundos (menor que o pingTimeout do servidor)
                pingInterval = setInterval(function() {
                    if (socket && socket.connected) {
                        socket.emit('ping_server', {
                            timestamp: Date.now(),
                            questionNumber: quizState.questionNumber
                        });
                        console.log('Ping enviado para manter conexão ativa');
                    } else {
                        // Se não estiver conectado, limpar o intervalo
                        clearInterval(pingInterval);
                    }
                }, 8000);
            });
            
            // Quando desconectar, limpar o intervalo de ping
            socket.on('disconnect', function(reason) {
                console.log('Socket.IO desconectado. Motivo:', reason);
                socketConnected = false;
                
                if (pingInterval) {
                    clearInterval(pingInterval);
                    pingInterval = null;
                }
                
                // Se a desconexão não foi intencional, tentar reconectar
                if (reason !== 'io client disconnect' && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    console.log('Tentando reconectar automaticamente...');
                    reconnectAttempts++;
                    
                    // Tentar reconectar após um pequeno delay
                    setTimeout(function() {
                        connectSocket();
                    }, 1000);
                } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                    console.log('Número máximo de tentativas de reconexão atingido. Ativando modo fallback.');
                    activateFallbackMode();
                }
            });
            
            // Configurar socket listeners
            setupSocketListeners();
            
            // Verificar se a conexão foi estabelecida após um tempo
            setTimeout(function() {
                if (!socketConnected && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    console.log('Socket.IO não conectou. Tentando novamente...');
                    reconnectAttempts++;
                    connectSocket();
                } else if (!socketConnected) {
                    console.log('Socket.IO falhou após várias tentativas. Usando fallback HTTP.');
                    activateFallbackMode();
                }
            }, 5000);
        } catch (error) {
            console.error('Erro ao conectar Socket.IO:', error);
            activateFallbackMode();
        }
    }
    
    // Ativar modo de fallback com requisições HTTP
    function activateFallbackMode() {
        // Verificar se já está em modo fallback
        if (usingFallback) {
            console.log('Já está em modo fallback. Ignorando.');
            return;
        }
        
        console.log('Ativando modo fallback com requisições HTTP...');
        usingFallback = true;
        
        // Desconectar Socket.IO se estiver conectado
        if (socket) {
            try {
                socket.disconnect();
                console.log('Socket.IO desconectado para evitar conflitos com fallback.');
            } catch (e) {
                console.error('Erro ao desconectar Socket.IO:', e);
            }
        }
        
        // Adicionar notificação de fallback
        addFallbackNotice();
        
        // Iniciar polling para atualizações
        startFallbackPolling();
        
        // Adicionar mensagem de sistema no chat
        addSystemMessage('Modo de compatibilidade ativado. Usando requisições HTTP.');
        
        console.log('Modo fallback ativado com sucesso. Usando requisições HTTP.');
        
        // Tentar voltar para Socket.IO após 30 segundos
        setTimeout(function() {
            if (usingFallback) {
                console.log('Tentando voltar para Socket.IO após 30 segundos em fallback...');
                attemptSocketReconnection();
            }
        }, 30000);
    }
    
    // Tentar reconectar ao Socket.IO após estar em modo fallback
    function attemptSocketReconnection() {
        console.log('Tentando reconectar ao Socket.IO após fallback...');
        
        // Criar nova conexão Socket.IO
        try {
            const tempSocket = io();
            
            // Verificar se conecta em 5 segundos
            let connected = false;
            
            tempSocket.on('connect', function() {
                console.log('Reconexão ao Socket.IO bem-sucedida após fallback!');
                connected = true;
                
                // Desativar modo fallback
                if (usingFallback) {
                    usingFallback = false;
                    
                    // Parar polling HTTP
                    if (fallbackPollingInterval) {
                        clearInterval(fallbackPollingInterval);
                        fallbackPollingInterval = null;
                    }
                    
                    // Remover notificação de fallback
                    const fallbackNotice = document.getElementById('fallbackNotice');
                    if (fallbackNotice) {
                        fallbackNotice.remove();
                    }
                    
                    // Usar o novo socket
                    socket = tempSocket;
                    socketConnected = true;
                    
                    // Configurar listeners
                    setupSocketListeners();
                    
                    // Adicionar mensagem de sistema
                    addSystemMessage('Conexão em tempo real restaurada!');
                    
                    console.log('Voltou para modo Socket.IO após fallback.');
                }
            });
            
            // Verificar se conectou após 5 segundos
            setTimeout(function() {
                if (!connected) {
                    console.log('Falha ao reconectar ao Socket.IO após fallback. Permanecendo em modo fallback.');
                    tempSocket.disconnect();
                    
                    // Tentar novamente após 60 segundos
                    setTimeout(attemptSocketReconnection, 60000);
                }
            }, 5000);
            
        } catch (error) {
            console.error('Erro ao tentar reconectar ao Socket.IO após fallback:', error);
        }
    }
    
    // Adicionar notificação de fallback
    function addFallbackNotice() {
        // Verificar se a notificação já existe
        if (document.getElementById('fallbackNotice')) {
            return;
        }
        
        const fallbackNotice = document.createElement('div');
        fallbackNotice.id = 'fallbackNotice';
        fallbackNotice.className = 'fallback-notice';
        fallbackNotice.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Modo de compatibilidade ativado';
        
        // Adicionar ao DOM - verificar se o elemento existe
        if (quizStatusElement && quizStatusElement.parentNode) {
            quizStatusElement.parentNode.insertBefore(fallbackNotice, quizStatusElement);
        } else if (questionContainer && questionContainer.parentNode) {
            questionContainer.parentNode.insertBefore(fallbackNotice, questionContainer);
        }
    }
    
    // Iniciar polling para atualizações no modo fallback com tratamento de erros aprimorado
    function startFallbackPolling() {
        // Parar polling anterior se existir
        if (fallbackPollingInterval) {
            clearInterval(fallbackPollingInterval);
        }
        
        // Resetar contador de erros
        fallbackErrorCount = 0;
        
        // Verificar status inicial
        checkQuizStatus();
        
        // Configurar polling a cada 3 segundos (aumentado para reduzir carga no servidor)
        fallbackPollingInterval = setInterval(function() {
            // Verificar se tivemos muitos erros consecutivos
            if (fallbackErrorCount > 5) {
                console.log('Muitos erros no modo fallback. Reduzindo frequência de polling...');
                // Reduzir frequência de polling temporariamente
                clearInterval(fallbackPollingInterval);
                setTimeout(function() {
                    // Reiniciar polling com frequência normal após pausa
                    fallbackErrorCount = 0;
                    startFallbackPolling();
                }, 10000);  // Pausa de 10 segundos
                return;
            }
            
            // Verificar status do quiz
            checkQuizStatus();
            
            if (quizRunning) {
                // Escalonar as requisições para não sobrecarregar o servidor
                setTimeout(function() { getVotes(); }, 500);
                setTimeout(function() { getChatMessages(); }, 1000);
            }
        }, 3000);
        
        // Carregar ranking a cada 10 segundos (aumentado para reduzir carga no servidor)
        setInterval(function() {
            if (fallbackErrorCount < 3) {  // Só atualizar ranking se não estiver tendo muitos erros
                getRanking();
            }
        }, 10000);
    }
    
    // Verificar status do quiz via HTTP com tratamento de erro aprimorado
    function checkQuizStatus() {
        const baseUrl = window.location.origin;
        fetch(`${baseUrl}/api/quiz/status-http`)
            .then(response => {
                // Verificar se a resposta é válida antes de tentar processar como JSON
                if (!response.ok) {
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data && data.success) {
                    quizRunning = data.quiz_running;
                    updateUI();
                }
            })
            .catch(error => {
                console.error('Erro ao verificar status:', error);
                // Tentar reconectar ao Socket.IO se o fallback também estiver falhando
                if (fallbackErrorCount === undefined) fallbackErrorCount = 0;
                fallbackErrorCount++;
                
                // Se tivermos muitos erros consecutivos no modo fallback, tentar voltar para Socket.IO
                if (fallbackErrorCount > 3 && usingFallback) {
                    console.log('Múltiplos erros no modo fallback. Tentando voltar para Socket.IO...');
                    // Limpar o polling do fallback
                    if (fallbackPollingInterval) {
                        clearInterval(fallbackPollingInterval);
                        fallbackPollingInterval = null;
                    }
                    // Tentar reconectar via Socket.IO
                    usingFallback = false;
                    connectSocket();
                }
            });
    }
    
    // Obter votos via HTTP com tratamento de erro aprimorado
    function getVotes() {
        // Se tivermos muitos erros, pular esta requisição
        if (fallbackErrorCount > 3) {
            console.log('Muitos erros recentes, pulando requisição de votos');
            return;
        }
        
        const baseUrl = window.location.origin;
        fetch(`${baseUrl}/api/quiz/votes-http`)
            .then(response => {
                if (!response.ok) {
                    fallbackErrorCount++;
                    throw new Error(`Erro HTTP: ${response.status}`);
                }
                // Reset do contador de erros em caso de sucesso
                fallbackErrorCount = 0;
                return response.json();
            })
            .then(data => {
                if (data && data.success) {
                    updateAllVotes(data.votes);
                }
            })
            .catch(error => {
                console.error('Erro ao obter votos:', error);
                fallbackErrorCount++;
                
                // Se tivermos muitos erros consecutivos, tentar voltar para Socket.IO
                if (fallbackErrorCount > 5 && usingFallback) {
                    console.log('Problemas persistentes com o modo fallback. Tentando voltar para Socket.IO...');
                    usingFallback = false;
                    connectSocket();
                }
            });
    }
    
    // Obter mensagens do chat via HTTP
    function getChatMessages() {
        const baseUrl = window.location.origin;
        fetch(`${baseUrl}/api/quiz/chat-http?since=${lastChatTimestamp}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        addChatMessage(msg.author, msg.message);
                        
                        // Atualizar o timestamp da última mensagem
                        if (msg.timestamp > lastChatTimestamp) {
                            lastChatTimestamp = msg.timestamp;
                        }
                    });
                }
            })
            .catch(error => console.error('Erro ao obter mensagens do chat:', error));
    }
    
    // Obter ranking via HTTP
    function getRanking() {
        const baseUrl = window.location.origin;
        fetch(`${baseUrl}/api/ranking-http`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateRanking(data.ranking);
                }
            })
            .catch(error => console.error('Erro ao obter ranking:', error));
    }
    
    // Adicionar botões de controle ao quiz
    function addControlButtons() {
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'quiz-controls';
        
        const startButton = document.createElement('button');
        startButton.textContent = 'Iniciar Quiz';
        startButton.className = 'btn-start';
        startButton.onclick = startQuiz;
        
        const stopButton = document.createElement('button');
        stopButton.textContent = 'Parar Quiz';
        stopButton.className = 'btn-stop';
        stopButton.onclick = stopQuiz;
        
        controlsDiv.appendChild(startButton);
        controlsDiv.appendChild(stopButton);
        
        // Adicionar ao DOM
        if (quizStatusElement) {
            quizStatusElement.parentNode.insertBefore(controlsDiv, quizStatusElement);
        }
    }
    
    // Configurar socket listeners
    function setupSocketListeners() {
        if (!socket) return;
        
        // Evento de conexão
        socket.on('connect', function() {
            console.log('Socket.IO conectado com sucesso');
            socketConnected = true;
            reconnectAttempts = 0; // Resetar tentativas de reconexão
            
            // Remover notificação de fallback se existir
            const fallbackNotice = document.getElementById('fallbackNotice');
            if (fallbackNotice) {
                fallbackNotice.remove();
            }
            
            // Adicionar mensagem de sistema no chat
            addSystemMessage('Conectado ao servidor em tempo real');
            
            // Se estava usando fallback, desativar
            if (usingFallback) {
                usingFallback = false;
                if (fallbackPollingInterval) {
                    clearInterval(fallbackPollingInterval);
                    fallbackPollingInterval = null;
                }
                console.log('Modo fallback desativado. Usando Socket.IO.');
            }
            
            // Solicitar status atual do quiz
            socket.emit('get_quiz_status');
            
            // Solicitar ranking
            socket.emit('get_ranking');
        });
        
        // Evento de desconexão
        socket.on('disconnect', function(reason) {
            console.log('Socket.IO desconectado:', reason);
            socketConnected = false;
            
            // Salvar o estado atual do quiz antes de tentar reconectar
            if (quizState.currentQuestion) {
                saveQuizState();
                console.log('Estado do quiz salvo antes da reconexão');
            }
            
            // Adicionar mensagem de sistema no chat
            addSystemMessage('Desconectado do servidor: ' + reason);
            
            // Lidar com diferentes tipos de desconexão com estratégia mais agressiva
            if (reason === 'io server disconnect' || reason === 'transport close' || reason === 'ping timeout') {
                // O servidor desconectou explicitamente ou houve um problema de transporte
                console.log('Problema de conexão detectado. Tentando reconectar imediatamente...');
                addSystemMessage('Reconectando ao servidor...');
                
                // Tentar reconectar imediatamente
                if (socket) {
                    // Forçar desconexão antes de reconectar para limpar o estado
                    try {
                        socket.disconnect();
                    } catch (e) {
                        console.error('Erro ao desconectar socket:', e);
                    }
                    
                    // Pequena pausa antes de reconectar
                    setTimeout(function() {
                        try {
                            socket.connect();
                            console.log('Tentativa de reconexão iniciada');
                        } catch (e) {
                            console.error('Erro ao reconectar socket:', e);
                            // Tentar criar uma nova conexão como último recurso
                            initSocketConnection();
                        }
                    }, 500);
                } else {
                    // Se o socket não existir, inicializar uma nova conexão
                    initSocketConnection();
                }
            } else if (reason === 'transport close') {
                // Problema de transporte (comum em redes instáveis ou durante contagem de votos)
                console.log('Conexão de transporte fechada. Tentando reconexão imediata...');
                addSystemMessage('Reconectando ao servidor...');
                
                // Tentar reconectar imediatamente
                if (socket) {
                    socket.io.reconnection(true);
                    socket.io.reconnectionAttempts(5);
                    socket.io.reconnectionDelay(300);
                    socket.io.reconnectionDelayMax(1000);
                    socket.connect();
                } else {
                    connectSocket();
                }
                
                // Verificar se a reconexão funcionou após apenas 3 segundos
                setTimeout(function() {
                    if (!socketConnected) {
                        console.log('Reconexão rápida falhou. Segunda tentativa com timeout maior...');
                        // Se ainda não conectou, tentar mais uma vez com configurações diferentes
                        if (socket) {
                            socket.connect();
                        } else {
                            connectSocket();
                        }
                        
                        // Se ainda não conectou após mais 2 segundos, ativar fallback
                        setTimeout(function() {
                            if (!socketConnected) {
                                console.log('Falha nas tentativas de reconexão. Ativando modo fallback.');
                                activateFallbackMode();
                            }
                        }, 2000);
                    }
                }, 3000);
            }
            else if (reason !== 'io client disconnect') {
                // Qualquer outro motivo de desconexão não intencional
                console.log('Desconexão não intencional. Tentando reconectar...');
                
                // Iniciar tentativas de reconexão
                const maxReconnectAttempts = 5; // Aumentado para 5 tentativas
                let reconnectAttempt = 0;
                
                const attemptReconnect = function() {
                    reconnectAttempt++;
                    console.log(`Tentativa de reconexão ${reconnectAttempt}/${maxReconnectAttempts}`);
                    
                    if (reconnectAttempt <= maxReconnectAttempts) {
                        // Tentar reconectar
                        if (socket) {
                            socket.connect();
                        } else {
                            connectSocket();
                        }
                        
                        // Verificar se a conexão foi estabelecida após um tempo
                        setTimeout(function() {
                            if (!socketConnected) {
                                attemptReconnect();
                            } else {
                                console.log('Reconectado com sucesso!');
                                addSystemMessage('Reconectado ao servidor com sucesso!');
                            }
                        }, 5000);
                    } else {
                        console.log('Falha nas tentativas de reconexão. Ativando modo fallback.');
                        activateFallbackMode();
                    }
                };
                
                // Iniciar primeira tentativa após 2 segundos
                setTimeout(attemptReconnect, 2000);
            }
        });
        
        // Evento de erro de conexão
        socket.on('connect_error', function(error) {
            console.error('Erro de conexão Socket.IO:', error);
            
            // Adicionar mensagem de sistema no chat sobre o erro
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                console.log(`Erro de conexão. Tentativa ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS}`);
            }
        });
        
        // Status do quiz
        socket.on('status', function(data) {
            console.log('Status recebido:', data);
            quizRunning = data.quiz_running;
            updateUI();
        });
        
        // Atualizar timer
        socket.on('update_timer', function(data) {
            console.log('Timer atualizado:', data);
            updateTimer(data.time);
        });
        
        // Atualizar ranking
        socket.on('update_ranking', function(data) {
            console.log('Ranking atualizado:', data);
            updateRanking(data.ranking);
        });
        
        // Adicionar listener para o evento ranking_update
        socket.on('ranking_update', function(data) {
            console.log('Ranking recebido via ranking_update:', data);
            if (data && data.success && data.ranking) {
                updateRanking(data.ranking);
            }
        });
        
        // Receber mensagem de chat
        socket.on('chat_message', function(data) {
            console.log('Mensagem de chat recebida:', data);
            addChatMessage(data.author, data.message);
            
            // Atualizar o timestamp da última mensagem para o modo fallback
            if (data.timestamp) {
                lastChatTimestamp = data.timestamp;
            }
        });
        
        // Atualizar votos
        socket.on('update_votes', function(data) {
            console.log('Votos atualizados:', data);
            
            // Verificar se os dados são válidos
            if (!data || !data.votes) {
                console.error('Dados de votos inválidos recebidos:', data);
                return;
            }
            
            // Normalizar os dados de votos (podem vir em diferentes formatos)
            const normalizedVotes = {
                a: data.votes.a || data.votes.A || 0,
                b: data.votes.b || data.votes.B || 0,
                c: data.votes.c || data.votes.C || 0,
                d: data.votes.d || data.votes.D || 0
            };
            
            // Atualizar a interface com os votos normalizados
            updateAllVotes(normalizedVotes);
            
            // Salvar os votos no estado local para persistência
            quizState.votes = normalizedVotes;
            quizState.lastUpdateTime = Date.now();
            saveQuizState();
            
            // Solicitar atualização de votos novamente em 2 segundos se estamos na terceira pergunta
            // para garantir que os votos continuem sendo atualizados mesmo com problemas de conexão
            if (quizState.questionNumber === 3 && socket && socket.connected) {
                setTimeout(function() {
                    try {
                        socket.emit('get_votes', {
                            timestamp: Date.now()
                        });
                    } catch (e) {
                        console.error('Erro ao solicitar atualização de votos:', e);
                    }
                }, 2000);
            }
        });
        
        // Evento de contabilização de votos
        socket.on('show_counting_votes', function(data) {
            console.log('Contabilizando votos:', data);
            showCountingVotes(data.time);
            
            // Resetar contador de erros de conexão quando começa a contabilização
            fallbackErrorCount = 0;
        });
        
        // Variável para controlar a frequência de keep-alives
        let lastKeepAliveResponse = 0;
        let lastPingSent = 0;
        const KEEP_ALIVE_THROTTLE = 2000; // Limitar a 1 resposta a cada 2 segundos
        const PING_THROTTLE = 3000; // Limitar a 1 ping a cada 3 segundos
        
        // Evento de keep-alive durante a contabilização de votos e momentos críticos
        socket.on('keep_alive', function(data) {
            console.log('Keep-alive recebido:', data);
            
            // Resetar contador de tentativas de reconexão
            reconnectAttempts = 0;
            
            // Verificar se já enviamos uma resposta recentemente para evitar flood
            const now = Date.now();
            if (now - lastKeepAliveResponse > KEEP_ALIVE_THROTTLE) {
                // Responder ao keep-alive para manter a conexão ativa nos dois sentidos
                if (socket && socket.connected) {
                    socket.emit('keep_alive_response', {
                        timestamp: now,
                        questionNumber: quizState.questionNumber,
                        clientId: socket.id
                    });
                    lastKeepAliveResponse = now;
                }
            }
            
            // Verificar se estamos na terceira pergunta ou em outro momento crítico
            // E se já enviamos um ping recentemente para evitar flood
            if ((quizState.questionNumber === 3 || data.critical === true) && 
                (now - lastPingSent > PING_THROTTLE)) {
                console.log('Keep-alive em momento crítico - ativando fallback HTTP');
                
                // Ativar fallback HTTP para manter a conexão ativa
                if (socket && socket.connected) {
                    try {
                        fetch('/api/quiz/keep-alive-http', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                timestamp: now,
                                questionNumber: quizState.questionNumber,
                                clientId: socket.id
                            })
                        })
                        .then(response => response.json())
                        .then(data => {
                            console.log('Resposta ao keep-alive HTTP:', data);
                            if (data.success) {
                                lastKeepAliveResponse = now;
                            } else {
                                console.error('Erro ao enviar keep-alive HTTP:', data.message);
                            }
                        })
                        .catch(error => {
                            console.error('Erro ao enviar keep-alive HTTP:', error);
                        });
                    } catch (e) {
                        console.error('Erro ao enviar keep-alive HTTP:', e);
                    }
                }
            }
            if (window.location.search.includes('debug=true')) {
                console.log('Keep-alive recebido:', data);
            }
            
            // Resetar contador de erros de conexão quando recebe um keep-alive
            fallbackErrorCount = 0;
        });
        
        // Exibir resultados
        socket.on('show_results', function(data) {
            console.log('Exibindo resultados:', data);
            
            // Resetar contador de erros de conexão
            fallbackErrorCount = 0;
            
            // Aguardar um pouco antes de mostrar os resultados (para efeito visual)
            setTimeout(() => {
                hideCountingVotes();
                showResults(data.correct_answer, data.explanation, data.votes);
                
                // Salvar a resposta correta no estado local
                if (quizState.currentQuestion) {
                    quizState.currentQuestion.correctAnswer = data.correct_answer;
                    quizState.lastUpdateTime = Date.now();
                    saveQuizState();
                }
            }, 1000);
        });

        // Próxima pergunta
        socket.on('next_question', function(data) {
            console.log('Próxima pergunta:', data);
            
            // Resetar contador de erros de conexão
            fallbackErrorCount = 0;
            
            // Salvar os dados da pergunta atual no sistema de persistência
            quizState.currentQuestion = data.question;
            quizState.questionNumber = data.question_num;
            quizState.totalQuestions = data.total_questions;
            quizState.lastUpdateTime = Date.now();
            saveQuizState();
            
            hideResults();
            showQuestion(data.question, data.question_num, data.total_questions);
            startTimer(data.answer_time);
            
            // Se estamos chegando na terceira pergunta (momento crítico), enviar ping adicional
            if (data.question_num === 3) {
                console.log('Terceira pergunta detectada - ativando modo de estabilidade');
                
                // Enviar pings periódicos para manter a conexão ativa
                let pingCount = 0;
                const maxPings = 5; // Reduzir o número de pings para evitar sobrecarga
                const pingInterval = setInterval(function() {
                    if (socket && socket.connected && pingCount < maxPings) {
                        console.log(`Ping enviado para manter conexão ativa (${pingCount+1}/${maxPings})`);
                        socket.emit('ping_server', {
                            timestamp: Date.now(),
                            questionNumber: data.question_num,
                            critical: true,
                            rateLimited: true
                        });
                        pingCount++;
                    } else {
                        clearInterval(pingInterval);
                    }
                }, 3000); // Aumentar o intervalo para reduzir a frequência
                
                // Ativar o modo de fallback HTTP para garantir a continuidade
                console.log('Ativando modo de fallback HTTP para a terceira pergunta');
                startFallbackPolling();
                
                // NÃO realizar a reconexão preventiva que estava causando problemas
                // Apenas salvar o estado para garantir a recuperação se necessário
                saveQuizState();
                console.log('Estado do quiz salvo para recuperação se necessário');
            }
        });
        
        // Evento de erro
        socket.on('error', function(data) {
            console.error('Erro recebido:', data);
            alert('Erro: ' + (data.message || 'Erro desconhecido'));
        });
    }

    // Carregar ranking
    function loadRanking() {
        console.log('Carregando ranking...');
        
        if (socketConnected) {
            socket.emit('get_ranking', {});
        } else {
            getRanking();
        }
    }

    // Iniciar o quiz
    function startQuiz() {
        if (!quizRunning) {
            if (socketConnected) {
                socket.emit('start_quiz', {});
                console.log('Solicitação para iniciar quiz enviada via Socket.IO');
            } else {
                fetch('/api/quiz/start-http', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Resposta ao iniciar quiz via HTTP:', data);
                    if (data.success) {
                        quizRunning = true;
                        updateUI();
                    } else {
                        alert('Erro ao iniciar quiz: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Erro ao iniciar quiz via HTTP:', error);
                    alert('Erro ao iniciar quiz: ' + error.message);
                });
            }
        }
    }

    // Parar o quiz
    function stopQuiz() {
        if (quizRunning) {
            if (socketConnected) {
                socket.emit('stop_quiz', {});
                console.log('Solicitação para parar quiz enviada via Socket.IO');
            } else {
                fetch('/api/quiz/stop-http', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Resposta ao parar quiz via HTTP:', data);
                    if (data.success) {
                        quizRunning = false;
                        updateUI();
                    } else {
                        alert('Erro ao parar quiz: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Erro ao parar quiz via HTTP:', error);
                    alert('Erro ao parar quiz: ' + error.message);
                });
            }
        }
    }

    // Atualizar interface com base no estado do quiz
    function updateUI() {
        if (questionContainer) {
            questionContainer.style.display = 'block';
        }
        
        if (quizRunning) {
            if (resultContainer) {
                resultContainer.style.display = 'none';
            }
        } else {
            // Parar o timer
            if (countdownInterval) {
                clearInterval(countdownInterval);
                countdownInterval = null;
            }
        }
    }

    // Iniciar o timer
    function startTimer(seconds) {
        console.log('Iniciando timer com ' + seconds + ' segundos');
        
        // Parar timer anterior se existir
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
        
        // Verificar se o valor de seconds é válido
        if (!seconds || isNaN(seconds) || seconds <= 0) {
            console.error('Valor inválido para timer:', seconds);
            seconds = 30; // Valor padrão em caso de erro
        }
        
        // Definir tempo inicial
        currentTime = parseInt(seconds);
        updateTimer(currentTime);
        
        // Iniciar contagem regressiva
        countdownInterval = setInterval(function() {
            currentTime--;
            updateTimer(currentTime);
            console.log('Timer: ' + currentTime + ' segundos restantes');
            
            if (currentTime <= 0) {
                console.log('Timer finalizado');
                clearInterval(countdownInterval);
                countdownInterval = null;
            }
        }, 1000);
    }

    // Atualizar o timer na interface
    function updateTimer(seconds) {
        if (timer) {
            timer.textContent = seconds;
            
            // Adicionar classe de alerta quando o tempo estiver acabando
            if (seconds <= 5) {
                timer.classList.add('timer-alert');
            } else {
                timer.classList.remove('timer-alert');
            }
        }
    }

    // Adicionar mensagem ao chat
    function addChatMessage(author, message) {
        if (!chatContainer) return;
        
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message';
        
        const authorElement = document.createElement('span');
        authorElement.className = 'chat-author';
        authorElement.textContent = author + ': ';
        
        const contentElement = document.createElement('span');
        contentElement.className = 'chat-content';
        contentElement.textContent = message;
        
        messageElement.appendChild(authorElement);
        messageElement.appendChild(contentElement);
        
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Adicionar mensagem de sistema ao chat
    function addSystemMessage(message) {
        if (!chatContainer) return;
        
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message system-message';
        messageElement.textContent = message;
        
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Atualizar votos para uma opção
    function updateVotes(option, votes, totalVotes) {
        const optionElements = {
            'A': optionA,
            'B': optionB,
            'C': optionC,
            'D': optionD
        };
        
        const optionElement = optionElements[option];
        if (!optionElement) return;
        
        const votesElement = optionElement.querySelector('.option-votes');
        const progressElement = optionElement.querySelector('.option-progress');
        
        if (!votesElement || !progressElement) return;
        
        // Calcular a porcentagem
        const percentage = totalVotes > 0 ? Math.round((votes / totalVotes) * 100) : 0;
        
        // Atualizar o texto dos votos com a porcentagem
        votesElement.innerHTML = `${votes} <span class="option-votes-percentage">(${percentage}%)</span>`;
        
        // Atualizar a barra de progresso
        progressElement.style.width = `${percentage}%`;
    }

    // Atualizar todos os votos
    function updateAllVotes(votesData) {
        if (!votesData) {
            console.error('Dados de votos inválidos:', votesData);
            return;
        }
        
        console.log('Atualizando votos na interface:', votesData);
        
        // Normalizar os dados de votos (podem vir em diferentes formatos)
        const normalizedVotes = {
            a: votesData.a || votesData.A || 0,
            b: votesData.b || votesData.B || 0,
            c: votesData.c || votesData.C || 0,
            d: votesData.d || votesData.D || 0
        };
        
        const totalVotes = normalizedVotes.a + normalizedVotes.b + normalizedVotes.c + normalizedVotes.d;
        
        // Atualizar cada opção
        updateVotes('A', normalizedVotes.a, totalVotes);
        updateVotes('B', normalizedVotes.b, totalVotes);
        updateVotes('C', normalizedVotes.c, totalVotes);
        updateVotes('D', normalizedVotes.d, totalVotes);
        
        // Verificar se estamos mostrando os resultados e atualizar os elementos do popup
        if (quizOverlay && quizOverlay.classList.contains('active') && 
            resultContainer && resultContainer.classList.contains('active') &&
            totalVotesElement && correctVotesElement && correctPercentageElement) {
            
            // Determinar a resposta correta e calcular estatísticas
            const correctAnswer = quizState.currentQuestion && quizState.currentQuestion.correctAnswer;
            let correctVotes = 0;
            
            if (correctAnswer) {
                const lowerCaseAnswer = correctAnswer.toLowerCase();
                correctVotes = normalizedVotes[lowerCaseAnswer] || 0;
            }
            
            const correctPercentage = totalVotes > 0 ? Math.round((correctVotes / totalVotes) * 100) : 0;
            
            // Atualizar os elementos do popup
            totalVotesElement.textContent = totalVotes;
            correctVotesElement.textContent = correctVotes;
            correctPercentageElement.textContent = `${correctPercentage}%`;
        }
        
        // Salvar os votos no estado local para persistência
        quizState.votes = normalizedVotes;
        quizState.lastUpdateTime = Date.now();
        saveQuizState();
    }

    // Mostrar a mensagem "Contabilizando votos..."
    function showCountingVotes() {
        console.log('Mostrando mensagem de contabilização de votos');
        if (countingVotesElement) {
            countingVotesElement.classList.add('active');
        }
    }

    // Esconder a mensagem "Contabilizando votos..."
    function hideCountingVotes() {
        console.log('Escondendo mensagem de contabilização de votos');
        if (countingVotesElement) {
            countingVotesElement.classList.remove('active');
        }
    }

    // Mostrar o popup de resultados
    function showResults(correctAnswer, explanation, votesData) {
        console.log('Mostrando resultados:', correctAnswer, explanation, votesData);
        
        if (!correctAnswerText || !explanationText || !quizOverlay || !resultContainer || 
            !totalVotesElement || !correctVotesElement || !correctPercentageElement) {
            console.error('Elementos necessários para mostrar resultados não encontrados');
            return;
        }
        
        // Marcar a opção correta
        const options = {
            'A': optionA,
            'B': optionB,
            'C': optionC,
            'D': optionD
        };
        
        // Remover classe 'correct' de todas as opções
        Object.values(options).forEach(option => {
            if (option) option.classList.remove('correct');
        });
        
        // Adicionar classe 'correct' à opção correta
        if (correctAnswer && options[correctAnswer]) {
            options[correctAnswer].classList.add('correct');
        }
        
        // Normalizar os dados de votos para garantir consistência
        const normalizedVotes = {
            a: votesData.a || votesData.A || 0,
            b: votesData.b || votesData.B || 0,
            c: votesData.c || votesData.C || 0,
            d: votesData.d || votesData.D || 0
        };
        
        // Calcular totais
        const totalVotes = normalizedVotes.a + normalizedVotes.b + normalizedVotes.c + normalizedVotes.d;
        let correctVotes = 0;
        
        // Determinar quantos votos foram para a resposta correta
        if (correctAnswer) {
            const lowerCaseAnswer = correctAnswer.toLowerCase();
            correctVotes = normalizedVotes[lowerCaseAnswer] || 0;
        }
        
        const correctPercentage = totalVotes > 0 ? Math.round((correctVotes / totalVotes) * 100) : 0;
        
        // Atualizar o conteúdo do popup
        correctAnswerText.innerHTML = `<i class="fas fa-check-circle"></i> Resposta Correta: ${correctAnswer}`;
        explanationText.innerHTML = explanation || "Sem explicação disponível.";
        totalVotesElement.textContent = totalVotes;
        correctVotesElement.textContent = correctVotes;
        correctPercentageElement.textContent = `${correctPercentage}%`;
        
        // Mostrar o overlay e o popup
        quizOverlay.classList.add('active');
        resultContainer.classList.add('active');
        
        // Atualizar os votos na interface para garantir que estejam corretos
        updateAllVotes(normalizedVotes);
        
        // Fechar automaticamente após 10 segundos
        setTimeout(hideResults, 10000);
        
        console.log('Popup de resultados exibido com fechamento automático em 10 segundos');
        
        // Salvar os dados no estado local para persistência
        quizState.votes = normalizedVotes;
        quizState.lastUpdateTime = Date.now();
        saveQuizState();
    }

    // Esconder o popup de resultados
    function hideResults() {
        if (quizOverlay) quizOverlay.classList.remove('active');
        if (resultContainer) resultContainer.classList.remove('active');
    }

    // Atualizar ranking
    function updateRanking(ranking) {
        if (!rankList) return;
        
        if (!ranking || ranking.length === 0) {
            rankList.innerHTML = '<div class="no-ranking">Nenhum participante ainda.</div>';
            return;
        }
        
        // Limpar ranking atual
        rankList.innerHTML = '';
        
        // Adicionar cada item ao ranking
        ranking.forEach((item, index) => {
            const rankItem = document.createElement('div');
            rankItem.className = 'rank-item';
            
            const position = document.createElement('div');
            position.className = 'rank-position';
            position.textContent = `#${index + 1}`;
            
            const name = document.createElement('div');
            name.className = 'rank-name';
            name.textContent = item.name;
            
            const score = document.createElement('div');
            score.className = 'rank-score';
            score.textContent = item.score;
            
            rankItem.appendChild(position);
            rankItem.appendChild(name);
            rankItem.appendChild(score);
            
            rankList.appendChild(rankItem);
        });
    }

    // Mostrar uma pergunta
    function showQuestion(question, questionNum, totalQuestionsCount) {
        console.log('Mostrando pergunta:', question);
        
        if (!questionText || !currentQuestionNum || !totalQuestions || 
            !optionA || !optionB || !optionC || !optionD) {
            console.error('Elementos necessários para mostrar pergunta não encontrados');
            return;
        }
        
        // Remover classe 'correct' de todas as opções
        optionA.classList.remove('correct');
        optionB.classList.remove('correct');
        optionC.classList.remove('correct');
        optionD.classList.remove('correct');
        
        currentQuestionNum.textContent = questionNum;
        totalQuestions.textContent = totalQuestionsCount;
        questionText.textContent = question.text || question.question;
        
        // Atualizar as opções - verificando diferentes formatos possíveis
        if (question.options) {
            // Formato 1: {A: "texto", B: "texto", ...}
            if (question.options.A !== undefined) {
                optionA.querySelector('.option-text').textContent = question.options.A;
                optionB.querySelector('.option-text').textContent = question.options.B;
                optionC.querySelector('.option-text').textContent = question.options.C;
                optionD.querySelector('.option-text').textContent = question.options.D;
            } 
            // Formato 2: ["texto", "texto", ...]
            else if (Array.isArray(question.options)) {
                optionA.querySelector('.option-text').textContent = question.options[0] || '';
                optionB.querySelector('.option-text').textContent = question.options[1] || '';
                optionC.querySelector('.option-text').textContent = question.options[2] || '';
                optionD.querySelector('.option-text').textContent = question.options[3] || '';
            }
        }
        
        // Resetar os votos
        const resetVotes = { a: 0, b: 0, c: 0, d: 0 };
        updateAllVotes(resetVotes);
        
        // Resetar as barras de progresso
        document.querySelectorAll('.option-progress').forEach(el => {
            if (el) el.style.width = '0%';
        });
        
        // Mostrar o container de perguntas e esconder o de resultados
        if (questionContainer) questionContainer.style.display = 'block';
        hideResults();
        
        console.log('Pergunta exibida com opções:', {
            A: optionA.querySelector('.option-text')?.textContent,
            B: optionB.querySelector('.option-text')?.textContent,
            C: optionC.querySelector('.option-text')?.textContent,
            D: optionD.querySelector('.option-text')?.textContent
        });
    }

    // Adicionar evento para voltar ao menu quando ESC for pressionado
    document.addEventListener('keydown', function(event) {
        // Verificar se a tecla pressionada é ESC (código 27)
        if (event.keyCode === 27) {
            console.log('Tecla ESC pressionada - voltando ao menu inicial');
            // Redirecionar para a página inicial
            window.location.href = '/';
        }
    });

    // Adicionar evento de clique para o botão de voltar
    const backButton = document.getElementById('backButton');
    if (backButton) {
        backButton.addEventListener('click', function() {
            console.log('Botão voltar clicado - redirecionando para o menu inicial');
            window.location.href = '/';
        });
    }

    // Função para conectar ao chat do YouTube diretamente da página do quiz
    function setupYouTubeConnect() {
        console.log("Inicializando controles de conexão do YouTube");
        
        const connectButton = document.getElementById('connectYoutubeChat');
        const urlInput = document.getElementById('youtubeUrlDirect');
        
        if (!connectButton || !urlInput) {
            console.error("Elementos de conexão do YouTube não encontrados");
            return;
        }
        
        console.log("Elementos de conexão do YouTube encontrados");
        
        // Carregar URL atual
        fetch('/api/config')
            .then(response => response.json())
            .then(data => {
                if (data && data.youtube_url) {
                    urlInput.value = data.youtube_url;
                    console.log("URL carregada:", data.youtube_url);
                }
            })
            .catch(error => console.error('Erro ao carregar URL:', error));
        
        // Adicionar evento de clique ao botão
        connectButton.addEventListener('click', function() {
            console.log("Botão de conexão clicado");
            
            const url = urlInput.value.trim();
            if (!url) {
                alert('Por favor, insira uma URL do YouTube válida');
                return;
            }
            
            console.log("Tentando conectar à URL:", url);
            
            // Mostrar mensagem de carregamento
            const chatContainer = document.getElementById('chatContainer');
            if (chatContainer) {
                chatContainer.innerHTML += `
                    <div class="chat-message system">
                        <div class="message-author system">Sistema</div>
                        <div class="message-text">Conectando ao chat do YouTube...</div>
                    </div>
                `;
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            // Enviar URL para o servidor
            fetch('/api/connect-youtube', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            })
            .then(response => response.json())
            .then(data => {
                console.log("Resposta do servidor:", data);
                
                if (data.success) {
                    if (chatContainer) {
                        chatContainer.innerHTML += `
                            <div class="chat-message system">
                                <div class="message-author system">Sistema</div>
                                <div class="message-text">Conectado com sucesso ao chat do YouTube!</div>
                            </div>
                        `;
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                } else {
                    if (chatContainer) {
                        chatContainer.innerHTML += `
                            <div class="chat-message system error">
                                <div class="message-author system">Sistema</div>
                                <div class="message-text">Erro ao conectar: ${data.message || 'Erro desconhecido'}</div>
                            </div>
                        `;
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                }
            })
            .catch(error => {
                console.error("Erro na requisição:", error);
                
                if (chatContainer) {
                    chatContainer.innerHTML += `
                        <div class="chat-message system error">
                            <div class="message-author system">Sistema</div>
                            <div class="message-text">Erro ao conectar: ${error}</div>
                        </div>
                    `;
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
            });
        });
    }

    // Inicializar quando o documento estiver pronto
    document.addEventListener('DOMContentLoaded', function() {
        console.log("DOM carregado, inicializando controles");
        setupYouTubeConnect();
    });
});
