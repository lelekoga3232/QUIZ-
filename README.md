# YouTube Live Quiz Game

Um jogo de quiz interativo para transmissões ao vivo no YouTube, onde os espectadores podem participar através do chat.

## Funcionalidades

- Configuração de link do YouTube para integração com o chat
- Captura de comandos do chat usando chat-downloader
- Sistema de votação em tempo real (!a, !b, !c, !d)
- Configuração de tempo para respostas
- Importação/exportação de perguntas e respostas em formato JSON
- Sistema de ranking dos 10 melhores participantes
- Interface responsiva inspirada em quiz trivia

## Instalação

1. Instale as dependências:
```
pip install -r requirements.txt
```

2. Execute a aplicação:
```
python app.py
```

3. Acesse a aplicação no navegador:
```
http://localhost:5000
```

## Como usar

1. Na página inicial, configure o link do YouTube e as configurações do quiz
2. Inicie o quiz e compartilhe o link com os espectadores
3. Os espectadores podem participar digitando !a, !b, !c ou !d no chat
4. O sistema contabiliza os votos e atualiza o ranking automaticamente
