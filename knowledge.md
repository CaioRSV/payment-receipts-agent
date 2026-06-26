# Base de Conhecimento

Este arquivo e o contexto editavel para o fallback do chatbot.

## Objetivo

- Ajudar usuarios com a geracao de recibos.
- Responder perguntas gerais quando a mensagem nao parecer um pedido de recibo.

## Fluxo de recibo

- O app deve detectar intencao com frases flexiveis em portugues ou ingles.
- Exemplos que devem disparar o fluxo de recibo:
  - generate receipt
  - gerar recibo
  - gere recibo
  - gere
  - mes
  - fevereiro
  - February
  - receipt
  - recibo

## Fallback de chat

- Se a mensagem nao parecer um pedido de recibo, responda normalmente como chatbot.
- Use este arquivo de conhecimento como contexto editavel para o comportamento de fallback.