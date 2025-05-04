"""
Versão simplificada do app.py para deploy no Render.com
Esta versão usa apenas Flask e comunicação HTTP, sem Socket.IO,
para evitar problemas de compatibilidade com Python 3.11.
"""
import os
import json
import time
import threading
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Criar a aplicação Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'quiz-youtube-live-secret-key'

# Diretório para armazenar dados
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Variáveis globais
quiz_running = False
current_question_index = 0
current_question = None
questions = []
current_votes = [0, 0, 0, 0]  # Votos para as opções A, B, C, D
voted_users = set()  # Conjunto de usuários que já votaram
user_votes = {}  # Dicionário para armazenar o voto de cada usuário
ranking = {}  # Ranking dos usuários
chat_messages = []  # Mensagens de chat

# Configurações do quiz
quiz_config = {
    'youtube_url': '',
    'answer_time': 20,  # Tempo para responder cada pergunta (em segundos)
    'result_display_time': 10,  # Tempo para exibir o resultado (em segundos)
    'auto_start': True  # Iniciar o quiz automaticamente
}

# Carregar perguntas do arquivo JSON
def load_questions():
    global questions
    try:
        questions_file = os.path.join(DATA_DIR, 'questions.json')
        if os.path.exists(questions_file):
            with open(questions_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            logger.info(f"Carregadas {len(questions)} perguntas do arquivo")
        else:
            # Criar perguntas de exemplo se o arquivo não existir
            questions = [
                {
                    "question": "Qual é a capital do Brasil?",
                    "options": ["Rio de Janeiro", "São Paulo", "Brasília", "Salvador"],
                    "correct": 2
                },
                {
                    "question": "Quem escreveu 'Dom Casmurro'?",
                    "options": ["José de Alencar", "Machado de Assis", "Carlos Drummond de Andrade", "Clarice Lispector"],
                    "correct": 1
                }
            ]
            save_questions()
            logger.info("Criadas perguntas de exemplo")
    except Exception as e:
        logger.error(f"Erro ao carregar perguntas: {e}")
        questions = []

# Salvar perguntas no arquivo JSON
def save_questions():
    try:
        questions_file = os.path.join(DATA_DIR, 'questions.json')
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        logger.info(f"Salvas {len(questions)} perguntas no arquivo")
    except Exception as e:
        logger.error(f"Erro ao salvar perguntas: {e}")

# Carregar ranking do arquivo JSON
def load_ranking():
    global ranking
    try:
        ranking_file = os.path.join(DATA_DIR, 'ranking.json')
        if os.path.exists(ranking_file):
            with open(ranking_file, 'r', encoding='utf-8') as f:
                ranking = json.load(f)
            logger.info(f"Ranking carregado com {len(ranking)} usuários")
        else:
            ranking = {}
            save_ranking()
    except Exception as e:
        logger.error(f"Erro ao carregar ranking: {e}")
        ranking = {}

# Salvar ranking no arquivo JSON
def save_ranking():
    try:
        ranking_file = os.path.join(DATA_DIR, 'ranking.json')
        with open(ranking_file, 'w', encoding='utf-8') as f:
            json.dump(ranking, f, ensure_ascii=False, indent=2)
        logger.info("Ranking salvo")
    except Exception as e:
        logger.error(f"Erro ao salvar ranking: {e}")

# Contar votos
def count_votes():
    total_votes = sum(current_votes)
    if total_votes == 0:
        return {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    
    return {
        'A': current_votes[0],
        'B': current_votes[1],
        'C': current_votes[2],
        'D': current_votes[3]
    }

# Atualizar ranking com base nos votos
def update_ranking(correct_answer):
    global ranking
    
    # Converter índice numérico para letra (0=A, 1=B, 2=C, 3=D)
    correct_letter = chr(65 + correct_answer)  # ASCII: A=65, B=66, etc.
    
    # Atualizar ranking com usuários que acertaram
    for user, vote in user_votes.items():
        if user not in ranking:
            ranking[user] = 0
        
        # Comparar voto (que é uma letra) com a resposta correta
        if vote == correct_letter:
            ranking[user] += 1
            logger.info(f"Usuário {user} acertou e ganhou 1 ponto. Total: {ranking[user]}")
    
    # Salvar ranking atualizado
    save_ranking()

# Carregar dados iniciais
load_questions()
load_ranking()

# Rotas da API

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/quiz-http')
def quiz_http():
    return render_template('quiz-http.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/quiz/status', methods=['GET'])
def api_quiz_status():
    """Rota para obter o status atual do quiz."""
    global quiz_running, current_question_index, current_question
    
    if not quiz_running:
        return jsonify({
            'running': False,
            'message': 'Quiz não está em execução'
        })
    
    if current_question_index >= len(questions):
        return jsonify({
            'running': True,
            'message': 'Quiz concluído',
            'completed': True
        })
    
    return jsonify({
        'running': True,
        'message': 'Quiz em execução',
        'completed': False,
        'current_question': current_question_index + 1,
        'total_questions': len(questions),
        'question': current_question,
        'answer_time': quiz_config['answer_time']
    })

@app.route('/api/quiz/votes', methods=['GET'])
def api_get_votes():
    """Rota para obter os votos atuais."""
    return jsonify({
        'votes': count_votes(),
        'timestamp': time.time()
    })

@app.route('/api/quiz/vote', methods=['POST'])
def api_vote():
    """Rota para registrar um voto."""
    global current_votes, voted_users, user_votes
    
    if not quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz não está em execução'
        })
    
    data = request.json
    user = data.get('user', 'Anônimo')
    vote = data.get('vote', '').upper()
    
    if vote not in ['A', 'B', 'C', 'D']:
        return jsonify({
            'success': False,
            'message': 'Voto inválido. Use A, B, C ou D.'
        })
    
    if user in voted_users:
        # Usuário já votou, atualizar o voto
        old_vote = user_votes.get(user)
        if old_vote:
            old_vote_index = ord(old_vote) - 65  # Converter A->0, B->1, etc.
            current_votes[old_vote_index] -= 1
    else:
        voted_users.add(user)
    
    # Registrar o novo voto
    vote_index = ord(vote) - 65  # Converter A->0, B->1, etc.
    current_votes[vote_index] += 1
    user_votes[user] = vote
    
    logger.info(f"Voto registrado: {user} votou na opção !{vote}")
    
    return jsonify({
        'success': True,
        'message': f'Voto registrado: {vote}',
        'votes': count_votes()
    })

@app.route('/api/quiz/chat', methods=['GET'])
def api_get_chat():
    """Rota para obter as mensagens de chat."""
    return jsonify({
        'messages': chat_messages[-50:],  # Retornar apenas as últimas 50 mensagens
        'timestamp': time.time()
    })

@app.route('/api/quiz/chat', methods=['POST'])
def api_send_chat():
    """Rota para enviar uma mensagem de chat."""
    global chat_messages
    
    data = request.json
    user = data.get('user', 'Anônimo')
    message = data.get('message', '')
    
    if not message:
        return jsonify({
            'success': False,
            'message': 'Mensagem vazia'
        })
    
    chat_message = {
        'author': user,
        'message': message,
        'timestamp': time.time()
    }
    
    chat_messages.append(chat_message)
    
    # Limitar o número de mensagens armazenadas
    if len(chat_messages) > 1000:
        chat_messages = chat_messages[-1000:]
    
    logger.info(f"Mensagem de chat: {user} -> {message}")
    
    return jsonify({
        'success': True,
        'message': 'Mensagem enviada'
    })

@app.route('/api/quiz/ranking', methods=['GET'])
def api_get_ranking():
    """Rota para obter o ranking atual."""
    # Converter o ranking para uma lista ordenada
    ranking_list = [{'user': user, 'score': score} for user, score in ranking.items()]
    ranking_list.sort(key=lambda x: x['score'], reverse=True)
    
    return jsonify({
        'ranking': ranking_list,
        'timestamp': time.time()
    })

@app.route('/api/quiz/current_question', methods=['GET'])
def api_get_current_question():
    """Rota para obter a pergunta atual."""
    global current_question, current_question_index
    
    if not quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz não está em execução'
        })
    
    if current_question_index >= len(questions):
        return jsonify({
            'success': False,
            'message': 'Quiz concluído'
        })
    
    return jsonify({
        'success': True,
        'question': current_question,
        'question_num': current_question_index + 1,
        'total_questions': len(questions),
        'answer_time': quiz_config['answer_time']
    })

@app.route('/api/quiz/results', methods=['GET'])
def api_get_results():
    """Rota para obter os resultados da pergunta atual."""
    global current_question
    
    if not quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz não está em execução'
        })
    
    if not current_question:
        return jsonify({
            'success': False,
            'message': 'Nenhuma pergunta atual'
        })
    
    # Verificar formato da pergunta e obter a resposta correta
    correct_answer = 0  # Valor padrão
    if 'correct' in current_question:
        correct_answer = current_question['correct']
    elif 'correct_answer' in current_question:
        correct_answer = current_question['correct_answer']
    
    # Converter índice numérico para letra (0=A, 1=B, 2=C, 3=D)
    correct_letter = chr(65 + correct_answer)  # ASCII: A=65, B=66, etc.
    
    explanation = current_question.get('explanation', 'Sem explicação disponível.')
    
    return jsonify({
        'success': True,
        'correct_answer': correct_letter,
        'explanation': explanation,
        'votes': count_votes()
    })

@app.route('/api/quiz/keep-alive-http', methods=['POST'])
def api_keep_alive_http():
    """Rota HTTP para manter a conexão ativa durante momentos críticos."""
    try:
        data = request.json
        logger.info(f"Keep-alive HTTP recebido: {data}")
        
        return jsonify({
            'success': True,
            'message': 'Keep-alive HTTP recebido com sucesso',
            'timestamp': time.time(),
            'server_time': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        logger.error(f"Erro no keep-alive HTTP: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro: {str(e)}',
            'timestamp': time.time()
        })

@app.route('/api/quiz/start', methods=['POST'])
def api_start_quiz():
    """Rota para iniciar o quiz."""
    global quiz_running, current_question_index, current_question, current_votes, voted_users, user_votes
    
    if quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz já está em execução'
        })
    
    if not questions:
        return jsonify({
            'success': False,
            'message': 'Nenhuma pergunta disponível'
        })
    
    # Iniciar o quiz
    quiz_running = True
    current_question_index = 0
    current_question = questions[current_question_index]
    current_votes = [0, 0, 0, 0]
    voted_users = set()
    user_votes = {}
    
    # Iniciar thread para executar o loop do quiz
    quiz_thread = threading.Thread(target=quiz_loop)
    quiz_thread.daemon = True
    quiz_thread.start()
    
    logger.info("Quiz iniciado")
    
    return jsonify({
        'success': True,
        'message': 'Quiz iniciado',
        'question': current_question,
        'question_num': current_question_index + 1,
        'total_questions': len(questions),
        'answer_time': quiz_config['answer_time']
    })

@app.route('/api/quiz/stop', methods=['POST'])
def api_stop_quiz():
    """Rota para parar o quiz."""
    global quiz_running
    
    if not quiz_running:
        return jsonify({
            'success': False,
            'message': 'Quiz não está em execução'
        })
    
    # Parar o quiz
    quiz_running = False
    
    logger.info("Quiz parado")
    
    return jsonify({
        'success': True,
        'message': 'Quiz parado'
    })

# Função para executar o loop do quiz
def quiz_loop():
    global quiz_running, current_question_index, current_question, current_votes, voted_users, user_votes, chat_messages
    
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
            
            # Aguardar o tempo de resposta
            logger.info(f"Pergunta {current_question_index + 1}/{len(questions)} - Aguardando {quiz_config['answer_time']} segundos")
            time.sleep(quiz_config['answer_time'])
            
            # SOLUÇÃO RADICAL: Reduzir drasticamente o tempo de contabilização de votos
            # para minimizar a chance de desconexões
            reduced_vote_count_time = 2  # Reduzir para apenas 2 segundos
            
            logger.info(f"Contabilizando votos (tempo reduzido: {reduced_vote_count_time}s)")
            time.sleep(reduced_vote_count_time)
            
            # Calcular resultado
            explanation = current_question.get('explanation', 'Sem explicação disponível.')
            
            # Converter índice numérico para letra (0=A, 1=B, 2=C, 3=D)
            correct_letter = chr(65 + correct_answer)  # ASCII: A=65, B=66, etc.
            
            # Atualizar ranking silenciosamente
            try:
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
                
                # Salvar ranking atualizado
                save_ranking()
                
                # Log do ranking atualizado
                logger.info(f"Ranking atualizado: {users_updated} usuários pontuaram")
            except Exception as e:
                logger.error(f"Erro ao atualizar ranking: {e}")
            
            # Aguardar antes de avançar para a próxima pergunta
            logger.info(f"Exibindo resultados por {quiz_config['result_display_time']} segundos")
            time.sleep(quiz_config['result_display_time'])
            
            # Avançar para a próxima pergunta
            current_question_index += 1
            logger.info(f"Avançando para a pergunta {current_question_index + 1}")
        else:
            # Se o quiz não estiver rodando, aguardar um pouco antes de verificar novamente
            time.sleep(1)

# Iniciar o quiz automaticamente após 2 segundos (para dar tempo de carregar tudo)
def auto_start_quiz():
    global quiz_running
    
    if quiz_config['auto_start'] and not quiz_running and questions:
        # Iniciar o quiz
        quiz_running = True
        
        # Iniciar thread para executar o loop do quiz
        quiz_thread = threading.Thread(target=quiz_loop)
        quiz_thread.daemon = True
        quiz_thread.start()
        
        logger.info("Quiz iniciado automaticamente")

# Verificar se estamos no Heroku ou Render
is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER') is not None or os.environ.get('DYNO') is not None

if __name__ == '__main__':
    # Configurar uma URL de exemplo para testes se não houver uma configurada
    if not quiz_config['youtube_url']:
        quiz_config['youtube_url'] = 'https://www.youtube.com/watch?v=exemplo'
        logger.info("URL de exemplo configurada para testes")
    
    # Iniciar o quiz automaticamente após 2 segundos
    threading.Timer(2.0, auto_start_quiz).start()
    
    # Obter a porta do ambiente (Render/Heroku define a porta via variável de ambiente PORT)
    port = int(os.environ.get('PORT', 5000))
    
    if is_production:
        # Em produção, não precisamos chamar app.run() porque o gunicorn cuida disso
        logger.info(f"Rodando em produção na porta {port}")
    else:
        # Em ambiente local, usamos app.run()
        logger.info(f"Rodando localmente na porta {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
