/**
 * socket-config.js - Configuração centralizada para Socket.IO e fetch
 * Este arquivo garante que todas as conexões usem o endereço correto
 */

// Obter o endereço base da página atual
const baseUrl = window.location.origin;
console.log(`Configurando para usar: ${baseUrl}`);

// Sobrescrever a função io para forçar o uso do endereço correto
if (window.io) {
    const originalIo = window.io;
    window.io = function(url, options) {
        // Se nenhuma URL for fornecida, usar a URL base da página
        if (!url || typeof url === 'object') {
            options = url;
            url = baseUrl;
        }
        
        // Garantir que a URL seja a correta
        if (url.indexOf('localhost') !== -1 || url.indexOf('127.0.0.1') !== -1) {
            url = baseUrl;
        }
        
        console.log(`Socket.IO conectando a: ${url}`);
        
        // Configurações otimizadas para máxima estabilidade durante operações críticas
        const defaultOptions = {
            transports: ['polling', 'websocket'],  // Usar polling primeiro para maior estabilidade
            upgrade: false,                        // DESATIVAR upgrade para evitar problemas de transport close
            reconnection: true,                    // Habilitar reconexão automática
            reconnectionAttempts: Infinity,        // Tentar reconectar indefinidamente
            reconnectionDelay: 100,                // Delay inicial para reconexão reduzido (ms)
            reconnectionDelayMax: 1000,            // Delay máximo para reconexão reduzido (ms)
            timeout: 60000,                        // Timeout aumentado para 60s
            forceNew: false,                       // Não forçar nova conexão
            autoConnect: true,                     // Conectar automaticamente
            multiplex: true,                       // Permitir multiplexing para melhor desempenho
            pingInterval: 5000,                    // Intervalo de ping reduzido para detectar problemas mais rápido
            pingTimeout: 120000,                   // Timeout de ping aumentado para 2 minutos
            rejectUnauthorized: false,             // Ignorar problemas de certificado
            secure: false,                         // Desativar SSL para conexões locais
            path: '/socket.io',                    // Caminho padrão
            withCredentials: false,                // Não enviar credenciais
            rememberUpgrade: false,                // Não lembrar upgrades para evitar problemas
            perMessageDeflate: false,              // Desativar compressão para reduzir CPU
            extraHeaders: {                        // Adicionar headers extras para evitar problemas de cache
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'X-Client-Timestamp': Date.now()
            }
        };
        
        // Mesclar opções padrão com as fornecidas
        const mergedOptions = Object.assign({}, defaultOptions, options || {});
        
        // Chamar a função original com a URL correta
        return originalIo(url, mergedOptions);
    };
    console.log('Socket.IO configurado com sucesso');
}

// Sobrescrever a função fetch para garantir URLs absolutas e melhorar tratamento de erros
const originalFetch = window.fetch;
window.fetch = function(url, options) {
    // Se a URL for relativa (começar com /)
    if (url && typeof url === 'string' && url.startsWith('/')) {
        url = baseUrl + url;
        console.log(`Convertendo URL relativa para absoluta: ${url}`);
    }
    
    // Adicionar timeout para evitar que requisições fiquem pendentes por muito tempo
    const fetchOptions = Object.assign({}, options || {}, {
        // Adicionar timeout de 5 segundos
        signal: options && options.signal ? options.signal : AbortSignal.timeout(5000)
    });
    
    // Chamar a função original com tratamento de erro aprimorado
    return originalFetch(url, fetchOptions)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }
            return response;
        })
        .catch(error => {
            console.error(`Erro na requisição para ${url}:`, error);
            // Relançar o erro para ser tratado pelo chamador
            throw error;
        });
};
console.log('Fetch configurado com sucesso');

// Exportar a URL base para uso em outros scripts
window.appBaseUrl = baseUrl;
console.log('Configuração concluída com sucesso');
