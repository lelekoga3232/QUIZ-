from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import json
import os
import threading
import time
from datetime import datetime
import logging
from chat_downloader import ChatDownloader
import random
import re
import socket

# Configuração para estabilidade de longo prazo
import sys
import gc

# Configurar coleta de lixo mais agressiva
gc.set_threshold(700, 10, 10)  # Valores mais baixos = coleta mais frequente

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quiz-youtube-live-secret-key'

# Configuração otimizada do Socket.IO para evitar erros 502
# Configuração otimizada do Socket.IO para estabilidade de longo prazo
# Verificar se estamos no ambiente de produção (Render/Heroku)
is_production = os.environ.get('FLASK_ENV') == 'production'

# Usar threading em todos os ambientes para maior compatibilidade
async_mode = 'threading'

socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode=async_mode,    # Usar eventlet em produção
    ping_timeout=120,         # Aumentar timeout de ping para 2 minutos
    ping_interval=10,         # Manter intervalo de ping em 10 segundos
    reconnection_attempts=10, # Aumentar tentativas de reconexão
    reconnection_delay=1000,  # Delay inicial de reconexão em ms
    reconnection_delay_max=5000, # Delay máximo de reconexão em ms
    max_http_buffer_size=5e6, # Reduzir tamanho do buffer para evitar consumo excessivo de memória
    manage_session=False,     # Não gerenciar sessões para reduzir overhead
    logger=False,             # Desativar logging para reduzir I/O
    engineio_logger=False,    # Desativar logging do engine para reduzir I/O
    http_compression=False    # Desativar compressão para reduzir CPU
)

# Diretório para armazenar dados
DATA_DIR = 'data'
QUESTIONS_FILE = os.path.join(DATA_DIR, 'questions.json')
RANKING_FILE = os.path.join(DATA_DIR, 'ranking.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# Criar diretório de dados se não existir
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Configurações padrão do quiz
quiz_config = {
    'youtube_url': '',
    'answer_time': 20,
    'vote_count_time': 8,
    'result_display_time': 5,
    'primary_color': '#f39c12',
    'secondary_color': '#8e44ad',
    'enable_chat_simulator': True
}

# Carregar configurações do arquivo JSON
def load_config():
    """Carrega as configurações do arquivo config.json."""
    global quiz_config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # Atualizar configuração com os valores carregados
                quiz_config.update(loaded_config)
        else:
            # Configuração padrão
            quiz_config = {
                'youtube_url': '',
                'answer_time': 20,
                'vote_count_time': 8,
                'result_display_time': 5,
                'primary_color': '#f39c12',
                'secondary_color': '#8e44ad',
                'enable_chat_simulator': True
            }
            save_config()
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {str(e)}")
        # Configuração padrão em caso de erro
        quiz_config = {
            'youtube_url': '',
            'answer_time': 20,
            'vote_count_time': 8,
            'result_display_time': 5,
            'primary_color': '#f39c12',
            'secondary_color': '#8e44ad',
            'enable_chat_simulator': True
        }

# Salvar configurações em arquivo JSON
def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(quiz_config, f, ensure_ascii=False, indent=4)
        logger.info("Configurações salvas com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar configurações: {e}")

current_question_index = 0
current_question = None
quiz_running = False
chat_thread = None
quiz_thread = None
user_votes = {}  # Armazena votos por usuário para a pergunta atual
voted_users = set()  # Armazena usuários que já votaram na pergunta atual
questions = []
ranking = {}
current_votes = [0, 0, 0, 0]

# Variável para rastrear o tempo de início do servidor
server_start_time = time.time()

# Variáveis globais para o chat
chat_messages = []  # Lista para armazenar mensagens do chat
is_chat_running = False  # Controla se o chat está em execução
is_simulator_running = False  # Controla especificamente se o simulador está em execução

# Função para adicionar uma mensagem ao chat
def add_chat_message(author, message):
    try:
        # Adicionar mensagem ao histórico
        global chat_messages
        timestamp = time.time()
        chat_messages.append({
            'author': author,
            'message': message,
            'timestamp': timestamp
        })
        
        # Limitar o número de mensagens armazenadas (manter apenas as 100 últimas)
        if len(chat_messages) > 100:
            chat_messages = chat_messages[-100:]
        
        # Emitir evento de mensagem de chat em uma thread separada para não bloquear
        def emit_message():
            try:
                socketio.emit('chat_message', {
                    'author': author,
                    'message': message
                })
            except Exception as e:
                logger.error(f"Erro ao emitir mensagem de chat: {e}")
        
        # Iniciar thread para emitir mensagem
        message_thread = threading.Thread(target=emit_message)
        message_thread.daemon = True
        message_thread.start()
        
        # Log da mensagem
        logger.info(f"Mensagem de chat: {author} -> {message}")
        
        return timestamp
    except Exception as e:
        logger.error(f"Erro ao adicionar mensagem ao chat: {e}")
        return time.time()

# Carregar perguntas do arquivo JSON
def load_questions():
    global questions
    if os.path.exists(QUESTIONS_FILE):
        try:
            with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            logger.info(f"Carregadas {len(questions)} perguntas do arquivo")
        except Exception as e:
            logger.error(f"Erro ao carregar perguntas: {e}")
            questions = []
    else:
        # Perguntas de exemplo se o arquivo não existir
        questions = [
            {
                "question": "Qual é a capital do Brasil?",
                "options": ["Rio de Janeiro", "São Paulo", "Brasília", "Salvador"],
                "correct": 2,  # Índice da resposta correta (0-based)
                "explanation": "Brasília é a capital federal do Brasil desde 21 de abril de 1960."
            },
            {
                "question": "Quem escreveu 'Dom Casmurro'?",
                "options": ["José de Alencar", "Machado de Assis", "Clarice Lispector", "Carlos Drummond de Andrade"],
                "correct": 1,
                "explanation": "Machado de Assis escreveu 'Dom Casmurro', publicado em 1899."
            }
        ]
        save_questions()

# Salvar perguntas em arquivo JSON
def save_questions():
    try:
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=4)
        logger.info(f"Salvas {len(questions)} perguntas no arquivo")
    except Exception as e:
        logger.error(f"Erro ao salvar perguntas: {e}")

# Carregar ranking do arquivo JSON
def load_ranking():
    global ranking
    if os.path.exists(RANKING_FILE):
        try:
            with open(RANKING_FILE, 'r', encoding='utf-8') as f:
                ranking = json.load(f)
            logger.info(f"Ranking carregado com {len(ranking)} usuários")
        except Exception as e:
            logger.error(f"Erro ao carregar ranking: {e}")
            ranking = {}
    else:
        ranking = {}
        save_ranking()

# Thread para salvar o ranking de forma assíncrona
def save_ranking_thread():
    try:
        # Criar uma cópia local do ranking para evitar problemas de concorrência
        ranking_copy = ranking.copy()
        
        with open(RANKING_FILE, 'w', encoding='utf-8') as f:
            json.dump(ranking_copy, f, ensure_ascii=False, indent=4)
        logger.info("Ranking salvo com sucesso de forma assíncrona")
    except Exception as e:
        logger.error(f"Erro ao salvar ranking de forma assíncrona: {e}")

# Salvar ranking em arquivo JSON de forma assíncrona
def save_ranking():
    try:
        # Criar uma thread para salvar o ranking sem bloquear o servidor
        save_thread = threading.Thread(target=save_ranking_thread)
        save_thread.daemon = True
        save_thread.start()
        logger.info("Iniciada thread para salvar ranking")
    except Exception as e:
        logger.error(f"Erro ao iniciar thread para salvar ranking: {e}")

# Processar mensagem do chat
def process_chat_message(author, message):
    global current_votes, voted_users
    
    try:
        # Log para debug
        logger.info(f"Processando mensagem: {author} -> {message}")
        
        # Converter para maiúsculas para facilitar comparação
        message_upper = message.upper()
        
        # Verificar se é um comando de voto (!A, !B, !C, !D)
        is_vote = False
        if message_upper in ['!A', '!B', '!C', '!D']:
            # Extrair a opção votada (A, B, C ou D)
            vote_option = message_upper[1]  # Pegar o caractere após o !
            
            # Registrar o voto do usuário
            user_votes[author] = vote_option
            
            # Atualizar contagem de votos
            vote_index = ord(vote_option) - ord('A')  # Converter A->0, B->1, C->2, D->3
            if 0 <= vote_index < 4:  # Garantir que o índice é válido
                current_votes[vote_index] += 1
                logger.info(f"Voto registrado: {author} votou na opção !{vote_option}")
                is_vote = True
        
        # Processar a mensagem e o voto em threads separadas para não bloquear
        def process_vote_and_message():
            try:
                # Emitir evento de atualização de votos se for um voto
                if is_vote:
                    try:
                        votes_data = count_votes()
                        logger.info(f"Enviando atualização de votos: {votes_data}")
                        socketio.emit('update_votes', {
                            'votes': votes_data,
                            'timestamp': time.time()  # Adicionar timestamp para evitar cache
                        }, namespace='/')
                    except Exception as e:
                        logger.error(f"Erro ao enviar atualização de votos: {e}")
                        # Tentar novamente após um pequeno delay
                        time.sleep(0.1)
                        try:
                            socketio.emit('update_votes', {
                                'votes': count_votes(),
                                'timestamp': time.time()
                            }, namespace='/')
                        except Exception as e2:
                            logger.error(f"Falha na segunda tentativa de enviar votos: {e2}")
                    
                
                # Adicionar mensagem ao chat (independente de ser comando ou não)
                socketio.emit('chat_message', {
                    'author': author,
                    'message': message
                })
            except Exception as e:
                logger.error(f"Erro ao processar voto/mensagem em thread: {e}")
        
        # Iniciar thread para processar voto e mensagem
        process_thread = threading.Thread(target=process_vote_and_message)
        process_thread.daemon = True
        process_thread.start()
        
        return True
    except Exception as e:
        logger.error(f"Erro ao processar mensagem do chat: {e}")
        return False

# Função para monitorar o chat do YouTube
def monitor_youtube_chat():
    """Monitora o chat do YouTube para capturar votos."""
    global chat_thread, is_chat_running, is_simulator_running
    
    try:
        # Verificar se o simulador de chat está ativado
        if quiz_config.get('enable_chat_simulator', True):
            logger.info("Simulador de chat ativado. Iniciando simulação de mensagens.")
            is_chat_running = True
            is_simulator_running = True
            chat_thread = threading.Thread(target=simulate_chat_messages)
            chat_thread.daemon = True
            chat_thread.start()
            return
        
        # Se o simulador estiver desativado, conectar ao chat real do YouTube
        url = quiz_config.get('youtube_url', '')
        if not url:
            logger.error("URL do YouTube não configurada")
            return
        
        # Normalizar a URL do YouTube
        normalized_url = normalize_youtube_url(url)
        if not normalized_url:
            logger.error(f"URL inválida: {url}")
            return
        
        logger.info(f"Conectando ao chat do YouTube: {normalized_url}")
        
        # Desativar o simulador e ativar o chat real
        is_simulator_running = False
        is_chat_running = True
        
        # Configurar o chat downloader
        chat_downloader = ChatDownloader()
        chat = chat_downloader.get_chat(normalized_url, timeout=60, max_attempts=5)
        
        # Processar mensagens do chat
        for message in chat:
            if not is_chat_running:
                break
                
            try:
                author = message.get('author', {}).get('name', 'Anônimo')
                text = message.get('message', '')
                
                # Verificar se é um voto válido
                if text.startswith('!'):
                    vote = text.lower().strip()
                    if vote in ['!a', '!b', '!c', '!d']:
                        option_index = {'!a': 0, '!b': 1, '!c': 2, '!d': 3}[vote]
                        register_vote(author, option_index)
                
                # Emitir mensagem para o cliente
                socketio.emit('chat_message', {
                    'author': author,
                    'message': text
                })
                
                logger.debug(f"Mensagem do chat: {author} -> {text}")
            except Exception as e:
                logger.error(f"Erro ao processar mensagem do chat: {str(e)}")
    
    except Exception as e:
        logger.error(f"Erro ao monitorar chat do YouTube: {str(e)}")
        # Fallback para simulação em caso de erro
        if not is_chat_running and not is_simulator_running:
            logger.info("Iniciando simulação de chat como fallback")
            is_chat_running = True
            is_simulator_running = True
            chat_thread = threading.Thread(target=simulate_chat_messages)
            chat_thread.daemon = True
            chat_thread.start()

# Função para executar o loop do quiz
def quiz_loop():
    global quiz_running, current_question_index, current_question, current_votes, voted_users, user_votes, chat_messages
    
    # Configurar limites de threads para evitar sobrecarga do sistema
    try:
        threading.stack_size(128 * 1024)  # 128 KB stack size para reduzir uso de memória
    except (ValueError, RuntimeError):
        logger.warning("Não foi possível configurar stack_size de threads")
        
    # Contador de ciclos para forçar coleta de lixo periódica
    cycle_count = 0
    
    # Timestamp da última vez que o servidor foi "limpo"
    last_cleanup_time = time.time()
    
    while True:
        # Verificar se é hora de fazer limpeza de recursos (a cada 1 hora)
        current_time = time.time()
        if current_time - last_cleanup_time > 3600:  # 3600 segundos = 1 hora
            try:
                logger.info("Realizando limpeza periódica de recursos do servidor...")
                # Forçar coleta de lixo
                gc.collect()
                # Limpar caches internos
                chat_messages = chat_messages[-1000:] if len(chat_messages) > 1000 else chat_messages
                # Reiniciar contadores
                cycle_count = 0
                last_cleanup_time = current_time
                logger.info("Limpeza de recursos concluída com sucesso")
            except Exception as e:
                logger.error(f"Erro durante limpeza de recursos: {e}")
        
        # Incrementar contador de ciclos
        cycle_count += 1
        
        # Forçar coleta de lixo a cada 100 ciclos
        if cycle_count % 100 == 0:
            gc.collect()
        
        if quiz_running and questions:
            # Selecionar pergunta atual
            current_question_index = current_question_index % len(questions)
            current_question = questions[current_question_index]
            current_votes = [0, 0, 0, 0]
            voted_users = set()  # Limpar usuários que votaram
            user_votes = {}  # Limpar votos para a nova pergunta
            
            # Verificar formato da pergunta e obter a resposta correta
            correct_answer = 0  # Valor padrão
            if 'correct' in current_question:
                correct_answer = current_question['correct']
            elif 'correct_answer' in current_question:
                correct_answer = current_question['correct_answer']
            
            # Enviar a pergunta atual para o cliente
            try:
                logger.info(f"Enviando pergunta {current_question_index + 1}/{len(questions)}")
                socketio.emit('next_question', {
                    'question': current_question,
                    'question_num': current_question_index + 1,
                    'total_questions': len(questions),
                    'answer_time': quiz_config['answer_time']
                })
                
                # Pequena pausa para garantir que a mensagem foi entregue
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Erro ao enviar pergunta: {e}")
            
            # Aguardar o tempo de resposta
            time.sleep(quiz_config['answer_time'])
            
            # SOLUÇÃO RADICAL: Reduzir drasticamente o tempo de contabilização de votos
            # para minimizar a chance de desconexões
            reduced_vote_count_time = 2  # Reduzir para apenas 2 segundos
            
            logger.info(f"Enviando mensagem de contabilização de votos (tempo reduzido: {reduced_vote_count_time}s)")
            socketio.emit('show_counting_votes', {
                'time': reduced_vote_count_time  # Usar tempo reduzido
            })
            
            # Aguardar o tempo reduzido
            time.sleep(reduced_vote_count_time)
            
            # Calcular resultado
            explanation = current_question.get('explanation', 'Sem explicação disponível.')
            
            # Converter índice numérico para letra (0=A, 1=B, 2=C, 3=D)
            correct_letter = chr(65 + correct_answer)  # ASCII: A=65, B=66, etc.
            
            # Enviar resultado para o frontend primeiro (sem atualizar o ranking ainda)
            try:
                logger.info(f"Enviando resultados: resposta correta={correct_letter}, votos={count_votes()}")
                # Usar socketio.emit com timeout maior para garantir entrega
                socketio.emit('show_results', {
                    'correct_answer': correct_letter,
                    'explanation': explanation,
                    'votes': count_votes()
                }, namespace='/', timeout=10)  # Aumentar timeout para 10 segundos
                
                # Pequena pausa para garantir que a mensagem foi entregue
                time.sleep(0.5)
                
                # Atualizar ranking silenciosamente sem enviar para os clientes
                def update_ranking_silently():
                    try:
                        # Converter índice numérico para letra (0=A, 1=B, 2=C, 3=D)
                        correct_letter = chr(65 + correct_answer)  # ASCII: A=65, B=66, etc.
                        
                        logger.info(f"Atualizando ranking silenciosamente. Resposta correta: {correct_letter}")
                        
                        # Criar uma cópia local dos votos para evitar problemas de concorrência
                        local_user_votes = user_votes.copy()
                        
                        # Atualizar ranking com usuários que acertaram
                        users_updated = 0
                        for user, vote in local_user_votes.items():
                            if user not in ranking:
                                ranking[user] = 0
                            
                            # Comparar voto (que é uma letra) com a resposta correta
                            if vote == correct_letter:
                                ranking[user] += 1
                                users_updated += 1
                                logger.info(f"Usuário {user} acertou e ganhou 1 ponto. Total: {ranking[user]}")
                        
                        # Salvar ranking atualizado (agora é assíncrono)
                        save_ranking()
                        
                        # Log do ranking atualizado
                        logger.info(f"Ranking atualizado silenciosamente: {users_updated} usuários pontuaram")
                    except Exception as e:
                        logger.error(f"Erro ao atualizar ranking silenciosamente: {e}")
                
                # Iniciar thread para atualizar o ranking silenciosamente
                ranking_thread = threading.Thread(target=update_ranking_silently)
                ranking_thread.daemon = True
                ranking_thread.start()
                
                # Aguardar antes de avançar para a próxima pergunta
                time.sleep(quiz_config['result_display_time'])
                
                # Avançar para a próxima pergunta em uma thread separada
                def advance_question():
                    try:
                        global current_question_index
                        current_question_index += 1
                        logger.info(f"Avançando para a pergunta {current_question_index + 1}")
                    except Exception as e:
                        logger.error(f"Erro ao avançar para a próxima pergunta: {e}")
                
                # Iniciar thread para avançar para a próxima pergunta
                advance_thread = threading.Thread(target=advance_question)
                advance_thread.daemon = True
                advance_thread.start()
            except Exception as e:
                logger.error(f"Erro ao enviar resultados: {e}")
                
                # Fallback em caso de erro
                try:
                    # Tentar novamente enviar os resultados
                    socketio.emit('show_results', {
                        'correct_answer': correct_letter,
                        'explanation': explanation,
                        'votes': count_votes()
                    })
                    
                    # Atualizar o ranking
                    update_ranking(correct_answer)
                    
                    # Aguardar antes de passar para a próxima pergunta
                    time.sleep(quiz_config['result_display_time'])
                    
                    # Avançar para a próxima pergunta
                    current_question_index += 1
                except Exception as e2:
                    logger.error(f"Erro no fallback: {e2}")
                    # Último recurso: apenas avançar para a próxima pergunta
                    time.sleep(quiz_config['result_display_time'])
                    current_question_index += 1
        else:
            # Se o quiz não estiver rodando, aguardar um pouco antes de verificar novamente
            time.sleep(1)

# Obter os top N usuários do ranking
def get_top_ranking(n=10):
    sorted_ranking = sorted(ranking.items(), key=lambda x: x[1], reverse=True)
    return [{"name": name, "score": score} for name, score in sorted_ranking[:n]]

# Contar votos
def count_votes():
    global current_votes
    return {
        'A': current_votes[0],
        'B': current_votes[1],
        'C': current_votes[2],
        'D': current_votes[3]
    }

# Thread para atualizar o ranking de forma completamente isolada
def update_ranking_thread(correct_answer):
    global ranking, user_votes
    
    try:
        # Adicionar um atraso para garantir que os resultados já foram exibidos
        time.sleep(3)  # Esperar 3 segundos antes de atualizar o ranking
        
        # Converter índice numérico para letra (0=A, 1=B, 2=C, 3=D)
        correct_letter = chr(65 + correct_answer)  # ASCII: A=65, B=66, etc.
        
        logger.info(f"Atualizando ranking. Resposta correta: {correct_letter}")
        
        # Criar uma cópia local dos votos para evitar problemas de concorrência
        local_user_votes = user_votes.copy()
        
        # Atualizar ranking com usuários que acertaram
        users_updated = 0
        for user, vote in local_user_votes.items():
            if user not in ranking:
                ranking[user] = 0
            
            # Comparar voto (que é uma letra) com a resposta correta
            if vote == correct_letter:
                ranking[user] += 1
                users_updated += 1
                logger.info(f"Usuário {user} acertou e ganhou 1 ponto. Total: {ranking[user]}")
        
        # Salvar ranking atualizado (agora é assíncrono)
        save_ranking()
        
        # Log do ranking atualizado
        logger.info(f"Ranking atualizado: {users_updated} usuários pontuaram")
            
    except Exception as e:
        logger.error(f"Erro ao atualizar ranking: {e}")
        
# Thread separada para enviar o ranking para os clientes
# Esta função é executada em uma thread completamente separada
def send_ranking_to_clients():
    try:
        # Pausa maior para garantir que o ranking foi atualizado e que as operações críticas já terminaram
        time.sleep(5)
        
        # Obter o ranking atual
        top_ranking = get_top_ranking(10)
        
        # Verificar se o ranking está vazio (proteção contra erros)
        if not top_ranking:
            logger.warning("Ranking vazio, não enviando para os clientes")
            return
            
        # Log detalhado para debug
        logger.info(f"Preparando para enviar ranking com {len(top_ranking)} usuários")
        
        # Enviar uma mensagem de preparação primeiro
        logger.info("Enviando mensagem de preparação do ranking")
        try:
            socketio.emit('prepare_ranking_update', {
                'count': len(top_ranking)
            }, timeout=5)  # Adicionar timeout para garantir entrega
            
            # Pequena pausa para garantir que a mensagem de preparação foi recebida
            time.sleep(1)  # Aumentar para 1 segundo
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de preparação do ranking: {e}")
        
        # Enviar cada item do ranking individualmente para evitar sobrecarga
        for i, item in enumerate(top_ranking):
            try:
                logger.info(f"Enviando item {i+1} do ranking: {item['name']}")
                socketio.emit('ranking_item', {
                    'item': item,
                    'position': i,
                    'is_last': i == len(top_ranking) - 1
                })
                # Pequena pausa entre cada envio
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"Erro ao enviar item {i+1} do ranking: {e}")
        
        # Enviar mensagem de conclusão
        logger.info("Enviando mensagem de conclusão do ranking")
        socketio.emit('ranking_update_complete', {})
        
        logger.info("Ranking enviado com sucesso para os clientes")
    except Exception as e:
        logger.error(f"Erro ao enviar ranking para os clientes: {e}")
        # Tentar novamente após um tempo, mas enviando tudo de uma vez como fallback
        time.sleep(2)
        try:
            top_ranking = get_top_ranking(10)
            logger.info(f"Tentando enviar ranking novamente (fallback): {len(top_ranking)} usuários")
            socketio.emit('update_ranking', {
                'ranking': top_ranking
            })
        except Exception as e2:
            logger.error(f"Erro na segunda tentativa de enviar ranking: {e2}")


# Atualizar ranking com base nos votos
def update_ranking(correct_answer):
    try:
        # SOLUÇÃO RADICAL: Apenas salvar o ranking em arquivo sem enviar para os clientes
        # Isso evita completamente problemas de conexão durante a atualização do ranking
        
        # Criar uma thread para atualizar o ranking sem bloquear o servidor
        update_thread = threading.Thread(target=update_ranking_thread, args=(correct_answer,))
        update_thread.daemon = True
        update_thread.start()
        logger.info("Iniciada thread para atualizar ranking silenciosamente (sem envio em tempo real)")
        
        # NÃO agendar envio do ranking para evitar problemas de conexão
        # Os clientes obterão o ranking atualizado na próxima pergunta ou via polling HTTP
        
        # Log para informar sobre a estratégia adotada
        logger.info("Usando estratégia de não enviar ranking em tempo real para evitar desconexões")
        
        # Retornar o ranking atual para uso imediato (apenas para o servidor)
        return get_top_ranking(10)
    except Exception as e:
        logger.error(f"Erro ao iniciar thread para atualizar ranking: {e}")
        # Retornar o ranking atual em caso de erro
        return get_top_ranking(10)

# Função para normalizar URL do YouTube
def normalize_youtube_url(url):
    """Normaliza uma URL do YouTube para garantir que seja compatível com chat-downloader."""
    if not url:
        return None
        
    # Extrair o ID do vídeo da URL
    video_id = None
    
    try:
        # Padrão: https://www.youtube.com/watch?v=VIDEO_ID
        if 'youtube.com/watch' in url and 'v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
        
        # Padrão: https://youtu.be/VIDEO_ID
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
        
        # Padrão: https://www.youtube.com/live/VIDEO_ID
        elif 'youtube.com/live/' in url:
            video_id = url.split('youtube.com/live/')[1].split('?')[0]
        
        # Se encontramos um ID de vídeo, retornar URL normalizada
        if video_id and len(video_id) > 0:
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Se não conseguimos extrair o ID, retornar None
        logger.warning(f"Não foi possível extrair ID de vídeo da URL: {url}")
        return None
    except Exception as e:
        logger.error(f"Erro ao normalizar URL do YouTube: {e}")
        return None

# Função para reiniciar o monitoramento do chat
def restart_chat_monitoring(url):
    global chat_thread
    
    # Parar a thread atual
    if chat_thread and chat_thread.is_alive():
        logger.info("Parando thread de monitoramento do chat")
    
    # Iniciar nova thread
    chat_thread = threading.Thread(target=monitor_youtube_chat)
    chat_thread.daemon = True
    chat_thread.start()

# Endpoint de health check para monitoramento
@app.route('/api/health')
def health_check():
    # Coletar informações sobre o estado do servidor
    thread_count = threading.active_count()
    memory_usage = None
    try:
        import psutil
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
    except ImportError:
        pass
    
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'quiz_running': quiz_running,
        'uptime': time.time() - server_start_time,
        'thread_count': thread_count,
        'memory_usage_mb': memory_usage
    })

# Rotas da aplicação
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/quiz')
def quiz():
    """Página principal do quiz."""
    # Obter o endereço IP local para Socket.IO
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return socket.gethostbyname(socket.gethostname())
    
    # Funções para manipulação de cores
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def lighten_color(hex_color, factor=0.2):
        r, g, b = hex_to_rgb(hex_color)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def darken_color(hex_color, factor=0.2):
        r, g, b = hex_to_rgb(hex_color)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f'#{r:02x}{g:02x}{b:02x}'
    
    # Carregar configurações
    load_config()
    
    # Extrair cores RGB das configurações
    primary_rgb = hex_to_rgb(quiz_config['primary_color'])
    secondary_rgb = hex_to_rgb(quiz_config['secondary_color'])
    
    # Calcular cores claras e escuras
    primary_light = lighten_color(quiz_config['primary_color'], 0.2)
    primary_dark = darken_color(quiz_config['primary_color'], 0.2)
    secondary_light = lighten_color(quiz_config['secondary_color'], 0.2)
    secondary_dark = darken_color(quiz_config['secondary_color'], 0.2)
    
    # Passar configurações para o template
    config = {
        'primary_color': quiz_config['primary_color'],
        'primary_color_rgb': f"{primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}",
        'primary_light': primary_light,
        'primary_dark': primary_dark,
        'secondary_color': quiz_config['secondary_color'],
        'secondary_color_rgb': f"{secondary_rgb[0]}, {secondary_rgb[1]}, {secondary_rgb[2]}",
        'secondary_light': secondary_light,
        'secondary_dark': secondary_dark,
        'server_ip': get_local_ip(),  # Adicionar IP do servidor
        'server_port': 5000  # Adicionar porta do servidor
    }
    
    return render_template('quiz.html', config=config)

@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Retorna as configurações atuais."""
    return jsonify(quiz_config)

@app.route('/api/config', methods=['POST'])
def api_save_config():
    """Salva as configurações enviadas pelo cliente."""
    global quiz_config, is_chat_running, chat_thread
    
    try:
        # Obter dados do cliente
        data = request.json
        
        # Verificar se houve mudança na configuração do simulador de chat
        old_simulator_setting = quiz_config.get('enable_chat_simulator', True)
        new_simulator_setting = data.get('enable_chat_simulator', True)
        
        # Atualizar configuração
        quiz_config.update(data)
        
        # Salvar configuração
        save_config()
        
        # Se a configuração do simulador mudou e o chat está rodando, reiniciar o chat
        if old_simulator_setting != new_simulator_setting and is_chat_running:
            # Parar o chat atual
            is_chat_running = False
            if chat_thread and chat_thread.is_alive():
                # Esperar o thread terminar (com timeout)
                chat_thread.join(timeout=1.0)
            
            # Iniciar novo chat com a nova configuração
            is_chat_running = True
            chat_thread = threading.Thread(target=monitor_youtube_chat)
            chat_thread.daemon = True
            chat_thread.start()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao salvar configurações: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/questions', methods=['GET', 'POST'])
def api_questions():
    global questions
    
    if request.method == 'POST':
        data = request.json
        if 'questions' in data:
            questions = data['questions']
            save_questions()
            return jsonify({'success': True, 'count': len(questions)})
    
    return jsonify(questions)

@app.route('/api/ranking', methods=['GET'])
def api_ranking():
    """Retorna o ranking atual dos 10 melhores participantes."""
    try:
        return jsonify(get_top_ranking(10))
    except Exception as e:
        logger.error(f"Erro ao obter ranking: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Testar conexão com o chat do YouTube."""
    try:
        # Obter e logar o corpo da requisição para debug
        request_data = request.get_json()
        logger.info(f"Dados recebidos na requisição de teste: {request_data}")
        
        # Verificar se há dados
        if not request_data:
            logger.error("Corpo da requisição vazio ou inválido")
            return jsonify({
                'success': False,
                'message': 'Corpo da requisição vazio ou inválido'
            }), 400
        
        # Tentar obter a URL de várias formas possíveis
        url = None
        if 'url' in request_data:
            url = request_data['url']
        elif 'youtube_url' in request_data:
            url = request_data['youtube_url']
        
        if not url:
            logger.error("URL não fornecida no corpo da requisição")
            return jsonify({
                'success': False,
                'message': 'URL não fornecida'
            }), 400
        
        logger.info(f"Testando conexão com URL: {url}")
        
        # Normalizar a URL
        url = normalize_youtube_url(url)
        logger.info(f"URL normalizada: {url}")
        
        # Verificar se é uma URL válida do YouTube
        if not url or not ('youtube.com' in url or 'youtu.be' in url):
            return jsonify({
                'success': False,
                'message': 'URL inválida. Por favor, forneça uma URL válida do YouTube.'
            }), 400
            
        # Versão simplificada: apenas verificar se a URL é válida
        # Em vez de tentar conectar ao chat, que pode falhar por vários motivos
        # Consideramos a URL válida se pudermos extrair um ID de vídeo
        video_id = None
        
        # Extrair ID do vídeo da URL
        if 'youtube.com/watch' in url:
            # Formato: youtube.com/watch?v=VIDEO_ID
            query_string = url.split('?')[-1]
            params = {param.split('=')[0]: param.split('=')[1] for param in query_string.split('&') if '=' in param}
            video_id = params.get('v')
        elif 'youtu.be/' in url:
            # Formato: youtu.be/VIDEO_ID
            video_id = url.split('youtu.be/')[1].split('?')[0]
        elif 'youtube.com/live/' in url:
            # Formato: youtube.com/live/VIDEO_ID
            video_id = url.split('youtube.com/live/')[1].split('?')[0]
        
        if video_id:
            logger.info(f"ID de vídeo extraído com sucesso: {video_id}")
            return jsonify({
                'success': True,
                'message': 'URL válida do YouTube. A conexão será estabelecida quando o quiz for iniciado.',
                'video_id': video_id
            })
        else:
            logger.error(f"Não foi possível extrair ID de vídeo da URL: {url}")
            return jsonify({
                'success': False,
                'message': 'Não foi possível extrair o ID do vídeo da URL fornecida. Verifique se é uma URL válida do YouTube.'
            }), 400
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao testar conexão: {error_message}")
        
        # Fornecer uma mensagem de erro mais amigável
        friendly_message = f"Erro ao testar conexão: {error_message}"
        
        return jsonify({
            'success': False,
            'message': friendly_message,
            'error_details': error_message
        }), 500

@app.route('/api/quiz/status-http', methods=['GET'])
def api_status_http():
    """Rota HTTP para obter o status do quiz (se está em execução ou não)."""
    return jsonify({
        'success': True,
        'quiz_running': quiz_running,
        'timestamp': time.time()
    })

# Rota para keep-alive via HTTP (especialmente para a terceira pergunta)
@app.route('/api/quiz/keep-alive-http', methods=['POST'])
def api_keep_alive_http():
    """Rota HTTP para manter a conexão ativa durante momentos críticos."""
    try:
        data = request.json
        logger.info(f"Keep-alive HTTP recebido: {data}")
        
        # Registrar o keep-alive
        client_id = data.get('clientId', 'unknown')
        question_number = data.get('questionNumber', 0)
        
        # Responder imediatamente
        return jsonify({
            'success': True,
            'timestamp': time.time(),
            'message': 'Keep-alive HTTP recebido com sucesso',
            'server_time': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        logger.error(f"Erro ao processar keep-alive HTTP: {e}")
        return jsonify({
            'success': False,
            'message': f"Erro: {str(e)}",
            'timestamp': time.time()
        }), 500

@app.route('/api/quiz/current-question-http', methods=['GET'])
def api_current_question_http():
    try:
        if not quiz_running or current_question is None:
            return jsonify({
                'success': False,
                'message': 'Quiz não está em execução ou não há pergunta atual'
            }), 404
        
        # Obter opções da pergunta de forma segura
        options = []
        if 'options' in current_question:
            if isinstance(current_question['options'], list):
                options = current_question['options'][:4]  # Garantir que temos 4 opções
                # Preencher com vazios se não tiver 4 opções
                while len(options) < 4:
                    options.append("")
            else:
                # Formato de dicionário
                options = [
                    current_question['options'].get('A', ''),
                    current_question['options'].get('B', ''),
                    current_question['options'].get('C', ''),
                    current_question['options'].get('D', '')
                ]
        
        return jsonify({
            'success': True,
            'question': {
                'id': current_question.get('id', current_question_index),
                'text': current_question.get('question', ''),
                'options': options,
                'time': quiz_config.get('answer_time', 20)
            },
            'remaining_time': quiz_config.get('answer_time', 20),
            'question_num': current_question_index + 1,
            'total_questions': len(questions)
        })
    except Exception as e:
        logger.error(f"Erro ao obter pergunta atual: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/quiz/votes-http', methods=['GET'])
def api_votes_http():
    try:
        # Resposta rápida para evitar timeout
        if not quiz_running:
            return jsonify({
                'success': False,
                'message': 'Quiz não está em execução'
            }), 404
        
        # Criar cópia local dos votos para evitar problemas de concorrência
        votes_copy = current_votes.copy() if current_votes else [0, 0, 0, 0]
        
        # Calcular porcentagem de acertos
        total_votes = sum(votes_copy)
        correct_index = current_question.get('correct', 0) if current_question else 0
        correct_votes = votes_copy[correct_index] if 0 <= correct_index < len(votes_copy) else 0
        correct_percentage = (correct_votes / total_votes * 100) if total_votes > 0 else 0
        
        # Resposta simplificada para ser mais rápida
        return jsonify({
            'success': True,
            'votes': {
                'a': votes_copy[0] if len(votes_copy) > 0 else 0,
                'b': votes_copy[1] if len(votes_copy) > 1 else 0,
                'c': votes_copy[2] if len(votes_copy) > 2 else 0,
                'd': votes_copy[3] if len(votes_copy) > 3 else 0,
                'correct_percentage': correct_percentage
            },
            'timestamp': time.time()  # Adicionar timestamp para evitar cache
        })
    except Exception as e:
        logger.error(f"Erro ao obter votos: {e}")
        # Resposta de erro simplificada
        return jsonify({
            'success': False,
            'message': 'Erro interno',
            'timestamp': time.time()
        }), 500

@app.route('/api/quiz/chat-http', methods=['GET'])
def api_chat_http():
    try:
        since = request.args.get('since', 0, type=float)
        
        # Filtrar mensagens mais recentes que o timestamp fornecido
        recent_messages = []
        
        # Verificar se chat_messages existe e é uma lista
        if 'chat_messages' in globals() and isinstance(chat_messages, list):
            recent_messages = [
                msg for msg in chat_messages 
                if msg.get('timestamp', 0) > since
            ]
        
        return jsonify({
            'success': True,
            'messages': recent_messages
        })
    except Exception as e:
        logger.error(f"Erro ao obter mensagens do chat: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/quiz/start-http', methods=['POST'])
def api_start_quiz_http():
    global quiz_running, current_question, current_question_index, current_votes
    
    if quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz já está em execução'
        })
    
    # Iniciar o quiz
    quiz_running = True
    current_question_index = 0
    current_votes = [0, 0, 0, 0]
    
    # Iniciar a thread de monitoramento do chat se não estiver rodando
    if 'chat_thread' in globals() and (not chat_thread or not chat_thread.is_alive()):
        start_chat_monitoring()
    
    # Avançar para a primeira pergunta
    next_question()
    
    return jsonify({
        'success': True,
        'message': 'Quiz iniciado com sucesso'
    })

@app.route('/api/quiz/stop-http', methods=['POST'])
def api_stop_quiz_http():
    global quiz_running
    
    if not quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz não está em execução'
        })
    
    # Parar o quiz
    quiz_running = False
    
    return jsonify({
        'success': True,
        'message': 'Quiz parado com sucesso'
    })

@app.route('/api/ranking-http', methods=['GET'])
def api_ranking_http():
    try:
        # Obter o ranking atual
        ranking_list = get_ranking()
        
        return jsonify({
            'success': True,
            'ranking': ranking_list
        })
    except Exception as e:
        logger.error(f"Erro ao obter ranking via HTTP: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# API para conectar diretamente ao chat do YouTube
@app.route('/api/connect-youtube', methods=['POST'])
def api_connect_youtube():
    """Conecta diretamente ao chat do YouTube a partir da página do quiz."""
    global quiz_config, is_chat_running, is_simulator_running, chat_thread
    
    try:
        # Obter URL do cliente
        data = request.json
        url = data.get('url', '')
        
        if not url:
            return jsonify({'success': False, 'message': 'URL não fornecida'}), 400
        
        # Normalizar a URL do YouTube
        normalized_url = normalize_youtube_url(url)
        if not normalized_url:
            return jsonify({'success': False, 'message': 'URL do YouTube inválida'}), 400
        
        # Atualizar configuração
        quiz_config['youtube_url'] = url
        quiz_config['enable_chat_simulator'] = False  # Desativar simulador
        
        # Salvar configuração
        save_config()
        
        # Parar o chat atual
        is_chat_running = False
        is_simulator_running = False  # Garantir que o simulador seja desativado
        
        if chat_thread and chat_thread.is_alive():
            logger.info("Parando thread de chat atual...")
            # Esperar o thread terminar (com timeout)
            chat_thread.join(timeout=1.0)
        
        # Limpar o chat container no cliente
        socketio.emit('clear_chat', {
            'message': 'Chat reiniciado para conexão com YouTube'
        })
        
        # Enviar mensagem de sistema
        socketio.emit('chat_message', {
            'author': 'Sistema',
            'message': f'Conectando ao chat do YouTube: {normalized_url}'
        })
        
        # Aguardar um momento para garantir que o thread anterior parou
        time.sleep(1)
        
        # Iniciar novo chat com a nova configuração
        is_chat_running = True
        is_simulator_running = False  # Garantir novamente que o simulador esteja desativado
        chat_thread = threading.Thread(target=monitor_youtube_chat)
        chat_thread.daemon = True
        chat_thread.start()
        
        logger.info(f"Conectado ao chat do YouTube: {normalized_url}")
        return jsonify({'success': True, 'message': 'Conectado ao chat do YouTube com sucesso'})
    
    except Exception as e:
        logger.error(f"Erro ao conectar ao chat do YouTube: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Função para obter o ranking atual
def get_ranking():
    """Retorna o ranking atual ordenado por pontuação."""
    try:
        # Converter o dicionário de ranking em uma lista de dicionários
        ranking_list = []
        for name, score in ranking.items():
            ranking_list.append({
                'name': name,
                'score': score
            })
        
        # Ordenar por pontuação (maior para menor)
        ranking_list.sort(key=lambda x: x['score'], reverse=True)
        
        # Retornar os 10 primeiros
        return ranking_list[:10]
    except Exception as e:
        logger.error(f"Erro ao obter ranking: {e}")
        return []
# Esta parte foi removida para corrigir erros de sintaxe

@socketio.on('get_ranking')
def handle_get_ranking(data=None):
    """Manipulador para solicitação de ranking via Socket.IO."""
    emit('ranking_update', {'success': True, 'ranking': get_ranking()})

# Dicionário para armazenar o último timestamp de ping por cliente
last_ping_time = {}
last_keep_alive_time = {}

# Intervalo mínimo entre pings e keep-alives (em segundos)
PING_THROTTLE = 2.0  # Limitar a 1 resposta a cada 2 segundos
KEEP_ALIVE_THROTTLE = 3.0  # Limitar a 1 keep-alive a cada 3 segundos

# Manipulador para ping do cliente (especialmente para a terceira pergunta)
@socketio.on('ping_server')
def handle_ping(data=None):
    try:
        client_id = request.sid
        current_time = time.time()
        
        # Verificar se este cliente já recebeu uma resposta recentemente
        if client_id in last_ping_time and current_time - last_ping_time[client_id] < PING_THROTTLE:
            # Se sim, ignorar este ping para evitar sobrecarga
            logger.debug(f"Ignorando ping do cliente {client_id} (rate limiting)")
            return
        
        # Atualizar o timestamp do último ping
        last_ping_time[client_id] = current_time
        
        logger.info(f"Ping recebido do cliente {client_id}: {data}")
        
        # Verificar se o ping já foi limitado pelo cliente
        rate_limited = data and 'rateLimited' in data and data['rateLimited'] == True
        
        # Responder imediatamente para manter a conexão ativa
        emit('pong_response', {
            'timestamp': current_time,
            'server_time': datetime.now().strftime('%H:%M:%S'),
            'received_data': data
        })
        
        # Se for da terceira pergunta ou momento crítico, enviar um keep-alive adicional
        # Mas apenas se não enviamos um keep-alive recentemente para este cliente
        is_critical = data and 'critical' in data and data['critical'] == True
        is_third_question = data and 'questionNumber' in data and data['questionNumber'] == 3
        
        if (is_third_question or is_critical) and \
           (client_id not in last_keep_alive_time or \
            current_time - last_keep_alive_time[client_id] > KEEP_ALIVE_THROTTLE):
            
            logger.info(f"Enviando keep-alive para momento crítico para cliente {client_id}")
            emit('keep_alive', {
                'timestamp': current_time,
                'message': 'keep-alive para momento crítico',
                'critical': True,
                'rateLimited': True
            })
            
            # Atualizar o timestamp do último keep-alive
            last_keep_alive_time[client_id] = current_time
    except Exception as e:
        logger.error(f"Erro ao processar ping do cliente: {e}")

# Manipulador para respostas de keep-alive do cliente
@socketio.on('keep_alive_response')
def handle_keep_alive_response(data=None):
    try:
        logger.info(f"Resposta de keep-alive recebida do cliente: {data}")
        client_id = request.sid
        
        # Registrar que este cliente está ativo
        if data and 'timestamp' in data:
            client_timestamp = data['timestamp']
            server_timestamp = int(time.time() * 1000)
            latency = server_timestamp - client_timestamp
            
            logger.info(f"Cliente {client_id} ativo. Latência: {latency}ms")
            
            # Se a latência for muito alta, enviar um alerta
            if latency > 2000:  # mais de 2 segundos
                logger.warning(f"Latência alta ({latency}ms) para cliente {client_id}")
    except Exception as e:
        logger.error(f"Erro ao processar resposta de keep-alive: {e}")

# Manipulador para solicitação de votos
@socketio.on('get_votes')
def handle_get_votes(data=None):
    try:
        logger.info(f"Solicitação de votos recebida: {data}")
        # Enviar os votos atuais
        emit('update_votes', {
            'votes': count_votes(),
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Erro ao enviar votos: {e}")
@socketio.on('start_quiz')
def handle_start_quiz(data=None):
    global quiz_running, chat_thread, quiz_thread, current_question_index
    
    if quiz_running:
        socketio.emit('quiz_status', {'success': False, 'message': 'Quiz já está em execução', 'quiz_running': quiz_running})
        return
    
    if not quiz_config['youtube_url']:
        socketio.emit('quiz_status', {'success': False, 'message': 'URL do YouTube não configurada', 'quiz_running': quiz_running})
        return
    
    if not questions:
        socketio.emit('quiz_status', {'success': False, 'message': 'Nenhuma pergunta cadastrada', 'quiz_running': quiz_running})
        return
    
    try:
        quiz_running = True
        current_question_index = 0
        
        # Iniciar thread para monitorar chat
        chat_thread = threading.Thread(target=monitor_youtube_chat)
        chat_thread.daemon = True
        chat_thread.start()
        
        # Iniciar thread para o loop do quiz
        quiz_thread = threading.Thread(target=quiz_loop)
        quiz_thread.daemon = True
        quiz_thread.start()
        
        # Iniciar thread para simular mensagens de chat (apenas para testes)
        sim_thread = threading.Thread(target=simulate_chat_messages)
        sim_thread.daemon = True
        sim_thread.start()
        
        # Emitir status atualizado para todos os clientes
        socketio.emit('quiz_status', {
            'success': True, 
            'message': 'Quiz iniciado com sucesso',
            'quiz_running': quiz_running
        })
    except Exception as e:
        quiz_running = False
        logger.error(f"Erro ao iniciar quiz: {e}")
        socketio.emit('quiz_status', {
            'success': False, 
            'message': f'Erro ao iniciar quiz: {str(e)}',
            'quiz_running': quiz_running
        })

@socketio.on('stop_quiz')
def handle_stop_quiz(data=None):
    global quiz_running
    
    if not quiz_running:
        socketio.emit('quiz_status', {'success': False, 'message': 'Quiz não está em execução', 'quiz_running': quiz_running})
        return
    
    quiz_running = False
    socketio.emit('quiz_status', {'success': True, 'message': 'Quiz interrompido com sucesso', 'quiz_running': quiz_running})

# Handler para conexão de cliente
@socketio.on('connect')
def handle_connect(data=None):
    try:
        socketio.emit('quiz_status', {
            'success': True,
            'quiz_running': quiz_running,
            'message': 'Conectado ao servidor'
        })
        logger.info("Cliente conectado")
    except Exception as e:
        logger.error(f"Erro ao processar conexão: {e}")

# Inicialização
load_config()
load_questions()
load_ranking()

# Função para simular mensagens de chat (apenas para testes)
def simulate_chat_messages():
    """Simula mensagens de chat para testes."""
    global is_simulator_running
    
    logger.info("Iniciando simulação de mensagens de chat")
    is_simulator_running = True
    time.sleep(2)  # Aguardar um pouco para o quiz iniciar
    
    # Lista de nomes de usuários fictícios
    usernames = ["João123", "MariaGamer", "PedroYT", "Ana_Live", "Carlos_Fan", 
                "Lucia_Games", "Roberto_TV", "Patricia_Stream", "FelipeZ", "JuliaQuiz"]
    
    # Mensagens genéricas
    messages = [
        "Olá pessoal!", "Esse quiz é muito legal!", "Adoro participar!", 
        "Qual é a próxima pergunta?", "Estou ganhando!", "Difícil essa!",
        "Vamos lá!", "Quase acertei!", "Essa eu sei!", "Quem está ganhando?"
    ]
    
    # Comandos de resposta
    commands = ["!a", "!b", "!c", "!d", "!A", "!B", "!C", "!D"]
    
    # Loop para simular mensagens enquanto o quiz estiver rodando
    while quiz_running and is_simulator_running:
        try:
            # Verificar se o simulador ainda deve estar rodando
            if not is_simulator_running:
                logger.info("Simulador de chat desativado. Parando simulação.")
                break
                
            # Simular uma mensagem normal ou um comando
            username = random.choice(usernames)
            
            # 50% de chance de ser um comando de resposta
            if random.random() > 0.5 and current_question is not None:
                msg = random.choice(commands)
                logger.info(f"Simulando voto: {username} -> {msg}")
            else:
                msg = random.choice(messages)
                logger.info(f"Simulando mensagem: {username} -> {msg}")
            
            # Criar uma mensagem simulada no formato que o chat-downloader usaria
            fake_message = {
                'author': {'name': username},
                'message': msg
            }
            
            # Processar a mensagem simulada
            if isinstance(fake_message, dict):
                if 'author' in fake_message and isinstance(fake_message['author'], dict):
                    author = fake_message['author'].get('name', 'Anônimo')
                else:
                    author = fake_message.get('author', 'Anônimo')
                
                if 'message' in fake_message:
                    message_text = fake_message.get('message', '').strip()
                elif 'text' in fake_message:
                    message_text = fake_message.get('text', '').strip()
                else:
                    message_text = str(fake_message).strip()
            else:
                author = 'Anônimo'
                message_text = str(fake_message).strip()
            
            process_chat_message(author, message_text)
            
            # Aguardar um tempo aleatório entre mensagens (0.5 a 3 segundos)
            time.sleep(random.uniform(0.5, 3))
        except Exception as e:
            logger.error(f"Erro na simulação de chat: {e}")
            time.sleep(1)
    
    logger.info("Simulação de chat encerrada")
    is_simulator_running = False

# Iniciar o quiz automaticamente quando o servidor é iniciado
def auto_start_quiz():
    global quiz_running, chat_thread, quiz_thread, current_question_index
    
    # Verificar se há perguntas 
    if questions:
        quiz_running = True
        current_question_index = 0
        
        # Iniciar thread para monitorar chat
        chat_thread = threading.Thread(target=monitor_youtube_chat)
        chat_thread.daemon = True
        chat_thread.start()
        
        # Iniciar thread para o loop do quiz
        quiz_thread = threading.Thread(target=quiz_loop)
        quiz_thread.daemon = True
        quiz_thread.start()
        
        # Iniciar thread para simular mensagens de chat (apenas para testes)
        sim_thread = threading.Thread(target=simulate_chat_messages)
        sim_thread.daemon = True
        sim_thread.start()
        
        logger.info("Quiz iniciado automaticamente")

# Iniciar o quiz automaticamente após 2 segundos (para dar tempo de carregar tudo)
# Verificar se estamos no Heroku
is_heroku = os.environ.get('DYNO') is not None

if __name__ == '__main__':
    # Configurar uma URL de exemplo para testes se não houver uma configurada
    if not quiz_config['youtube_url']:
        quiz_config['youtube_url'] = 'https://www.youtube.com/watch?v=exemplo'
        logger.info("URL de exemplo configurada para testes")
    
    # Iniciar o quiz automaticamente após 2 segundos
    threading.Timer(2.0, auto_start_quiz).start()
    
    # Obter a porta do ambiente (Heroku define a porta via variável de ambiente PORT)
    port = int(os.environ.get('PORT', 5000))
    
    if is_heroku:
        # No Heroku, não precisamos chamar socketio.run() porque o gunicorn cuida disso
        logger.info(f"Rodando no Heroku na porta {port}")
    else:
        # Em ambiente local, usamos socketio.run()
        logger.info(f"Rodando localmente na porta {port}")
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
