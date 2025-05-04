/**
 * Sistema de persistência local para o Quiz
 * Este arquivo contém funções para salvar e restaurar o estado do quiz
 * durante desconexões ou problemas de rede
 */

// Estado global do quiz
const quizState = {
    currentQuestion: null,
    questionNumber: 0,
    totalQuestions: 0,
    votes: {},
    lastUpdateTime: 0,
    lastQuestionId: null,  // Para evitar resetar para a primeira pergunta
    lastResults: null      // Para manter resultados durante desconexões
};

// Variável para rastrear a última pergunta exibida
let lastDisplayedQuestionId = null;

// Interceptar chamadas de função para adicionar persistência
window.addEventListener('load', function() {
    console.log('Inicializando sistema de persistência do quiz');
    
    // Tentar restaurar o estado salvo ao carregar a página
    setTimeout(function() {
        const savedState = loadQuizState();
        if (savedState && isQuizStateRecent() && savedState.currentQuestion) {
            console.log('Restaurando estado do quiz automaticamente');
            // A função showQuestion será chamada pelo quiz.js
        }
    }, 1000);
    
    // Interceptar chamadas para evitar resetar o quiz
    setInterval(function() {
        // Verificar se o quiz resetou para a primeira pergunta
        const questionElement = document.getElementById('questionText');
        const questionNumberElement = document.getElementById('questionNumber');
        
        if (questionElement && questionNumberElement) {
            const currentQuestionText = questionElement.innerText;
            let currentQuestionNumber = 0;
            
            try {
                // Extrair o número da pergunta atual
                const questionNumberText = questionNumberElement.innerText;
                const match = questionNumberText.match(/(\d+)\s*\//);
                if (match && match[1]) {
                    currentQuestionNumber = parseInt(match[1]);
                }
            } catch (e) {
                console.error('Erro ao extrair número da pergunta:', e);
            }
            
            // Se voltou para a pergunta 1 mas tínhamos uma pergunta posterior salva
            if (currentQuestionNumber === 1 && quizState.questionNumber > 1) {
                console.log('Detectado reset do quiz. Restaurando estado anterior...');
                // Aguardar um pouco e restaurar
                setTimeout(function() {
                    restoreQuizState();
                }, 500);
            }
            
            // Salvar a pergunta atual para detecção de reset
            if (currentQuestionText && currentQuestionNumber > 0) {
                lastDisplayedQuestionId = currentQuestionNumber;
                
                // Atualizar o estado global apenas se o número for maior que o atual
                // Isso evita que o estado seja sobrescrito com uma pergunta anterior
                if (currentQuestionNumber >= quizState.questionNumber) {
                    // Extrair informações da interface para salvar
                    const options = [];
                    const optionElements = document.querySelectorAll('.quiz-option .option-text');
                    optionElements.forEach(el => options.push(el.innerText));
                    
                    // Criar objeto de pergunta
                    const questionObj = {
                        question: currentQuestionText,
                        options: {
                            A: options[0] || '',
                            B: options[1] || '',
                            C: options[2] || '',
                            D: options[3] || ''
                        }
                    };
                    
                    // Extrair número total de perguntas
                    let totalQuestions = 0;
                    try {
                        const totalMatch = questionNumberElement.innerText.match(/\/(\d+)/);
                        if (totalMatch && totalMatch[1]) {
                            totalQuestions = parseInt(totalMatch[1]);
                        }
                    } catch (e) {
                        console.error('Erro ao extrair total de perguntas:', e);
                    }
                    
                    // Salvar estado atual
                    saveQuizState(questionObj, currentQuestionNumber, totalQuestions, null);
                }
            }
        }
    }, 2000); // Verificar a cada 2 segundos
});

/**
 * Salva o estado atual do quiz no localStorage
 * @param {Object} question - Objeto da pergunta atual
 * @param {Number} questionNum - Número da pergunta atual
 * @param {Number} totalQuestions - Total de perguntas
 * @param {Object} votes - Votos atuais
 */
function saveQuizState(question, questionNum, totalQuestions, votes) {
    try {
        // Atualizar o estado
        quizState.currentQuestion = question;
        quizState.questionNumber = questionNum;
        quizState.totalQuestions = totalQuestions;
        quizState.votes = votes || {};
        quizState.lastUpdateTime = Date.now();
        
        // Salvar no localStorage
        localStorage.setItem('quizState', JSON.stringify(quizState));
        console.log('Estado do quiz salvo localmente:', quizState);
        return true;
    } catch (e) {
        console.error('Erro ao salvar estado do quiz:', e);
        return false;
    }
}

/**
 * Carrega o estado do quiz do localStorage
 * @returns {Object|null} Estado do quiz ou null se não existir
 */
function loadQuizState() {
    try {
        const savedState = localStorage.getItem('quizState');
        if (savedState) {
            const parsedState = JSON.parse(savedState);
            
            // Atualizar o estado global
            Object.assign(quizState, parsedState);
            
            console.log('Estado do quiz carregado do armazenamento local:', quizState);
            return quizState;
        }
    } catch (e) {
        console.error('Erro ao carregar estado do quiz:', e);
    }
    return null;
}

/**
 * Verifica se o estado salvo é recente (menos de 5 minutos)
 * @returns {Boolean} true se o estado for recente
 */
function isQuizStateRecent() {
    const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
    return quizState.lastUpdateTime > fiveMinutesAgo;
}

/**
 * Restaura a pergunta atual do estado salvo
 * @param {Function} showQuestionCallback - Função para exibir a pergunta (opcional)
 * @param {Function} hideResultsCallback - Função para esconder resultados (opcional)
 * @returns {Boolean} true se restaurou com sucesso
 */
function restoreQuizState(showQuestionCallback, hideResultsCallback) {
    if (quizState.currentQuestion && quizState.questionNumber > 0 && isQuizStateRecent()) {
        console.log('Restaurando estado anterior do quiz na interface');
        
        // Se não foram fornecidas funções de callback, usar manipulação direta do DOM
        if (!showQuestionCallback) {
            // Esconder resultados se necessário
            const resultsElement = document.querySelector('.quiz-results');
            if (resultsElement) {
                resultsElement.style.display = 'none';
            }
            
            // Mostrar a pergunta
            const questionElement = document.getElementById('questionText');
            const questionNumberElement = document.getElementById('questionNumber');
            const optionsContainer = document.querySelector('.quiz-options');
            
            if (questionElement && questionNumberElement && optionsContainer) {
                // Atualizar texto da pergunta
                questionElement.innerText = quizState.currentQuestion.question || quizState.currentQuestion.text;
                
                // Atualizar número da pergunta
                questionNumberElement.innerText = `${quizState.questionNumber}/${quizState.totalQuestions}`;
                
                // Atualizar opções
                if (quizState.currentQuestion.options) {
                    const options = quizState.currentQuestion.options;
                    const optionElements = optionsContainer.querySelectorAll('.quiz-option');
                    
                    // Converter para array se for objeto
                    let optionsArray = options;
                    if (!Array.isArray(options)) {
                        optionsArray = [
                            options.A || options[0],
                            options.B || options[1],
                            options.C || options[2],
                            options.D || options[3]
                        ];
                    }
                    
                    // Atualizar cada opção
                    optionElements.forEach((element, index) => {
                        if (index < optionsArray.length) {
                            const optionText = element.querySelector('.option-text');
                            if (optionText) {
                                optionText.innerText = optionsArray[index];
                            }
                        }
                    });
                }
                
                // Mostrar a pergunta
                const questionContainer = document.querySelector('.quiz-question');
                if (questionContainer) {
                    questionContainer.style.display = 'block';
                }
                
                console.log('Estado do quiz restaurado via DOM');
                return true;
            }
        } else {
            // Usar callbacks fornecidos
            if (hideResultsCallback) hideResultsCallback();
            
            if (showQuestionCallback) {
                showQuestionCallback(
                    quizState.currentQuestion,
                    quizState.questionNumber,
                    quizState.totalQuestions
                );
            }
            
            console.log('Estado do quiz restaurado via callbacks');
            return true;
        }
    }
    return false;
}

/**
 * Limpa o estado salvo do quiz
 */
function clearQuizState() {
    localStorage.removeItem('quizState');
    
    // Resetar o estado global
    quizState.currentQuestion = null;
    quizState.questionNumber = 0;
    quizState.totalQuestions = 0;
    quizState.votes = {};
    quizState.lastUpdateTime = 0;
    
    console.log('Estado do quiz limpo');
}
